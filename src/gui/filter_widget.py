"""
Виджет для отображения фильтров веток и команд переводчиков
"""

from typing import Dict, Any, List, Set, Tuple
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QScrollArea, QFrame
)

# Цвета для команд
TEAM_COLORS = [
    "#1abc9c", "#2ecc71", "#3498db", "#9b59b6", "#f1c40f", "#e67e22", "#e74c3c",
    "#16a085", "#27ae60", "#2980b9", "#8e44ad", "#f39c12", "#d35400", "#c0392b",
    "#00b894", "#00cec9", "#0984e3", "#6c5ce7", "#fdcb6e", "#e17055", "#d63031",
]


class TranslationFilterWidget(QWidget):
    """Виджет для отображения и выбора фильтров переводов"""
    
    # Сигналы
    filters_changed = pyqtSignal()  # Сигнал об изменении фильтров
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.branches = {}  # Данные о ветках
        self.team_colors = {}  # Цвета для команд
        self._setup_ui()
    
    def _setup_ui(self):
        """Настройка интерфейса виджета"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Единый фильтр переводов (ветки + команды)
        translations_title_label = QLabel("Переводчики")
        font = translations_title_label.font()
        font.setBold(True)
        translations_title_label.setFont(font)
        main_layout.addWidget(translations_title_label)

        translations_frame = QFrame()
        translations_frame.setObjectName("contentFrame")
        branches_layout = QVBoxLayout(translations_frame)
        branches_layout.setContentsMargins(5, 3, 3, 3)
        
        # Контейнер для чекбоксов веток и команд
        branches_scroll = QScrollArea()
        branches_scroll.setWidgetResizable(True)
        branches_content = QWidget()
        self.branches_layout = QVBoxLayout(branches_content)
        self.branches_layout.setContentsMargins(0, 0, 0, 5)
        self.branches_layout.setSpacing(3)
        branches_scroll.setWidget(branches_content)
        branches_layout.addWidget(branches_scroll)
        
        # Добавляем выравнивание по верху
        self.branches_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        main_layout.addWidget(translations_frame)
    
    def clear(self):
        """Очищает фильтры."""
        self._clear_layout(self.branches_layout)
        self.branches = {}

    def update_filters(self, branches: Dict[str, Dict[str, Any]], team_groups_by_branch: Dict[str, List[Tuple[str, ...]]]):
        """Обновление фильтров на основе данных о ветках и командах"""
        # Очищаем существующие фильтры
        self._clear_layout(self.branches_layout)
        
        # Сохраняем данные о ветках
        self.branches = branches
        
        # Подготавливаем отображение команд по веткам
        sorted_branches = sorted(branches.items(), key=lambda item: int(item[0]))
        
        # Формируем кластеры команд для определения цветов
        global_team_groups_ordered = []
        seen_global_keys = set()
        
        for branch_id, teams_list in team_groups_by_branch.items():
            for display_group in teams_list:
                key_group = tuple(sorted(display_group))  # для уникальности
                if key_group not in seen_global_keys:
                    global_team_groups_ordered.append(display_group)
                    seen_global_keys.add(key_group)
        
        # Формируем кластеры команд для определения цветов
        clusters = []
        for group_tuple in global_team_groups_ordered:
            current_set = set(group_tuple)
            if not current_set:
                continue

            merged_with = None
            to_remove = []
            for cluster in clusters:
                if cluster & current_set:
                    current_set |= cluster
                    to_remove.append(cluster)
                    merged_with = cluster
            for r in to_remove:
                clusters.remove(r)
            clusters.append(current_set)

        # Назначаем цвета
        self.team_colors = {}
        for idx, cluster in enumerate(clusters):
            color = TEAM_COLORS[idx % len(TEAM_COLORS)]
            for team_name in cluster:
                self.team_colors[team_name] = color
        
        # Теперь наполняем layout: сначала ветка, затем её команды
        for branch_id, branch_info in sorted_branches:
            branch_checkbox = QCheckBox(branch_info["name"])
            branch_checkbox.setChecked(True)
            
            # Названия веток делаем подчеркнутыми и жирными
            font = branch_checkbox.font()
            font.setUnderline(True)
            font.setBold(True)
            branch_checkbox.setFont(font)

            self.branches_layout.addWidget(branch_checkbox)
            branch_info["checkbox"] = branch_checkbox
            branch_info["team_widgets"] = []  # Для хранения дочерних виджетов
            
            teams_in_branch = team_groups_by_branch.get(branch_id, [])
            teams_count = len(teams_in_branch)

            for i, group_tuple in enumerate(teams_in_branch):
                display_name = ", ".join(group_tuple)
                prefix = "└─ " if i == teams_count - 1 else "├─ "
                
                # Создаем контейнер для строки с командой
                team_container = QWidget()
                team_layout = QHBoxLayout(team_container)
                team_layout.setContentsMargins(3, 0, 0, 0) # Отступ слева
                team_layout.setSpacing(0)
                
                # Элементы строки
                prefix_label = QLabel(prefix)
                team_checkbox = QCheckBox() # Чекбокс без текста
                team_name_label = QLabel(display_name)
                
                # Стилизация
                first_team = group_tuple[0]
                color = self.team_colors.get(first_team, "#e0e0e0")
                original_stylesheet = f"color: {color}; font-style: italic;"
                team_name_label.setStyleSheet(original_stylesheet)
                
                # Добавляем элементы в layout
                team_layout.addWidget(prefix_label)
                team_layout.addWidget(team_checkbox)
                team_layout.addWidget(team_name_label)
                team_layout.addStretch()

                # Настройка чекбокса
                team_checkbox.setChecked(True)
                team_checkbox.stateChanged.connect(self.filters_changed.emit)
                team_checkbox.setProperty("team_group", tuple(sorted(group_tuple)))

                self.branches_layout.addWidget(team_container)
                
                # Сохраняем виджеты для управления их состоянием
                branch_info["team_widgets"].append({
                    "container": team_container,
                    "prefix_label": prefix_label,
                    "name_label": team_name_label,
                    "original_stylesheet": original_stylesheet,
                })
            
            # Подключаем обработчик изменения состояния ветки
            branch_checkbox.stateChanged.connect(
                lambda state, b_info=branch_info: self._on_branch_state_changed(state, b_info)
            )
    
    def get_selected_branch_ids(self) -> Set[str]:
        """Возвращает множество выбранных веток перевода"""
        selected_branches = set()
        
        for branch_id, branch_info in self.branches.items():
            if branch_info.get("checkbox") and branch_info["checkbox"].isChecked():
                selected_branches.add(branch_id)
                
        return selected_branches
    
    def get_selected_team_groups(self) -> Set[Tuple[str, ...]]:
        """Возвращает множество выбранных групп-команд (в виде кортежей)."""
        selected_groups = set()
        for i in range(self.branches_layout.count()):
            layout_item = self.branches_layout.itemAt(i)
            if layout_item is None:
                continue

            widget = layout_item.widget()
            if widget is None:
                continue

            # Ищем чекбокс: либо сам виджет, либо его дочерний элемент
            checkbox = None
            if isinstance(widget, QCheckBox):
                # Это чекбокс ветки, у него нет 'team_group'
                pass
            else:
                # Это контейнер QWidget для команды
                checkbox = widget.findChild(QCheckBox)

            if checkbox and checkbox.isChecked():
                group = checkbox.property("team_group")
                if group:
                    selected_groups.add(group)
        return selected_groups
    
    def get_team_colors(self) -> Dict[str, str]:
        """Возвращает словарь цветов для команд"""
        return self.team_colors
    
    def _on_branch_state_changed(self, state: int, branch_info: Dict[str, Any]):
        """Обрабатывает изменение состояния чекбокса ветки."""
        is_enabled = state == Qt.CheckState.Checked.value

        for team_widgets in branch_info.get("team_widgets", []):
            team_widgets["container"].setEnabled(is_enabled)
            
            prefix_label = team_widgets.get("prefix_label")
            name_label = team_widgets.get("name_label")
            
            if is_enabled:
                if prefix_label:
                    prefix_label.setStyleSheet("")
                if name_label:
                    name_label.setStyleSheet(team_widgets.get("original_stylesheet", ""))
            else:
                disabled_style = "color: #888888;"
                if prefix_label:
                    prefix_label.setStyleSheet(disabled_style)
                if name_label:
                    name_label.setStyleSheet(f"{disabled_style} font-style: italic;")

        # Сигнализируем об изменении фильтров
        self.filters_changed.emit()
    
    def _clear_layout(self, layout):
        """Очищает все элементы из layout"""
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater() 