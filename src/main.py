"""
Основной модуль для работы с RanobeLIB API
"""

import os
import re
import shutil
import signal
import sys
from typing import Any, Dict, List, Optional

from . import __version__
from .api import OperationCancelledError, RanobeLibAPI
from .auth import RanobeLibAuth
from .branches import (
    get_branch_info_for_display,
    get_formatted_branches_with_teams,
    get_unique_chapters_count,
)
from .creators import EpubCreator, Fb2Creator, HtmlCreator, TxtCreator
from .img import ImageHandler
from .parser import RanobeLibParser
from .processing import ContentProcessor
from .settings import USER_DATA_DIR, settings


def main(use_gui: bool = False):
    """Основная функция программы."""
    if use_gui:
        try:
            from .gui.app import run_gui

            return run_gui()
        except ImportError as e:
            print(f"⚠️ Ошибка запуска графического интерфейса: {e}")
            print("ℹ️ Запускаю консольную версию...")
            return run_cli()

    return run_cli()


def run_cli():
    """Запуск консольной версии."""
    api = RanobeLibAPI()
    auth = RanobeLibAuth(api)
    parser = RanobeLibParser(api)
    image_handler = ImageHandler(api)
    api.set_token_refresh_callback(auth.refresh_token)

    def signal_handler(sig, frame):
        api.cancel_pending_requests()
        raise OperationCancelledError("Операция отменена пользователем")

    signal.signal(signal.SIGINT, signal_handler)

    creators = [
        EpubCreator(api, parser, image_handler),
        Fb2Creator(api, parser, image_handler),
        HtmlCreator(api, parser, image_handler),
        TxtCreator(api, parser, image_handler),
    ]

    _print_header()
    _handle_authentication(auth)
    print("─" * 60)

    _show_settings()

    if _ask_change_settings():
        _change_settings()
    print("─" * 60)

    slug = _get_novel_slug(api)

    print("🔄 Получение информации о новелле...")
    novel_info = api.get_novel_info(slug)
    if not novel_info.get("id"):
        print(
            "❌ Не удалось загрузить информацию о новелле. Возможно, ссылка некорректна или требуется авторизация."
        )
        return

    title_raw = novel_info.get("rus_name") or novel_info.get("eng_name") or "Без названия"
    title = re.sub(r"\s*\((?:Новелла|Novel)\)\s*$", "", title_raw, flags=re.IGNORECASE).strip()
    print(f"📖 Название: {title}")

    try:
        print("🔄 Получение списка глав...")
        chapters_data = api.get_novel_chapters(slug)
        if not chapters_data:
            if novel_info.get("is_licensed"):
                print("❌ Доступ ограничен по требованию Правообладателя или РКН")
            else:
                print("❌ Не удалось загрузить список глав.")
            return

        branches = get_formatted_branches_with_teams(novel_info, chapters_data)
        selected_branch_id = _select_branch(branches, chapters_data)
        if not selected_branch_id:
            return

        selected_creators = _select_output_formats(creators)

        temp_images_dir = os.path.join(USER_DATA_DIR, "cache", f"temp_images_{novel_info.get('id')}")
        if os.path.exists(temp_images_dir):
            try:
                shutil.rmtree(temp_images_dir)
            except Exception:
                pass

        if selected_creators == "CACHE_ONLY":
            print("─" * 60)
            print("🔄 Загрузка глав...")
            try:
                creator = creators[0]
                creator.update_settings()
                _, image_folder = creator.prepare_dirs(novel_info.get("id"))
                if settings.get("cache_chapters", True):
                    novel_name = novel_info.get("rus_name") or novel_info.get("name")
                    if novel_name:
                        from .cache import ChapterCache
                        ChapterCache().save_novel_info(str(novel_info.get("id")), str(novel_name))
                creator.prepare_chapters(novel_info, chapters_data, selected_branch_id, image_folder)
                print("✅ Главы успешно загружены в кэш")
            except OperationCancelledError:
                raise
            except Exception as e:
                print(f"❌ Ошибка при загрузке глав: {e}")
        elif selected_creators:
            _generate_books(
                novel_info,
                chapters_data,
                selected_branch_id,
                selected_creators,
            )
    except OperationCancelledError:
        print("\n⛔️ Прервано пользователем.")
    finally:
        _cleanup_temp_folder(novel_info.get("id"))


