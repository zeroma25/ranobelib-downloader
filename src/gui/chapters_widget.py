"""
Виджет для отображения и выбора глав
"""

from typing import Dict, Any, List, Set, Optional, Tuple
import re
import base64

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLabel, QSplitter, QGroupBox
)

from ..branches import get_formatted_branches_with_teams
from .settings_widget import SettingsWidget
from .chapter_tree import ChapterTree
from .filter_widget import TranslationFilterWidget


class ChaptersWidget(QWidget):
    """Виджет для отображения и выбора глав"""
    
    def __init__(self):
        super().__init__()
        self.novel_info = None
        self.chapters_data = None
        self.branches = {}
        self.team_colors = {}
        self.chapters_state = {}
        self._setup_ui()
        self.select_all_button.setVisible(False)
        self.select_default_button.setVisible(False)
        self.deselect_all_button.setVisible(False)
    
    def _setup_ui(self):
        """Настройка интерфейса виджета"""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Создаем разделитель для фильтров/настроек и списка глав
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Правая панель - фильтры и настройки
        filters_widget = QWidget()
        filters_layout = QVBoxLayout(filters_widget)
        filters_layout.setContentsMargins(5, 5, 5, 5)
        
        # Создаем виджет фильтров
        self.filter_widget = TranslationFilterWidget()
        filters_layout.addWidget(self.filter_widget)
        
        # Настройки скачивания
        self.settings_widget = SettingsWidget()
        filters_layout.addWidget(self.settings_widget)

        # Левая панель - дерево глав
        chapters_widget = QWidget()
        chapters_layout = QVBoxLayout(chapters_widget)
        chapters_layout.setContentsMargins(5, 5, 5, 5)
        
        # Заголовок и элементы управления
        header_layout = QHBoxLayout()
        
        self.chapters_label = QLabel('<b>Главы</b> <span style="font-weight:normal;">(Отображено: 0 | Выбрано: 0)</span>')
        font = self.chapters_label.font()
        font.setBold(False)
        self.chapters_label.setFont(font)
        header_layout.addWidget(self.chapters_label)
        header_layout.addStretch()
        
        # Кнопка "Выбрать все"
        self.select_all_button = QPushButton()
        self.select_all_button.setToolTip("Выбрать все главы")
        self.select_all_button.setObjectName("selectAllButton")
        # self.select_all_button.setCursor(Qt.CursorShape.PointingHandCursor)
        select_icon_base64 = "iVBORw0KGgoAAAANSUhEUgAAABgAAAAYCAYAAADgdz34AAAACXBIWXMAAAsTAAALEwEAmpwYAAAAn0lEQVR4nN2UQQ6DIBAA/UQbn1TTl9TnyqF39B/TgJqgkXbdpYk6R4UZXBKr6jIAT2BgPz3QSAJhoRYvCUQUXx45TwC4A6/cvqxHEmCUu2lpawqEUwZhRu7md6pAOF0qIiO3BNZCtyW3jugGdPNz4A3Ugn3yS04im3JzIBnXYixFA784VKCnwM+OL4FGGfHAwzoJMccJYMP/M+DTOzk/H7uLPObilbBMAAAAAElFTkSuQmCC"
        select_pixmap = QPixmap()
        select_pixmap.loadFromData(base64.b64decode(select_icon_base64))
        self.select_all_button.setIcon(QIcon(select_pixmap))
        self.select_all_button.setIconSize(QSize(16, 16))
        self.select_all_button.setFixedSize(QSize(16, 16))
        header_layout.addWidget(self.select_all_button)

        # Кнопка "Выбрать по умолчанию"
        self.select_default_button = QPushButton()
        self.select_default_button.setToolTip("Выбрать главы по умолчанию")
        self.select_default_button.setObjectName("selectDefaultButton")
        # self.select_default_button.setCursor(Qt.CursorShape.PointingHandCursor)
        default_icon_base64 = "iVBORw0KGgoAAAANSUhEUgAAABgAAAAYCAYAAADgdz34AAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAJcEhZcwAADsMAAA7DAcdvqGQAAACVSURBVEhL7ZRtCoAgDIZnB+k+0T06eHoP2+RFxBipMH+ED6w12LuPDOk/xBhPtsDWi2c7UEYHiaPcKKODxIiwGchU3QZvhoNPk4h3TBlr1HlabL7BavDJatCO/L8CwmYgyzqEOZ76iYI8MEAzSUnk4V+UDS621KQTKS7aOWCxeWeQb9OacooBPF+mu7xYbDD3TIwhegBqO/gGN0mWuAAAAABJRU5ErkJggg=="
        default_pixmap = QPixmap()
        default_pixmap.loadFromData(base64.b64decode(default_icon_base64))
        self.select_default_button.setIcon(QIcon(default_pixmap))
        self.select_default_button.setIconSize(QSize(16, 16))
        self.select_default_button.setFixedSize(QSize(16, 16))
        header_layout.addWidget(self.select_default_button)

        # Кнопка "Снять все"
        self.deselect_all_button = QPushButton()
        self.deselect_all_button.setToolTip("Снять выбор со всех глав")
        self.deselect_all_button.setObjectName("deselectAllButton")
        # self.deselect_all_button.setCursor(Qt.CursorShape.PointingHandCursor)
        deselect_icon_base64 = "iVBORw0KGgoAAAANSUhEUgAAABgAAAAYCAYAAADgdz34AAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAJcEhZcwAADsMAAA7DAcdvqGQAAACDSURBVEhL7ZQNCoAgDIVnB+k+0T06eHoP2+QRkog/5KDwgzkFt+dDlP6D937ncBytWI4NbfJgYy8n2uTBRo9lNSjL1i3Iw3hdAIZuR99z8GQKFJkCRVQFnAx4iNWESiKLnBALHBxBpBFpLrU6wJjeX2SQE+JTdGCNMatMRjjQvZPBEF2DJdgZJPXSzgAAAABJRU5ErkJggg=="
        deselect_pixmap = QPixmap()
        deselect_pixmap.loadFromData(base64.b64decode(deselect_icon_base64))
        self.deselect_all_button.setIcon(QIcon(deselect_pixmap))
        self.deselect_all_button.setIconSize(QSize(16, 16))
        self.deselect_all_button.setFixedSize(QSize(16, 16))
        header_layout.addWidget(self.deselect_all_button)
        
        chapters_layout.addLayout(header_layout)
        
        # Дерево глав
        self.chapters_tree = ChapterTree()
        chapters_layout.addWidget(self.chapters_tree)
        
        # Добавляем панели в разделитель (главы слева, фильтры и настройки справа)
        splitter.addWidget(chapters_widget)
        splitter.addWidget(filters_widget)

        # Настраиваем размеры разделителя: больше места под главы
        splitter.setSizes([750, 300])
        
        main_layout.addWidget(splitter)
        
        # Настраиваем обработчики событий
        self.select_all_button.clicked.connect(lambda: self.chapters_tree.set_check_state_for_all_items(Qt.CheckState.Checked))
        self.select_default_button.clicked.connect(self.chapters_tree.select_default_chapters)
        self.deselect_all_button.clicked.connect(lambda: self.chapters_tree.set_check_state_for_all_items(Qt.CheckState.Unchecked))
        self.filter_widget.filters_changed.connect(self._update_chapters_tree)
        self.chapters_tree.stats_changed.connect(self._update_stats_label)

    def clear(self):
        """Очищает виджет от информации о новелле."""
        self.novel_info = None
        self.chapters_data = None
        self.branches = {}
        self.chapters_state = {}
        self.chapters_tree.clear()
        self.filter_widget.clear()
        self._update_stats_label(0, 0)

    def get_selected_chapters_and_formats(self) -> Tuple[List[Dict[str, Any]], List[str], str]:
        """Возвращает кортеж с выбранными главами, форматами и путем сохранения."""
        selected_chapters = self.get_selected_chapters()
        selected_formats = self.settings_widget.get_selected_formats()
        save_directory = self.settings_widget.get_save_directory()
        return selected_chapters, selected_formats, save_directory

    def get_settings_widget(self) -> SettingsWidget:
        """Возвращает экземпляр виджета настроек."""
        return self.settings_widget

    def update_chapters(self, novel_info: Dict[str, Any], chapters_data: List[Dict[str, Any]]):
        """Обновление списка глав на основе данных новеллы"""
        self.novel_info = novel_info
        self.chapters_data = chapters_data
        
        # Получаем информацию о ветках перевода
        self.branches = get_formatted_branches_with_teams(novel_info, chapters_data)
        
        # Подготавливаем отображение команд по веткам
        sorted_branches = sorted(self.branches.items(), key=lambda item: int(item[0]))

        # Сначала собираем команды по веткам, сохраняя порядок первого появления
        branch_team_groups_ordered = {bid: [] for bid, _ in sorted_branches}
        global_team_groups_ordered = []
        seen_global_keys = set()
        seen_per_branch = {bid: set() for bid, _ in sorted_branches}

        for chapter in self.chapters_data or []:
            for branch in chapter.get("branches", []):
                if not isinstance(branch, dict):
                    continue

                branch_id_raw = branch.get("branch_id")
                branch_id = str(branch_id_raw if branch_id_raw is not None else "0")
                teams_list = branch.get("teams", []) or []
                team_names = [team.get("name", "Неизвестный") for team in teams_list]
                if not team_names:
                    team_names = ["Неизвестный"]

                display_group = tuple(team_names)  # исходный порядок
                key_group = tuple(sorted(team_names))  # для уникальности

                # Глобальный список (для цветов)
                if key_group not in seen_global_keys:
                    global_team_groups_ordered.append(display_group)
                    seen_global_keys.add(key_group)

                # Для конкретной ветки
                if key_group not in seen_per_branch[branch_id]:
                    branch_team_groups_ordered[branch_id].append(display_group)
                    seen_per_branch[branch_id].add(key_group)
        
        # Обновляем фильтры
        self.filter_widget.update_filters(self.branches, branch_team_groups_ordered)
        
        # Получаем цвета команд
        self.team_colors = self.filter_widget.get_team_colors()
        
        # Устанавливаем цвета для делегата отрисовки
        self.chapters_tree.set_team_colors(self.team_colors)
        
        # Обновляем дерево глав
        self._update_chapters_tree()

        # Выбираем главы по умолчанию при первой загрузке
        self.chapters_tree.select_default_chapters()
    
    def _parse_chapter_number(self, number_str: str) -> tuple:
        """Преобразование строки номера главы в кортеж чисел для сортировки."""
        # Разбиваем строку на компоненты по разделителям
        parts = re.split(r'[.\-_]', str(number_str))
        # Преобразуем каждый компонент в число, если возможно
        result = []
        for part in parts:
            try:
                result.append(int(part))
            except ValueError:
                # Если не удалось преобразовать в число, оставляем как строку
                result.append(part)
        return tuple(result)
    
    def _update_chapters_tree(self):
        """Обновление дерева глав с учетом текущих фильтров"""
        if not self.chapters_data:
            return
            
        # Сохраняем текущее состояние чекбоксов
        self.chapters_state = self.chapters_tree.save_chapters_state()
        
        # Получаем состояние фильтров
        selected_branch_ids = self.filter_widget.get_selected_branch_ids()
        selected_team_groups = self.filter_widget.get_selected_team_groups()
        
        # Группировка глав по томам
        volumes = {}
        
        for chapter in self.chapters_data:
            vol_num = str(chapter.get("volume", "0"))
            
            # Получаем все ветки главы и проверяем, подходят ли они под фильтры
            available_translations = []
            for branch in chapter.get("branches", []):
                branch_id = "0"
                teams = []
                current_group_tuple = tuple()

                if isinstance(branch, dict):
                    branch_id_raw = branch.get("branch_id")
                    branch_id = str(branch_id_raw if branch_id_raw is not None else "0")
                    teams_list = branch.get("teams", []) or []
                    teams = [team.get("name", "Неизвестный") for team in teams_list]
                    if not teams:
                        teams = ["Неизвестный"]
                    current_group_tuple = tuple(sorted(teams))
                elif branch is not None:
                    branch_id = str(branch)
                    teams = ["Неизвестный"]
                    current_group_tuple = ("Неизвестный",)

                # Проверяем, подходит ли ветка под фильтры
                if branch_id in selected_branch_ids and current_group_tuple in selected_team_groups:
                    available_translations.append({"id": branch_id, "teams": teams})

            # Если нет подходящих веток, пропускаем главу
            if not available_translations:
                continue
                
            # Добавляем главу в соответствующий том
            if vol_num not in volumes:
                volumes[vol_num] = []
            
            volumes[vol_num].append((chapter, available_translations))
        
        # Обновляем дерево глав
        self.chapters_tree.update_chapters_tree(volumes, self.chapters_state)

    def get_selected_chapters(self) -> List[Dict[str, Any]]:
        """Возвращает список выбранных для скачивания глав-переводов"""
        return self.chapters_tree.get_selected_chapters()
    
    def _update_stats_label(self, total_translations: int, selected_translations: int):
        """Обновляет текст метки с информацией о количестве глав"""
        self.chapters_label.setText(f'<b>Главы</b> <span style="font-weight:normal;">(Отображено: {total_translations} | Выбрано: {selected_translations})</span>')
        
        # Обновляем видимость кнопок выбора/снятия
        is_visible = total_translations > 0
        self.select_all_button.setVisible(is_visible)
        self.select_default_button.setVisible(is_visible)
        self.deselect_all_button.setVisible(is_visible) 