"""
Модуль для создания TXT файлов
"""

import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from ..processing import ContentProcessor


class TxtCreator(ContentProcessor):
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
        _, image_folder = self.prepare_dirs(novel_info.get("id"))

        prepared_chapters = self.prepare_chapters(
            novel_info, chapters_data, selected_branch_id, image_folder
        )

        print(f"📦 Создание {self.format_name}...")

        full_text = self._build_text_content(novel_info, prepared_chapters)

        title, _, _, _ = self.extract_title_author_summary(novel_info)
        txt_filename = self.get_safe_filename(title, "txt")

        with open(txt_filename, "w", encoding="utf-8") as f:
            f.write(full_text)

        return txt_filename

    def _build_text_content(self, novel_info: Dict[str, Any], prepared_chapters: List[Dict[str, Any]]) -> str:
        """Сборка текстового содержимого книги."""
        title, author, _, _ = self.extract_title_author_summary(novel_info)

        lines = [title]
        if author:
            lines.append(f"Автор: {author}")
        lines.append("\n" + "=" * 60 + "\n")

        volume_chapters: Dict[str, List[Dict[str, Any]]] = {}
        for chapter in prepared_chapters:
            volume_chapters.setdefault(str(chapter["volume"]), []).append(chapter)

        sorted_volumes = sorted(volume_chapters.keys(), key=lambda x: int(x) if x.isdigit() else 0)

        total_volumes = self.get_total_volume_count(novel_info)

        for vol_num in sorted_volumes:
            if self.group_by_volumes and total_volumes > 1:
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

        if total_volumes > 1 and not self.group_by_volumes and volume != "0":
            chapter_title = f'Том {volume} Глава {prepared_chapter["number"]}'
        else:
            chapter_title = f'Глава {prepared_chapter["number"]}'

        if ch_name:
            chapter_title += f" - {ch_name}"

        html_content = prepared_chapter["html"]
        plain_text = self._html_to_text(html_content)

        return f"{chapter_title}\n\n{plain_text}\n\n"

    def _html_to_text(self, html: str) -> str:
        """Преобразование HTML-содержимого в простой текст."""
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")

        for img in soup.find_all("img"):
            img.decompose()

        text = soup.get_text(separator="\n")

        lines = [line.strip() for line in text.splitlines()]
        non_empty_lines = [line for line in lines if line]
        clean_text = "\n".join(non_empty_lines)

        return re.sub(r"\n{3,}", "\n\n", clean_text) 