def _print_header():
    """Печать заголовка программы."""
    print("═" * 60)
    print(f"📚 RanobeLIB Downloader v{__version__} 📚".center(60))
    print("═" * 60)


def _handle_authentication(auth: RanobeLibAuth):
    """Обработка процесса аутентификации."""
    token_data = auth.load_token()
    user_info = None

    if token_data and "access_token" in token_data:
        auth.api.set_token(token_data["access_token"])
        user_info = auth.validate_token()
        if user_info:
            print(f"🔑 Выполнен вход как: {user_info.get('username', 'Пользователь')}")
            return

        print("⚠️ Сохранённый токен недействителен")
        if "refresh_token" in token_data:
            if auth.refresh_token():
                user_info = auth.validate_token()
                if user_info:
                    print(f"🔑 Выполнен вход как: {user_info.get('username', 'Пользователь')}")
                    return

    choice = input("🔑 Пройти авторизацию на сайте? (y/n): ").strip().lower()
    if choice in {"y", "yes", "да", "д", "1"}:
        if auth.authorize_with_cli():
            user_info = auth.validate_token()
            if user_info:
                print(f"🔑 Выполнен вход как: {user_info.get('username', 'Пользователь')}")
    else:
        print("ℹ️ Продолжаем без авторизации (часть контента может быть недоступна)")


def _show_settings():
    """Отображение текущих настроек."""
    print("⚙️ Текущие настройки:")
    print(f"  • Использовать локальный кэш: {'✅' if settings.get('cache_chapters', True) else '❌'}")
    print(f"  • Скачивать обложку: {'✅' if settings.get('download_cover') else '❌'}")
    print(f"  • Скачивать изображения: {'✅' if settings.get('download_images') else '❌'}")
    print(f"  • Сжимать изображения: {'✅' if settings.get('compress_images') else '❌'}")
    print(f"  • Добавлять данные о переводчике: {'✅' if settings.get('add_translator') else '❌'}")
    print(f"  • Группировать по томам: {'✅' if settings.get('group_by_volumes') else '❌'}")
    print(f"  • Каталог для сохранения: {settings.get('save_directory')}")


def _ask_change_settings():
    """Спрашивает пользователя, хочет ли он изменить настройки."""
    choice = input("🛠️ Изменить настройки? (y/n): ").strip().lower()
    return choice in {"y", "yes", "да", "д", "1"}


