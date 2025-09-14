"""
Диалог для предпросмотра содержимого главы
"""

import base64
from typing import Any, Dict

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import QDialog, QLabel, QPushButton, QTextBrowser, QToolBar, QVBoxLayout

from ..api import RanobeLibAPI
from ..img import ImageHandler
from ..parser import RanobeLibParser


class ContentLoader(QThread):
    """Рабочий поток для загрузки содержимого главы"""

    content_loaded = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(
        self,
        api: RanobeLibAPI,
        parser: RanobeLibParser,
        novel_info: Dict[str, Any],
        chapter_info: Dict[str, Any],
        branch_id: str,
    ):
        super().__init__()
        self.api = api
        self.parser = parser
        self.novel_info = novel_info
        self.chapter_info = chapter_info
        self.branch_id = branch_id

    def run(self):
        """Загружает содержимое главы"""
        try:
            novel_slug = self.novel_info.get("slug_url") or f"{self.novel_info.get('id')}--{self.novel_info.get('slug')}"
            if not novel_slug:
                raise ValueError("Slug новеллы не найден")

            volume = str(self.chapter_info.get("volume", "1"))
            number = str(self.chapter_info.get("number", "1"))
            branch_id = self.branch_id if self.branch_id != "0" else None

            chapter_data = self.api.get_chapter_content(novel_slug, volume, number, branch_id)
            if not chapter_data:
                raise ValueError("Данные главы не получены")

            html_content = ""
            if chapter_data.get("content"):
                content = chapter_data["content"]
                if isinstance(content, dict) and content.get("type") == "doc" and content.get("content"):
                    html_content = self.parser.json_to_html(
                        content["content"], chapter_data.get("attachments", [])
                    )
                else:
                    html_content = str(content)
            
            if not html_content:
                raise ValueError("Содержимое главы пустое")

            self.content_loaded.emit(html_content)

        except Exception as e:
            self.error_occurred.emit(str(e))


