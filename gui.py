"""
Скрипт для скачивания новелл с сайта RanobeLIB в режиме графического интерфейса.
"""
import PyQt6.QtWebEngineWidgets
from src.main import main


def run():
    """Запуск основной функции для GUI с корректной обработкой принудительного прерывания."""
    try:
        main(use_gui=True)
    except KeyboardInterrupt:
        print("\n⛔️ Прервано пользователем.")


if __name__ == "__main__":
    run() 
