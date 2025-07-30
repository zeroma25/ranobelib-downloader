"""
Виджет с настройками для выбора формата скачивания и пути сохранения
"""

import os
from typing import Any, Dict, List

from PyQt6.QtCore import pyqtSignal
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

    def __init__(self):
        super().__init__()
        self.format_checkboxes = {}
        self.option_checkboxes = {}
        self._setup_ui()
        self._load_settings()
        self._connect_signals()

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
        self.path_edit.setText(os.path.abspath("downloads"))
        self.path_edit.setReadOnly(True)
        path_layout.addWidget(self.path_edit)

        self.browse_button = QPushButton("...")
        self.browse_button.setFixedWidth(30)
        self.browse_button.setToolTip("Выбрать каталог")
        self.browse_button.clicked.connect(self._browse_directory)
        path_layout.addWidget(self.browse_button)

        settings_layout.addLayout(path_layout)
        main_layout.addWidget(content_frame)

        self.download_button = QPushButton("Скачать")
        self.download_button.setMinimumHeight(40)
        self.download_button.setObjectName("downloadButton")

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
        """Открывает диалог выбора директории для сохранения файлов"""
        directory = QFileDialog.getExistingDirectory(
            self, "Выберите каталог для сохранения", self.path_edit.text()
        )
        if directory:
            self.path_edit.setText(os.path.normpath(directory))

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