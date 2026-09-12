from app.core import storage


def test_load_ssids_missing_file_returns_empty_list(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'SSIDS_FILE', tmp_path / 'saved_ssids.json')
    assert storage.load_ssids() == []


def test_save_ssid_persists_and_dedupes(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'CONFIG_DIR', tmp_path)
    monkeypatch.setattr(storage, 'SSIDS_FILE', tmp_path / 'saved_ssids.json')

    storage.save_ssid('HomeNetwork')
    storage.save_ssid('OfficeNetwork')
    storage.save_ssid('HomeNetwork')  # duplicate, should not be added again

    assert storage.load_ssids() == ['HomeNetwork', 'OfficeNetwork']


def test_load_ssids_ignores_corrupted_file(tmp_path, monkeypatch):
    ssids_file = tmp_path / 'saved_ssids.json'
    ssids_file.write_text('not valid json', encoding='utf-8')
    monkeypatch.setattr(storage, 'SSIDS_FILE', ssids_file)
    assert storage.load_ssids() == []
