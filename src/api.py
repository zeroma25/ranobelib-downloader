"""
Модуль для работы с API RanobeLIB
"""

import threading
import time
from collections import deque
from typing import Any, Callable, Deque, Dict, List, Optional
from urllib.parse import urlparse

import requests

DEFAULT_REQUESTS_LIMIT = 90
REQUESTS_PERIOD = 60
REQUEST_TIMEOUT = 10
RETRY_DELAYS = [3, 3, 30, 30, 30]


class OperationCancelledError(Exception):
    """Исключение, выбрасываемое при отмене операции."""


class RanobeLibAPI:
    """Класс для работы с API RanobeLIB"""

    def __init__(self):
        self.api_url = "https://api.cdnlibs.org/api/manga/"
        self.site_url = "https://ranobelib.me"
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Origin": self.site_url,
                "Referer": f"{self.site_url}/",
                "Site-Id": "3",
            }
        )
        self.rate_limit = DEFAULT_REQUESTS_LIMIT
        self.rate_remaining = DEFAULT_REQUESTS_LIMIT
        self.window_start_time = time.monotonic()
        self.token_refresh_callback: Optional[Callable[[], bool]] = None
        self.cancellation_event = threading.Event()

    def cancel_pending_requests(self):
        """Установка флага отмены для ожидающих запросов."""
        self.cancellation_event.set()

    def set_token_refresh_callback(self, callback: Callable[[], bool]):
        """Установка функции-обработчика для обновления токена."""
        self.token_refresh_callback = callback

    def set_token(self, token: str) -> None:
        """Установка токена для авторизованных запросов."""
        token = token.strip()
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

    def clear_token(self) -> None:
        """Очистка токена из заголовков сессии."""
        if "Authorization" in self.session.headers:
            del self.session.headers["Authorization"]

    def make_request(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        retry: bool = True,
    ) -> Dict[str, Any]:
        """Выполнение запроса к API с контролем частоты, обработкой ошибок и повторными попытками."""
        if self.cancellation_event.is_set():
            raise OperationCancelledError("Операция отменена")
            
        self.wait_for_rate_limit()
        
        if self.cancellation_event.is_set():
            raise OperationCancelledError("Операция отменена")

        if not retry:
            try:
                return self._perform_request(url, params)
            except requests.exceptions.RequestException:
                return {}

        return self._retry_request(self._perform_request, url, params)

    def extract_slug_from_url(self, url: str) -> Optional[str]:
        """Извлечение slug из URL новеллы."""
        parsed_url = urlparse(url)
        path_parts = parsed_url.path.strip("/").split("/")

        if len(path_parts) >= 3 and path_parts[0] == "ru" and path_parts[1] == "book":
            return path_parts[2]
        return None

    def get_novel_info(self, slug: str) -> Dict[str, Any]:
        """Получение информации о новелле."""
        fields = [
            "summary",
            "genres",
            "tags",
            "teams",
            "authors",
            "status_id",
            "artists",
            "format",
            "publisher",
        ]

        url_params = "&".join([f"fields[]={field}" for field in fields])
        url = f"{self.api_url}{slug}?{url_params}"

        data = self.make_request(url)
        return data.get("data", {})

    def get_novel_chapters(self, slug: str) -> List[Dict[str, Any]]:
        """Получение списка глав новеллы."""
        url = f"{self.api_url}{slug}/chapters"
        data = self.make_request(url)

        chapters: List[Dict[str, Any]] = data.get("data", [])

        filtered_chapters: List[Dict[str, Any]] = []
        for chapter in chapters:
            branches = chapter.get("branches", [])
            is_on_moderation = any(
                isinstance(branch, dict)
                and branch.get("moderation", {}).get("id") == 0
                for branch in branches
            )

            if is_on_moderation:
                continue
                
            valid_branches = []
            for branch in branches:
                if isinstance(branch, dict):
                    restricted = branch.get("restricted_view")
                    if restricted and restricted.get("is_open") is False:
                        continue
                valid_branches.append(branch)

            if valid_branches:
                chapter["branches"] = valid_branches
                filtered_chapters.append(chapter)

        return filtered_chapters

    def get_chapter_content(
        self,
        slug: str,
        volume: str,
        number: str,
        branch_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Получение содержимого главы."""
        url = f"{self.api_url}{slug}/chapter"
        params = {"volume": volume, "number": number}
        if branch_id:
            params["branch_id"] = branch_id

        data = self.make_request(url, params=params)
        return data.get("data", {})

    def get_current_user(self) -> Dict[str, Any]:
        """Получение информации о текущем пользователе."""
        url = "https://api.cdnlibs.org/api/auth/me"
        data = self.make_request(url, retry=False)
        return data.get("data", {})

    def wait_for_rate_limit(self) -> None:
        """Динамическая задержка на основе реальных заголовков сервера."""
        if self.rate_remaining <= 2:
            elapsed = time.monotonic() - self.window_start_time
            wait_time = REQUESTS_PERIOD - elapsed
            if wait_time > 0:
                self._interruptible_sleep(wait_time)
            self.window_start_time = time.monotonic()
            
        elif self.rate_remaining <= 10:
            elapsed = time.monotonic() - self.window_start_time
            remaining_time = REQUESTS_PERIOD - elapsed
            if remaining_time > 0:
                delay = remaining_time / self.rate_remaining
                self._interruptible_sleep(delay)

    def _interruptible_sleep(self, duration: float):
        """Приостанавливает выполнение на заданное время, но может быть прервано событием отмены."""
        if duration <= 0:
            return

        end_time = time.monotonic() + duration
        while time.monotonic() < end_time:
            if self.cancellation_event.wait(timeout=0.1):
                raise OperationCancelledError("Операция отменена")

    def _retry_request(self, func: Callable, *args, **kwargs) -> Dict[str, Any]:
        """Выполнение функции с повторными попытками."""
        for i, delay in enumerate(RETRY_DELAYS):
            try:
                return func(*args, **kwargs)
            except requests.exceptions.RequestException as e:
                is_last_attempt = i == len(RETRY_DELAYS) - 1
                is_long_delay = delay >= 30

                if is_long_delay:
                    print(f"\n⚠️ Ошибка соединения: {e}. Следующая попытка через {delay} секунд...")

                if is_last_attempt:
                    print(f"❌ Соединение не установлено: {e}. Проверьте подключение к сети или попробуйте позже.")
                    raise

                self._interruptible_sleep(delay)

        return {}

    def _perform_request(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Непосредственное выполнение запроса и обработка ответа."""
        try:
            response = self.session.get(url, params=params, timeout=REQUEST_TIMEOUT)

            limit_header = response.headers.get("X-RateLimit-Limit")
            if limit_header and limit_header.isdigit():
                self.rate_limit = int(limit_header)

            remaining_header = response.headers.get("X-RateLimit-Remaining")
            if remaining_header and remaining_header.isdigit():
                new_remaining = int(remaining_header)
                if new_remaining > self.rate_remaining:
                    self.window_start_time = time.monotonic()
                self.rate_remaining = new_remaining

            if response.status_code == 401 and self.token_refresh_callback:
                print("\n🔑 Токен недействителен. Попытка обновления...")
                if self.token_refresh_callback():
                    print("✅ Токен обновлен. Повторяем запрос...")
                    response = self.session.get(url, params=params, timeout=REQUEST_TIMEOUT)
                else:
                    print("⚠️ Не удалось обновить токен.")

            if response.status_code == 404:
                try:
                    return response.json()
                except requests.exceptions.JSONDecodeError:
                    return {}

            response.raise_for_status()
            return response.json()
        except requests.exceptions.JSONDecodeError:
            print(f"⚠️ Ошибка декодирования JSON ответа для URL: {url}")
            raise 