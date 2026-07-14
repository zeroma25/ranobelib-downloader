"""
Модуль для обработки и подготовки контента новеллы
"""

import os
import re
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup, Tag

from .api import RanobeLibAPI
from .cache import ChapterCache
from .img import ImageHandler
from .parser import RanobeLibParser
from .settings import USER_DATA_DIR, settings


class ContentProcessor:
    """Класс для получения, обработки и подготовки контента новеллы"""

    _global_cache: Dict[Tuple[Any, Optional[str]], List[Dict[str, Any]]] = {}

    def __init__(self, api: RanobeLibAPI, parser: RanobeLibParser, image_handler: ImageHandler):
        self.api = api
        self.parser = parser
        self.image_handler = image_handler
        self.cache = ChapterCache()
        self.override_image_folder = None
        self.update_settings()

    def update_settings(self):
        """Обновление настроек из модуля settings"""
        self.cache_chapters = settings.get("cache_chapters", True)
        self.download_cover_enabled = settings.get("download_cover")
        self.download_images_enabled = settings.get("download_images")
        self.group_by_volumes = settings.get("group_by_volumes")
        self.add_translator = settings.get("add_translator")

    def prepare_chapters(
        self,
        novel_info: Dict[str, Any],
        chapters_data: List[Dict[str, Any]],
        selected_branch_id: Optional[str],
        image_folder: str,
    ) -> List[Dict[str, Any]]:
        """Получение списка подготовленных глав."""
        self.update_settings()

        cache_key = (novel_info.get("id"), selected_branch_id)
        if cache_key in self._global_cache:
            return self._global_cache[cache_key]

        print("🔄 Обработка глав...")
        filtered = self._filter_chapters(chapters_data, selected_branch_id)

        from tqdm import tqdm

        prepared: List[Dict[str, Any]] = []
        for i, ch_data in enumerate(tqdm(filtered, desc="⏱️ Загрузка глав", unit="ch", miniters=1, smoothing=0.1)):
            prepared.append(
                self._process_single_chapter(ch_data, novel_info, image_folder)
            )

        self._global_cache[cache_key] = prepared

        return prepared

    def extract_title_author_summary(self, novel_info: Dict[str, Any]) -> Tuple[str, str, str, List[str]]:
        """Получение метаданных из информации о новелле."""
        title_raw = (
            novel_info.get("rus_name")
            or novel_info.get("eng_name")
            or novel_info.get("name", "Без названия")
        )
        title_raw = self.parser.decode_html_entities(title_raw)
        title = re.sub(r"\s*\((?:Новелла|Novel)\)\s*$", "", title_raw, flags=re.IGNORECASE).strip()

        author = ""
        if novel_info.get("authors"):
            author = novel_info["authors"][0].get("name", "")

        summary = ""
        raw_summary = novel_info.get("summary")
        if raw_summary:
            if isinstance(raw_summary, dict):
                if raw_summary.get("type") == "doc" and raw_summary.get("content"):
                    raw_summary = self.parser.json_to_html(raw_summary["content"], [])
                else:
                    raw_summary = str(raw_summary)
            elif not isinstance(raw_summary, str):
                raw_summary = str(raw_summary)
            summary = self.parser.decode_html_entities(raw_summary.strip())

        genres: List[str] = []
        if novel_info.get("genres"):
            genres.extend([g.get("name") for g in novel_info["genres"]])
        if novel_info.get("tags"):
            genres.extend([g.get("name") for g in novel_info["tags"]])

        return title, author, summary, genres

    def extract_year(self, novel_info: Dict[str, Any]) -> str | None:
        """Попытка извлечения года публикации."""
        release_raw = novel_info.get("releaseDateString")
        if release_raw:
            m = re.search(r"\d{4}", str(release_raw))
            if m:
                return m.group(0)
        return None

    _volumes_count_cache: Dict[Any, int] = {}

    def get_total_volume_count(
        self,
        novel_info: Dict[str, Any],
        chapters_data: Optional[List[Dict[str, Any]]] = None,
    ) -> int:
        """Возвращает количество уникальных томов во всей новелле."""
        novel_id = novel_info.get("id")
        if novel_id in self._volumes_count_cache:
            return self._volumes_count_cache[novel_id]

        if not chapters_data:
            slug = novel_info.get("slug_url") or f"{novel_info.get('id')}--{novel_info.get('slug')}"
            try:
                chapters_data = self.api.get_novel_chapters(slug)
            except Exception:
                chapters_data = []

        volumes_set = {str(chapter.get("volume", "0")) for chapter in (chapters_data or [])}
        total_volumes = len(volumes_set)

        if total_volumes == 0:
            total_volumes = 1

        self._volumes_count_cache[novel_id] = total_volumes
        return total_volumes

    def prepare_dirs(self, novel_id: Any) -> Tuple[str, str]:
        """Подготовка каталога загрузок и временного каталога."""
        downloads_dir = settings.get("save_directory")
        os.makedirs(downloads_dir, exist_ok=True)
        
        if self.override_image_folder:
            return downloads_dir, self.override_image_folder
            
        temp_dir = os.path.join(USER_DATA_DIR, "cache")
        os.makedirs(temp_dir, exist_ok=True)
        if self.cache_chapters:
            image_folder = os.path.join(temp_dir, f"cache_images_{novel_id}")
        else:
            image_folder = os.path.join(temp_dir, f"temp_images_{novel_id}")
        return downloads_dir, image_folder

    def get_safe_filename(self, title: str, extension: str) -> str:
        """Создание безопасного имени файла и обеспечение его уникальности."""
        safe_title = re.sub(r'[\\/*?:"<>|]', "", title)
        downloads_dir = settings.get("save_directory")
        os.makedirs(downloads_dir, exist_ok=True)
        filename = os.path.join(downloads_dir, f"{safe_title}.{extension}")
        counter = 1
        while os.path.exists(filename):
            filename = os.path.join(downloads_dir, f"{safe_title} ({counter}).{extension}")
            counter += 1
        return filename

    def download_cover(self, novel_info: Dict[str, Any], image_folder: str) -> Optional[str]:
        """Скачивание обложки."""
        if not self.download_cover_enabled:
            return None

        cover_filename: Optional[str] = None
        if novel_info.get("cover") and novel_info["cover"].get("default"):
            cover_url = novel_info["cover"]["default"]
            cover_filename = self.image_handler.download_image(
                url=cover_url, folder=image_folder, filename="cover", deduplicate=True
            )
        return cover_filename

    def _process_html_images(self, html_content: str, image_folder: str, branch_id: str) -> str:
        """Обработка HTML-контента: скачивание изображений, обновление путей и обработка дубликатов."""
        soup = BeautifulSoup(html_content, "html.parser")
        for img in soup.find_all("img"):
            if not isinstance(img, Tag):
                continue

            if not self.download_images_enabled:
                img.decompose()
                continue

            img_src = img.get("src")
            if not isinstance(img_src, str) or not img_src.strip():
                img.decompose()
                continue

            final_filename = self.image_handler.download_image(
                url=img_src, folder=image_folder, deduplicate=True, filename_prefix=f"img_b{branch_id}"
            )

            if final_filename:
                img["src"] = f"images/{final_filename}"
                img.insert_before(soup.new_tag("br"))
                img.insert_after(soup.new_tag("br"))
            else:
                img.decompose()

        return str(soup)

    def _convert_br_to_paragraphs(self, html: str) -> str:
        """Замена разрывов строк <br> на абзацы <p>...</p>."""
        if not html:
            return ""

        normalized = re.sub(r"(?i)<br\s*/?>", "<br>", html)
        parts = re.split(r"(?:<br>\s*)+", normalized)

        output_parts: List[str] = []
        for part in parts:
            text = part.strip()
            if not text:
                continue

            text = re.sub(r"(?i)^<p[^>]*>", "", text)
            text = re.sub(r"(?i)</p>$", "", text)
            text = text.strip()

            if not text:
                continue

            output_parts.append(f"<p>{text}</p>")

        return "".join(output_parts)

    def _parse_chapter_number(self, number_str: str) -> tuple:
        """Преобразование строки номера главы в кортеж чисел для сортировки."""
        parts = re.split(r"[.\-_]", str(number_str))
        result = []
        for part in parts:
            try:
                result.append(int(part))
            except ValueError:
                result.append(part)
        return tuple(result)

    def _filter_chapters(
        self,
        chapters_data: List[Dict[str, Any]],
        selected_branch_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Фильтрация глав по выбранной ветке и их сортировка."""
        if selected_branch_id == "default":
            from .branches import get_default_branch_chapters

            filtered = get_default_branch_chapters(chapters_data)
            return filtered

        if selected_branch_id:
            filtered = []
            for chapter in chapters_data:
                for branch in chapter.get("branches", []):
                    branch_id_str = "0"
                    if isinstance(branch, dict):
                        branch_id_val = branch.get("branch_id")
                        branch_id_str = str(branch_id_val if branch_id_val is not None else "0")
                    elif branch is not None:
                        branch_id_str = str(branch)

                    if branch_id_str == selected_branch_id:
                        filtered.append({"chapter": chapter, "branch": branch})
        else:
            filtered = [
                {"chapter": chapter, "branch": branch}
                for chapter in chapters_data
                for branch in chapter.get("branches", [])
            ]

        filtered.sort(key=lambda x: x["chapter"].get("index", 0))
        filtered.sort(key=lambda x: self._parse_chapter_number(x["chapter"].get("number", "0")))
        return filtered

    def _fetch_chapter_html(
        self,
        novel_info: Dict[str, Any],
        volume: str,
        number: str,
        branch_id: str,
    ) -> str:
        """Получение HTML-контента главы (без обработки изображений)."""
        chapter_data = self.api.get_chapter_content(
            novel_info.get("slug_url") or f"{novel_info.get('id')}--{novel_info.get('slug')}",
            volume,
            number,
            branch_id if branch_id != "0" else None,
        )

        html = ""
        if chapter_data.get("content"):
            content = chapter_data["content"]
            if (
                isinstance(content, dict)
                and content.get("type") == "doc"
                and content.get("content")
            ):
                html = self.parser.json_to_html(
                    content["content"], chapter_data.get("attachments", [])
                )
            else:
                html = str(content)
        return html

    def _prepare_chapter_content(self, html: str, image_folder: str, branch_id: str) -> str:
        """Скачивание изображений, замена путей и перевод <br> в параграфы."""
        html_with_images = self._process_html_images(html, image_folder, branch_id)
        html_cleaned = self._cleanup_html_text(html_with_images)
        return self._convert_br_to_paragraphs(html_cleaned)

    def _process_single_chapter(
        self,
        ch_data: Dict[str, Any],
        novel_info: Dict[str, Any],
        image_folder: str,
    ) -> Dict[str, Any]:
        """Загрузка и обработка одной главы."""
        ch_info = ch_data["chapter"]
        branch = ch_data["branch"]

        volume = str(ch_info.get("volume", "0"))
        number = str(ch_info.get("number", "0"))
        branch_id = "0"
        if isinstance(branch, dict):
            branch_id_val = branch.get("branch_id")
            branch_id = str(branch_id_val if branch_id_val is not None else "0")
        elif branch is not None:
            branch_id = str(branch)

        novel_id = str(novel_info.get("id"))
        
        processed_html = None

        if self.cache_chapters:
            cached = self.cache.get_chapter(novel_id, branch_id, volume, number)
            if cached:
                html = cached.get("html", "")
                all_images_exist = True
                
                for match in re.finditer(r'<img[^>]*src=["\'](images/[^"\']+)["\']', html):
                    img_filename = os.path.basename(match.group(1))
                    img_path = os.path.join(image_folder, img_filename)
                    if not os.path.exists(img_path):
                        all_images_exist = False
                        print(f"⚠️ Изображение {img_filename} из кэша не найдено. Глава будет перекачана.")
                        break
                
                if all_images_exist:
                    processed_html = html
                else:
                    for match in re.finditer(r'<img[^>]*src=["\'](images/[^"\']+)["\']', html):
                        img_filename = os.path.basename(match.group(1))
                        img_path = os.path.join(image_folder, img_filename)
                        if os.path.exists(img_path):
                            try:
                                os.remove(img_path)
                            except OSError:
                                pass
                    
                    prefix = f"img_b{branch_id}"
                    if prefix in self.image_handler.image_counters:
                        del self.image_handler.image_counters[prefix]

        if processed_html is None:
            raw_html = self._fetch_chapter_html(novel_info, volume, number, branch_id)
            processed_html = self._prepare_chapter_content(raw_html, image_folder, branch_id)
            if self.cache_chapters:
                self.cache.save_chapter(
                    novel_id, branch_id, volume, number, ch_info.get("name"), processed_html
                )

        if self.add_translator and isinstance(branch, dict):
            translator_names = []

            teams = branch.get("teams")
            if teams and isinstance(teams, list):
                translator_names.extend([team.get("name") for team in teams if team.get("name")])

            team_info = branch.get("team")
            if not translator_names and team_info and isinstance(team_info, dict):
                team_name = team_info.get("name")
                if team_name:
                    translator_names.append(team_name)

            if not translator_names:
                translator_names.append("Неизвестный")

            translator_str = "Переводчик: " + ", ".join(filter(None, translator_names))
            soup = BeautifulSoup(processed_html, "html.parser")

            translator_tag = soup.new_tag("p")
            translator_tag.string = translator_str
            translator_tag.attrs["style"] = "font-weight: bold; font-style: italic; text-align: right;"

            soup.insert(0, translator_tag)
            processed_html = str(soup)

        result = {
            "volume": volume,
            "number": number,
            "name": ch_info.get("name"),
            "html": processed_html,
        }

        return result

    def _cleanup_html_text(self, html: str) -> str:
        """Очистка текста внутри HTML от лишних переносов строк, пробелов и тегов."""
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        for text_node in soup.find_all(text=True):
            if text_node.parent and text_node.parent.name in ["style", "script", "pre"]:
                continue

            current_text = str(text_node)
            new_text = re.sub(" +", " ", current_text.replace("\n", " "))

            if new_text != current_text:
                text_node.replace_with(new_text)  # type: ignore

        for p_tag in soup.find_all("p"):
            if isinstance(p_tag, Tag) and p_tag.has_attr("data-paragraph-index"):  # type: ignore[attr-defined]
                del p_tag["data-paragraph-index"]  # type: ignore[index]

        return str(soup) 