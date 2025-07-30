"""
Менеджер авторизации для работы с API RanobeLIB
"""

import base64
from typing import Any, Callable, Dict, Optional

from PyQt6.QtCore import QObject, QPoint, QSize, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon, QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import QLabel, QMenu, QMessageBox, QPushButton, QVBoxLayout, QWidget, QWidgetAction

from ..api import RanobeLibAPI
from ..auth import RanobeLibAuth


class AuthWorker(QThread):
    """Рабочий поток для авторизации"""

    finished = pyqtSignal(bool, str)

    def __init__(self, auth: RanobeLibAuth, auth_data: Dict[str, str], parent=None):
        super().__init__(parent)
        self.auth = auth
        self.auth_data = auth_data

    def run(self):
        """Запуск процесса авторизации"""
        try:
            token = self.auth.finish_authorization(self.auth_data)
            if token:
                self.finished.emit(True, "Авторизация успешна")
            else:
                self.finished.emit(False, "Не удалось получить токен")
        except Exception as e:
            self.finished.emit(False, str(e))


class AvatarLoader(QThread):
    """Рабочий поток для асинхронной загрузки аватара"""

    finished = pyqtSignal(QPixmap)
    error = pyqtSignal(str)

    def __init__(self, url: str, session, parent=None):
        super().__init__(parent)
        self.url = url
        self.session = session

    def run(self):
        """Запуск загрузки изображения."""
        try:
            response = self.session.get(self.url, timeout=10)
            response.raise_for_status()
            pixmap = QPixmap()
            if not pixmap.loadFromData(response.content):
                raise ValueError("Не удалось создать QPixmap из полученных данных")
            self.finished.emit(pixmap)
        except Exception as e:
            self.error.emit(str(e))


