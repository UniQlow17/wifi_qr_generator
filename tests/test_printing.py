import pytest
from PIL import Image

from app.core import printing


@pytest.fixture
def image():
    return Image.new('RGB', (10, 10), 'white')


def test_print_image_windows_uses_startfile(monkeypatch, tmp_path, image):
    monkeypatch.setattr(printing.platform, 'system', lambda: 'Windows')
    monkeypatch.setattr(printing.tempfile, 'gettempdir', lambda: str(tmp_path))

    calls = []
    monkeypatch.setattr(printing.os, 'startfile', lambda path, verb: calls.append((path, verb)), raising=False)

    printing.print_image(image)

    assert len(calls) == 1
    path, verb = calls[0]
    assert verb == 'print'
    assert path.endswith('wifi_qr_generator_print.png')


def test_print_image_linux_uses_xdg_open(monkeypatch, tmp_path, image):
    monkeypatch.setattr(printing.platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(printing.tempfile, 'gettempdir', lambda: str(tmp_path))

    calls = []

    def fake_run(args, check=False):
        calls.append(args)

    monkeypatch.setattr(printing.subprocess, 'run', fake_run)

    printing.print_image(image)

    assert calls == [['xdg-open', str(tmp_path / 'wifi_qr_generator_print.png')]]


def test_print_image_raises_friendly_error_on_failure(monkeypatch, tmp_path, image):
    monkeypatch.setattr(printing.platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(printing.tempfile, 'gettempdir', lambda: str(tmp_path))

    def fake_run(args, check=False):
        raise OSError('xdg-open not found')

    monkeypatch.setattr(printing.subprocess, 'run', fake_run)

    with pytest.raises(RuntimeError, match='меню печати'):
        printing.print_image(image)


def test_print_image_unsupported_platform(monkeypatch, tmp_path, image):
    monkeypatch.setattr(printing.platform, 'system', lambda: 'PlanNine')
    monkeypatch.setattr(printing.tempfile, 'gettempdir', lambda: str(tmp_path))

    with pytest.raises(RuntimeError):
        printing.print_image(image)
