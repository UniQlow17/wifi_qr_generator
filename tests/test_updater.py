from app.core import updater


def test_is_newer_true_when_tag_ahead():
    assert updater.is_newer('v1.2.0', current_version='1.1.9') is True


def test_is_newer_false_when_tag_behind_or_equal():
    assert updater.is_newer('v1.0.0', current_version='1.0.0') is False
    assert updater.is_newer('v0.9.0', current_version='1.0.0') is False


def test_is_newer_false_on_unparseable_input():
    assert updater.is_newer('not-a-version', current_version='1.0.0') is False
    assert updater.is_newer('', current_version='1.0.0') is False
    assert updater.is_newer(None, current_version='1.0.0') is False


def test_find_asset_for_this_platform_matches_by_name(monkeypatch):
    monkeypatch.setattr(updater.platform, 'system', lambda: 'Windows')
    release_info = {
        'assets': [
            {'name': 'wifi_qr_generator-macos', 'browser_download_url': 'x'},
            {'name': 'wifi_qr_generator-windows.exe', 'browser_download_url': 'y'},
        ]
    }
    asset = updater.find_asset_for_this_platform(release_info)
    assert asset['browser_download_url'] == 'y'


def test_find_asset_for_this_platform_no_match(monkeypatch):
    monkeypatch.setattr(updater.platform, 'system', lambda: 'Windows')
    release_info = {'assets': [{'name': 'wifi_qr_generator-macos', 'browser_download_url': 'x'}]}
    assert updater.find_asset_for_this_platform(release_info) is None


def test_find_asset_for_this_platform_unsupported_platform(monkeypatch):
    monkeypatch.setattr(updater.platform, 'system', lambda: 'PlanNine')
    release_info = {'assets': [{'name': 'wifi_qr_generator-windows.exe'}]}
    assert updater.find_asset_for_this_platform(release_info) is None


def test_check_for_update_returns_none_when_offline(monkeypatch):
    monkeypatch.setattr(updater, 'fetch_latest_release', lambda: None)
    assert updater.check_for_update() is None


def test_check_for_update_returns_none_when_not_newer(monkeypatch):
    monkeypatch.setattr(
        updater, 'fetch_latest_release', lambda: {'tag_name': 'v0.0.1', 'assets': []}
    )
    assert updater.check_for_update() is None


def test_check_for_update_returns_none_when_no_matching_asset(monkeypatch):
    monkeypatch.setattr(
        updater, 'fetch_latest_release', lambda: {'tag_name': 'v99.0.0', 'assets': []}
    )
    monkeypatch.setattr(updater, 'find_asset_for_this_platform', lambda info: None)
    assert updater.check_for_update() is None


def test_check_for_update_returns_tag_and_asset(monkeypatch):
    asset = {'name': 'wifi_qr_generator-windows.exe', 'browser_download_url': 'https://x'}
    monkeypatch.setattr(
        updater, 'fetch_latest_release', lambda: {'tag_name': 'v99.0.0', 'assets': [asset]}
    )
    monkeypatch.setattr(updater, 'find_asset_for_this_platform', lambda info: asset)
    assert updater.check_for_update() == ('v99.0.0', asset)


def test_check_for_update_swallows_errors(monkeypatch):
    def boom():
        raise RuntimeError('network exploded')

    monkeypatch.setattr(updater, 'fetch_latest_release', boom)
    assert updater.check_for_update() is None


def test_download_and_relaunch_refuses_when_not_frozen(monkeypatch):
    monkeypatch.setattr(updater, 'is_frozen', lambda: False)
    try:
        updater.download_and_relaunch({'browser_download_url': 'https://x'})
        assert False, 'expected RuntimeError'
    except RuntimeError as exc:
        assert 'собранном приложении' in str(exc)
