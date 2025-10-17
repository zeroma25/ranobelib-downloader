"""
Модуль для работы с API RanobeLIB
"""

import threading
import time
from collections import deque
from typing import Any, Callable, Deque, Dict, List, Optional
from urllib.parse import urlparse

import requests

REQUESTS_LIMIT = 90
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
        self.request_timestamps: Deque[float] = deque()
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
        upcoming_requests: int = 0,
    ) -> Dict[str, Any]:
        """Выполнение запроса к API с контролем частоты, обработкой ошибок и повторными попытками."""
        self.cancellation_event.clear()
        self.wait_for_rate_limit(upcoming_requests=upcoming_requests)

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

            if not is_on_moderation:
                filtered_chapters.append(chapter)

        return filtered_chapters

    def get_chapter_content(
        self,
        slug: str,
        volume: str,
        number: str,
        branch_id: Optional[str] = None,
        upcoming_requests: int = 0,
    ) -> Dict[str, Any]:
        """Получение содержимого главы."""
        url = f"{self.api_url}{slug}/chapter"
        params = {"volume": volume, "number": number}
        if branch_id:
            params["branch_id"] = branch_id

        data = self.make_request(url, params=params, upcoming_requests=upcoming_requests)
        return data.get("data", {})

    def get_current_user(self) -> Dict[str, Any]:
        """Получение информации о текущем пользователе."""
        url = "https://api.cdnlibs.org/api/auth/me"
        data = self.make_request(url, retry=False)
        return data.get("data", {})

    def wait_for_rate_limit(self, upcoming_requests: int = 0) -> None:
        """Динамическая задержка для соблюдения лимита и равномерного распределения запросов."""
        current_time = time.monotonic()

        while self.request_timestamps and self.request_timestamps[0] < current_time - REQUESTS_PERIOD:
            self.request_timestamps.popleft()

        requests_in_period = len(self.request_timestamps)

        if requests_in_period + upcoming_requests + 1 <= REQUESTS_LIMIT:
            self.request_timestamps.append(time.monotonic())
            return

        if requests_in_period >= REQUESTS_LIMIT:
            wait_for_slot = self.request_timestamps[0] - (current_time - REQUESTS_PERIOD)
            if wait_for_slot > 0:
                self._interruptible_sleep(wait_for_slot)

            current_time = time.monotonic()
            while self.request_timestamps and self.request_timestamps[0] < current_time - REQUESTS_PERIOD:
                self.request_timestamps.popleft()
            requests_in_period = len(self.request_timestamps)

        if self.request_timestamps:
            interval = REQUESTS_PERIOD / REQUESTS_LIMIT
            next_allowed_time = self.request_timestamps[-1] + interval
            wait_time = next_allowed_time - current_time
            if wait_time > 0:
                self._interruptible_sleep(wait_time)

        self.request_timestamps.append(time.monotonic())

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