def _change_settings():
    """Изменение настроек пользователем."""
    print("⚙️ Изменение настроек:")

    choice = (
        input(f"  Использовать локальный кэш? (y/n) [{('y' if settings.get('cache_chapters', True) else 'n')}]: ")
        .strip()
        .lower()
    )
    if choice:
        settings.set("cache_chapters", choice in {"y", "yes", "да", "д", "1"})

    choice = (
        input("  Очистить весь кэш загрузок прямо сейчас? (y/n) [n]: ")
        .strip()
        .lower()
    )
    if choice in {"y", "yes", "да", "д", "1"}:
        try:
            from .cache import ChapterCache
            ChapterCache().clear_all_cache()
            print("✅ Кэш очищен")
        except Exception as e:
            print(f"❌ Не удалось очистить кэш: {e}")

    choice = (
        input(f"  Скачивать обложку? (y/n) [{('y' if settings.get('download_cover') else 'n')}]: ")
        .strip()
        .lower()
    )
    if choice:
        settings.set("download_cover", choice in {"y", "yes", "да", "д", "1"})

    choice = (
        input(f"  Скачивать изображения из глав? (y/n) [{('y' if settings.get('download_images') else 'n')}]: ")
        .strip()
        .lower()
    )
    if choice:
        settings.set("download_images", choice in {"y", "yes", "да", "д", "1"})

    choice = (
        input(f"  Сжимать изображения? (y/n) [{('y' if settings.get('compress_images') else 'n')}]: ")
        .strip()
        .lower()
    )
    if choice:
        settings.set("compress_images", choice in {"y", "yes", "да", "д", "1"})

    choice = (
        input(f"  Добавлять данные о переводчике? (y/n) [{('y' if settings.get('add_translator') else 'n')}]: ")
        .strip()
        .lower()
    )
    if choice:
        settings.set("add_translator", choice in {"y", "yes", "да", "д", "1"})

    choice = (
        input(f"  Группировать главы по томам? (y/n) [{('y' if settings.get('group_by_volumes') else 'n')}]: ")
        .strip()
        .lower()
    )
    if choice:
        settings.set("group_by_volumes", choice in {"y", "yes", "да", "д", "1"})

    current_dir = settings.get("save_directory")
    new_dir = input(f"  Каталог для сохранения [{current_dir}]: ").strip()
    if new_dir:
        if not os.path.exists(new_dir):
            try:
                os.makedirs(new_dir, exist_ok=True)
                print(f"✅ Создан каталог: {new_dir}")
            except Exception as e:
                print(f"❌ Не удалось создать каталог: {e}")
                new_dir = current_dir
        settings.set("save_directory", os.path.abspath(new_dir))

    print("✅ Настройки сохранены")


def _get_novel_slug(api: RanobeLibAPI) -> str:
    """Запрос ссылки на новеллу и извлечение из нее slug."""
    while True:
        novel_url = input("🔗 Введите ссылку на новеллу: ")
        slug = api.extract_slug_from_url(novel_url)
        if slug:
            return slug
        print("⚠️ Неверный формат ссылки. Пример: https://ranobelib.me/ru/book/11407--solo-leveling")


def _select_branch(branches: Dict, chapters_data: List[Dict[str, Any]]) -> Optional[str]:
    """Отображение доступных веток перевода и выбор одной из них."""
    if not branches:
        print("❌ Не найдено ни одной ветки перевода с главами.")
        return None

    if len(branches) == 1:
        branch_id = next(iter(branches))
        print(f"💬 Перевод: {get_branch_info_for_display(branches[branch_id])}")
        return branch_id

    print("─" * 60)
    print("📊 Доступные переводы:")

    display_options = []

    default_option = (
        "default",
        f"По умолчанию [Автовыбор] ({get_unique_chapters_count(chapters_data)} глав)",
    )
    display_options.append(default_option)

    sorted_branches = sorted(branches.items(), key=lambda x: x[1]["chapter_count"], reverse=True)
    for branch_id, branch_info in sorted_branches:
        display_options.append((branch_id, get_branch_info_for_display(branch_info)))

    for i, (_, display_str) in enumerate(display_options):
        print(f"  {i+1}. {display_str}")

    while True:
        try:
            choice = int(input("📑 Выберите перевод (номер): "))
            if 1 <= choice <= len(display_options):
                return display_options[choice - 1][0]
            print(f"⚠️ Пожалуйста, выберите номер от 1 до {len(display_options)}")
        except ValueError:
            print("⚠️ Пожалуйста, введите число")


