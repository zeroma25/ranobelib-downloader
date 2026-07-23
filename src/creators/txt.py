"""
Модуль для создания TXT файлов
"""

import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from ..settings import settings


class TxtCreator:
    def __init__(self, processor):
        self.processor = processor
        self.parser = processor.parser

    """Класс для создания TXT-файлов"""

    @property
    def format_name(self) -> str:
        """Возвращает имя формата книги."""
        return "TXT"

    def create(
        self,
        novel_info: Dict[str, Any],
        chapters_data: List[Dict[str, Any]],
        selected_branch_id: Optional[str] = None,
    ) -> str:
        """Создание TXT файла с главами новеллы."""
        _, image_folder = self.processor.file_manager.prepare_dirs(novel_info.get("id"))

        prepared_chapters = self.processor.chapter_loader.prepare_chapters(
            novel_info, chapters_data, selected_branch_id, image_folder
        )

        print(f"📦 Создание {self.format_name}...")

        full_text = self._build_text_content(novel_info, prepared_chapters)

        title, _, _, _ = self.processor.metadata_extractor.extract_title_author_summary(novel_info)
        txt_filename = self.processor.file_manager.get_safe_filename(title, "txt")

        with open(txt_filename, "w", encoding="utf-8") as f:
            f.write(full_text)

        return txt_filename

    def _build_text_content(self, novel_info: Dict[str, Any], prepared_chapters: List[Dict[str, Any]]) -> str:
        """Сборка текстового содержимого книги."""
        title, author, _, _ = self.processor.metadata_extractor.extract_title_author_summary(novel_info)

        lines = [title]
        if author:
            lines.append(f"Автор: {author}")
        lines.append("\n" + "=" * 60 + "\n")

        volume_chapters: Dict[str, List[Dict[str, Any]]] = {}
        for chapter in prepared_chapters:
            volume_chapters.setdefault(str(chapter["volume"]), []).append(chapter)

        sorted_volumes = sorted(volume_chapters.keys(), key=lambda x: int(x) if x.isdigit() else 0)

        total_volumes = self.processor.metadata_extractor.get_total_volume_count(novel_info)

        for vol_num in sorted_volumes:
            if settings.get("group_by_volumes") and total_volumes > 1:
                lines.append(f"Том {vol_num}\n")
                lines.append("-" * 60 + "\n")

            for prep in volume_chapters[vol_num]:
                lines.append(self._format_chapter_to_text(prep, vol_num, total_volumes))

        return "\n".join(lines)

    def _format_chapter_to_text(
        self, prepared_chapter: Dict[str, Any], volume: str, total_volumes: int
    ) -> str:
        """Форматирование одной главы в текстовый блок."""
        ch_name = self.parser.decode_html_entities(prepared_chapter.get("name", "").strip())
        chapter_title = self.processor.chapter_formatter.format_chapter_title(
            ch_name, prepared_chapter["number"], volume, total_volumes
        )

        html_content = prepared_chapter["html"]
        plain_text = self._html_to_text(html_content)

        return f"{chapter_title}\n\n{plain_text}\n\n"

    def _html_to_text(self, html: str) -> str:
        """Преобразование HTML-содержимого в простой текст."""
        if not html:
            return ""
        soup = BeautifulSoup(html, "lxml")

        for img in soup.find_all("img"):
            img.decompose()

        for figure in soup.find_all("figure"):
            figure.decompose()

        text = soup.get_text(separator="\n")

        lines = [line.strip() for line in text.splitlines()]
        non_empty_lines = [line for line in lines if line]
        clean_text = "\n".join(non_empty_lines)

        return re.sub(r"\n{3,}", "\n\n", clean_text) 