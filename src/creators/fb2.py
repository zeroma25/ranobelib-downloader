"""
Модуль для создания FB2 файлов
"""

import base64
import datetime
import mimetypes
import os
import xml.sax.saxutils as saxutils
from typing import Any, Dict, List, Optional, Set, Tuple

from bs4 import BeautifulSoup, Tag

from ..settings import settings


class Fb2Creator:
    def __init__(self, processor):
        self.processor = processor
        self.parser = processor.parser

    """Класс для создания FB2-файлов"""

    _FB2_NAMESPACE = "http://www.gribuser.ru/xml/fictionbook/2.0"
    _XLINK_NAMESPACE = "http://www.w3.org/1999/xlink"

    @property
    def format_name(self) -> str:
        """Возвращает имя формата книги."""
        return "FB2"

    def create(
        self,
        novel_info: Dict[str, Any],
        chapters_data: List[Dict[str, Any]],
        selected_branch_id: Optional[str] = None,
    ) -> str:
        """Создание FB2-файла с главами новеллы."""
        _, image_folder = self.processor.file_manager.prepare_dirs(novel_info.get("id"))

        prepared_chapters = self.processor.chapter_loader.prepare_chapters(
            novel_info, chapters_data, selected_branch_id, image_folder
        )
        cover_filename = self.processor.chapter_loader.download_cover(novel_info, image_folder)

        description_xml = self._build_description_xml(novel_info, cover_filename)
        body_xml, referenced_images = self._build_body_xml(prepared_chapters, novel_info)
        binaries_xml = self._build_binaries_xml(image_folder, referenced_images, cover_filename)

        fb2_full = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            f'<FictionBook xmlns="{self._FB2_NAMESPACE}" xmlns:l="{self._XLINK_NAMESPACE}">\n'
            f"{description_xml}\n{body_xml}\n{binaries_xml}\n"
            "</FictionBook>"
        )

        title = self.processor.metadata_extractor.extract_title_author_summary(novel_info)[0]
        fb2_filename = self.processor.file_manager.get_safe_filename(title, "fb2")

        with open(fb2_filename, "w", encoding="utf-8") as f:
            f.write(fb2_full)

        return fb2_filename

    def _html_to_fb2(self, html: str) -> Tuple[str, Set[str]]:
        """Базовое преобразование HTML-контента в FB2-разметку."""
        soup = BeautifulSoup(html, "lxml")
        referenced_images: Set[str] = set()

        for img in soup.find_all("img"):
            if isinstance(img, Tag) and img.has_attr("src"):
                src = os.path.basename(str(img["src"]))
                referenced_images.add(src)
                new_tag = soup.new_tag("image", attrs={"l:href": f"#{src}"})
                img.replace_with(new_tag)

        for i_tag in soup.find_all(["i", "em"]):
            if isinstance(i_tag, Tag):
                i_tag.name = "emphasis"
        for b_tag in soup.find_all(["b", "strong"]):
            if isinstance(b_tag, Tag):
                b_tag.name = "strong"

        output_parts: List[str] = []
        for element in soup.contents:
            text = str(element).strip()
            if not text:
                continue

            if isinstance(element, Tag) and element.name == "image":
                output_parts.append(str(element))
            elif text.lower().startswith("<p"):
                output_parts.append(text)
            else:
                output_parts.append(f"<p>{text}</p>")

        return "\n".join(output_parts), referenced_images

    def _encode_image(self, path: str) -> Tuple[str, str]:
        """Возвращает MIME-тип и base64-содержимое файла."""
        mime = mimetypes.guess_type(path)[0] or "image/jpeg"
        with open(path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("ascii")
        return mime, encoded

    def _build_description_xml(self, novel_info: Dict[str, Any], cover_filename: Optional[str]) -> str:
        """Создание XML-блока <description> для FB2."""
        title, author, annotation, genres = self.processor.metadata_extractor.extract_title_author_summary(novel_info)
        year = self.processor.metadata_extractor.extract_year(novel_info) or str(datetime.datetime.now().year)

        genres_xml = "\n    ".join(f"<genre>{saxutils.escape(g)}</genre>" for g in genres)
        author_xml = f"<author>\n      <nickname>{saxutils.escape(author)}</nickname>\n    </author>" if author else ""
        cover_xml = (
            f'<coverpage>\n      <image l:href="#{cover_filename}"/>\n    </coverpage>'
            if cover_filename
            else ""
        )

        if annotation:
            annotation_lines = [
                f"      <p>{saxutils.escape(line.strip())}</p>" for line in annotation.split("\n") if line.strip()
            ]
            annotation_body = "\n".join(annotation_lines)
            annotation_xml = f"<annotation>\n{annotation_body}\n    </annotation>"
        else:
            annotation_xml = ""

        return f"""\
<description>
  <title-info>
    {genres_xml}
    {author_xml}
    <book-title>{saxutils.escape(title)}</book-title>
    {annotation_xml}
    {cover_xml}
    <date value="{year}">{year}</date>
    <lang>ru</lang>
  </title-info>
  <document-info>
    <id>ranobelib-{novel_info.get('id')}</id>
    <version>1.0</version>
    <date value="{datetime.date.today().isoformat()}"/>
  </document-info>
</description>"""

    def _build_body_xml(
        self,
        prepared_chapters: List[Dict[str, Any]],
        novel_info: Dict[str, Any],
    ) -> Tuple[str, Set[str]]:
        """Создание XML-блока <body> и возвращение множества всех использованных изображений."""
        volume_chapters: Dict[str, List[str]] = {}
        all_referenced_images: Set[str] = set()

        total_volumes = self.processor.metadata_extractor.get_total_volume_count(novel_info)

        print("📦 Создание FB2...")
        for i, prep in enumerate(prepared_chapters, 1):
            ch_name = self.parser.decode_html_entities(prep.get("name", "").strip())
            vol_num = str(prep["volume"])

            if total_volumes > 1 and not settings.get("group_by_volumes") and vol_num != "0":
                chapter_title = f'Том {vol_num} Глава {prep["number"]}'
            else:
                chapter_title = f'Глава {prep["number"]}'

            if ch_name:
                chapter_title += f" - {saxutils.escape(ch_name)}"

            fb2_fragment, images = self._html_to_fb2(prep["html"])
            all_referenced_images.update(images)
            section_xml = f"""\
<section id="ch{i}"><title><p>{saxutils.escape(chapter_title)}</p></title>
{fb2_fragment}
</section>"""
            volume_chapters.setdefault(vol_num, []).append(section_xml)

        body_parts = []
        if settings.get("group_by_volumes") and total_volumes > 1 and volume_chapters:
            for vol_num in sorted(volume_chapters.keys(), key=lambda x: int(x) if x.isdigit() else 0):
                chapters_xml = "\n".join(volume_chapters[vol_num])
                body_parts.append(
                    f'<section id="vol{vol_num}"><title><p>Том {vol_num}</p></title>{chapters_xml}</section>'
                )
        elif volume_chapters:
            for vol_num in sorted(volume_chapters.keys(), key=lambda x: int(x) if x.isdigit() else 0):
                body_parts.extend(volume_chapters[vol_num])

        return f"<body>\n{''.join(body_parts)}\n</body>", all_referenced_images

    def _build_binaries_xml(
        self, image_folder: str, referenced_images: Set[str], cover_filename: Optional[str]
    ) -> str:
        """Создание XML-блока с бинарными данными изображений."""
        if not os.path.exists(image_folder):
            return ""

        binaries_parts = []
        if cover_filename:
            referenced_images.add(cover_filename)

        for filename in referenced_images:
            image_path = os.path.join(image_folder, filename)
            if not os.path.exists(image_path):
                print(f"⚠️ Изображение {filename} не найдено, пропуск.")
                continue
            try:
                mime, data_b64 = self._encode_image(image_path)
                binaries_parts.append(f'<binary id={saxutils.quoteattr(filename)} content-type="{mime}">{data_b64}</binary>')
            except Exception as e:
                print(f"⚠️ Не удалось добавить изображение {filename} в FB2: {e}")

        return "\n".join(binaries_parts) 