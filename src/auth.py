"""
Модуль для аутентификации в API RanobeLIB
"""

import os
import time
import base64
import hashlib
import json
import secrets
import threading
import requests
import webview
from urllib.parse import urlparse, parse_qs
from typing import Optional, Dict, Any

from .api import RanobeLibAPI
from .settings import USER_DATA_DIR

class RanobeLibAuth:
    """Класс для работы с аутентификацией в API RanobeLIB"""
    
    def __init__(self, api: RanobeLibAPI):
        self.api = api
        self.token_path = os.path.join(USER_DATA_DIR, "auth.json")
    
    def get_auth_code_via_webview(self) -> Optional[Dict[str, str]]:
        """Открытие окна webview для получения кода авторизации. Возвращает словарь с кодом и секретом."""
        secret = self._generate_random_string(128)
        state = self._generate_random_string(40)
        redirect_uri = f"{self.api.site_url}/ru/front/auth/oauth/callback"
        challenge = self._code_challenge(secret)

        challenge_url = (
            "https://auth.lib.social/auth/oauth/authorize?scope=&client_id=1&response_type=code"
            f"&redirect_uri={redirect_uri}&state={state}&code_challenge={challenge}"
            "&code_challenge_method=S256&prompt=consent"
        )
        
        # Этот метод теперь должен вызываться в основном потоке
        auth_code = self._get_authorization_code(challenge_url, redirect_uri)
        if not auth_code:
            return None
        
        return {"code": auth_code, "secret": secret, "redirect_uri": redirect_uri}

    def finish_authorization(self, auth_data: Dict[str, str]) -> Optional[str]:
        """Завершает процесс авторизации, обменивая код на токен."""
        code = auth_data.get("code")
        secret = auth_data.get("secret")
        redirect_uri = auth_data.get("redirect_uri")
        
        if not all([code, secret, redirect_uri]):
             raise ValueError("Отсутствуют необходимые данные для завершения авторизации.")

        token_data = self._exchange_code_for_token(code, secret, redirect_uri)  # type: ignore
        if token_data and "access_token" in token_data:
            self.api.set_token(token_data["access_token"])
            self.save_token(token_data)
            print("✅ Токен успешно получен")
            return token_data["access_token"]
        else:
            print("⚠️ Ответ не содержит access_token")
            return None
    
    def authorize_with_webview(self) -> Optional[str]:
        """Открытие окна авторизации и автоматическое получение токена после входа пользователя."""
        auth_data = self.get_auth_code_via_webview()
        if not auth_data:
            return None
        return self.finish_authorization(auth_data)

    def save_token(self, token_data: Dict[str, Any]) -> None:
        """Сохранение данных аутентификации в файл."""
        try:
            with open(self.token_path, 'w', encoding='utf-8') as f:
                json.dump(token_data, f, indent=2)
        except OSError as e:
            print(f"⚠️ Не удалось сохранить токен в файл: {e}")

    def logout(self) -> None:
        """Выход из системы: удаление токена и очистка данных."""
        self.api.clear_token()
        if os.path.exists(self.token_path):
            try:
                os.remove(self.token_path)
                print("🗑️ Файл токена удален.")
            except OSError as e:
                print(f"⚠️ Не удалось удалить файл токена: {e}")

    def load_token(self) -> Optional[Dict[str, Any]]:
        """Загрузка сохранённых данных аутентификации, если они существуют."""
        if os.path.exists(self.token_path):
            try:
                with open(self.token_path, 'r', encoding='utf-8') as f:
                    token_data = json.load(f)
                    return token_data
            except (OSError, json.JSONDecodeError) as e:
                print(f"⚠️ Не удалось загрузить сохранённый токен: {e}")
        return None

    def refresh_token(self) -> bool:
        """Обновление access-токена с помощью refresh-токена."""
        token_data = self.load_token()
        if not token_data or "refresh_token" not in token_data:
            return False

        refresh_token_str = token_data["refresh_token"]
        
        print("🔄 Обновление токена...")
        token_url = "https://api.cdnlibs.org/api/auth/oauth/token"
        payload = {
            "grant_type": "refresh_token",
            "client_id": 1,
            "refresh_token": refresh_token_str,
        }
        headers = dict(self.api.session.headers)
        headers.setdefault("Origin", self.api.site_url)
        headers.setdefault("Referer", f"{self.api.site_url}/")

        try:
            response = self.api.session.post(token_url, json=payload, headers=headers, timeout=10)

            # Если токен обновления недействителен, сервер вернет 400
            if response.status_code == 400:
                print("⚠️ Refresh-токен недействителен. Требуется повторная авторизация.")
                return False
                
            response.raise_for_status()
            new_token_data = response.json()

            if "access_token" in new_token_data:
                print("✅ Токен успешно обновлён")
                self.api.set_token(new_token_data["access_token"])
                # Сохраняем обновленные данные, включая, возможно, новый refresh_token
                self.save_token(new_token_data)
                return True
            else:
                print("⚠️ Ответ при обновлении токена не содержит access_token")
                return False
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Не удалось обновить токен: {e}")
            return False

    def validate_token(self) -> Optional[Dict[str, Any]]:
        """Проверка действительности токена. Возвращает данные пользователя в случае успеха."""
        user_data = self.api.get_current_user()

        if isinstance(user_data, dict) and "id" in user_data:
            return user_data
        return None
    
    def _generate_random_string(self, length: int) -> str:
        """Генерация случайной строки из буквенно-цифрового алфавита."""
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    def _code_challenge(self, verifier: str) -> str:
        """Вычисление code_challenge в соответствии с PKCE (SHA256 + Base64url, без =)"""
        digest = hashlib.sha256(verifier.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")

    def _get_authorization_code(self, challenge_url: str, redirect_uri: str) -> Optional[str]:
        """Открытие webview для получения кода авторизации."""
        print("🔐 Открываем окно авторизации...")

        auth_code_container: Dict[str, Optional[str]] = {"code": None}
        window_ready = threading.Event()

        def on_loaded():
            """Сигнализирование, что окно готово к работе."""
            window_ready.set()

        def _watch_redirect():
            """Отслеживание URL в webview и извлечение кода авторизации."""
            window_ready.wait()  # Ждём, пока окно не будет полностью загружено

            while not auth_code_container["code"]:
                try:
                    current_url = window.get_current_url()
                    if current_url is None:  # Окно было закрыто
                        break

                    if current_url.startswith(redirect_uri):
                        parsed_url = urlparse(current_url)
                        query_params = parse_qs(parsed_url.query)
                        code = query_params.get("code", [None])[0]
                        if code:
                            auth_code_container["code"] = code
                            window.destroy()
                        break
                except Exception:
                    # Окно может быть уничтожено в любой момент
                    break
                time.sleep(0.5)

        window = webview.create_window(
            "Авторизация RanobeLIB",
            url=challenge_url,
            width=650,
            height=750,
            resizable=True,
        )
        window.events.loaded += on_loaded

        thread = threading.Thread(target=_watch_redirect, daemon=True)
        thread.start()

        webview.start(gui='edgechromium')

        if not auth_code_container["code"]:
            print("⚠️ Не удалось получить код авторизации. Вход отменён.")
        return auth_code_container["code"]

    def _exchange_code_for_token(self, code: str, secret: str, redirect_uri: str) -> Optional[Dict[str, Any]]:
        """Обмен кода авторизации на токен."""
        token_url = "https://api.cdnlibs.org/api/auth/oauth/token"
        payload = {
            "grant_type": "authorization_code",
            "client_id": 1,
            "redirect_uri": redirect_uri,
            "code_verifier": secret,
            "code": code,
        }
        headers = dict(self.api.session.headers)
        headers.setdefault("Origin", self.api.site_url)
        headers.setdefault("Referer", f"{self.api.site_url}/")

        try:
            response = self.api.session.post(token_url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Не удалось получить токен: {e}")
            return None 