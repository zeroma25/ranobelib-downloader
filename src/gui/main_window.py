"""
Главное окно приложения RanobeLIB
"""

import base64
import re
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QSettings, QSize, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..api import RanobeLibAPI
from ..auth import RanobeLibAuth
from ..img import ImageHandler
from ..parser import RanobeLibParser
from .auth_manager import AuthManager
from .chapters_widget import ChaptersWidget
from .download_dialog import DownloadDialog
from .utils import load_stylesheet, show_error_message


class NovelInfoWorker(QThread):
    """Рабочий поток для загрузки информации о новелле"""

    finished = pyqtSignal(dict, list)
    error = pyqtSignal(str)

    def __init__(self, api, parser, slug, is_authenticated: bool):
        super().__init__()
        self.api = api
        self.parser = parser
        self.slug = slug
        self.is_authenticated = is_authenticated

    def run(self):
        try:
            novel_info = self.api.get_novel_info(self.slug)
            if not novel_info.get("id"):
                error_message = "Ошибка загрузки. Возможно, ссылка некорректна."
                if not self.is_authenticated:
                    error_message = (
                        "Ошибка загрузки. Возможно, ссылка некорректна или требуется авторизация."
                    )
                raise ValueError(error_message)

            chapters_data = self.api.get_novel_chapters(self.slug)
            if not chapters_data:
                raise ValueError("Не удалось загрузить список глав")

            self.finished.emit(novel_info, chapters_data)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """Главное окно приложения"""

    def __init__(self):
        super().__init__()

        self.api = RanobeLibAPI()
        self.auth = RanobeLibAuth(self.api)
        self.parser = RanobeLibParser(self.api)
        self.image_handler = ImageHandler(self.api)
        self.api.set_token_refresh_callback(self.auth.refresh_token)
        self.auth_manager = AuthManager(self.api, self.auth, self)

        self.novel_info: Optional[Dict[str, Any]] = None
        self.chapters_data: List[Dict[str, Any]] = []
        self.load_button: Optional[QToolButton] = None
        self.auth_button: Optional[QPushButton] = None
        self.novel_info_bar: Optional[QWidget] = None
        self.novel_title_label: Optional[QLabel] = None
        self.info_icon_label: Optional[QLabel] = None
        self.about_button: Optional[QPushButton] = None
        self._cover_thumb_cache: Dict[str, str] = {}
        self._initial_layout_done = False
        self.novel_info_worker = None

        self.setWindowTitle(f"RanobeLIB Downloader v{__version__}")
        self.setMinimumSize(700, 500)

        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("Готов к работе")

        self._setup_ui()
        self._setup_connections()

        stylesheet = load_stylesheet()
        if stylesheet:
            self.setStyleSheet(stylesheet)

        self.resize(900, 600)
        self.settings = QSettings("RanobeLIB", "Downloader")
        self._load_settings()

        if self.auth_button:
            self.auth_manager.auth_changed.connect(self._on_auth_changed)
            self.auth_manager.status_message.connect(self.statusbar.showMessage)

    def showEvent(self, event):
        """Перехват события первого отображения окна для настройки кнопок."""
        super().showEvent(event)
        if not self._initial_layout_done:
            button_height = self.url_input.height()
            if self.auth_button:
                self.auth_manager.configure_auth_button(self.auth_button, button_height)
            if self.about_button:
                self.about_button.setFixedSize(button_height, button_height)
            if hasattr(self, '_position_load_button'):
                self._position_load_button()
            self._initial_layout_done = True

    def _setup_ui(self):
        """Настройка пользовательского интерфейса"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 0)

        toolbar = QToolBar()
        toolbar.setObjectName("mainToolBar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(16, 16))
        self.addToolBar(toolbar)

        address_layout = QHBoxLayout()
        address_layout.setContentsMargins(10, 10, 10, 0)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://ranobelib.me/ru/book/...")

        base64_icon = "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAAACXBIWXMAAAsTAAALEwEAmpwYAAAAY0lEQVR4nO3UsQmEYAyA0X8SXUQLB3ACcQ13FCyvPnAP4Ylop4IHEQ7xg7SvCCQpvZ2FDnWKCh9MaKLADN8NbV90H0r0GC7OaG1BqyOwCAV/CXnYHgVj2X9id51eF/oc0mOaAR2mDe1O9aKOAAAAAElFTkSuQmCC"
        pixmap = QPixmap()
        pixmap.loadFromData(base64.b64decode(base64_icon))
        icon = QIcon(pixmap)

        self.load_button = QToolButton(self.url_input)
        self.load_button.setIcon(icon)
        self.load_button.setObjectName("loadButton")
        self.load_button.setToolTip("Загрузить")
        self.load_button.setVisible(False)
        self.load_button.setCursor(Qt.CursorShape.ArrowCursor)
        self.load_button.setFixedSize(22, 22)
        
        def position_load_button():
            button_y = (self.url_input.height() - self.load_button.height()) // 2
            button_x = self.url_input.width() - self.load_button.width() - 3
            self.load_button.move(button_x, button_y)
        
        self.url_input.resizeEvent = lambda event: (
            QLineEdit.resizeEvent(self.url_input, event),
            position_load_button()
        )[1]
        
        self._position_load_button = position_load_button

        address_layout.addWidget(self.url_input)

        self.auth_button = QPushButton("Вход")
        self.auth_button.setObjectName("authButton")
        self.auth_button.setToolTip("Авторизация на сайте RanobeLIB")
        address_layout.addWidget(self.auth_button)

        self.about_button = QPushButton("?")
        self.about_button.setObjectName("aboutButton")
        self.about_button.setToolTip("О программе")
        font = self.about_button.font()
        font.setBold(True)
        self.about_button.setFont(font)
        address_layout.addWidget(self.about_button)

        address_widget = QWidget()
        address_widget.setLayout(address_layout)
        toolbar.addWidget(address_widget)

        self.novel_info_bar = QWidget()
        self.novel_info_bar.setObjectName("novelInfoBar")
        novel_info_layout = QHBoxLayout(self.novel_info_bar)
        novel_info_layout.setContentsMargins(5, 0, 5, 0)

        self.novel_title_label = QLabel("Вставьте ссылку на новеллу и нажмите Enter для загрузки")
        self.novel_title_label.setObjectName("novelTitleLabel")
        font = self.novel_title_label.font()
        font.setPointSize(11)
        font.setBold(True)
        self.novel_title_label.setFont(font)

        self.info_icon_label = QLabel("🛈")
        self.info_icon_label.setObjectName("novelInfoIcon")
        self.info_icon_label.setVisible(False)

        novel_info_layout.addWidget(self.info_icon_label)
        novel_info_layout.addWidget(self.novel_title_label)
        novel_info_layout.addStretch()

        main_layout.addWidget(self.novel_info_bar, 0)

        self.chapters_widget = ChaptersWidget()
        main_layout.addWidget(self.chapters_widget, 1)

    def _setup_connections(self):
        """Настройка сигналов и слотов"""
        self.url_input.returnPressed.connect(self._load_novel)
        if self.load_button:
            self.load_button.clicked.connect(self._load_novel)
            self.url_input.textChanged.connect(self._on_url_text_changed)
        if self.auth_button:
            self.auth_button.clicked.connect(self._show_auth_menu)
        if self.about_button:
            self.about_button.clicked.connect(self._show_about)
        self.chapters_widget.settings_widget.download_button.clicked.connect(self._start_download)

    def _on_url_text_changed(self, text: str):
        """Показывает или скрывает кнопку загрузки в зависимости от наличия текста"""
        if self.load_button:
            self.load_button.setVisible(bool(text))

    def _load_settings(self):
        """Загрузка настроек приложения"""
        if self.settings.contains("geometry"):
            self.restoreGeometry(self.settings.value("geometry"))
        if self.settings.contains("state"):
            self.restoreState(self.settings.value("state"))
        if self.settings.contains("last_url"):
            self.url_input.setText(self.settings.value("last_url"))

        if hasattr(self, "chapters_widget") and hasattr(self.chapters_widget, "settings_widget"):
            self.chapters_widget.settings_widget._load_settings()

    def _save_settings(self):
        """Сохранение настроек приложения"""
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("state", self.saveState())
        self.settings.setValue("last_url", self.url_input.text())

    def _show_auth_menu(self):
        """Показ меню авторизации."""
        if self.auth_button:
            self.auth_manager.show_auth_menu(self.auth_button)

    def _on_auth_changed(self):
        """Обработчик изменения состояния авторизации"""
        if self.auth_button:
            self.auth_button.setIcon(QIcon())
            self.auth_button.setText("")
            self.auth_manager.configure_auth_button(self.auth_button, self.url_input.height())

    def _show_about(self):
        """Показ информации о программе"""
        QMessageBox.about(
            self,
            "О программе",
            f"<h3>RanobeLIB Downloader v{__version__}</h3>"
            "<p>Программа для скачивания новелл с сайта RanobeLIB.</p>"
            "<p><a href='https://github.com/zeroma25/ranobelib-downloader'>GitHub</a></p>",
        )

    def _load_novel(self):
        """Загрузка информации о новелле по URL"""
        url = self.url_input.text().strip()
        if not url:
            show_error_message(self, "Ошибка", "Введите URL новеллы")
            return

        slug = self.api.extract_slug_from_url(url)
        if not slug:
            show_error_message(self, "Ошибка", "Неверный формат ссылки на новеллу")
            return

        self.statusbar.showMessage("Загрузка информации о новелле...")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        is_authenticated = self.auth_manager.is_authenticated()
        self.novel_info_worker = NovelInfoWorker(self.api, self.parser, slug, is_authenticated)
        self.novel_info_worker.finished.connect(self._on_novel_info_loaded)
        self.novel_info_worker.error.connect(self._on_novel_info_error)
        self.novel_info_worker.start()

    def _on_novel_info_loaded(self, novel_info, chapters_data):
        """Обработчик успешной загрузки информации о новелле"""
        QApplication.restoreOverrideCursor()
        self.novel_info = novel_info
        self.chapters_data = chapters_data

        def clean_title(t_raw: Optional[str]) -> str:
            """Очищает название от HTML-сущностей и суффикса (Новелла)"""
            if not t_raw:
                return ""
            t_decoded = self.parser.decode_html_entities(t_raw)
            return re.sub(r"\s*\(Новелла\)\s*$", "", t_decoded).strip()

        rus_title = clean_title(self.novel_info.get("rus_name"))
        eng_title = clean_title(self.novel_info.get("eng_name"))

        if rus_title and eng_title and rus_title.strip().lower() != eng_title.strip().lower():
            title = f"{rus_title} / {eng_title}"
        else:
            title = rus_title or eng_title or "Без названия"

        details_html = ""

        if self.novel_info.get("authors"):
            author_name = self.novel_info["authors"][0].get("name", "Неизвестен")
            details_html += f"<p><b>Автор:</b> {author_name}</p>"

        status_id = self.novel_info.get("status_id")
        status_map = {1: "Выпускается", 2: "Завершен", 3: "Заморожен"}
        if status_id in status_map:
            details_html += f"<p><b>Статус:</b> {status_map[status_id]}</p>"

        novel_genres_list = self.novel_info.get("genres")
        if novel_genres_list:
            genre_names = sorted(
                [g.get("name", "") for g in novel_genres_list if g and g.get("name")]
            )
            if genre_names:
                details_html += f"<p><b>Жанры:</b> {', '.join(genre_names)}</p>"

        novel_tags_list = self.novel_info.get("tags")
        if novel_tags_list:
            tag_names = sorted(
                [t.get("name", "") for t in novel_tags_list if t and t.get("name")]
            )
            if tag_names:
                tags_text = ", ".join([f"#{name}" for name in tag_names])
                details_html += f"<p><b>Теги:</b> {tags_text}</p>"

        raw_summary = self.novel_info.get("summary", "Описание отсутствует.")
        decoded_summary = self.parser.decode_html_entities(raw_summary)
        summary = decoded_summary.replace("\n", "<br>")
        details_html += f'<div style="margin-top: 10px;"><b>Описание:</b><br/>{summary}</div>'

        cover_url = (self.novel_info.get("cover", {}) or {}).get("thumbnail")

        thumb_b64 = None
        if cover_url:
            thumb_b64 = self._cover_thumb_cache.get(cover_url)
            if thumb_b64 is None:
                try:
                    response = self.api.session.get(cover_url, timeout=10)
                    response.raise_for_status()
                    thumb_b64 = base64.b64encode(response.content).decode("ascii")
                    self._cover_thumb_cache[cover_url] = thumb_b64
                except Exception as e:
                    print(f"⚠️ Не удалось загрузить миниатюру обложки: {e}")
                    thumb_b64 = None

        tooltip_html = ""
        if thumb_b64:
            tooltip_html = (
                f'<div style="width: 450px;">'
                f'<table border="0" style="border-spacing: 0;">'
                f"<tr>"
                f'<td valign="top" style="padding-right: 10px;">'
                f'<img src="data:image/jpeg;base64,{thumb_b64}" style="max-width: 120px; display: block;"/>'
                f"</td>"
                f'<td valign="top">{details_html}</td>'
                f"</tr>"
                f"</table>"
                f"</div>"
            )
        else:
            tooltip_html = f'<div style="width: 400px;">{details_html}</div>'

        if self.novel_title_label:
            self.novel_title_label.setText(title)
            self.novel_title_label.setStyleSheet("")
        if self.info_icon_label:
            self.info_icon_label.setToolTip(tooltip_html)
            self.info_icon_label.setVisible(True)

        self.chapters_widget.update_chapters(self.novel_info, self.chapters_data)

        self.statusbar.showMessage(
            f"Загружена информация о новелле: {self.novel_info.get('rus_name', '')}"
        )

    def _on_novel_info_error(self, error_message):
        """Обработчик ошибки при загрузке информации о новелле"""
        QApplication.restoreOverrideCursor()
        self.statusbar.showMessage("Ошибка загрузки новеллы")
        if self.novel_title_label:
            self.novel_title_label.setText(error_message)
            self.novel_title_label.setStyleSheet("color: #e74c3c;")
        if self.info_icon_label:
            self.info_icon_label.setVisible(False)

        self.chapters_widget.clear()

    def _start_download(self):
        """Начало процесса загрузки выбранных глав"""
        if not self.novel_info or not self.chapters_data:
            show_error_message(self, "Ошибка", "Сначала загрузите информацию о новелле")
            return

        selected_chapters = self.chapters_widget.get_selected_chapters()
        if not selected_chapters:
            show_error_message(self, "Ошибка", "Не выбрано ни одной главы для загрузки")
            return

        settings_widget = self.chapters_widget.settings_widget
        selected_formats = settings_widget.get_selected_formats()
        if not selected_formats:
            show_error_message(self, "Ошибка", "Не выбран ни один формат для скачивания")
            return

        save_dir = settings_widget.get_save_directory()
        if not save_dir:
            save_dir = QFileDialog.getExistingDirectory(self, "Выберите каталог для сохранения")
            if not save_dir:
                return
            settings_widget.set_save_directory(save_dir)

        options = settings_widget.get_options()

        download_dialog = DownloadDialog(
            self.novel_info,
            selected_chapters,
            selected_formats,
            self.api,
            self.parser,
            self.image_handler,
            save_dir,
            options,
            self,
        )
        download_dialog.exec()

    def closeEvent(self, event):
        """Обработка закрытия приложения"""
        self._save_settings()
        super().closeEvent(event) 