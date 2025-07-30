"""
Модуль для создания HTML файлов
"""

import base64
import mimetypes
import os
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup, Tag

from ..processing import ContentProcessor


class HtmlCreator(ContentProcessor):
    """Класс для создания HTML-файлов"""

    @property
    def format_name(self) -> str:
        """Возвращает имя формата книги."""
        return "HTML"

    def create(
        self,
        novel_info: Dict[str, Any],
        chapters_data: List[Dict[str, Any]],
        selected_branch_id: Optional[str] = None,
    ) -> str:
        """Создание HTML файла с главами новеллы."""
        _, image_folder = self.prepare_dirs(novel_info.get("id"))

        prepared_chapters = self.prepare_chapters(
            novel_info, chapters_data, selected_branch_id, image_folder
        )
        cover_filename = self.download_cover(novel_info, image_folder)

        print(f"📦 Создание {self.format_name}...")

        full_html = self._build_html_content(
            novel_info, prepared_chapters, cover_filename, image_folder
        )

        title, _, _, _ = self.extract_title_author_summary(novel_info)
        html_filename = self.get_safe_filename(title, "html")

        with open(html_filename, "w", encoding="utf-8") as f:
            f.write(full_html)

        return html_filename

    def _build_html_content(
        self,
        novel_info: Dict[str, Any],
        prepared_chapters: List[Dict[str, Any]],
        cover_filename: Optional[str],
        image_folder: str,
    ) -> str:
        """Сборка полного HTML-содержимого книги."""
        title, _, _, _ = self.extract_title_author_summary(novel_info)

        toc_html = self._create_toc_html(novel_info, prepared_chapters)
        js_script = self._get_javascript()

        head = self._create_html_head(title, js_script)
        body_content = self._create_html_body(novel_info, prepared_chapters, cover_filename, toc_html)

        embedded_body = self._embed_images_as_base64(body_content, image_folder)

        return f'<!DOCTYPE html>\n<html lang="ru">\n{head}\n{embedded_body}\n</html>'

    def _create_html_head(self, title: str, js_script: str) -> str:
        """Создание секции <head> для HTML-документа."""
        decoded_title = self.parser.decode_html_entities(title)

        style = """
<style>
    :root {
        --bg-color: #f9f9f9; --text-color: #333; --header-color: #1a1a1a;
        --border-color: #ddd; --summary-bg: #fff; --summary-border: #ccc;
        --button-bg: #fff; --button-shadow: rgba(0,0,0,0.15);
    }
    .dark-mode {
        --bg-color: #1e1e1e; --text-color: #ccc; --header-color: #f1f1f1;
        --border-color: #444; --summary-bg: #2a2a2a; --summary-border: #555;
        --button-bg: #333; --button-shadow: rgba(255,255,255,0.1);
    }
    body { 
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; 
        line-height: 1.6; padding: 1em; max-width: 800px; margin: auto; 
        background-color: var(--bg-color); color: var(--text-color); transition: background-color 0.3s, color 0.3s;
    }
    body.toc-is-open {
        overflow: hidden;
    }
    h1, h2, h3 { text-align: center; color: var(--header-color); }
    h1 { font-size: 2.2em; }
    h2 { font-size: 1.8em; border-bottom: 2px solid var(--border-color); padding-bottom: 10px; margin-top: 1.5em;}
    h3 { font-size: 1.5em; }
    .cover img { max-width: 60%; height: auto; display: block; margin: 20px auto; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
    .summary { background-color: var(--summary-bg); border-left: 4px solid var(--summary-border); padding: 1em; margin: 2em 0; white-space: pre-wrap; }
    .chapter { margin-top: 2em; padding-top: 1em; border-top: 1px solid var(--border-color); }
    .chapter-title { font-size: 1.5em; font-weight: bold; }
    p { margin: 1em 0; }
    img { max-width: 100%; height: auto; display: block; margin: 1em auto; border-radius: 4px; }
    
    #toc-sidebar {
        position: fixed; top: 0; left: 0; height: 100%; width: 300px;
        background-color: var(--bg-color); border-right: 1px solid var(--border-color);
        transform: translateX(-100%); transition: transform 0.3s ease-in-out, background-color 0.3s, border-color 0.3s;
        z-index: 1001; display: flex; flex-direction: column; padding: 0;
    }
    #toc-sidebar.open { transform: translateX(0); }
    #toc-header {
        position: sticky; top: 0; flex-shrink: 0;
        display: flex; align-items: center; cursor: pointer;
        padding: 1em; background-color: var(--bg-color);
        border-bottom: 1px solid var(--border-color);
        transition: background-color 0.3s, border-color 0.3s;
    }
    #toc-header h2 { text-align: left; margin: 0 0 0 1em; font-size: 1.2em; border-bottom: none; padding-bottom: 0; }
    #toc-header .back-arrow-svg { width: 1.2em; height: 1.2em; flex-shrink: 0; }
    #toc-sidebar .toc-main-list {
        list-style-type: none; padding: 1em; margin: 0;
        overflow-y: auto; flex-grow: 1; padding-bottom: 4vh;
    }
    #toc-sidebar li a { text-decoration: none; color: var(--text-color); display: block; padding: 8px 10px; border-radius: 4px; }
    #toc-sidebar li a:hover { background-color: var(--summary-bg); }

    .toc-volume-header {
        cursor: pointer; padding: 8px 10px; border-radius: 4px;
        position: relative; user-select: none;
        padding-left: 25px;
    }
    .toc-volume-header strong { font-weight: bold; }
    .toc-volume-header:hover { background-color: var(--summary-bg); }
    .toc-volume-header::before {
        content: '▶'; position: absolute; left: 10px; top: 50%;
        transform: translateY(-50%) rotate(0deg);
        transition: transform 0.2s ease-in-out;
    }
    .toc-volume-header.open::before { transform: translateY(-50%) rotate(90deg); }
    .toc-volume-chapters {
        list-style-type: none; padding-left: 15px;
        display: none;
    }
    .toc-volume-chapters.open { display: block; }
    
    #toc-overlay {
        display: none; position: fixed; top: 0; left: 0;
        width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000;
    }
    #toc-overlay.open { display: block; }

    #controls-wrapper {
        position: fixed; bottom: 0; right: 0;
        width: 100px; height: 120px; z-index: 1002;
    }
    #controls {
        position: absolute; bottom: 20px; right: 20px;
        display: flex; flex-direction: column; gap: 10px;
        opacity: 0; pointer-events: none;
        transition: opacity 0.3s ease-in-out;
    }
    /* --- Desktop-specific rules --- */
    /* Show on hover, but NOT when scrolling */
    body:not(.is-scrolling) #controls-wrapper:hover #controls {
        opacity: 1;
        pointer-events: auto;
    }
    /* --- Touch-specific rule --- */
    /* Show when toggled via JS */
    #controls.visible {
        opacity: 1;
        pointer-events: auto;
    }
    #controls button {
        width: 50px; height: 50px; border-radius: 50%; border: none;
        background-color: var(--button-bg); color: var(--text-color);
        font-size: 24px; cursor: pointer; display: flex;
        align-items: center; justify-content: center;
        box-shadow: 0 2px 5px var(--button-shadow);
    }
</style>
"""

        return (
            "<head>\n"
            f'<meta charset="UTF-8">\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            f"<title>{decoded_title}</title>\n"
            f"{style}\n"
            "</head>"
            "<body>"
            f"{js_script}"
            "</body>"
        )

    def _create_html_body(
        self,
        novel_info: Dict[str, Any],
        prepared_chapters: List[Dict[str, Any]],
        cover_filename: Optional[str],
        toc_html: str,
    ) -> str:
        """Создание содержимого для <body>."""
        title, author, summary, _ = self.extract_title_author_summary(novel_info)

        controls = """
<div id="controls-wrapper">
    <div id="controls">
        <button id="toggle-theme" title="Переключить тему">🌓</button>
        <button id="toggle-toc" title="Оглавление">📖</button>
    </div>
</div>"""
        sidebar = f'<nav id="toc-sidebar">{toc_html}</nav><div id="toc-overlay"></div>'

        body_parts = [f"<body>{controls}{sidebar}"]

        body_parts.append("<main>")
        body_parts.append(f"<h1>{self.parser.decode_html_entities(title)}</h1>")
        if author:
            body_parts.append(f"<h2>{self.parser.decode_html_entities(author)}</h2>")
        if cover_filename and self.download_cover_enabled:
            body_parts.append(f'<div class="cover"><img src="images/{cover_filename}" alt="Обложка"></div>')

        if summary:
            body_parts.append(f'<div class="summary">{summary}</div>')

        volume_chapters: Dict[str, List[Dict[str, Any]]] = {}
        for chapter in prepared_chapters:
            volume_chapters.setdefault(str(chapter["volume"]), []).append(chapter)

        sorted_volumes = sorted(volume_chapters.keys(), key=lambda x: int(x) if x.isdigit() else 0)

        total_volumes = self.get_total_volume_count(novel_info)

        for vol_num in sorted_volumes:
            if self.group_by_volumes and total_volumes > 1:
                body_parts.append(f'<h2 id="vol-{vol_num}">Том {vol_num}</h2>')

            for prep in volume_chapters[vol_num]:
                ch_name = self.parser.decode_html_entities(prep.get("name", "").strip())

                if total_volumes > 1 and not self.group_by_volumes and vol_num != "0":
                    chapter_title = f'Том {vol_num} Глава {prep["number"]}'
                else:
                    chapter_title = f'Глава {prep["number"]}'

                if ch_name:
                    chapter_title += f" - {ch_name}"

                chapter_id = f'ch-{prep["volume"]}-{prep["number"]}'
                body_parts.append(f'<div class="chapter" id="{chapter_id}">')
                body_parts.append(f'<h3 class="chapter-title">{chapter_title}</h3>')
                body_parts.append(prep["html"])
                body_parts.append("</div>")

        body_parts.append("</main>")
        body_parts.append("</body>")
        return "\n".join(body_parts)

    def _create_toc_html(
        self, novel_info: Dict[str, Any], prepared_chapters: List[Dict[str, Any]]
    ) -> str:
        """Создание HTML для оглавления."""
        header = """
<div id="toc-header">
    <svg class="back-arrow-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><path fill="currentColor" d="M9.4 233.4c-12.5 12.5-12.5 32.8 0 45.3l160 160c12.5 12.5 32.8 12.5 45.3 0s12.5-32.8 0-45.3L109.2 288 416 288c17.7 0 32-14.3 32-32s-14.3-32-32-32l-306.7 0L214.6 118.6c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0l-160 160z"></path></svg>
    <h2>Оглавление</h2>
</div>"""

        volume_chapters: Dict[str, List[Dict[str, Any]]] = {}
        for chapter in prepared_chapters:
            volume_chapters.setdefault(str(chapter["volume"]), []).append(chapter)

        sorted_volumes = sorted(volume_chapters.keys(), key=lambda x: int(x) if x.isdigit() else 0)

        total_volumes = self.get_total_volume_count(novel_info)

        has_volumes = self.group_by_volumes and total_volumes > 1

        toc_list_parts = ['<ul class="toc-main-list">']
        for vol_num in sorted_volumes:
            if has_volumes:
                toc_list_parts.append(
                    f'<li><div class="toc-volume-header open"><strong>Том {vol_num}</strong></div><ul class="toc-volume-chapters open">'
                )

            for prep in volume_chapters[vol_num]:
                ch_name = self.parser.decode_html_entities(prep.get("name", "").strip())

                if total_volumes > 1 and not self.group_by_volumes and vol_num != "0":
                    chapter_title = f'Том {vol_num} Глава {prep["number"]}'
                else:
                    chapter_title = f'Глава {prep["number"]}'

                if ch_name:
                    chapter_title += f" - {ch_name}"

                chapter_id = f'ch-{prep["volume"]}-{prep["number"]}'
                toc_list_parts.append(f'<li><a href="#{chapter_id}">{chapter_title}</a></li>')

            if has_volumes:
                toc_list_parts.append("</ul></li>")
        toc_list_parts.append("</ul>")

        return header + "\n" + "\n".join(toc_list_parts)

    def _get_javascript(self) -> str:
        """Возвращает строку с JS-кодом для интерактивности."""
        return """
<script>
document.addEventListener('DOMContentLoaded', () => {
    const body = document.body;
    const themeToggleButton = document.getElementById('toggle-theme');
    const tocToggleButton = document.getElementById('toggle-toc');
    const tocSidebar = document.getElementById('toc-sidebar');
    const tocOverlay = document.getElementById('toc-overlay');
    const tocHeader = document.getElementById('toc-header');
    const controls = document.getElementById('controls');
    const controlsWrapper = document.getElementById('controls-wrapper');
    const isTouch = ('ontouchstart' in window) || (navigator.maxTouchPoints > 0);

    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark') {
        body.classList.add('dark-mode');
    }
    themeToggleButton.addEventListener('click', () => {
        body.classList.toggle('dark-mode');
        localStorage.setItem('theme', body.classList.contains('dark-mode') ? 'dark' : 'light');
    });

    const toggleTOC = () => {
        body.classList.toggle('toc-is-open');
        tocSidebar.classList.toggle('open');
        tocOverlay.classList.toggle('open');
    };
    tocToggleButton.addEventListener('click', toggleTOC);
    tocOverlay.addEventListener('click', toggleTOC);
    tocHeader.addEventListener('click', toggleTOC);
    tocSidebar.querySelectorAll('a').forEach(link => {
        link.addEventListener('click', (e) => {
            setTimeout(toggleTOC, 100);
        });
    });
    
    tocSidebar.querySelectorAll('.toc-volume-header').forEach(header => {
        header.addEventListener('click', () => {
            header.classList.toggle('open');
            const chapterList = header.nextElementSibling;
            if (chapterList && chapterList.classList.contains('toc-volume-chapters')) {
                chapterList.classList.toggle('open');
            }
        });
    });

    if (isTouch) {
        const mainContent = document.querySelector('main');
        if (mainContent) {
            mainContent.addEventListener('click', () => {
                controls.classList.toggle('visible');
            });
        }
        window.addEventListener('scroll', () => {
            if (controls.classList.contains('visible')) {
                controls.classList.remove('visible');
            }
        }, { passive: true });
    } else {
        let scrollTimeout;
        window.addEventListener('scroll', () => {
            body.classList.add('is-scrolling');
            clearTimeout(scrollTimeout);
            scrollTimeout = setTimeout(() => {
                body.classList.remove('is-scrolling');
            }, 150);
        }, { passive: true });
    }
});
</script>"""

    def _embed_images_as_base64(self, html_content: str, image_folder: str) -> str:
        """Встраивание всех изображений в HTML как base64 data URI."""
        soup = BeautifulSoup(html_content, "html.parser")
        for img in soup.find_all("img"):
            if not isinstance(img, Tag) or not img.has_attr("src"):
                continue

            src_attr = img["src"]
            src = str(src_attr[0] if isinstance(src_attr, list) else src_attr)

            if src.startswith("data:"):
                continue

            filename = os.path.basename(src)
            image_path = os.path.join(image_folder, filename)

            if os.path.exists(image_path):
                mime_type = mimetypes.guess_type(image_path)[0] or "image/jpeg"
                with open(image_path, "rb") as f:
                    encoded_string = base64.b64encode(f.read()).decode("utf-8")
                img["src"] = f"data:{mime_type};base64,{encoded_string}"
            else:
                print(f"⚠️ Изображение не найдено для встраивания: {image_path}")

        return str(soup) 