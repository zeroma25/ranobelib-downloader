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

from .api import RanobeLibAPI


class ImageHandler:
    """Класс для обработки изображений"""

    def __init__(self, api: RanobeLibAPI):
        self.api = api
        self.image_counter: int = 1
        self.hash_to_filename: dict[str, str] = {}

    def reset(self):
        """Сброс состояния обработчика для новой сессии скачивания."""
        self.image_counter = 1
        self.hash_to_filename = {}

    def download_image(
        self,
        url: str,
        folder: str,
        filename: Optional[str] = None,
        deduplicate: bool = False,
    ) -> Optional[str]:
        """Скачивание, обработка и сохранение изображения."""
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

        processed_path = self._convert_and_resize(temp_path)

        if deduplicate:
            file_hash = self._get_file_hash(processed_path)
            if file_hash and file_hash in self.hash_to_filename:
                if os.path.exists(processed_path):
                    os.remove(processed_path)
                return self.hash_to_filename[file_hash]

        if filename:
            _, ext = os.path.splitext(processed_path)
            final_name = f"{filename}{ext}"
        else:
            _, ext = os.path.splitext(processed_path)
            final_name = f"img_{self.image_counter}{ext}"
            self.image_counter += 1

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

        return final_name

    def _fetch_image(self, url: str) -> Tuple[bytes, Optional[str]]:
        """Скачивание содержимого изображения и его Content-Type."""
        if url.startswith("/"):
            url = self.api.site_url.rstrip("/") + url

        try:
            site_netloc = urlparse(self.api.site_url).netloc
            target_netloc = urlparse(url).netloc
            if site_netloc and target_netloc and target_netloc == site_netloc:
                self.api.wait_for_rate_limit()
        except Exception:
            pass

        response = self.api.session.get(url, timeout=10)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
        return response.content, content_type

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

    def _convert_and_resize(self, filepath: str) -> str:
        """Конвертация webp/bmp в jpg и изменение размера больших изображений."""
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

        try:
            with Image.open(filepath) as img:
                width, height = img.size
                if width > 800 or height > 800:
                    ratio = min(800 / width, 800 / height)
                    new_size = (int(width * ratio), int(height * ratio))
                    resample_filter = getattr(Image, "LANCZOS", getattr(Image, "ANTIALIAS", 0))
                    resized_img = img.resize(new_size, resample_filter)
                    resized_img.save(filepath, quality=90)
        except Exception as e:
            print(f"\n⚠️ Не удалось изменить размер изображения {filepath}: {e}")

        return filepath

    def _get_file_hash(self, filepath: str) -> Optional[str]:
        """Вычисление MD5-хэша содержимого файла."""
        try:
            with open(filepath, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()
        except OSError as e:
            print(f"\n⚠️ Не удалось вычислить хэш изображения {filepath}: {e}")
            return None 