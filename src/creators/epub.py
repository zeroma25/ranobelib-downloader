"""
Модуль для создания EPUB файлов
"""

import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from ebooklib import epub

from ..processing import ContentProcessor


class EpubCreator(ContentProcessor):
    """Класс для создания EPUB-файлов"""

    def __init__(self, api, parser, image_handler):
        super().__init__(api, parser, image_handler)

    @property
    def format_name(self) -> str:
        """Возвращает имя формата книги."""
        return "EPUB"

    def create(
        self,
        novel_info: Dict[str, Any],
        chapters_data: List[Dict[str, Any]],
        selected_branch_id: Optional[str] = None,
    ) -> str:
        """Создание EPUB файла с главами новеллы."""
        book = epub.EpubBook()
        _, image_folder = self.prepare_dirs(novel_info.get("id"))

        self._set_metadata(book, novel_info)

        spine, toc = [], []
        cover_item = self._create_cover(book, novel_info, image_folder)
        if cover_item:
            spine.append(cover_item)

        chapter_spine, chapter_toc, referenced_images = self._add_chapters_and_toc(
            book, novel_info, chapters_data, selected_branch_id, image_folder
        )
        spine.extend(chapter_spine)
        toc.extend(chapter_toc)

        self._add_images(book, image_folder, referenced_images)

        book.toc = toc
        book.spine = spine
        book.add_item(epub.EpubNcx())

        title = self.parser.decode_html_entities(book.title)
        epub_filename = self.get_safe_filename(title, "epub")

        epub.write_epub(epub_filename, book, {})

        return epub_filename

    def _set_metadata(self, book: epub.EpubBook, novel_info: Dict[str, Any]):
        """Установка метаданных для EPUB книги."""
        title, author, summary, genres = self.extract_title_author_summary(novel_info)
        book.set_identifier(f"ranobelib-{novel_info.get('id')}")
        book.set_title(title)
        if author:
            book.add_author(author)
        if summary:
            book.add_metadata("DC", "description", summary)
        if genres:
            book.add_metadata("DC", "subject", ", ".join(genres))
        year_str = self.extract_year(novel_info)
        if year_str:
            book.add_metadata("DC", "date", year_str)

    def _create_cover(
        self, book: epub.EpubBook, novel_info: Dict[str, Any], image_folder: str
    ) -> Optional[epub.EpubItem]:
        """Скачивание и создание страницы с обложкой."""
        cover_path = self.download_cover(novel_info, image_folder)
        if not cover_path:
            return None

        _, ext = os.path.splitext(cover_path)
        with open(os.path.join(image_folder, cover_path), "rb") as f:
            book.set_cover(f"images/cover{ext}", f.read(), create_page=False)

        cover_item = epub.EpubItem(
            uid="cover",
            file_name="cover.xhtml",
            media_type="application/xhtml+xml",
            content=f"""\
<html xmlns="http://www.w3.org/1999/xhtml" lang="ru">
  <head>
    <title>Cover</title>
  </head>
  <body style="margin: 0; padding: 0;">
    <img src="images/cover{ext}" style="width: 100%; height: auto;" alt="Cover" />
  </body>
</html>""".encode(
                "utf-8"
            ),
        )
        book.add_item(cover_item)
        return cover_item

    def _add_chapters_and_toc(
        self,
        book: epub.EpubBook,
        novel_info: Dict[str, Any],
        chapters_data: List[Dict[str, Any]],
        selected_branch_id: Optional[str],
        image_folder: str,
    ) -> Tuple[List[Any], List[Any], Set[str]]:
        """Добавление глав в книгу и формирование оглавления (TOC)."""
        toc: List[Any] = []
        spine: List[Any] = []
        referenced_images: Set[str] = set()
        volume_chapters: Dict[str, List[Any]] = {}

        prepared_chapters = self.prepare_chapters(
            novel_info, chapters_data, selected_branch_id, image_folder
        )

        total_volumes = self.get_total_volume_count(novel_info)

        print("📦 Создание EPUB...")
        for i, prep in enumerate(prepared_chapters):
            ch_name = self.parser.decode_html_entities(prep.get("name", "").strip())
            vol_num = str(prep["volume"])

            if total_volumes > 1 and not self.group_by_volumes and vol_num != "0":
                chapter_title = f'Том {vol_num} Глава {prep["number"]}'
            else:
                chapter_title = f'Глава {prep["number"]}'

            if ch_name:
                chapter_title += f" - {ch_name}"

            chapter = epub.EpubHtml(
                title=chapter_title, file_name=f"chapter_{i+1}.xhtml", lang="ru"
            )
            chapter.content = f"<h1>{chapter_title}</h1>{prep['html']}"

            book.add_item(chapter)
            volume_chapters.setdefault(vol_num, []).append(chapter)
            spine.append(chapter)

            for img_filename in re.findall(r"src=['\"]images/([^'\"]+)['\"]", prep["html"]):
                referenced_images.add(img_filename)

        if self.group_by_volumes and total_volumes > 1 and volume_chapters:
            for vol_num in sorted(volume_chapters.keys(), key=lambda x: int(x) if x.isdigit() else 0):
                toc.append((epub.Section(f"Том {vol_num}"), tuple(volume_chapters[vol_num])))
        elif volume_chapters:
            all_chapters = []
            for vol_num in sorted(volume_chapters.keys(), key=lambda x: int(x) if x.isdigit() else 0):
                all_chapters.extend(volume_chapters[vol_num])
            toc.extend(all_chapters)

        return spine, toc, referenced_images

    def _add_images(self, book: epub.EpubBook, image_folder: str, referenced_images: Set[str]):
        """Добавление изображений в книгу."""
        if not os.path.exists(image_folder):
            return

        for filename in referenced_images:
            if filename.startswith("cover."):
                continue

            if filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif")):
                image_path = os.path.join(image_folder, filename)
                if not os.path.exists(image_path):
                    print(f"⚠️ Изображение {filename} не найдено, пропуск.")
                    continue
                with open(image_path, "rb") as img_file:
                    ext = os.path.splitext(filename)[1][1:].replace("jpg", "jpeg")
                    image_item = epub.EpubItem(
                        uid=f"image_{filename}",
                        file_name=f"images/{filename}",
                        media_type=f"image/{ext}",
                        content=img_file.read(),
                    )
                    book.add_item(image_item) 