def _select_output_formats(creators: List[Any]) -> List[Any]:
    """Выбор форматов для сохранения книги."""
    if not creators:
        return []

    options = {f"{i+1}": creator for i, creator in enumerate(creators)}
    has_all_option = len(creators) > 1
    all_option_num = str(len(creators) + 1) if has_all_option else None

    cache_enabled = settings.get("cache_chapters", True)

    while True:
        print("─" * 60)
        print("⚙️ Доступные для сохранения форматы:")
        if cache_enabled:
            print("  0. Только кэш (без создания книг)")
        for i, creator in enumerate(creators):
            print(f"  {i+1}. {creator.format_name}")
        if has_all_option:
            print(f"  {all_option_num}. Все форматы")

        prompt = "📑 Выберите формат(ы) (можно несколько через запятую): "
        choice_str = input(prompt).strip()

        choices = {c.strip() for c in choice_str.split(",")}

        if not choices:
            print("⚠️ Выбор не может быть пустым. Пожалуйста, попробуйте снова.")
            continue

        if cache_enabled and "0" in choices:
            if len(choices) > 1:
                print("⚠️ Если вы выбираете '0. Только кэш', другие варианты указывать не нужно.")
                continue
            return "CACHE_ONLY"
        elif not cache_enabled and "0" in choices:
            print("⚠️ Опция 'Только кэш' недоступна, так как использование локального кэша отключено.")
            continue

        if has_all_option and all_option_num in choices:
            if len(choices) > 1:
                print(f"⚠️ Если вы выбираете '{all_option_num}. Все форматы', другие варианты указывать не нужно.")
                continue
            return creators

        selected_creators = set()
        invalid_choices = []

        for choice in choices:
            if choice in options:
                selected_creators.add(options[choice])
            else:
                invalid_choices.append(choice)

        if invalid_choices:
            print(f"⚠️ Неверный выбор: {', '.join(sorted(invalid_choices))}. Пожалуйста, попробуйте снова.")
            continue

        if selected_creators:
            return [c for c in creators if c in selected_creators]


def _generate_books(
    novel_info,
    chapters_data,
    selected_branch_id,
    creators: List[Any],
):
    """Запуск процесса создания файлов книг в выбранных форматах."""
    print("─" * 60)
    
    novel_id = novel_info.get("id")
    temp_dir = os.path.join(USER_DATA_DIR, "cache")
    
    if settings.get("cache_chapters", True):
        source_folder = os.path.join(temp_dir, f"cache_images_{novel_id}")
    else:
        source_folder = os.path.join(temp_dir, f"temp_images_{novel_id}")
        
    if settings.get("cache_chapters", True):
        novel_name = novel_info.get("rus_name") or novel_info.get("name")
        if novel_name:
            from .cache import ChapterCache
            ChapterCache().save_novel_info(str(novel_info.get("id")), str(novel_name))
        
    override_folder = None
    
    if creators:
        creators[0].update_settings()
        _, image_folder = creators[0].prepare_dirs(novel_id)
        creators[0].prepare_chapters(novel_info, chapters_data, selected_branch_id, image_folder)

    if settings.get("compress_images") and (settings.get("download_images") or settings.get("download_cover")) and creators:
        if settings.get("cache_chapters", True):
            print("Сжатие изображений...")
            target_folder = os.path.join(temp_dir, f"temp_images_{novel_id}")
            creators[0].image_handler.compress_folder(source_folder, target_folder)
            override_folder = target_folder
        
    for creator in creators:
        try:
            if override_folder:
                creator.override_image_folder = override_folder
            creator.update_settings()

            filename = creator.create(novel_info, chapters_data, selected_branch_id)
            print(f"✅ {creator.format_name} успешно создан: {filename}")
        except OperationCancelledError:
            raise
        except Exception as e:
            print(f"❌ Ошибка при создании {creator.format_name}: {e}")


def _cleanup_temp_folder(novel_id: Any):
    """Удаление временной папки текущей сессии и очистка кэшей в памяти."""
    temp_dir = os.path.join(USER_DATA_DIR, "cache", f"temp_images_{novel_id}")
    if os.path.exists(temp_dir):
        print("🧹 Очистка временных файлов...")
        try:
            shutil.rmtree(temp_dir)
        except OSError as e:
            print(f"⚠️ Не удалось удалить {temp_dir}: {e}")

    ContentProcessor.clear_novel_cache(novel_id)

if __name__ == "__main__":
    try:
        use_gui = "--gui" in sys.argv or "-g" in sys.argv
        main(use_gui)
    finally:
        print("═" * 60)
        input("👋 Нажмите Enter для выхода...") 