class PreviewDialog(QDialog):
    """Диалог для предпросмотра главы с настройками отображения"""

    def __init__(
        self,
        novel_info: Dict[str, Any],
        chapter_info: Dict[str, Any],
        branch_id: str,
        api: RanobeLibAPI,
        parser: RanobeLibParser,
        image_handler: ImageHandler,
        parent=None,
    ):
        super().__init__(parent)
        self.novel_info = novel_info
        self.chapter_info = chapter_info
        self.branch_id = branch_id
        self.api = api
        self.parser = parser
        self.image_handler = image_handler
        self.content_loader = None
        self.original_content = ""

        self.font_size = 12
        self.min_font_size = 8
        self.max_font_size = 24
        self.base_zoom_factor = 1.0
        self.current_zoom_factor = 1.0

        self._setup_ui()
        self._load_content()

    def _setup_ui(self):
        """Настройка интерфейса диалога"""
        self.setModal(False)
        self.setWindowFlags(Qt.WindowType.Window)
        self.setObjectName("previewDialog")

        chapter_title = f"Глава {self.chapter_info.get('number', '?')}"
        if self.chapter_info.get("name"):
            chapter_title += f" - {self.chapter_info.get('name')}"

        branch_info = None
        for branch in self.chapter_info.get("branches", []):
            if str(branch.get("branch_id", "0")) == str(self.branch_id):
                branch_info = branch
                break

        team_name = "Неизвестный переводчик"
        if branch_info and isinstance(branch_info, dict):
            teams = branch_info.get("teams", [])
            if teams:
                team_names = [team.get("name", "") for team in teams if team.get("name")]
                if team_names:
                    team_name = ", ".join(team_names)

        window_title = f"{chapter_title} [{team_name}]"
        self.setWindowTitle(window_title)
        self.resize(800, 600)

        main_layout = QVBoxLayout(self)

        toolbar = QToolBar()
        toolbar.setMovable(False)

        decrease_font_btn = QPushButton("А⁻")
        decrease_font_btn.setToolTip("Уменьшить шрифт")
        decrease_font_btn.clicked.connect(self._decrease_font)
        toolbar.addWidget(decrease_font_btn)

        self.font_size_label = QLabel(f"{self.font_size}px")
        self.font_size_label.setMinimumWidth(40)
        self.font_size_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        toolbar.addWidget(self.font_size_label)

        increase_font_btn = QPushButton("А⁺")
        increase_font_btn.setToolTip("Увеличить шрифт")
        increase_font_btn.clicked.connect(self._increase_font)
        toolbar.addWidget(increase_font_btn)

        toolbar.addSeparator()

        reset_font_btn = QPushButton("Сброс")
        reset_font_btn.setToolTip("Сбросить размер шрифта")
        reset_font_btn.clicked.connect(self._reset_font)
        toolbar.addWidget(reset_font_btn)

        main_layout.addWidget(toolbar)

        self.content_area = QTextBrowser()
        self.content_area.setReadOnly(True)
        self.content_area.setOpenExternalLinks(False)

        main_layout.addWidget(self.content_area)

        self._apply_font_size()

    def _setup_content_styles(self):
        """Настройка стилей для содержимого"""
        styles = f"""
        <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            font-size: {self.font_size}px;
            line-height: 1.3;
            color: #e0e0e0;
            background-color: transparent;
            margin: 20px;
        }}
        
        p {{
            text-indent: 15px;  /* Красная строка */
            margin: 0.5em 0;
            text-align: justify;
        }}
        
        h1, h2, h3, h4, h5, h6 {{
            text-indent: 0;
            margin: 1.5em 0 1em 0;
            font-weight: bold;
        }}
        
        h1 {{ font-size: {self.font_size + 6}px; }}
        h2 {{ font-size: {self.font_size + 4}px; }}
        h3 {{ font-size: {self.font_size + 2}px; }}
        
        .image-container {{
            display: block;
            margin: 2em 0;
            text-align: center;
            clear: both;
        }}
        
        .image-container img {{
            max-width: 100%;
            height: auto;
            display: inline-block;
            border-radius: 4px;
        }}
        
        /* Обеспечиваем отступы от текста */
        p + .image-container {{
            margin-top: 2em;
        }}
        
        .image-container + p {{
            margin-top: 2em;
        }}
        
        .image-container + * {{
            margin-top: 1.5em;
        }}
        
        blockquote {{
            border-left: 3px solid #2a82da;
            padding-left: 1em;
            margin: 1em 0;
            font-style: italic;
        }}
        
        em, i {{
            font-style: italic;
        }}
        
        strong, b {{
            font-weight: bold;
        }}
        
        hr {{
            border: none;
            border-top: 1px solid #555555;
            margin: 2em 0;
        }}
        </style>
        """
        return styles

    def _load_content(self):
        """Загружает содержимое главы в отдельном потоке"""
        self.content_area.setHtml(
            f"""
            <div style="text-align: center; color: #888888; padding: 50px;">
                <p>Загрузка содержимого главы...</p>
            </div>
            """
        )

        self.content_loader = ContentLoader(
            self.api, self.parser, self.novel_info, self.chapter_info, self.branch_id
        )
        self.content_loader.content_loaded.connect(self._on_content_loaded)
        self.content_loader.error_occurred.connect(self._on_content_error)
        self.content_loader.start()

    def _on_content_loaded(self, content: str):
        """Обработка успешной загрузки содержимого"""
        try:
            self.original_content = self._process_images_in_content(content)
            self._update_content_display()

        except Exception as e:
            self._on_content_error(f"Ошибка обработки содержимого: {e}")

    def _update_content_display(self):
        """Обновляет отображение содержимого с текущими стилями"""
        if self.original_content:
            styled_content = self._setup_content_styles() + self.original_content
            self.content_area.clear()
            self.content_area.setHtml(styled_content)
            self.content_area.update()
            self.content_area.repaint()

    def _on_content_error(self, error_message: str):
        """Обработка ошибки загрузки"""
        self.content_area.setHtml(
            f"""
            <div style="text-align: center; color: #e74c3c; padding: 50px;">
                <h3>Ошибка загрузки</h3>
                <p>{error_message}</p>
            </div>
            """
        )

    def _process_images_in_content(self, content: str) -> str:
        """Обрабатывает изображения в содержимом, заменяя их на base64"""
        import re

        def replace_image(match):
            img_url = match.group(1)
            try:
                if img_url.startswith('/'):
                    img_url = f"https://ranobelib.me{img_url}"
                elif not img_url.startswith(('http://', 'https://')):
                    img_url = f"https://ranobelib.me/{img_url}"
                
                response = self.api.session.get(img_url, timeout=10)
                response.raise_for_status()

                content_type = response.headers.get("content-type", "image/jpeg")
                if not content_type.startswith("image/"):
                    content_type = "image/jpeg"

                img_base64 = base64.b64encode(response.content).decode("ascii")
                data_url = f"data:{content_type};base64,{img_base64}"

                return f'<div class="image-container"><img src="{data_url}" alt="Изображение"></div>'

            except Exception as e:
                print(f"Ошибка загрузки изображения {img_url}: {e}")
                return f'<div class="image-container"><div style="color: #888; text-align: center; padding: 20px; border: 1px dashed #555; border-radius: 4px;">[Изображение не загружено]</div></div>'

        pattern = r'<img[^>]*src=["\']([^"\']+)["\'][^>]*>'
        processed_content = re.sub(pattern, replace_image, content)

        return processed_content

    def _increase_font(self):
        """Увеличивает размер шрифта"""
        if self.font_size < self.max_font_size:
            self.font_size += 1
            self.content_area.zoomIn(1)
            self.current_zoom_factor *= 1.1
            self.font_size_label.setText(f"{self.font_size}px")

    def _decrease_font(self):
        """Уменьшает размер шрифта"""
        if self.font_size > self.min_font_size:
            self.font_size -= 1
            self.content_area.zoomOut(1)
            self.current_zoom_factor /= 1.1
            self.font_size_label.setText(f"{self.font_size}px")

    def _reset_font(self):
        """Сбрасывает размер шрифта к значению по умолчанию"""
        if self.current_zoom_factor > 1.0:
            while self.current_zoom_factor > 1.05:
                self.content_area.zoomOut(1)
                self.current_zoom_factor /= 1.1
        elif self.current_zoom_factor < 1.0:
            while self.current_zoom_factor < 0.95:
                self.content_area.zoomIn(1)
                self.current_zoom_factor *= 1.1
        
        self.font_size = 12
        self.current_zoom_factor = 1.0
        self.font_size_label.setText(f"{self.font_size}px")

    def _apply_font_size(self):
        """Применяет новый размер шрифта"""
        self.font_size_label.setText(f"{self.font_size}px")
        self._update_content_display()

    def closeEvent(self, event):
        """Обработка закрытия диалога"""
        if self.content_loader and self.content_loader.isRunning():
            self.content_loader.terminate()
            self.content_loader.wait(3000)
        super().closeEvent(event) 