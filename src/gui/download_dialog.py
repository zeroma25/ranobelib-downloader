"""
Диалог для отображения процесса загрузки глав и создания книг
"""

import os
import shutil
import time
from typing import Any, Dict, List

from PyQt6.QtCore import QThread, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from ..api import OperationCancelledError, RanobeLibAPI
from ..creators import EpubCreator, Fb2Creator, HtmlCreator, TxtCreator
from ..img import ImageHandler
from ..parser import RanobeLibParser
from ..processing import ContentProcessor
from ..settings import USER_DATA_DIR


class DownloadWorker(QThread):
    """Рабочий поток для скачивания глав и создания книг"""

    progress_update = pyqtSignal(str, int)
    chapter_download = pyqtSignal(int, int)
    time_update = pyqtSignal(float, float)  # elapsed, remaining
    format_progress = pyqtSignal(str, int, int)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(
        self,
        novel_info: Dict[str, Any],
        selected_chapters: List[Dict[str, Any]],
        selected_formats: List[str],
        api: RanobeLibAPI,
        parser: RanobeLibParser,
        image_handler: ImageHandler,
        save_dir: str,
        options: Dict[str, bool],
    ):
        super().__init__()
        self.novel_info = novel_info
        self.selected_chapters = selected_chapters
        self.selected_formats = selected_formats
        self.api = api
        self.parser = parser
        self.image_handler = image_handler
        self.save_dir = save_dir
        self.options = options
        self.is_cancelled = False
        self._temp_dir = ""

        self.start_time = 0
        self.prepared_chapters = []
        self.created_files = []

    def cancel(self):
        """Сигнал потоку на остановку."""
        if not self.is_cancelled:
            self.progress_update.emit("Отмена процесса...", 0)
            self.is_cancelled = True
            self.api.cancel_pending_requests()

    def run(self):
        """Запуск процесса скачивания и создания книг"""
        self.start_time = time.time()
        self.image_handler.reset()

        novel_id = self.novel_info.get("id")
        self._temp_dir = os.path.join(USER_DATA_DIR, "temp", f"images_{novel_id}")

        should_emit_finish = True
        try:
            os.makedirs(self._temp_dir, exist_ok=True)

            self._download_chapters()

            if not self.is_cancelled:
                self._create_books()

        except OperationCancelledError:
            should_emit_finish = True
            self.is_cancelled = True
        except Exception as e:
            should_emit_finish = False
            if not self.is_cancelled:
                self.error.emit(str(e))
        finally:
            self._cleanup_temp_files()
            if should_emit_finish:
                self.finished.emit(self.created_files)

    def _download_chapters(self):
        """Скачивание выбранных глав"""
        total_chapters = len(self.selected_chapters)
        self.progress_update.emit("Подготовка к загрузке глав...", 0)

        processor = ContentProcessor(self.api, self.parser, self.image_handler)
        processor.update_settings()

        processor.download_cover_enabled = self.options.get(
            "download_cover", processor.download_cover_enabled
        )
        processor.download_images_enabled = self.options.get(
            "download_images", processor.download_images_enabled
        )
        processor.group_by_volumes = self.options.get("group_by_volumes", processor.group_by_volumes)
        processor.add_translator = self.options.get("add_translator", processor.add_translator)

        for i, chapter_data in enumerate(self.selected_chapters):
            if self.is_cancelled:
                return

            chapter_info = chapter_data["chapter"]
            branch_ids = chapter_data["branch_ids"]
            branch_id = branch_ids[0] if branch_ids else "0"
            branch_info = next(
                (
                    b
                    for b in chapter_info.get("branches", [])
                    if str(b.get("branch_id", "0")) == str(branch_id)
                ),
                {"branch_id": branch_id},
            )

            self.chapter_download.emit(i + 1, total_chapters)
            chapter_title = f"Глава {chapter_info.get('number', '?')}"
            if chapter_info.get("name"):
                chapter_title += f" - {chapter_info.get('name')}"

            self.progress_update.emit(
                f"Загрузка {chapter_title}...", int(100 * (i / total_chapters))
            )

            prepared_chapter = processor._process_single_chapter(
                {"chapter": chapter_info, "branch": branch_info},
                self.novel_info,
                self._temp_dir,
                total_chapters - (i + 1),
            )

            self.prepared_chapters.append(prepared_chapter)

            elapsed_time = time.time() - self.start_time
            chapters_done = i + 1
            remaining_time = -1.0
            if chapters_done > 0:
                avg_time_per_chapter = elapsed_time / chapters_done
                chapters_remaining = total_chapters - chapters_done
                remaining_time = avg_time_per_chapter * chapters_remaining
            self.time_update.emit(elapsed_time, remaining_time)

        self.progress_update.emit("Все главы загружены", 100)

    def _create_books(self):
        """Создание книг в выбранных форматах"""
        creators = {
            "EPUB": EpubCreator(self.api, self.parser, self.image_handler),
            "FB2": Fb2Creator(self.api, self.parser, self.image_handler),
            "HTML": HtmlCreator(self.api, self.parser, self.image_handler),
            "TXT": TxtCreator(self.api, self.parser, self.image_handler),
        }

        total_formats = len(self.selected_formats)
        for i, format_name in enumerate(self.selected_formats):
            if self.is_cancelled:
                return

            self.format_progress.emit(format_name, i + 1, total_formats)
            self.progress_update.emit(f"Создание {format_name}...", 0)

            try:
                creator = creators.get(format_name)
                if not creator:
                    continue

                if hasattr(creator, "content_processor"):
                    creator.content_processor.update_settings()

                if hasattr(creator, "content_processor"):
                    creator.content_processor.download_cover_enabled = self.options.get(
                        "download_cover", creator.content_processor.download_cover_enabled
                    )
                    creator.content_processor.download_images_enabled = self.options.get(
                        "download_images", creator.content_processor.download_images_enabled
                    )
                    creator.content_processor.group_by_volumes = self.options.get(
                        "group_by_volumes", creator.content_processor.group_by_volumes
                    )
                    creator.content_processor.add_translator = self.options.get(
                        "add_translator", creator.content_processor.add_translator
                    )

                ContentProcessor._global_cache = {
                    (self.novel_info.get("id"), None): self.prepared_chapters
                }

                filename = creator.create(self.novel_info, self.prepared_chapters, None)

                if self.save_dir and os.path.exists(filename):
                    new_path = os.path.join(self.save_dir, os.path.basename(filename))
                    if os.path.abspath(filename) != os.path.abspath(new_path):
                        shutil.move(filename, new_path)
                        filename = new_path

                self.created_files.append(filename)
                self.progress_update.emit(
                    f"Создан файл {format_name}: {os.path.basename(filename)}", 100
                )

            except Exception as e:
                self.progress_update.emit(f"Ошибка при создании {format_name}: {e}", 0)

    def _cleanup_temp_files(self):
        """Очистка временных файлов"""
        if not self._temp_dir or not os.path.exists(self._temp_dir):
            return

        self.progress_update.emit("Очистка временных файлов...", 0)
        try:
            shutil.rmtree(self._temp_dir)
            self.progress_update.emit("Временные файлы удалены", 100)
        except Exception as e:
            self.progress_update.emit(f"Не удалось удалить временные файлы: {e}", 0)

        novel_id = self.novel_info.get("id")
        cache_key = (novel_id, None)
        if cache_key in ContentProcessor._global_cache:
            ContentProcessor._global_cache.pop(cache_key, None)
        self.progress_update.emit("Кэш глав очищен", 100)


