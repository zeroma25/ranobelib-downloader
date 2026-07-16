"""
Модуль для аутентификации в API RanobeLIB
"""

import base64
import hashlib
import json
import os
import secrets
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

import keyring
import keyring.errors
import requests

from .api import RanobeLibAPI
from .settings import USER_DATA_DIR


class RanobeLibAuth:
    """Класс для работы с аутентификацией в API RanobeLIB"""

    def __init__(self, api: RanobeLibAPI):
        self.api = api
        self.keyring_service = "ranobelib-downloader"
        self.keyring_username = "auth_token"
        self.fallback_token_path = os.path.join(USER_DATA_DIR, "auth.json")

    def generate_auth_details(self) -> Dict[str, str]:
        """Генерация данных для авторизации (URL, секрет и др.)."""
        secret = self._generate_random_string(128)
        state = self._generate_random_string(40)
        redirect_uri = f"{self.api.site_url}/ru/front/auth/oauth/callback"
        challenge = self._code_challenge(secret)

        challenge_url = (
            "https://auth.lib.social/auth/oauth/authorize?scope=&client_id=1&response_type=code"
            f"&redirect_uri={redirect_uri}&state={state}&code_challenge={challenge}"
            "&code_challenge_method=S256&prompt=consent"
        )

        return {
            "url": challenge_url,
            "secret": secret,
            "redirect_uri": redirect_uri,
            "state": state
        }

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

    def login_with_direct_token(self, token: str) -> Optional[str]:
        """Прямая авторизация по готовому токену."""
        self.api.set_token(token)
        if self.validate_token():
            self.save_token({"access_token": token})
            print("✅ Токен успешно сохранён")
            return token
        else:
            print("⚠️ Введенный токен недействителен")
            self.api.clear_token()
            return None

    def get_auth_code_via_cli(self) -> Optional[Dict[str, str]]:
        """Получение кода авторизации через консоль (копирование ссылки)."""
        auth_details = self.generate_auth_details()
        challenge_url = auth_details["url"]
        
        print("\n" + "═" * 60)
        print("🔐 АВТОРИЗАЦИЯ")
        print("\nСпособ 1 (Токен напрямую - Рекомендуется):")
        print("1. Зайдите на сайт https://ranobelib.me и авторизуйтесь.")
        print("2. Откройте Инструменты разработчика (F12) -> вкладка Network (Сеть).")
        print("3. Включите фильтр 'Fetch/XHR' и обновите страницу (F5).")
        print("4. Кликните на любой успешный GET запрос (например, 'me' или 'count').")
        print("5. В разделе Request Headers (Заголовки запроса) найдите 'Authorization: Bearer <ваш-токен>'.")
        print("6. Скопируйте этот длинный токен (всё что идет после слова Bearer) и вставьте ниже.")
        
        print("\nСпособ 2 (Перехват ссылки с кодом):")
        print("1. Откройте Инструменты разработчика (F12) -> вкладка Network (Сеть).")
        print("2. Включите 'Preserve log / Persist Logs' (Сохранять журнал / Непрерывные логи).")
        print(f"3. Откройте ссылку:\n   {challenge_url}")
        print("4. После авторизации найдите в списке запрос 'callback?code=' и скопируйте его URL.")
        print("═" * 60 + "\n")

        user_input = input("🔗 Вставьте токен ИЛИ ссылку с кодом: ").strip()
        if not user_input:
            print("ℹ️ Авторизация отменена.")
            return None

        if user_input.lower().startswith("bearer "):
            user_input = user_input[7:].strip()

        if "://" not in user_input and "code=" not in user_input and len(user_input) > 40:
            return {"direct_token": user_input}

        code = user_input
        if "code=" in user_input:
            try:
                parsed_url = urlparse(user_input)
                query_params = parse_qs(parsed_url.query)
                extracted_code = query_params.get("code", [None])[0]
                if extracted_code:
                    code = extracted_code
            except Exception:
                pass
        
        auth_details["code"] = code
        return auth_details

    def authorize_with_cli(self) -> Optional[str]:
        """Консольный процесс авторизации."""
        auth_data = self.get_auth_code_via_cli()
        if not auth_data:
            return None
            
        if "direct_token" in auth_data:
            return self.login_with_direct_token(auth_data["direct_token"])

        return self.finish_authorization(auth_data)

    def save_token(self, token_data: Dict[str, Any]) -> None:
        """Сохранение данных аутентификации (keyring с фолбэком на файл)."""
        saved_to_keyring = False
        try:
            token_json = json.dumps(token_data)
            chunk_size = 1000
            chunks = [token_json[i:i + chunk_size] for i in range(0, len(token_json), chunk_size)]
            
            keyring.set_password(self.keyring_service, f"{self.keyring_username}_count", str(len(chunks)))
            for i, chunk in enumerate(chunks):
                keyring.set_password(self.keyring_service, f"{self.keyring_username}_{i}", chunk)
            saved_to_keyring = True
        except Exception as e:
            print(f"⚠️ Не удалось сохранить токен в keyring (используем фолбэк): {e}")

        if not saved_to_keyring:
            try:
                with open(self.fallback_token_path, "w", encoding="utf-8") as f:
                    json.dump(token_data, f, indent=2)
            except OSError as e:
                print(f"⚠️ Фолбэк также не удался. Не удалось сохранить токен в файл: {e}")

    def logout(self) -> None:
        """Выход из системы: удаление токена из всех хранилищ."""
        self.api.clear_token()
        
        try:
            try:
                keyring.delete_password(self.keyring_service, self.keyring_username)
            except keyring.errors.PasswordDeleteError:
                pass

            count_str = keyring.get_password(self.keyring_service, f"{self.keyring_username}_count")
            if count_str:
                for i in range(int(count_str)):
                    try:
                        keyring.delete_password(self.keyring_service, f"{self.keyring_username}_{i}")
                    except keyring.errors.PasswordDeleteError:
                        pass
                try:
                    keyring.delete_password(self.keyring_service, f"{self.keyring_username}_count")
                except keyring.errors.PasswordDeleteError:
                    pass
            print("🗑️ Токен удален из keyring (если был).")
        except Exception as e:
            print(f"⚠️ Ошибка при удалении токена из keyring: {e}")

        if os.path.exists(self.fallback_token_path):
            try:
                os.remove(self.fallback_token_path)
                print("🗑️ Файл токена (фолбэк) удален.")
            except OSError as e:
                print(f"⚠️ Не удалось удалить файл токена: {e}")

    def load_token(self) -> Optional[Dict[str, Any]]:
        """Загрузка данных аутентификации (keyring -> фолбэк-файл)."""
        token_data = None
        
        try:
            count_str = keyring.get_password(self.keyring_service, f"{self.keyring_username}_count")
            if count_str:
                token_json = ""
                for i in range(int(count_str)):
                    chunk = keyring.get_password(self.keyring_service, f"{self.keyring_username}_{i}")
                    if chunk is not None:
                        token_json += chunk
                if token_json:
                    token_data = json.loads(token_json)
        except Exception as e:
            print(f"⚠️ Ошибка доступа к keyring при загрузке: {e}")

        if not token_data and os.path.exists(self.fallback_token_path):
            try:
                with open(self.fallback_token_path, "r", encoding="utf-8") as f:
                    token_data = json.load(f)
                    
                if token_data:
                    try:
                        self.save_token(token_data)
                        if keyring.get_password(self.keyring_service, f"{self.keyring_username}_count"):
                            os.remove(self.fallback_token_path)
                            print("✅ Токен успешно мигрирован из auth.json в keyring. Файл удален.")
                    except Exception as e:
                        print(f"⚠️ Миграция в keyring не удалась (продолжаем использовать файл): {e}")
            except (OSError, json.JSONDecodeError) as e:
                print(f"⚠️ Не удалось загрузить токен из файла: {e}")

        return token_data

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

        try:
            response = self.api.session.post(token_url, json=payload, headers=headers, timeout=10)

            if response.status_code == 400:
                print("⚠️ Refresh-токен недействителен. Требуется повторная авторизация.")
                return False

            response.raise_for_status()
            new_token_data = response.json()

            if "access_token" in new_token_data:
                print("✅ Токен успешно обновлён")
                self.api.set_token(new_token_data["access_token"])
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
        return "".join(secrets.choice(alphabet) for _ in range(length))

    def _code_challenge(self, verifier: str) -> str:
        """Вычисление code_challenge в соответствии с PKCE (SHA256 + Base64url, без =)"""
        digest = hashlib.sha256(verifier.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")

    def _exchange_code_for_token(
        self, code: str, secret: str, redirect_uri: str
    ) -> Optional[Dict[str, Any]]:
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

        try:
            response = self.api.session.post(token_url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Не удалось получить токен: {e}")
            return None 