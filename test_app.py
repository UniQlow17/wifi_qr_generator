import pytest
from app import app
import json
import base64


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_index_page(client):
    """Test that the index page loads successfully."""
    response = client.get('/')
    assert response.status_code == 200
    assert b"QR Wi-Fi Generator" in response.data


def test_generate_qr_success(client):
    """Test successful QR code generation."""
    response = client.post('/generate_qr', data={
        'ssid': 'TestNetwork',
        'password': 'testpassword',
        'encryption': 'WPA'
    })
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'qr_code' in data
    assert data['qr_code'].startswith('data:image/png;base64,')
    # Decode base64 to check if it's a valid image (optional, more complex)
    # img_data = base64.b64decode(data['qr_code'].split(',')[1])
    # assert len(img_data) > 0 # Simple check for non-empty image data


def test_generate_qr_missing_ssid(client):
    """Test QR code generation with missing SSID."""
    response = client.post('/generate_qr', data={
        'password': 'testpassword',
        'encryption': 'WPA'
    })
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data
    assert data['error'] == 'SSID is required'


def test_generate_qr_no_password_none_encryption(client):
    """Test QR code generation with no password and 'None' encryption."""
    response = client.post('/generate_qr', data={
        'ssid': 'OpenNetwork',
        'password': '',
        'encryption': 'nopass'
    })
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'qr_code' in data


def test_generate_qr_wep_encryption(client):
    """Test QR code generation with WEP encryption."""
    response = client.post('/generate_qr', data={
        'ssid': 'WEPNetwork',
        'password': 'wepkey',
        'encryption': 'WEP'
    })
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'qr_code' in data
