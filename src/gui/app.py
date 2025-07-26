"""
Точка входа для запуска GUI приложения
"""

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt

from .main_window import MainWindow


def run_gui():
    """Запуск графического интерфейса"""
    app = QApplication(sys.argv)
    app.setApplicationName("RanobeLIB Downloader")
    app.setOrganizationName("RanobeLIB")
    
    # Применяем темную тему Fusion
    app.setStyle("Fusion")
    
    # Настраиваем темную палитру
    dark_palette = QPalette()
    
    # Основные цвета
    dark_color = QColor(45, 45, 45)
    disabled_color = QColor(70, 70, 70)
    text_color = QColor(200, 200, 200)
    highlight_color = QColor(42, 130, 218)
    
    # Настройка палитры
    dark_palette.setColor(QPalette.ColorRole.Window, dark_color)
    dark_palette.setColor(QPalette.ColorRole.WindowText, text_color)
    dark_palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
    dark_palette.setColor(QPalette.ColorRole.AlternateBase, dark_color)
    dark_palette.setColor(QPalette.ColorRole.ToolTipBase, dark_color)
    dark_palette.setColor(QPalette.ColorRole.ToolTipText, text_color)
    dark_palette.setColor(QPalette.ColorRole.Text, text_color)
    dark_palette.setColor(QPalette.ColorRole.Button, dark_color)
    dark_palette.setColor(QPalette.ColorRole.ButtonText, text_color)
    dark_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    dark_palette.setColor(QPalette.ColorRole.Link, highlight_color)
    dark_palette.setColor(QPalette.ColorRole.Highlight, highlight_color)
    dark_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
    
    # Отключенные элементы
    dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, disabled_color)
    dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled_color)
    dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled_color)
    
    # Применяем палитру
    app.setPalette(dark_palette)
    
    # Запуск главного окна
    main_window = MainWindow()
    main_window.show()
    
    # Запуск цикла событий приложения
    return app.exec() 