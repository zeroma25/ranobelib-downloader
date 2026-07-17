"""
Модуль для работы с изображениями RanobeLIB
"""

import hashlib
import os
import secrets
from typing import Optional, Tuple

import requests
from PIL import Image
from urllib.parse import urlparse

from .api import RanobeLibAPI, OperationCancelledError
from .settings import settings


class ImageHandler:
    """Класс для обработки изображений"""

    def __init__(self, api: RanobeLibAPI):
        self.api = api
        self.image_counters: dict[str, int] = {}
        self.hash_to_filename: dict[str, str] = {}
        self.size_to_filenames: dict[int, list[str]] = {}
        self.populated_folders: set[str] = set()

    def reset(self):
        """Сброс состояния обработчика для новой сессии скачивания."""
        self.image_counters = {}
        self.hash_to_filename = {}
        self.size_to_filenames = {}
        self.populated_folders = set()

    def populate_hash_cache(self, folder: str):
        """Заполняет кэш хэшей уже существующими файлами из папки для дедупликации между сессиями."""
        if not hasattr(self, "populated_folders"):
            self.populated_folders = set()
        if not hasattr(self, "size_to_filenames"):
            self.size_to_filenames = {}
            
        if folder in self.populated_folders:
            return
            
        self.populated_folders.add(folder)
        
        if not os.path.exists(folder):
            return
        
        size_to_files: dict[int, list[str]] = {}
        for filename in os.listdir(folder):
            if filename.startswith("temp_") or not os.path.isfile(os.path.join(folder, filename)):
                continue
            filepath = os.path.join(folder, filename)
            try:
                size = os.path.getsize(filepath)
                if size not in size_to_files:
                    size_to_files[size] = []
                size_to_files[size].append(filename)
            except OSError:
                pass
                
        for size, filenames in size_to_files.items():
            if size not in self.size_to_filenames:
                self.size_to_filenames[size] = []
            self.size_to_filenames[size].extend(filenames)

        for size, filenames in size_to_files.items():
            if len(filenames) > 1:
                for filename in filenames:
                    filepath = os.path.join(folder, filename)
                    file_hash = self._get_file_hash(filepath)
                    if file_hash and file_hash not in self.hash_to_filename:
                        self.hash_to_filename[file_hash] = filename

    def download_image(
        self,
        url: str,
        folder: str,
        filename: Optional[str] = None,
        deduplicate: bool = False,
        filename_prefix: str = "img",
    ) -> Optional[str]:
        """Скачивание, обработка и сохранение изображения."""
        if deduplicate:
            self.populate_hash_cache(folder)
            
        os.makedirs(folder, exist_ok=True)

        try:
            content, content_type = self._fetch_image(url)
        except requests.exceptions.RequestException as e:
            print(f"\n⚠️ Ошибка при скачивании изображения {url}: {e}")
            return None

        ext = self._get_extension_from_content_type(content_type)
        temp_name = f"temp_{secrets.token_hex(8)}{ext}"
        temp_path = os.path.join(folder, temp_name)

        with open(temp_path, "wb") as f:
            f.write(content)

        processed_path = self._convert_image(temp_path)

        if settings.get("compress_images") and not settings.get("cache_chapters", True):
            self._compress_image(processed_path, processed_path)

        if deduplicate:
            try:
                processed_size = os.path.getsize(processed_path)
            except OSError:
                processed_size = -1
                
            if processed_size > 0 and processed_size in self.size_to_filenames:
                for existing_filename in self.size_to_filenames[processed_size]:
                    if existing_filename not in self.hash_to_filename.values():
                        existing_path = os.path.join(folder, existing_filename)
                        if os.path.exists(existing_path):
                            ex_hash = self._get_file_hash(existing_path)
                            if ex_hash and ex_hash not in self.hash_to_filename:
                                self.hash_to_filename[ex_hash] = existing_filename

            file_hash = self._get_file_hash(processed_path)
            if file_hash and file_hash in self.hash_to_filename:
                target_filename = self.hash_to_filename[file_hash]
                target_path = os.path.join(folder, target_filename)
                if os.path.exists(target_path):
                    if os.path.exists(processed_path):
                        os.remove(processed_path)
                    return target_filename
                else:
                    del self.hash_to_filename[file_hash]

        if filename:
            _, ext = os.path.splitext(processed_path)
            final_name = f"{filename}{ext}"
        else:
            _, ext = os.path.splitext(processed_path)
            counter = self.image_counters.get(filename_prefix, 1)
            while True:
                exists = any(
                    os.path.exists(os.path.join(folder, f"{filename_prefix}_{counter}{e}"))
                    for e in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"]
                )
                if not exists:
                    final_name = f"{filename_prefix}_{counter}{ext}"
                    break
                counter += 1
            self.image_counters[filename_prefix] = counter + 1

        final_path = os.path.join(folder, final_name)
        if os.path.exists(processed_path) and processed_path != final_path:
            try:
                os.replace(processed_path, final_path)
            except OSError as e:
                print(f"\n⚠️ Не удалось заменить изображение {processed_path} -> {final_path}: {e}")
                if os.path.exists(processed_path):
                    try:
                        os.remove(processed_path)
                    except OSError:
                        pass
                return None

        if deduplicate and "file_hash" in locals() and file_hash:
            self.hash_to_filename[file_hash] = final_name
            if "processed_size" in locals() and processed_size > 0:
                if processed_size not in self.size_to_filenames:
                    self.size_to_filenames[processed_size] = []
                if final_name not in self.size_to_filenames[processed_size]:
                    self.size_to_filenames[processed_size].append(final_name)

        return final_name

    def _fetch_image(self, url: str) -> Tuple[bytes, Optional[str]]:
        """Скачивание содержимого изображения и его Content-Type с повторными попытками."""
        def fetch():
            full_url = self.api.site_url.rstrip("/") + url if url.startswith("/") else url

            try:
                site_netloc = urlparse(self.api.site_url).netloc
                target_netloc = urlparse(full_url).netloc
                if site_netloc and target_netloc and target_netloc == site_netloc:
                    self.api.wait_for_rate_limit()
            except Exception:
                pass

            if self.api.cancellation_event.is_set():
                raise OperationCancelledError

            response = self.api.session.get(full_url, timeout=10)
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
            return response.content, content_type
            
        return self.api._retry_request(fetch)

    def _get_extension_from_content_type(self, content_type: Optional[str]) -> str:
        """Определение расширения файла на основе MIME-типа."""
        ext_map = {
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/png": ".png",
            "image/gif": ".gif",
            "image/webp": ".webp",
            "image/bmp": ".bmp",
            "image/svg+xml": ".svg",
        }
        if content_type is None:
            return ".jpg"
        return ext_map.get(content_type, ".jpg")

    def _convert_image(self, filepath: str) -> str:
        """Конвертация webp/bmp в jpg."""
        filename, ext = os.path.splitext(os.path.basename(filepath))
        if ext.lower() in [".webp", ".bmp"]:
            try:
                with Image.open(filepath) as img:
                    rgb_img = img.convert("RGB")
                    new_filepath = os.path.join(os.path.dirname(filepath), f"{filename}.jpg")
                    rgb_img.save(new_filepath, format="JPEG", quality=90)
                if os.path.exists(filepath):
                    os.remove(filepath)
                filepath = new_filepath
            except Exception as e:
                print(f"\n⚠️ Не удалось конвертировать {filepath} в JPG: {e}")

        return filepath

    def _compress_image(self, src_path: str, dst_path: str) -> None:
        """Универсальная функция сжатия одного изображения."""
        import shutil
        in_place = os.path.abspath(src_path) == os.path.abspath(dst_path)

        try:
            with Image.open(src_path) as img:
                width, height = img.size
                img_format = img.format or "JPEG"
                if width > 800 or height > 800:
                    ratio = min(800 / width, 800 / height)
                    new_size = (int(width * ratio), int(height * ratio))
                    resample_filter = getattr(Image, "LANCZOS", getattr(Image, "ANTIALIAS", 0))
                    resized_img = img.resize(new_size, resample_filter)
                    resized_img.save(dst_path, format=img_format, quality=90)
                else:
                    if not in_place:
                        shutil.copy2(src_path, dst_path)

        except Exception as e:
            print(f"\n⚠️ Не удалось изменить размер изображения {src_path}: {e}")
            if not in_place:
                shutil.copy2(src_path, dst_path)

    def compress_folder(self, source_folder: str, target_folder: str) -> None:
        """Сжатие всех изображений из исходной папки в целевую."""
        os.makedirs(target_folder, exist_ok=True)
        if not os.path.exists(source_folder):
            return

        for filename in os.listdir(source_folder):
            src_path = os.path.join(source_folder, filename)
            dst_path = os.path.join(target_folder, filename)
            if not os.path.isfile(src_path):
                continue
            self._compress_image(src_path, dst_path)

    def _get_file_hash(self, filepath: str) -> Optional[str]:
        """Вычисление MD5-хэша содержимого файла."""
        try:
            hash_md5 = hashlib.md5()
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except OSError as e:
            print(f"\n⚠️ Не удалось вычислить хэш изображения {filepath}: {e}")
            return None 