class DownloadDialog(QDialog):
    """Диалог для отображения прогресса загрузки"""

    def __init__(
        self,
        novel_info: Dict[str, Any],
        selected_chapters: List[Dict[str, Any]],
        selected_formats: List[str],
        api: RanobeLibAPI,
        parser: RanobeLibParser,
        image_handler: ImageHandler,
        save_dir: str,
        options: Dict[str, bool],
        parent=None,
    ):
        super().__init__(parent)
        self.novel_info = novel_info
        self.selected_chapters = selected_chapters
        self.selected_formats = selected_formats
        self.api = api
        self.parser = parser
        self.image_handler = image_handler
        self.save_dir = save_dir
        self.options = options

        self.download_worker = None
        self.created_files = []

        self._setup_ui()
        self._start_download()

    def _setup_ui(self):
        """Настройка интерфейса диалога"""
        self.setWindowTitle("Загрузка и создание книг")
        self.setMinimumWidth(600)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)

        chapters_group = QGroupBox("Прогресс загрузки глав")
        chapters_layout = QVBoxLayout(chapters_group)

        self.chapters_progress = QProgressBar()
        self.chapters_progress.setMinimum(0)
        self.chapters_progress.setMaximum(len(self.selected_chapters))
        self.chapters_progress.setValue(0)
        chapters_layout.addWidget(self.chapters_progress)

        self.chapters_label = QLabel("0 из 0 глав загружено")
        chapters_layout.addWidget(self.chapters_label)

        time_layout = QHBoxLayout()
        self.elapsed_time_label = QLabel("Прошло: 00:00")
        self.remaining_time_label = QLabel("Осталось: вычисление...")
        time_layout.addWidget(self.elapsed_time_label)
        time_layout.addStretch()
        time_layout.addWidget(self.remaining_time_label)
        chapters_layout.addLayout(time_layout)

        layout.addWidget(chapters_group)

        formats_group = QGroupBox("Прогресс создания книг")
        formats_layout = QVBoxLayout(formats_group)

        self.formats_progress = QProgressBar()
        self.formats_progress.setMinimum(0)
        self.formats_progress.setMaximum(len(self.selected_formats))
        self.formats_progress.setValue(0)
        formats_layout.addWidget(self.formats_progress)

        self.formats_label = QLabel("0 из 0 форматов создано")
        formats_layout.addWidget(self.formats_label)

        layout.addWidget(formats_group)

        log_group = QGroupBox("Лог операций")
        log_layout = QVBoxLayout(log_group)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(150)
        log_layout.addWidget(self.log_text)

        layout.addWidget(log_group)

        buttons_layout = QHBoxLayout()

        self.open_folder_button = QPushButton("Открыть папку")
        self.open_folder_button.setEnabled(False)
        self.open_folder_button.clicked.connect(self._open_folder)
        buttons_layout.addWidget(self.open_folder_button)

        self.close_button = QPushButton("Отмена")
        self.close_button.clicked.connect(self._cancel_download)
        buttons_layout.addWidget(self.close_button)

        layout.addLayout(buttons_layout)

    def _start_download(self):
        """Запуск процесса загрузки"""
        title = self.novel_info.get("rus_name") or self.novel_info.get("eng_name", "Новелла")
        self.log_text.append(f"<b>Начало загрузки новеллы: {title}</b>")
        self.log_text.append(f"Выбрано глав: {len(self.selected_chapters)}")
        self.log_text.append(f"Выбранные форматы: {', '.join(self.selected_formats)}")
        self.log_text.append("─" * 50)

        self.download_worker = DownloadWorker(
            self.novel_info,
            self.selected_chapters,
            self.selected_formats,
            self.api,
            self.parser,
            self.image_handler,
            self.save_dir,
            self.options,
        )

        self.download_worker.progress_update.connect(self._on_progress_update)
        self.download_worker.chapter_download.connect(self._on_chapter_download)
        self.download_worker.time_update.connect(self._on_time_update)
        self.download_worker.format_progress.connect(self._on_format_progress)
        self.download_worker.finished.connect(self._on_download_finished)
        self.download_worker.error.connect(self._on_download_error)

        self.download_worker.start()

    def _cancel_download(self):
        """Отмена процесса загрузки"""
        if self.download_worker and self.download_worker.isRunning():
            self.close_button.setEnabled(False)
            self.log_text.append("<b>Отмена операции... Ожидание завершения текущей задачи.</b>")
            self.download_worker.cancel()

    def closeEvent(self, event):
        """Перехват события закрытия окна для отмены операции."""
        if self.download_worker and self.download_worker.isRunning():
            self._cancel_download()
            event.ignore()
        else:
            event.accept()

    def _format_time(self, seconds: float) -> str:
        """Форматирует секунды в строку MM:SS"""
        if seconds < 0:
            return "вычисление..."
        seconds = int(seconds)
        minutes = seconds // 60
        seconds %= 60
        return f"{minutes:02d}:{seconds:02d}"

    def _on_progress_update(self, message: str, progress: int):
        """Обработка обновления прогресса"""
        self.log_text.append(message)

    def _on_chapter_download(self, current: int, total: int):
        """Обработка прогресса загрузки глав"""
        self.chapters_progress.setValue(current)
        self.chapters_label.setText(f"{current} из {total} глав загружено")

    def _on_time_update(self, elapsed: float, remaining: float):
        """Обработка обновления времени"""
        self.elapsed_time_label.setText(f"Прошло: {self._format_time(elapsed)}")
        self.remaining_time_label.setText(f"Осталось: ~{self._format_time(remaining)}")

    def _on_format_progress(self, format_name: str, current: int, total: int):
        """Обработка прогресса создания форматов"""
        self.formats_progress.setValue(current)
        self.formats_label.setText(f"{current} из {total} форматов создано")
        self.log_text.append(f"<b>Создание формата {format_name}...</b>")

        if self.download_worker:
            elapsed = time.time() - self.download_worker.start_time
            self.elapsed_time_label.setText(f"Прошло: {self._format_time(elapsed)}")
            self.remaining_time_label.setText("Осталось: создание книг...")

    def _on_download_finished(self, created_files: List[str]):
        """Обработка завершения загрузки"""
        self.created_files = created_files

        self.log_text.append("─" * 50)
        if self.download_worker and self.download_worker.is_cancelled:
            self.log_text.append("<b>Загрузка отменена</b>")
        else:
            self.log_text.append("<b>Загрузка завершена</b>")

        if self.download_worker:
            elapsed = time.time() - self.download_worker.start_time
            self.elapsed_time_label.setText(f"Прошло: {self._format_time(elapsed)}")
            self.remaining_time_label.setText("Осталось: 00:00")

        if created_files:
            self.log_text.append("<b>Созданные файлы:</b>")
            for filename in created_files:
                self.log_text.append(f"- {os.path.basename(filename)}")
            self.open_folder_button.setEnabled(True)

        self.close_button.setText("Закрыть")
        self.close_button.setEnabled(True)
        try:
            self.close_button.clicked.disconnect(self._cancel_download)
        except TypeError:
            pass
        self.close_button.clicked.connect(self.accept)

    def _open_folder(self):
        """Открывает каталог с загруженными файлами."""
        if os.path.isdir(self.save_dir):
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(self.save_dir)))

    def _on_download_error(self, error_message: str):
        """Обработка ошибки при загрузке"""
        self.log_text.append(f"<span style='color: red;'><b>Ошибка:</b> {error_message}</span>")

        if self.download_worker:
            elapsed = time.time() - self.download_worker.start_time
            self.elapsed_time_label.setText(f"Прошло: {self._format_time(elapsed)}")
            self.remaining_time_label.setText("Осталось: --:--")

        self.close_button.setText("Закрыть")
        self.close_button.setEnabled(True)
        try:
            self.close_button.clicked.disconnect(self._cancel_download)
        except TypeError:
            pass
        self.close_button.clicked.connect(self.accept) 