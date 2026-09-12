"""Persists previously used SSIDs between runs of the desktop app."""
import json
from pathlib import Path

CONFIG_DIR = Path.home() / '.wifi_qr_generator'
SSIDS_FILE = CONFIG_DIR / 'saved_ssids.json'


def load_ssids():
    try:
        with open(SSIDS_FILE, 'r', encoding='utf-8') as f:
            ssids = json.load(f)
            return [s for s in ssids if isinstance(s, str)]
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []


def save_ssid(ssid):
    ssids = load_ssids()
    if ssid in ssids:
        return ssids

    ssids.append(ssid)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(SSIDS_FILE, 'w', encoding='utf-8') as f:
        json.dump(ssids, f, ensure_ascii=False, indent=2)
    return ssids
