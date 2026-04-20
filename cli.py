"""
Скрипт для скачивания новелл с сайта RanobeLIB в консольном режиме.
"""

from src.main import main
from src.api import OperationCancelledError
from src.sys_utils import setup_utf8_output


def run():
    """Запуск основной функции для CLI с корректной обработкой принудительного прерывания."""
    setup_utf8_output()
    try:
        main(use_gui=False)
    except (KeyboardInterrupt, OperationCancelledError):
        print("\n⛔️ Прервано пользователем.")
    finally:
        print("═" * 60)
        try:
            input("👋 Нажмите Enter для выхода...")
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    run() 