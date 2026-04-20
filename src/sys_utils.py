import sys
import io

def setup_utf8_output():
    # Настройка sys.stdout и sys.stderr на работу с UTF-8 на Windows.
    if sys.platform == "win32":
        # Перенастройка потоков вывода на UTF-8, если это возможно
        if hasattr(sys.stdout, "reconfigure"):
            try:
                sys.stdout.reconfigure(encoding='utf-8')
                sys.stderr.reconfigure(encoding='utf-8')
            except (AttributeError, io.UnsupportedOperation):
                pass
        else:
            # Для старых версий Python или если reconfigure не поддерживается
            try:
                sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
                sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
            except (AttributeError, io.UnsupportedOperation):
                pass
