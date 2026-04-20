"""
Скрипт для скачивания новелл с сайта RanobeLIB в режиме графического интерфейса.
"""

from src.main import main
from src.sys_utils import setup_utf8_output


def run():
    """Запуск основной функции для GUI с корректной обработкой принудительного прерывания."""
    setup_utf8_output()
    try:
        main(use_gui=True)
    except KeyboardInterrupt:
        print("\n⛔️ Прервано пользователем.")


if __name__ == "__main__":
    run() 