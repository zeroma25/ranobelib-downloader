"""
Модуль для работы с ветками переводов и командами переводчиков
"""
import re
from collections import defaultdict
from typing import Any, Dict, List, Set


def get_formatted_branches_with_teams(
    novel_info: Dict[str, Any], chapters_data: List[Dict[str, Any]]
) -> Dict[str, Dict[str, Any]]:
    """Формирование агрегированных данных по веткам переводов, командам и числу глав."""
    base_branches = _get_base_branches_from_novel_info(novel_info)
    chapter_counts = _get_chapter_counts_by_branch(chapters_data)
    teams_by_branch = _get_teams_by_branch(chapters_data)

    formatted_branches = {}
    all_branch_ids = set(base_branches.keys()) | set(chapter_counts.keys())

    for branch_id in all_branch_ids:
        if chapter_counts.get(branch_id, 0) == 0:
            continue

        branch_info = base_branches.get(branch_id, {"id": branch_id, "teams": [], "active_teams": []})
        all_team_names = teams_by_branch.get(branch_id, set())

        formatted_branches[branch_id] = {
            "id": branch_id,
            "name": _format_branch_name(branch_id, branch_info),
            "chapter_count": chapter_counts.get(branch_id, 0),
            "team_names": sorted(list(all_team_names)),
        }

    return formatted_branches


def get_branch_info_for_display(branch_info: Dict[str, Any]) -> str:
    """Формирование строки для отображения информации о ветке перевода."""
    branch_name = branch_info["name"]
    chapter_count = branch_info["chapter_count"]
    team_names = branch_info["team_names"]

    result = branch_name

    if team_names:
        name_parts = {part.strip() for part in branch_name.split(",")}
        if set(team_names) - name_parts:
            result += f" [{', '.join(team_names)}]"

    result += f" ({chapter_count} глав)"
    return result


def get_unique_chapters_count(chapters_data: List[Dict[str, Any]]) -> int:
    """Подсчет количества уникальных глав (по номеру и тому)."""
    return len({(c.get("volume", "0"), c.get("number", "0")) for c in chapters_data})


def get_default_branch_chapters(
    chapters_data: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Выбирает набор глав по умолчанию, по одному переводу на главу."""
    sorted_chapters_list = sorted(chapters_data, key=lambda x: x.get("index", 0))
    sorted_chapters_list.sort(key=lambda x: _parse_chapter_number_for_sort(x.get("number", "0")))

    chapter_branch_map = defaultdict(dict)
    unique_chapter_keys = []
    seen_keys = set()

    for chapter in sorted_chapters_list:
        key = (str(chapter.get("volume", "0")), str(chapter.get("number", "0")))
        if key not in seen_keys:
            unique_chapter_keys.append(key)
            seen_keys.add(key)

        for branch in chapter.get("branches", []):
            branch_id_str = "0"
            if isinstance(branch, dict):
                branch_id_val = branch.get("branch_id")
                branch_id_str = str(branch_id_val if branch_id_val is not None else "0")
            elif branch is not None:
                branch_id_str = str(branch)

            if branch_id_str not in chapter_branch_map[key]:
                chapter_branch_map[key][branch_id_str] = {
                    "chapter": chapter,
                    "branch": branch,
                }

    selected_chapter_keys = set()
    final_list = []

    while len(selected_chapter_keys) < len(unique_chapter_keys):
        first_unselected_key = None
        prioritized_branch_id = None

        for key in unique_chapter_keys:
            if key not in selected_chapter_keys:
                available_branches = chapter_branch_map.get(key, {})
                if available_branches:
                    first_unselected_key = key
                    prioritized_branch_id = next(iter(available_branches))
                    break

        if not first_unselected_key or not prioritized_branch_id:
            break

        for key in unique_chapter_keys:
            if key not in selected_chapter_keys:
                available_branches = chapter_branch_map.get(key, {})
                if prioritized_branch_id in available_branches:
                    final_list.append(available_branches[prioritized_branch_id])
                    selected_chapter_keys.add(key)

    final_list.sort(key=lambda x: x["chapter"].get("index", 0))
    final_list.sort(key=lambda x: _parse_chapter_number_for_sort(x["chapter"].get("number", "0")))

    return final_list


def _get_base_branches_from_novel_info(novel_info: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Извлечение базовой информации о ветках и командах из данных о новелле."""
    branches = {}
    for team in novel_info.get("teams", []):
        details = team.get("details", {}) or {}
        branch_id_raw = details.get("branch_id")
        branch_id = str(branch_id_raw if branch_id_raw is not None else "0")

        if branch_id not in branches:
            branches[branch_id] = {"id": branch_id, "teams": [], "active_teams": []}

        team_info = {
            "id": team.get("id", 0),
            "name": team.get("name", "Неизвестный"),
            "is_active": details.get("is_active", False),
        }
        branches[branch_id]["teams"].append(team_info)
        if team_info["is_active"]:
            branches[branch_id]["active_teams"].append(team_info)

    if "0" not in branches:
        branches["0"] = {"id": "0", "teams": [], "active_teams": []}
    return branches


def _get_chapter_counts_by_branch(chapters_data: List[Dict[str, Any]]) -> Dict[str, int]:
    """Подсчет количества глав для каждой ветки."""
    counts = defaultdict(int)
    for chapter in chapters_data:
        for branch in chapter.get("branches", []):
            branch_id = "0"
            if isinstance(branch, dict):
                branch_id_raw = branch.get("branch_id")
                branch_id = str(branch_id_raw if branch_id_raw is not None else "0")
            elif branch is not None:
                branch_id = str(branch)
            counts[branch_id] += 1
    return counts


def _get_teams_by_branch(chapters_data: List[Dict[str, Any]]) -> Dict[str, Set[str]]:
    """Извлечение команд переводчиков из данных о главах и сопоставление их с ветками."""
    teams = defaultdict(set)
    for chapter in chapters_data:
        for branch in chapter.get("branches", []):
            if not isinstance(branch, dict):
                continue

            branch_id_raw = branch.get("branch_id")
            branch_id = str(branch_id_raw if branch_id_raw is not None else "0")
            teams_list = branch.get("teams", []) or []
            if teams_list:
                for team in teams_list:
                    teams[branch_id].add(team.get("name", "Неизвестный"))
            elif not teams_list:
                team_info = branch.get("team")
                if team_info and isinstance(team_info, dict) and team_info.get("name"):
                    teams[branch_id].add(team_info.get("name"))
                else:
                    teams[branch_id].add("Неизвестный")
    return teams


def _format_branch_name(branch_id: str, branch_info: Dict[str, Any]) -> str:
    """Формирование основного отображаемого имени для ветки."""
    if branch_info["active_teams"]:
        return ", ".join([team["name"] for team in branch_info["active_teams"]])

    if branch_info["teams"]:
        min_id_team = min(branch_info["teams"], key=lambda t: t.get("id", 0))
        return min_id_team["name"]

    return "Неизвестный"


def _parse_chapter_number_for_sort(number_str: str) -> tuple:
    """Преобразование строки номера главы в кортеж чисел для сортировки."""
    parts = re.split(r"[.\-_]", str(number_str))
    result = []
    for part in parts:
        try:
            result.append(int(part))
        except ValueError:
            result.append(part)
    return tuple(result) 