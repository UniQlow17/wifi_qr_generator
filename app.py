from flask import Flask, render_template, request, jsonify
import qrcode
from PIL import Image, ImageDraw, ImageFont
import io
import base64

app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/generate_qr', methods=['POST'])
def generate_qr():
    ssid = request.form.get('ssid')
    password = request.form.get('password', '')
    encryption = request.form.get('encryption', 'WPA')

    if not ssid:
        return jsonify({'error': 'SSID is required'}), 400

    # Format the Wi-Fi string
    wifi_string = f"WIFI:S:{ssid};T:{encryption};P:{password};;"

    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(wifi_string)
    qr.make(fit=True)

    img_qr = qr.make_image(fill_color="black", back_color="white").convert(
        'RGB')

    # Add SSID text on top
    text_to_display = f"WIFI: {ssid}"
    font_size = 50  # Further increased font size
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except IOError:
        # Fallback to default font if arial.ttf is not found
        font = ImageFont.load_default()

    # Calculate text size
    dummy_draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    text_bbox = dummy_draw.textbbox((0, 0), text_to_display, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]

    # Create a new image with space for text
    # Ensure the new image width is at least the QR code width or text width
    max_width = max(img_qr.width,
                    text_width + 80)  # Increased padding for text
    new_img_height = img_qr.height + text_height + 50  # Increased padding between text and QR

    new_img = Image.new('RGB', (max_width, new_img_height), 'white')
    draw = ImageDraw.Draw(new_img)

    # Center text
    text_x = (new_img.width - text_width) / 2
    text_y = 15  # Adjusted Y for text
    draw.text((text_x, text_y), text_to_display, font=font, fill=(0, 0, 0))

    # Paste QR code below text, centered horizontally
    qr_x = (new_img.width - img_qr.width) / 2
    new_img.paste(img_qr, (
    int(qr_x), int(text_y + text_height + 25)))  # Adjusted padding

    # Save image to a byte stream
    byte_io = io.BytesIO()
    new_img.save(byte_io, 'PNG')
    byte_io.seek(0)

    # Encode to base64
    encoded_img = base64.b64encode(byte_io.getvalue()).decode('ascii')

    return jsonify({'qr_code': f'data:image/png;base64,{encoded_img}'})


if __name__ == '__main__':
    app.run(debug=True)
