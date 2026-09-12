from app.core import wifi_detect


def test_detect_current_wifi_unsupported_platform(monkeypatch):
    monkeypatch.setattr(wifi_detect.platform, 'system', lambda: 'PlanNine')
    assert wifi_detect.detect_current_wifi() == (None, None)


def test_detect_current_wifi_swallows_platform_specific_errors(monkeypatch):
    def boom():
        raise RuntimeError('no wifi hardware')

    monkeypatch.setattr(wifi_detect.platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(wifi_detect, '_detect_linux', boom)
    assert wifi_detect.detect_current_wifi() == (None, None)


def test_list_known_networks_unsupported_platform(monkeypatch):
    monkeypatch.setattr(wifi_detect.platform, 'system', lambda: 'PlanNine')
    assert wifi_detect.list_known_networks() == []


def test_list_known_networks_dispatches_by_platform(monkeypatch):
    monkeypatch.setattr(wifi_detect.platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(
        wifi_detect, '_list_linux_known_ssids', lambda: ['Home', 'Office']
    )
    assert wifi_detect.list_known_networks() == ['Home', 'Office']


def test_list_known_networks_swallows_errors(monkeypatch):
    def boom():
        raise RuntimeError('nmcli not found')

    monkeypatch.setattr(wifi_detect.platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(wifi_detect, '_list_linux_known_ssids', boom)
    assert wifi_detect.list_known_networks() == []


def test_get_saved_password_unsupported_platform(monkeypatch):
    monkeypatch.setattr(wifi_detect.platform, 'system', lambda: 'PlanNine')
    assert wifi_detect.get_saved_password('Home') is None


def test_get_saved_password_dispatches_by_platform(monkeypatch):
    monkeypatch.setattr(wifi_detect.platform, 'system', lambda: 'Darwin')
    monkeypatch.setattr(wifi_detect, '_get_macos_password', lambda ssid: f'pw-for-{ssid}')
    assert wifi_detect.get_saved_password('Home') == 'pw-for-Home'


def test_get_saved_password_swallows_errors(monkeypatch):
    def boom(ssid):
        raise RuntimeError('keychain access denied')

    monkeypatch.setattr(wifi_detect.platform, 'system', lambda: 'Darwin')
    monkeypatch.setattr(wifi_detect, '_get_macos_password', boom)
    assert wifi_detect.get_saved_password('Home') is None
