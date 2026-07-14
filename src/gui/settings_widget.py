"""
Виджет с настройками для выбора формата скачивания и пути сохранения
"""

import base64
import os
from typing import Any, Dict, List

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..settings import settings


class SettingsWidget(QWidget):
    """Виджет с настройками для скачивания"""

    settings_changed = pyqtSignal()
    cache_cleared = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.format_checkboxes = {}
        self.option_checkboxes = {}
        self.current_novel_id = None
        self._setup_ui()
        self._load_settings()
        self._connect_signals()

    def set_current_novel_id(self, novel_id: str):
        self.current_novel_id = novel_id

    def _setup_ui(self):
        """Настройка интерфейса виджета"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 10, 0, 0)

        settings_title_label = QLabel("Настройки")
        font = settings_title_label.font()
        font.setBold(True)
        settings_title_label.setFont(font)
        main_layout.addWidget(settings_title_label)

        content_frame = QFrame()
        content_frame.setObjectName("contentFrame")
        settings_layout = QVBoxLayout(content_frame)

        cache_layout = QHBoxLayout()
        cache_layout.setContentsMargins(0, 0, 0, 0)
        
        self.option_checkboxes["cache_chapters"] = QCheckBox("Использовать локальный кэш")
        self.option_checkboxes["cache_chapters"].setChecked(True)
        self.option_checkboxes["cache_chapters"].setToolTip(
            "Сохранять главы на устройстве и использовать их при повторных запросах"
        )
        cache_layout.addWidget(self.option_checkboxes["cache_chapters"])
        
        cache_layout.addStretch()

        self.clear_cache_button = QPushButton()
        self.clear_cache_button.setFixedSize(20, 20)
        self.clear_cache_button.setToolTip("Очистка кэша")
        
        clear_icon_b64 = "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAACXBIWXMAAAsTAAALEwEAmpwYAAABvUlEQVR4nO2WPS9DURjHT4IaxCSi4QNUDIrU4C0+gyhDQyw20sGiY0eRMFmtxIQISxlE+AIkmAxIJN7fFsRPHn0kp++p3nu79L/ce59z7v39z3nO87TGVOShAD8wVU74KUlNew1vAk4UfgY0V+CuiwrcLTjQCCwD58ABMJqj1OTqdxreClySqbgX8CHgWQHHQBswCXxq7NYVOFANzAPf1ooFGtbxcJoJv9P5TljQWSCmz19AROcNAx8an3MK3gtc6UdvgEFrLF5gJ8ZKhUetFR0CLVnmZDMx/ncO/guuA1asXC8BvjzzU0wADfr8+h94wGog77Iaa6wd2JMzUcDErt4nioWHgCd9+QIIWmNBq8QWC+zE7+qBzmIN+IBN/cA90KXxDuBO41u50gHM6JwXoK8oeB4TE3oVbQO1JoukOnT7pU+MmFJEqok/7QgcqEkHSHVoiYoWSoLnMCGr6gGqgDWNxax5Rxrbl45pnBKZ6djQ+wc5FzpHSlR07fgPj2Vi3UrFG9CvYxGNSbMaMG6JVBOPQLf2BOkToqhr8DzpkD4hWjVeicx0yF+tes8MpO2EdMyAKYdImgiVBe6WfgAaB71vZ0ZojQAAAABJRU5ErkJggg=="
        clear_pixmap = QPixmap()
        clear_pixmap.loadFromData(base64.b64decode(clear_icon_b64))
        self.clear_cache_button.setIcon(QIcon(clear_pixmap))
        
        self.clear_cache_button.setStyleSheet("QPushButton { background-color: #d44637; } QPushButton:hover { background-color: #e74c3c; }")
        
        cache_layout.addWidget(self.clear_cache_button)
        settings_layout.addLayout(cache_layout)
        settings_layout.addSpacing(5)
        
        self.clear_cache_button.clicked.connect(self._show_clear_cache_menu)

        separator = QFrame()
        separator.setFixedHeight(1)
        separator.setStyleSheet("background-color: #555;")
        settings_layout.addWidget(separator)
        settings_layout.addSpacing(5)

        self.option_checkboxes["download_cover"] = QCheckBox("Скачивать обложку")
        self.option_checkboxes["download_cover"].setChecked(True)
        self.option_checkboxes["download_cover"].setToolTip("Включает скачивание обложки новеллы")
        settings_layout.addWidget(self.option_checkboxes["download_cover"])

        self.option_checkboxes["download_images"] = QCheckBox("Скачивать изображения из глав")
        self.option_checkboxes["download_images"].setChecked(True)
        self.option_checkboxes["download_images"].setToolTip(
            "Включает скачивание изображений из глав"
        )
        settings_layout.addWidget(self.option_checkboxes["download_images"])

        self.option_checkboxes["compress_images"] = QCheckBox("Сжимать изображения")
        self.option_checkboxes["compress_images"].setChecked(True)
        self.option_checkboxes["compress_images"].setToolTip(
            "Ограничение высоты/ширины изображений до 800px"
        )
        settings_layout.addWidget(self.option_checkboxes["compress_images"])

        self.option_checkboxes["add_translator"] = QCheckBox("Добавлять данные о переводчике")
        self.option_checkboxes["add_translator"].setChecked(False)
        self.option_checkboxes["add_translator"].setToolTip(
            "Добавляет строку с переводчиком после названия главы"
        )
        settings_layout.addWidget(self.option_checkboxes["add_translator"])

        self.option_checkboxes["group_by_volumes"] = QCheckBox("Группировать главы по томам")
        self.option_checkboxes["group_by_volumes"].setChecked(True)
        self.option_checkboxes["group_by_volumes"].setToolTip(
            "Группировка по томам вместо указания тома в названии главы"
        )
        settings_layout.addWidget(self.option_checkboxes["group_by_volumes"])

        settings_layout.setSpacing(3)
        formats_label = QLabel("Формат книги:")
        formats_label.setStyleSheet("margin-top: 5px;")
        settings_layout.addWidget(formats_label)

        formats = [
            ("EPUB", "Универсальный формат для большинства устройств и приложений"),
            ("FB2", "Популярный в России формат на основе XML"),
            ("HTML", "Веб-страница для чтения в браузере"),
            ("TXT", "Простой текст без форматирования и изображений"),
        ]

        formats_layout = QGridLayout()
        formats_layout.setSpacing(5)

        for i, (format_name, format_desc) in enumerate(formats):
            checkbox = QCheckBox(format_name)
            checkbox.setChecked(format_name == "EPUB")
            checkbox.setToolTip(format_desc)

            row = i // 4
            col = i % 4
            formats_layout.addWidget(checkbox, row, col)

            self.format_checkboxes[format_name] = checkbox

        settings_layout.addLayout(formats_layout)

        path_label = QLabel("Каталог для сохранения:")
        path_label.setStyleSheet("margin-top: 5px;")
        settings_layout.addWidget(path_label)

        path_layout = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setMinimumHeight(28)
        self.path_edit.setText(os.path.abspath("downloads"))
        self.path_edit.setReadOnly(True)
        path_layout.addWidget(self.path_edit)

        self.browse_button = QPushButton("...")
        self.browse_button.setFixedWidth(30)
        self.browse_button.setMinimumHeight(28)
        self.browse_button.setToolTip("Выбрать каталог")
        self.browse_button.clicked.connect(self._browse_directory)
        path_layout.addWidget(self.browse_button)

        settings_layout.addLayout(path_layout)
        settings_layout.addStretch()
        main_layout.addWidget(content_frame)

        self.download_button = QPushButton(" Скачать")
        self.download_button.setMinimumHeight(40)
        self.download_button.setObjectName("downloadButton")

        base64_icon = "PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHdpZHRoPScyNCcgaGVpZ2h0PScyNCcgdmlld0JveD0nMCAwIDI0IDI0Jz48ZyBmaWxsPScjZmZmZmZmJyBmaWxsLXJ1bGU9J2V2ZW5vZGQnIGNsaXAtcnVsZT0nZXZlbm9kZCc+PHBhdGggZD0nTTEzIDExLjE1VjRhMSAxIDAgMSAwLTIgMHY3LjE1TDguNzggOC4zNzRhMSAxIDAgMSAwLTEuNTYgMS4yNWw0IDVhMSAxIDAgMCAwIDEuNTYgMGw0LTVhMSAxIDAgMSAwLTEuNTYtMS4yNXonLz48cGF0aCBkPSdNOS42NTcgMTUuODc0TDcuMzU4IDEzSDVhMiAyIDAgMCAwLTIgMnY0YTIgMiAwIDAgMCAyIDJoMTRhMiAyIDAgMCAwIDItMnYtNGEyIDIgMCAwIDAtMi0yaC0yLjM1OGwtMi4zIDIuODc0YTMgMyAwIDAgMS00LjY4NSAwTTE3IDE2YTEgMSAwIDEgMCAwIDJoLjAxYTEgMSAwIDEgMCAwLTJ6Jy8+PC9nPjwvc3ZnPg=="
        pixmap = QPixmap()
        pixmap.loadFromData(base64.b64decode(base64_icon))
        icon = QIcon(pixmap)
        self.download_button.setIcon(icon)

        main_layout.addWidget(self.download_button)

    def _load_settings(self):
        """Загрузка настроек из модуля settings"""
        for key, checkbox in self.option_checkboxes.items():
            checkbox.setChecked(settings.get(key))

        self.path_edit.setText(settings.get("save_directory"))

        selected_formats = settings.get("selected_formats", ["EPUB"])
        for format_name, checkbox in self.format_checkboxes.items():
            checkbox.setChecked(format_name in selected_formats)

    def _connect_signals(self):
        """Подключение сигналов к слотам"""
        for key, checkbox in self.option_checkboxes.items():
            checkbox.stateChanged.connect(lambda state, k=key: self._save_option(k, bool(state)))

        for checkbox in self.format_checkboxes.values():
            checkbox.stateChanged.connect(self._save_formats)

        self.path_edit.textChanged.connect(lambda text: self._save_option("save_directory", text))

    def _save_option(self, key: str, value: Any):
        """Сохранение отдельной настройки"""
        settings.set(key, value)
        self.settings_changed.emit()

    def _save_formats(self):
        """Сохранение выбранных форматов"""
        selected = self.get_selected_formats()
        settings.set("selected_formats", selected)
        self.settings_changed.emit()

    def _browse_directory(self):
        """Открытие диалога выбора каталога"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Выберите каталог для сохранения",
            self.path_edit.text(),
            QFileDialog.Option.ShowDirsOnly,
        )

        if dir_path:
            self.path_edit.setText(os.path.abspath(dir_path))

    def _show_clear_cache_menu(self):
        from PyQt6.QtWidgets import QMenu
        from ..cache import ChapterCache
        
        cache = ChapterCache()
        menu = QMenu(self)
        
        action_clear_all = menu.addAction("Очистить весь кэш")
        action_clear_all.triggered.connect(self._clear_cache)
        
        if self.current_novel_id:
            action_clear_current = menu.addAction("Очистить кэш текущей новеллы")
            action_clear_current.triggered.connect(lambda checked: self._clear_novel_cache(self.current_novel_id))
            
        cached_novels = cache.get_all_cached_novels()
        if cached_novels:
            menu.addSeparator()
            for novel in cached_novels:
                action = menu.addAction(f"Очистить: {novel['name']}")
                action.triggered.connect(lambda checked, nid=novel['id']: self._clear_novel_cache(nid))
                
        menu.exec(self.clear_cache_button.mapToGlobal(self.clear_cache_button.rect().bottomLeft()))

    def _clear_cache(self):
        """Очистка кэша с подтверждением"""
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self,
            "Очистка кэша",
            "Вы действительно хотите очистить весь кэш скачанных глав и временные файлы?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                from ..cache import ChapterCache
                ChapterCache().clear_all_cache()
                QMessageBox.information(self, "Успех", "Кэш успешно очищен.")
                self.cache_cleared.emit()
            except Exception as e:
                QMessageBox.warning(self, "Ошибка", f"Не удалось очистить кэш:\n{e}")

    def _clear_novel_cache(self, novel_id: str):
        """Очистка кэша определенной новеллы"""
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self,
            "Очистка кэша",
            "Вы действительно хотите очистить кэш скачанных глав для этой новеллы?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                from ..cache import ChapterCache
                ChapterCache().clear_novel_cache(novel_id)
                QMessageBox.information(self, "Успех", "Кэш новеллы успешно очищен.")
                self.cache_cleared.emit()
            except Exception as e:
                QMessageBox.warning(self, "Ошибка", f"Не удалось очистить кэш:\n{e}")

    def get_selected_formats(self) -> List[str]:
        """Возвращает список выбранных форматов"""
        return [
            format_name
            for format_name, checkbox in self.format_checkboxes.items()
            if checkbox.isChecked()
        ]

    def get_save_directory(self) -> str:
        """Возвращает выбранный каталог для сохранения"""
        return self.path_edit.text()

    def set_save_directory(self, directory: str):
        """Устанавливает каталог для сохранения"""
        self.path_edit.setText(os.path.normpath(directory))

    def get_options(self) -> Dict[str, bool]:
        """Возвращает словарь с настройками опций"""
        return {key: checkbox.isChecked() for key, checkbox in self.option_checkboxes.items()}

    def get_focus_chain(self) -> List[QWidget]:
        """Возвращает виджеты настроек в порядке табуляции."""
        chain: List[QWidget] = []

        checkbox = self.option_checkboxes.get("cache_chapters")
        if checkbox is not None:
            chain.append(checkbox)
            
        chain.append(self.clear_cache_button)

        for key in ["download_cover", "download_images", "compress_images", "add_translator", "group_by_volumes"]:
            checkbox = self.option_checkboxes.get(key)
            if checkbox is not None:
                chain.append(checkbox)

        for key in ["EPUB", "FB2", "HTML", "TXT"]:
            checkbox = self.format_checkboxes.get(key)
            if checkbox is not None:
                chain.append(checkbox)

        chain.append(self.path_edit)
        chain.append(self.browse_button)
        chain.append(self.download_button)
        return chain 