"""Opens the OS's native print flow for a generated QR code image."""
import os
import platform
import subprocess
import tempfile
from pathlib import Path


def print_image(image):
    """Save `image` to a temp file and hand it to the OS's print flow.
    Raises RuntimeError with a user-facing message on failure."""
    temp_path = Path(tempfile.gettempdir()) / 'wifi_qr_generator_print.png'
    image.save(temp_path)

    system = platform.system()
    try:
        if system == 'Windows':
            os.startfile(str(temp_path), 'print')  # noqa: S606 (Windows-only API)
        elif system == 'Darwin':
            subprocess.run(['open', '-a', 'Preview', str(temp_path)], check=True)
            subprocess.run([
                'osascript', '-e',
                'tell application "System Events" to keystroke "p" using command down',
            ], check=True)
        elif system == 'Linux':
            # Most desktop image viewers registered via xdg-open have their
            # own Ctrl+P print dialog.
            subprocess.run(['xdg-open', str(temp_path)], check=True)
        else:
            raise RuntimeError(f'Печать не поддерживается на платформе {system}.')
    except Exception as exc:
        raise RuntimeError(
            'Не удалось автоматически открыть меню печати. '
            f'Откройте файл "{temp_path}" вручную и распечатайте его.'
        ) from exc
