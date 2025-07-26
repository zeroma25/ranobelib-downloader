"""
Модуль для работы с API RanobeLIB
"""

import requests
import time
from typing import Optional, Dict, List, Any, Deque, Callable
from urllib.parse import urlparse
from collections import deque

REQUESTS_LIMIT = 90  # Максимальное количество запросов
REQUESTS_PERIOD = 60  # Временной период в секундах
REQUEST_TIMEOUT = 10  # 10 секунд
RETRY_DELAYS = [3, 3, 30, 30, 30]  # секунды

class RanobeLibAPI:
    """Класс для работы с API RanobeLIB"""
    
    def __init__(self):
        self.api_url = "https://api.cdnlibs.org/api/manga/"
        self.site_url = "https://ranobelib.me"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.request_timestamps: Deque[float] = deque()
        self.token_refresh_callback: Optional[Callable[[], bool]] = None
    
    def set_token_refresh_callback(self, callback: Callable[[], bool]):
        """Установка функции-обработчика для обновления токена."""
        self.token_refresh_callback = callback

    def set_token(self, token: str) -> None:
        """Установка токена для авторизованных запросов."""
        token = token.strip()
        if token:
            # Дополняем заголовки токеном и обязательными полями
            self.session.headers["Authorization"] = f"Bearer {token}"
            self.session.headers.setdefault("Origin", self.site_url)
            self.session.headers.setdefault("Referer", f"{self.site_url}/")
    
    def clear_token(self) -> None:
        """Очистка токена из заголовков сессии."""
        if "Authorization" in self.session.headers:
            del self.session.headers["Authorization"]
    
    def make_request(self, url: str, params: Optional[Dict[str, Any]] = None, retry: bool = True, upcoming_requests: int = 0) -> Dict[str, Any]:
        """Выполнение запроса к API с контролем частоты, обработкой ошибок и повторными попытками."""
        self._wait_for_rate_limit(upcoming_requests=upcoming_requests)

        if not retry:
            try:
                return self._perform_request(url, params)
            except requests.exceptions.RequestException:
                return {}

        return self._retry_request(self._perform_request, url, params)
    
    def extract_slug_from_url(self, url: str) -> Optional[str]:
        """Извлечение slug из URL новеллы."""
        parsed_url = urlparse(url)
        path_parts = parsed_url.path.strip('/').split('/')
        
        if len(path_parts) >= 3 and path_parts[0] == "ru" and path_parts[1] == "book":
            return path_parts[2]
        return None
    
    def get_novel_info(self, slug: str) -> Dict[str, Any]:
        """Получение информации о новелле."""
        fields = [
            "summary", "genres", "tags", "teams", "authors", 
            "status_id", "artists", "format", "publisher"
        ]
        
        url_params = "&".join([f"fields[]={field}" for field in fields])
        url = f"{self.api_url}{slug}?{url_params}"
        
        data = self.make_request(url)
        return data.get("data", {})
    
    def get_novel_chapters(self, slug: str) -> List[Dict[str, Any]]:
        """Получение списка глав новеллы."""
        url = f"{self.api_url}{slug}/chapters"
        data = self.make_request(url)
        return data.get("data", [])
    
    def get_chapter_content(self, slug: str, volume: str, number: str, branch_id: Optional[str] = None, upcoming_requests: int = 0) -> Dict[str, Any]:
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
        
    def _wait_for_rate_limit(self, upcoming_requests: int = 0) -> None:
        """Динамическая задержка для соблюдения лимита и равномерного распределения запросов."""
        current_time = time.time()
        # Очищаем устаревшие временные метки
        while self.request_timestamps and current_time - self.request_timestamps[0] > REQUESTS_PERIOD:
            self.request_timestamps.popleft()

        # Если общее количество запросов (текущие + предстоящие + 1) не превышает лимит, то пропускаем задержку
        if len(self.request_timestamps) + upcoming_requests + 1 <= REQUESTS_LIMIT:
            self.request_timestamps.append(time.time())
            return

        while True:
            current_time = time.time()

            # Очищаем устаревшие временные метки
            while self.request_timestamps and current_time - self.request_timestamps[0] > REQUESTS_PERIOD:
                self.request_timestamps.popleft()

            # Проверяем лимит запросов
            if len(self.request_timestamps) >= REQUESTS_LIMIT:
                wait_duration = (self.request_timestamps[0] + REQUESTS_PERIOD) - current_time
                if wait_duration > 0:
                    time.sleep(wait_duration)
                continue  # Перепроверяем состояние после ожидания

            # Плавающая задержка для равномерного распределения
            if self.request_timestamps:
                time_until_period_end = REQUESTS_PERIOD - (current_time - self.request_timestamps[0])
                remaining_requests = max(1, REQUESTS_LIMIT - len(self.request_timestamps))
                average_spacing = time_until_period_end / remaining_requests
                
                # Замеряем время выполнения кода до этой точки, чтобы учесть его в задержке
                time_before_sleep = time.time()
                elapsed_since_loop_start = time_before_sleep - current_time
                
                # Новая логика задержки для компенсации неточностей
                sleep_duration = average_spacing - elapsed_since_loop_start
                if sleep_duration > 0:
                    time.sleep(sleep_duration)

            break  # Можно выполнять запрос

        # Регистрируем временную метку текущего запроса
        self.request_timestamps.append(time.time())
    
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
                
                time.sleep(delay)
        
        return {}

    def _perform_request(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Непосредственное выполнение запроса и обработка ответа."""
        try:
            response = self.session.get(
                url, params=params, timeout=REQUEST_TIMEOUT
            )
            
            if response.status_code == 401 and self.token_refresh_callback:
                print("\n🔑 Токен недействителен. Попытка обновления...")
                if self.token_refresh_callback():
                    print("✅ Токен обновлен. Повторяем запрос...")
                    response = self.session.get(
                        url, params=params, timeout=REQUEST_TIMEOUT
                    )
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