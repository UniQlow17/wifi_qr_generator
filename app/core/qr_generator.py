"""Builds a Wi-Fi QR code image with the SSID printed above it."""
import qrcode
from PIL import Image, ImageDraw, ImageFont


def generate_wifi_qr_image(ssid, password='', encryption='WPA'):
    wifi_string = f"WIFI:S:{ssid};T:{encryption};P:{password};;"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(wifi_string)
    qr.make(fit=True)

    img_qr = qr.make_image(fill_color="black", back_color="white").convert('RGB')

    text_to_display = f"WIFI: {ssid}"
    try:
        font = ImageFont.truetype("arial.ttf", 50)
    except IOError:
        font = ImageFont.load_default()

    dummy_draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    text_bbox = dummy_draw.textbbox((0, 0), text_to_display, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]

    max_width = max(img_qr.width, text_width + 80)
    new_img_height = img_qr.height + text_height + 50

    new_img = Image.new('RGB', (max_width, new_img_height), 'white')
    draw = ImageDraw.Draw(new_img)

    text_x = (new_img.width - text_width) / 2
    text_y = 15
    draw.text((text_x, text_y), text_to_display, font=font, fill=(0, 0, 0))

    qr_x = (new_img.width - img_qr.width) / 2
    new_img.paste(img_qr, (int(qr_x), int(text_y + text_height + 25)))

    return new_img
