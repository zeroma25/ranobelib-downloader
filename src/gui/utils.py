"""
Вспомогательные функции для GUI
"""

import os
from typing import Optional, Callable, Any

from PyQt6.QtCore import QObject
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QMessageBox, QWidget


def load_stylesheet() -> Optional[str]:
    """Загружает CSS стили для приложения"""
    style_path = os.path.join(os.path.dirname(__file__), "styles", "style.css")
    if os.path.exists(style_path):
        with open(style_path, "r", encoding="utf-8") as f:
            return f.read()
    return None


def create_action(
    parent: QObject,
    text: str,
    slot: Optional[Callable] = None,
    shortcut: Optional[str] = None,
    icon: Optional[QIcon] = None,
    tip: Optional[str] = None,
    checkable: bool = False,
    signal: str = "triggered"
) -> QAction:
    """Создание QAction с заданными параметрами"""
    action = QAction(text, parent)
    if icon:
        action.setIcon(icon)
    if shortcut:
        action.setShortcut(shortcut)
    if tip:
        action.setToolTip(tip)
        action.setStatusTip(tip)
    if slot:
        getattr(action, signal).connect(slot)
    if checkable:
        action.setCheckable(True)
    return action


def show_error_message(parent: Optional[QWidget], title: str, message: str) -> None:
    """Показывает диалоговое окно с сообщением об ошибке"""
    QMessageBox.critical(parent, title, message)


def show_info_message(parent: Optional[QWidget], title: str, message: str) -> None:
    """Показывает информационное диалоговое окно"""
    QMessageBox.information(parent, title, message) 