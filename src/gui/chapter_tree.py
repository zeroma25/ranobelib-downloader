"""
Виджет дерева глав для отображения и выбора глав новеллы
"""

from typing import Any, Dict, List

from PyQt6.QtCore import QTimer, Qt, QVariant, pyqtSignal
from PyQt6.QtWidgets import QMenu, QTreeWidgetItem, QTreeWidgetItemIterator, QTreeWidget

from .chapter_delegate import TEAM_NAME_ROLE, SINGLE_LINE_ITEM_ROLE, ChapterItemDelegate


class ChapterTree(QTreeWidget):
    """Виджет дерева глав для отображения и выбора глав новеллы"""

    stats_changed = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.chapters_state = {}
        self._stats_update_timer = QTimer(self)
        self._stats_update_timer.setSingleShot(True)
        self._stats_update_timer.timeout.connect(self._update_stats)
        self._setup_ui()

    def _setup_ui(self):
        """Настройка интерфейса виджета"""
        self.setHeaderHidden(True)
        self.setAlternatingRowColors(True)
        self.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.itemChanged.connect(self._update_stats_on_change)

        self.delegate = ChapterItemDelegate(self)
        self.setItemDelegate(self.delegate)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def set_team_colors(self, colors: Dict[str, str]):
        """Установка словаря цветов для команд."""
        self.delegate.set_team_colors(colors)

    def update_chapters_tree(
        self, volumes_data: Dict[str, List[tuple]], chapters_state: Dict[tuple, Qt.CheckState]
    ):
        """Обновление дерева глав на основе данных о томах и главах"""
        self.chapters_state = chapters_state.copy() if chapters_state else {}
        self.clear()

        for vol_num in sorted(volumes_data.keys(), key=lambda x: int(x) if x.isdigit() else 0):
            vol_name = f"Том {vol_num}" if vol_num != "0" else "Том не указан"
            vol_item = QTreeWidgetItem([vol_name])

            font = vol_item.font(0)
            font.setBold(True)
            vol_item.setFont(0, font)

            vol_item.setFlags(
                vol_item.flags() | Qt.ItemFlag.ItemIsAutoTristate | Qt.ItemFlag.ItemIsUserCheckable
            )
            vol_item.setCheckState(0, Qt.CheckState.Checked)
            self.addTopLevelItem(vol_item)

            for chapter_info in volumes_data[vol_num]:
                chapter, translations = chapter_info

                ch_name = chapter.get("name", "").strip()
                ch_number = chapter.get("number", "?")

                chapter_title = f"Глава {ch_number} - {ch_name}" if ch_name else f"Глава {ch_number}"

                if len(translations) == 1:
                    trans_info = translations[0]
                    branch_id = trans_info["id"]
                    teams = trans_info["teams"]
                    translator_name = ", ".join(teams) if teams else "Неизвестный"
                    coloring_team_name = teams[0] if teams else translator_name

                    full_title = f"{chapter_title} [{translator_name}]"

                    ch_item = QTreeWidgetItem([full_title])
                    ch_item.setData(0, SINGLE_LINE_ITEM_ROLE, True)
                    ch_item.setData(0, TEAM_NAME_ROLE, coloring_team_name)
                    ch_item.setFlags(ch_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)

                    key = (
                        str(chapter.get("volume", "0")),
                        str(chapter.get("number", "0")),
                        str(branch_id),
                    )
                    check_state = self.chapters_state.get(key, Qt.CheckState.Checked)
                    ch_item.setCheckState(0, check_state)

                    ch_item.setData(0, Qt.ItemDataRole.UserRole, QVariant(chapter))
                    ch_item.setData(1, Qt.ItemDataRole.UserRole, QVariant(branch_id))

                    vol_item.addChild(ch_item)
                else:
                    ch_item = QTreeWidgetItem([chapter_title])
                    ch_item.setFlags(
                        ch_item.flags() | Qt.ItemFlag.ItemIsAutoTristate | Qt.ItemFlag.ItemIsUserCheckable
                    )
                    ch_item.setCheckState(0, Qt.CheckState.Checked)
                    vol_item.addChild(ch_item)

                    for trans_info in translations:
                        branch_id = trans_info["id"]
                        teams = trans_info["teams"]

                        translator_name = ", ".join(teams) if teams else "Неизвестный"
                        coloring_team_name = teams[0] if teams else translator_name
                        display_name = f"[{translator_name}]"

                        translation_item = QTreeWidgetItem([display_name])
                        translation_item.setData(0, TEAM_NAME_ROLE, coloring_team_name)

                        translation_item.setFlags(translation_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)

                        key = (
                            str(chapter.get("volume", "0")),
                            str(chapter.get("number", "0")),
                            str(branch_id),
                        )
                        check_state = self.chapters_state.get(key, Qt.CheckState.Checked)
                        translation_item.setCheckState(0, check_state)

                        translation_item.setData(0, Qt.ItemDataRole.UserRole, QVariant(chapter))
                        translation_item.setData(1, Qt.ItemDataRole.UserRole, QVariant(branch_id))

                        ch_item.addChild(translation_item)

        self.expandAll()
        self._update_stats()

    def save_chapters_state(self):
        """Сохраняет текущее состояние (выбрано/не выбрано) всех глав-переводов."""
        self.chapters_state.clear()

        iterator = QTreeWidgetItemIterator(self)
        while iterator.value():
            item = iterator.value()
            if item:
                chapter_data = item.data(0, Qt.ItemDataRole.UserRole)
                branch_id = item.data(1, Qt.ItemDataRole.UserRole)

                if chapter_data and branch_id is not None:
                    key = (
                        str(chapter_data.get("volume", "0")),
                        str(chapter_data.get("number", "0")),
                        str(branch_id),
                    )
                    self.chapters_state[key] = item.checkState(0)
            iterator += 1

        return self.chapters_state

    def get_selected_chapters(self) -> List[Dict[str, Any]]:
        """Возвращает список выбранных для скачивания глав-переводов"""
        selected_chapters = []

        for i in range(self.topLevelItemCount()):
            vol_item = self.topLevelItem(i)
            if vol_item is None:
                continue

            for j in range(vol_item.childCount()):
                ch_item = vol_item.child(j)
                if ch_item is None:
                    continue

                if ch_item.childCount() == 0:
                    if ch_item.checkState(0) == Qt.CheckState.Checked:
                        chapter_data = ch_item.data(0, Qt.ItemDataRole.UserRole)
                        branch_id = ch_item.data(1, Qt.ItemDataRole.UserRole)
                        if chapter_data and branch_id is not None:
                            if ch_item.data(0, TEAM_NAME_ROLE) is not None:
                                selected_chapters.append(
                                    {"chapter": chapter_data, "branch_ids": [branch_id]}
                                )
                else:
                    for k in range(ch_item.childCount()):
                        translation_item = ch_item.child(k)
                        if translation_item is None:
                            continue

                        if translation_item.checkState(0) == Qt.CheckState.Checked:
                            chapter_data = translation_item.data(0, Qt.ItemDataRole.UserRole)
                            branch_id = translation_item.data(1, Qt.ItemDataRole.UserRole)

                            if chapter_data and branch_id is not None:
                                selected_chapters.append(
                                    {"chapter": chapter_data, "branch_ids": [branch_id]}
                                )

        return selected_chapters

    def set_check_state_for_all_items(self, state: Qt.CheckState):
        """Устанавливает состояние чекбокса для всех элементов в дереве"""
        self.itemChanged.disconnect(self._update_stats_on_change)

        iterator = QTreeWidgetItemIterator(self)
        while iterator.value():
            item = iterator.value()
            if item:
                item.setCheckState(0, state)
            iterator += 1

        self.itemChanged.connect(self._update_stats_on_change)
        self._update_stats()

    def select_default_chapters(self):
        """Выбирает по одному переводу для каждой главы по умолчанию."""
        try:
            self.itemChanged.disconnect(self._update_stats_on_change)
        except TypeError:
            pass

        iterator = QTreeWidgetItemIterator(self)
        while iterator.value():
            item = iterator.value()
            if item:
                item.setCheckState(0, Qt.CheckState.Unchecked)
            iterator += 1

        selected_chapter_keys = set()

        while True:
            first_unselected_item = None

            iterator = QTreeWidgetItemIterator(self)
            while iterator.value():
                item = iterator.value()
                if item:
                    chapter_data = item.data(0, Qt.ItemDataRole.UserRole)
                    branch_id = item.data(1, Qt.ItemDataRole.UserRole)

                    if chapter_data and branch_id is not None:
                        key = (
                            str(chapter_data.get("volume", "0")),
                            str(chapter_data.get("number", "0")),
                        )
                        if key not in selected_chapter_keys:
                            first_unselected_item = item
                            break
                iterator += 1

            if not first_unselected_item:
                break

            first_unselected_item.setCheckState(0, Qt.CheckState.Checked)
            chapter_data = first_unselected_item.data(0, Qt.ItemDataRole.UserRole)
            selected_branch_id = first_unselected_item.data(1, Qt.ItemDataRole.UserRole)

            if chapter_data:
                key = (str(chapter_data.get("volume", "0")), str(chapter_data.get("number", "0")))
                selected_chapter_keys.add(key)

            while iterator.value():
                item = iterator.value()
                if item:
                    chapter_data_next = item.data(0, Qt.ItemDataRole.UserRole)
                    branch_id_next = item.data(1, Qt.ItemDataRole.UserRole)

                    if chapter_data_next and branch_id_next is not None:
                        key_next = (
                            str(chapter_data_next.get("volume", "0")),
                            str(chapter_data_next.get("number", "0")),
                        )

                        if key_next not in selected_chapter_keys and branch_id_next == selected_branch_id:
                            item.setCheckState(0, Qt.CheckState.Checked)
                            selected_chapter_keys.add(key_next)
                iterator += 1

        self.itemChanged.connect(self._update_stats_on_change)
        self._update_stats()

    def _update_stats_on_change(self, item, column):
        """Обновляет статистику при изменении состояния элемента"""
        if column == 0:
            self._stats_update_timer.start(50)

    def _update_stats(self):
        """Обновляет статистику выбранных глав"""
        total_translations = 0
        selected_translations = 0

        for i in range(self.topLevelItemCount()):
            vol_item = self.topLevelItem(i)
            if vol_item is None:
                continue

            for j in range(vol_item.childCount()):
                ch_item = vol_item.child(j)
                if ch_item is None:
                    continue

                if ch_item.childCount() == 0:
                    if ch_item.data(0, TEAM_NAME_ROLE) is not None:
                        total_translations += 1
                        if ch_item.checkState(0) == Qt.CheckState.Checked:
                            selected_translations += 1
                else:
                    for k in range(ch_item.childCount()):
                        translation_item = ch_item.child(k)
                        if translation_item is None:
                            continue

                        total_translations += 1

                        if translation_item.checkState(0) == Qt.CheckState.Checked:
                            selected_translations += 1

        self.stats_changed.emit(total_translations, selected_translations)

        if viewport := self.viewport():
            viewport.update()

    def _show_context_menu(self, position):
        """Показывает контекстное меню для дерева глав."""
        menu = QMenu(self)
        menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        menu.setWindowFlags(menu.windowFlags() | Qt.WindowType.FramelessWindowHint)
        
        expand_action = menu.addAction("Развернуть все")
        collapse_action = menu.addAction("Свернуть все")

        viewport = self.viewport()
        global_pos = (
            viewport.mapToGlobal(position) if viewport is not None else self.mapToGlobal(position)
        )
        action = menu.exec(global_pos)
        if action == expand_action:
            self.expandAll()
        elif action == collapse_action:
            self.collapseAll() 