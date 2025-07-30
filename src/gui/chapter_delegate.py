"""
Делегат для отрисовки элементов глав с цветным и курсивным текстом
"""

import re
from typing import Dict

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QPalette
from PyQt6.QtWidgets import QApplication, QStyle, QStyledItemDelegate, QStyleOptionViewItem

SINGLE_LINE_ITEM_ROLE = Qt.ItemDataRole.UserRole + 1
TEAM_NAME_ROLE = Qt.ItemDataRole.UserRole + 2


class ChapterItemDelegate(QStyledItemDelegate):
    """Делегат для отрисовки элементов глав с цветным и курсивным текстом."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.team_colors = {}

    def set_team_colors(self, colors: Dict[str, str]):
        """Установка словаря цветов для команд."""
        self.team_colors = colors

    def paint(self, painter, option, index):
        is_single_line = index.data(SINGLE_LINE_ITEM_ROLE)
        team_name = index.data(TEAM_NAME_ROLE)

        if not is_single_line and not team_name:
            super().paint(painter, option, index)
            return

        options = QStyleOptionViewItem(option)
        self.initStyleOption(options, index)

        if options.state & QStyle.StateFlag.State_Selected:
            options.palette.setColor(QPalette.ColorRole.Highlight, QColor("#314d68"))

        style = options.widget.style() if options.widget else QApplication.style()
        text = options.text

        options.text = ""
        if style:
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, options, painter)

        default_color = options.palette.color(QPalette.ColorRole.Text)
        team_color_hex = self.team_colors.get(team_name)
        team_qcolor = QColor(team_color_hex) if team_color_hex else default_color

        text_rect = (
            style.subElementRect(QStyle.SubElement.SE_ItemViewItemText, options, options.widget)
            if style
            else options.rect
        )

        if painter:
            painter.save()
            original_font = options.font

            if is_single_line:
                match = re.match(r"(.*) (\[.*\])", text) if text else None
                if match:
                    part1, part2 = match.groups()

                    font = QFont(original_font)
                    font.setItalic(False)
                    painter.setFont(font)
                    painter.setPen(default_color)
                    painter.drawText(text_rect, options.displayAlignment, part1)

                    part1_width = painter.fontMetrics().horizontalAdvance(part1)
                    text_rect.setLeft(text_rect.left() + part1_width)
                    font.setItalic(True)
                    painter.setFont(font)
                    painter.setPen(team_qcolor)
                    painter.drawText(text_rect, options.displayAlignment, "    " + part2)
                else:
                    painter.setFont(original_font)
                    painter.setPen(default_color)
                    painter.drawText(text_rect, options.displayAlignment, text)

            elif team_name:
                font = QFont(original_font)
                font.setItalic(True)
                painter.setFont(font)
                painter.setPen(team_qcolor)
                painter.drawText(text_rect, options.displayAlignment, text)

            painter.restore() 