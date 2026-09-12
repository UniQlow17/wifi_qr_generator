from PIL import Image

from app.core.qr_generator import generate_wifi_qr_image


def test_generate_wifi_qr_image_returns_image():
    image = generate_wifi_qr_image('TestNetwork', 'testpassword', 'WPA')
    assert isinstance(image, Image.Image)
    assert image.width > 0
    assert image.height > 0


def test_generate_wifi_qr_image_no_password_open_network():
    image = generate_wifi_qr_image('OpenNetwork', '', 'nopass')
    assert isinstance(image, Image.Image)


def test_generate_wifi_qr_image_wep_encryption():
    image = generate_wifi_qr_image('WEPNetwork', 'wepkey', 'WEP')
    assert isinstance(image, Image.Image)