class AuthManager(QObject):
    """Менеджер авторизации пользователя"""

    auth_changed = pyqtSignal()
    status_message = pyqtSignal(str, int)

    def __init__(self, api: RanobeLibAPI, auth: RanobeLibAuth, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.api = api
        self.auth = auth
        self.user_data: Dict[str, Any] = {}
        self.avatar_worker: Optional[AvatarLoader] = None
        self.auth_worker: Optional[AuthWorker] = None
        self.parent_widget = parent
        self.raw_avatar_pixmap: Optional[QPixmap] = None

        self._load_saved_token()

    def logout(self):
        """Выход из системы."""
        self.auth.logout()
        self.user_data = {}
        self.raw_avatar_pixmap = None
        self.status_message.emit("Выход из системы выполнен", 3000)
        self.auth_changed.emit()

    def _load_saved_token(self) -> bool:
        """Загрузка сохраненного токена авторизации."""
        token_data = self.auth.load_token()
        if token_data and "access_token" in token_data:
            self.api.set_token(token_data["access_token"])
            if self.auth.validate_token():
                self.user_data = self.api.get_current_user()
                self.status_message.emit("Авторизация загружена из сохраненных данных", 3000)
                return True
            else:
                self.status_message.emit(
                    "Сохраненный токен недействителен, требуется повторная авторизация", 5000
                )
        return False

    def show_auth_menu(self, button: QPushButton):
        """Показывает всплывающее меню в зависимости от состояния авторизации."""
        menu = QMenu(self.parent_widget)
        menu.setObjectName("authMenu")

        if self.is_authenticated():
            self._create_authenticated_menu(menu, button)
        else:
            self._create_unauthenticated_menu(menu)

        menu_width = menu.sizeHint().width()
        button_global_pos = button.mapToGlobal(QPoint(0, 0))

        x = button_global_pos.x() + button.width() - menu_width
        y = button_global_pos.y() + button.height() + 3

        menu.exec(QPoint(x, y))

    def _create_unauthenticated_menu(self, menu: QMenu):
        """Создает меню для неавторизованного пользователя."""
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(10, 10, 10, 10)

        info_text = "<p>Для загрузки некоторого контента требуется авторизация на сайте RanobeLIB.</p>"
        info_label = QLabel(info_text)
        info_label.setWordWrap(True)
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_layout.addWidget(info_label)

        info_action = QWidgetAction(menu)
        info_action.setDefaultWidget(info_widget)
        menu.addAction(info_action)

        button_container = QWidget()
        button_layout = QVBoxLayout(button_container)
        button_layout.setContentsMargins(10, 5, 10, 10)

        login_button = QPushButton("Вход")
        login_button.setStyleSheet("background-color: #2a82da; color: white; padding: 5px;")
        login_button.setFixedWidth(100)
        login_button.clicked.connect(menu.close)
        login_button.clicked.connect(self.start_auth_process)

        button_layout.addWidget(login_button, 0, Qt.AlignmentFlag.AlignCenter)

        login_action = QWidgetAction(menu)
        login_action.setDefaultWidget(button_container)
        menu.addAction(login_action)

    def _create_authenticated_menu(self, menu: QMenu, button: QPushButton):
        """Создает меню для авторизованного пользователя."""
        user_widget = QWidget()
        user_layout = QVBoxLayout(user_widget)
        user_layout.setContentsMargins(10, 10, 10, 10)
        user_layout.setSpacing(10)
        user_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        avatar_label = QLabel()
        avatar_label.setFixedSize(96, 96)
        avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar_label.setStyleSheet("border: 2px solid #555555; border-radius: 5px;")
        self.load_avatar(avatar_label)
        user_layout.addWidget(avatar_label)

        username_label = QLabel(self.get_username())
        username_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        username_label.setStyleSheet("font-weight: bold; background-color: transparent;")
        user_layout.addWidget(username_label)

        user_action = QWidgetAction(menu)
        user_action.setDefaultWidget(user_widget)
        menu.addAction(user_action)

        button_container = QWidget()
        button_layout = QVBoxLayout(button_container)
        button_layout.setContentsMargins(10, 5, 10, 10)

        logout_button = QPushButton("Выход")
        logout_button.setStyleSheet("background-color: #e74c3c; color: white; padding: 5px;")
        logout_button.setFixedWidth(100)
        logout_button.clicked.connect(self.logout)
        logout_button.clicked.connect(menu.close)

        button_layout.addWidget(logout_button, 0, Qt.AlignmentFlag.AlignCenter)

        logout_action = QWidgetAction(menu)
        logout_action.setDefaultWidget(button_container)
        menu.addAction(logout_action)

    def start_auth_process(self):
        """Запуск процесса авторизации."""
        if self.auth_worker and self.auth_worker.isRunning():
            self.status_message.emit("Процесс авторизации уже запущен.", 3000)
            return

        self.status_message.emit("Открывается окно авторизации...", 0)

        auth_data = self.auth.get_auth_code_via_webview()

        if not auth_data:
            self.status_message.emit("Авторизация отменена пользователем.", 3000)
            return

        self.status_message.emit("Код авторизации получен, обмен на токен...", 0)

        self.auth_worker = AuthWorker(self.auth, auth_data)
        self.auth_worker.finished.connect(self._on_auth_finished)
        self.auth_worker.start()

    def _on_auth_finished(self, success: bool, message: str):
        """Обработка завершения авторизации."""
        if success:
            self.user_data = self.api.get_current_user()
            self.status_message.emit("Авторизация прошла успешно!", 3000)
            self.auth_changed.emit()
        else:
            self.status_message.emit(f"Ошибка авторизации: {message}", 5000)
            QMessageBox.critical(self.parent_widget, "Ошибка авторизации", message)

        self.auth_worker = None

    def is_authenticated(self) -> bool:
        """Проверка состояния авторизации."""
        return bool(self.user_data and self.user_data.get("username"))

    def get_username(self) -> str:
        """Получение имени пользователя."""
        return self.user_data.get("username", "")

    def get_avatar_url(self) -> Optional[str]:
        """Получение URL аватара пользователя."""
        if self.user_data and self.user_data.get("avatar"):
            return self.user_data["avatar"].get("url")
        return None

    def _process_and_set_avatar(
        self,
        avatar_pixmap: QPixmap,
        target_widget: QLabel | QPushButton,
        on_complete: Optional[Callable] = None,
        height: Optional[int] = None,
    ):
        """Обрабатывает (масштабирует, скругляет) и устанавливает аватар на виджет."""
        if not target_widget:
            return

        widget_size = height if height else target_widget.height()
        if widget_size <= 0:
            widget_size = 30

        target_widget.setFixedSize(widget_size, widget_size)

        scaled_pixmap = avatar_pixmap.scaled(
            widget_size,
            widget_size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        rounded_pixmap = QPixmap(scaled_pixmap.size())
        rounded_pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(rounded_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, scaled_pixmap.width(), scaled_pixmap.height(), 4, 4)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, scaled_pixmap)
        painter.end()

        if isinstance(target_widget, QPushButton):
            target_widget.setEnabled(True)
            target_widget.setText("")
            target_widget.setIcon(QIcon(rounded_pixmap))
            target_widget.setIconSize(QSize(widget_size - 6, widget_size - 6))
            target_widget.setToolTip(f"{self.get_username()}")
        elif isinstance(target_widget, QLabel):
            target_widget.setPixmap(rounded_pixmap)

        if on_complete:
            on_complete()

    def load_avatar(
        self,
        target_widget: QLabel | QPushButton,
        on_complete: Optional[Callable] = None,
        height: Optional[int] = None,
    ) -> None:
        """Загрузка аватара пользователя и установка его на виджет (кнопку или метку)."""
        if self.raw_avatar_pixmap:
            self._process_and_set_avatar(self.raw_avatar_pixmap, target_widget, on_complete, height)
            return

        avatar_url = self.get_avatar_url()
        if not avatar_url:
            return

        if isinstance(target_widget, QPushButton):
            target_widget.setText("…")
            if height:
                target_widget.setFixedSize(height, height)
            target_widget.setEnabled(False)

        self.avatar_worker = AvatarLoader(avatar_url, self.api.session)

        def on_avatar_loaded(avatar_pixmap: QPixmap):
            """Обработка успешной загрузки аватара."""
            if not target_widget:
                return

            self.raw_avatar_pixmap = avatar_pixmap
            self._process_and_set_avatar(avatar_pixmap, target_widget, on_complete, height)

        def on_avatar_error(error_message: str):
            """Обработка ошибки загрузки аватара."""
            print(f"Ошибка загрузки аватара: {error_message}")
            if isinstance(target_widget, QPushButton):
                target_widget.setEnabled(True)

                username = self.get_username()
                first_letter = username[0].upper() if username else "?"

                widget_size = height if height else target_widget.height()
                if widget_size <= 0:
                    widget_size = 30

                target_widget.setFixedSize(widget_size, widget_size)
                target_widget.setText(first_letter)
                target_widget.setIcon(QIcon())
                target_widget.setStyleSheet("font-weight: bold;")
                target_widget.setToolTip(f"{username}")

            if on_complete:
                on_complete()

        self.avatar_worker.finished.connect(on_avatar_loaded)
        self.avatar_worker.error.connect(on_avatar_error)
        self.avatar_worker.start()

    def configure_auth_button(self, button: QPushButton, input_height: int) -> None:
        """Настройка кнопки авторизации в зависимости от состояния входа."""
        if self.is_authenticated():
            self.load_avatar(button, height=input_height)
        else:
            button.setEnabled(True)
            button.setText("")

            base64_icon = "iVBORw0KGgoAAAANSUhEUgAAABgAAAAYCAYAAADgdz34AAAACXBIWXMAAAsTAAALEwEAmpwYAAAA6klEQVR4nO2SvQ7BYBiFq4vJQmJRG4bubsFmcyusXERvQppOSETchMUiNiOJn43hkS85RKIt4hNLn+RdTs57Ttu3jpNhA8ADQuCoiYC6zfAdzxitYqMgVODIBGrG0oY2Co4Kuz8tUJW2t1FwUJj3q4JIYWPdw8xEWmijoAFsE45c+7rAoMMO9bkOOryd8IxEABdoAgNgDiyBk2YprS+P+0lwHugBm5g/Jwnj7ZrdV+FlYPGwuAYCoA34QEHjSwvkuWF2y2kFMxnNJ2i9+cY5oAOstDtNM19kKr4T/ghQ0u45zWQF528FGU4MV3Z+ORoPzBgyAAAAAElFTkSuQmCC"
            pixmap = QPixmap()
            pixmap.loadFromData(base64.b64decode(base64_icon))
            icon = QIcon(pixmap)
            button.setIcon(icon)

            button_size = input_height
            if button_size <= 0:
                button_size = 30

            button.setFixedSize(button_size, button_size)
            button.setIconSize(QSize(button_size - 8, button_size - 8))

            button.setToolTip("Вы не авторизованы")