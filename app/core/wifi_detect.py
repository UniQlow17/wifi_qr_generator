"""Best-effort detection of Wi-Fi networks known to the OS, using each
platform's native tooling. Every step is wrapped so that missing tools,
permission prompts, or unsupported platforms simply result in a partial
(or empty) result instead of an error.

Passwords are only ever fetched on demand for one SSID at a time (never
bulk-exported for every known network at once), so this module never has
a reason to persist them anywhere itself.
"""
import functools
import platform
import re
import subprocess


def _run(args, timeout=5):
    try:
        result = subprocess.run(args, capture_output=True, timeout=timeout)
        return result.stdout.decode('utf-8', errors='replace')
    except Exception:
        return None


# --------------------------------------------------------------------------
# Windows: native WLAN API (ctypes), not `netsh` text parsing. netsh's field
# labels (e.g. "Key Content") are translated on non-English Windows installs,
# which silently broke password lookup.
# --------------------------------------------------------------------------

MAX_INTERFACES = 16
MAX_PROFILES = 512

WLAN_INTERFACE_STATE_CONNECTED = 1
WLAN_INTF_OPCODE_CURRENT_CONNECTION = 7
WLAN_PROFILE_GET_PLAINTEXT_KEY = 0x00000004


@functools.lru_cache(maxsize=1)
def _win_types():
    import ctypes
    from ctypes import wintypes

    class GUID(ctypes.Structure):
        _fields_ = [
            ('Data1', wintypes.DWORD),
            ('Data2', wintypes.WORD),
            ('Data3', wintypes.WORD),
            ('Data4', ctypes.c_ubyte * 8),
        ]

    class WLAN_INTERFACE_INFO(ctypes.Structure):
        _fields_ = [
            ('InterfaceGuid', GUID),
            ('strInterfaceDescription', ctypes.c_wchar * 256),
            ('isState', ctypes.c_uint),
        ]

    class WLAN_INTERFACE_INFO_LIST(ctypes.Structure):
        _fields_ = [
            ('dwNumberOfItems', wintypes.DWORD),
            ('dwIndex', wintypes.DWORD),
            ('InterfaceInfo', WLAN_INTERFACE_INFO * MAX_INTERFACES),
        ]

    class DOT11_SSID(ctypes.Structure):
        _fields_ = [
            ('uSSIDLength', ctypes.c_ulong),
            ('ucSSID', ctypes.c_ubyte * 32),
        ]

    class WLAN_ASSOCIATION_ATTRIBUTES(ctypes.Structure):
        _fields_ = [
            ('dot11Ssid', DOT11_SSID),
            ('dot11BssType', ctypes.c_uint),
            ('dot11Bssid', ctypes.c_ubyte * 6),
            ('dot11PhyType', ctypes.c_uint),
            ('uDot11PhyIndex', ctypes.c_ulong),
            ('wlanSignalQuality', ctypes.c_ulong),
            ('ulRxRate', ctypes.c_ulong),
            ('ulTxRate', ctypes.c_ulong),
        ]

    class WLAN_SECURITY_ATTRIBUTES(ctypes.Structure):
        _fields_ = [
            ('bSecurityEnabled', ctypes.c_int),
            ('bOneXEnabled', ctypes.c_int),
            ('dot11AuthAlgorithm', ctypes.c_uint),
            ('dot11CipherAlgorithm', ctypes.c_uint),
        ]

    class WLAN_CONNECTION_ATTRIBUTES(ctypes.Structure):
        _fields_ = [
            ('isState', ctypes.c_uint),
            ('wlanConnectionMode', ctypes.c_uint),
            ('strProfileName', ctypes.c_wchar * 256),
            ('wlanAssociationAttributes', WLAN_ASSOCIATION_ATTRIBUTES),
            ('wlanSecurityAttributes', WLAN_SECURITY_ATTRIBUTES),
        ]

    class WLAN_PROFILE_INFO(ctypes.Structure):
        _fields_ = [
            ('strProfileName', ctypes.c_wchar * 256),
            ('dwFlags', wintypes.DWORD),
        ]

    class WLAN_PROFILE_INFO_LIST(ctypes.Structure):
        _fields_ = [
            ('dwNumberOfItems', wintypes.DWORD),
            ('dwIndex', wintypes.DWORD),
            ('ProfileInfo', WLAN_PROFILE_INFO * MAX_PROFILES),
        ]

    return {
        'ctypes': ctypes,
        'wintypes': wintypes,
        'WLAN_INTERFACE_INFO_LIST': WLAN_INTERFACE_INFO_LIST,
        'WLAN_CONNECTION_ATTRIBUTES': WLAN_CONNECTION_ATTRIBUTES,
        'WLAN_PROFILE_INFO_LIST': WLAN_PROFILE_INFO_LIST,
    }


class _WlanSession:
    """Opens a WLAN API handle and enumerates interfaces; closes everything
    on exit. Returns an empty interface list if wlanapi is unavailable."""

    def __init__(self):
        self.t = _win_types()
        self.ctypes = self.t['ctypes']
        self.wintypes = self.t['wintypes']
        self.wlanapi = None
        self.client_handle = None
        self.interfaces = []
        self._interface_list_ptr = None

    def __enter__(self):
        ctypes_ = self.ctypes
        wintypes = self.wintypes
        try:
            self.wlanapi = ctypes_.windll.wlanapi
        except (AttributeError, OSError):
            return self

        self.client_handle = wintypes.HANDLE()
        negotiated_version = wintypes.DWORD()
        if self.wlanapi.WlanOpenHandle(
            2, None, ctypes_.byref(negotiated_version), ctypes_.byref(self.client_handle)
        ) != 0:
            self.wlanapi = None
            return self

        self._interface_list_ptr = ctypes_.POINTER(self.t['WLAN_INTERFACE_INFO_LIST'])()
        if self.wlanapi.WlanEnumInterfaces(
            self.client_handle, None, ctypes_.byref(self._interface_list_ptr)
        ) != 0:
            return self

        info_list = self._interface_list_ptr.contents
        count = min(info_list.dwNumberOfItems, MAX_INTERFACES)
        self.interfaces = [info_list.InterfaceInfo[i] for i in range(count)]
        return self

    def get_profile_password(self, interface_guid, profile_name):
        ctypes_ = self.ctypes
        wintypes = self.wintypes
        profile_xml_ptr = ctypes_.c_wchar_p()
        flags = wintypes.DWORD(WLAN_PROFILE_GET_PLAINTEXT_KEY)
        granted_access = wintypes.DWORD()
        ret = self.wlanapi.WlanGetProfile(
            self.client_handle, ctypes_.byref(interface_guid), profile_name, None,
            ctypes_.byref(profile_xml_ptr), ctypes_.byref(flags), ctypes_.byref(granted_access),
        )
        if ret != 0:
            return None
        try:
            xml_str = profile_xml_ptr.value or ''
            # Without elevated (administrator) rights, Windows still returns
            # success but leaves the key DPAPI-encrypted for any profile
            # other than the currently active connection — signalled by
            # <protected>true</protected>. Returning that blob as if it were
            # the real password would silently bake garbage into the QR code.
            if re.search(r'<protected>true</protected>', xml_str, re.IGNORECASE):
                return None
            match = re.search(r'<keyMaterial>(.*?)</keyMaterial>', xml_str)
            return match.group(1) if match else None
        finally:
            self.wlanapi.WlanFreeMemory(profile_xml_ptr)

    def get_profile_names(self, interface_guid):
        ctypes_ = self.ctypes
        profile_list_ptr = ctypes_.POINTER(self.t['WLAN_PROFILE_INFO_LIST'])()
        ret = self.wlanapi.WlanGetProfileList(
            self.client_handle, ctypes_.byref(interface_guid), None,
            ctypes_.byref(profile_list_ptr),
        )
        if ret != 0:
            return []
        try:
            profile_list = profile_list_ptr.contents
            count = min(profile_list.dwNumberOfItems, MAX_PROFILES)
            return [profile_list.ProfileInfo[i].strProfileName for i in range(count)]
        finally:
            self.wlanapi.WlanFreeMemory(profile_list_ptr)

    def __exit__(self, *exc_info):
        ctypes_ = self.ctypes
        if self._interface_list_ptr:
            self.wlanapi.WlanFreeMemory(self._interface_list_ptr)
        if self.client_handle is not None and self.wlanapi is not None:
            self.wlanapi.WlanCloseHandle(self.client_handle, None)


def _detect_windows():
    ssid = None
    password = None

    with _WlanSession() as session:
        if not session.wlanapi:
            return None, None

        ctypes_ = session.ctypes
        wintypes = session.wintypes

        for iface in session.interfaces:
            if iface.isState != WLAN_INTERFACE_STATE_CONNECTED:
                continue

            data_size = wintypes.DWORD()
            data_ptr = ctypes_.c_void_p()
            opcode_type = ctypes_.c_uint()
            ret = session.wlanapi.WlanQueryInterface(
                session.client_handle, ctypes_.byref(iface.InterfaceGuid),
                WLAN_INTF_OPCODE_CURRENT_CONNECTION, None,
                ctypes_.byref(data_size), ctypes_.byref(data_ptr),
                ctypes_.byref(opcode_type),
            )
            if ret != 0:
                continue

            try:
                conn = ctypes_.cast(
                    data_ptr, ctypes_.POINTER(session.t['WLAN_CONNECTION_ATTRIBUTES'])
                ).contents
                dot11_ssid = conn.wlanAssociationAttributes.dot11Ssid
                ssid_bytes = bytes(dot11_ssid.ucSSID[:dot11_ssid.uSSIDLength])
                ssid = ssid_bytes.decode('utf-8', errors='replace')
                profile_name = conn.strProfileName
            finally:
                session.wlanapi.WlanFreeMemory(data_ptr)

            password = session.get_profile_password(iface.InterfaceGuid, profile_name)
            break

    return ssid, password


def _list_windows_known_ssids():
    ssids = []
    with _WlanSession() as session:
        if not session.wlanapi:
            return []
        for iface in session.interfaces:
            for name in session.get_profile_names(iface.InterfaceGuid):
                if name and name not in ssids:
                    ssids.append(name)
    return ssids


def _get_windows_password(ssid):
    with _WlanSession() as session:
        if not session.wlanapi:
            return None
        for iface in session.interfaces:
            password = session.get_profile_password(iface.InterfaceGuid, ssid)
            if password:
                return password
    return None


# --------------------------------------------------------------------------
# macOS
# --------------------------------------------------------------------------

def _macos_wifi_device():
    hw_output = _run(['networksetup', '-listallhardwareports'])
    if not hw_output:
        return None
    for block in hw_output.split('\n\n'):
        if 'Wi-Fi' in block or 'AirPort' in block:
            match = re.search(r'Device:\s*(\S+)', block)
            if match:
                return match.group(1)
    return None


def _get_macos_password(ssid):
    # Requires the user's Keychain consent; if denied or unavailable this
    # simply returns nothing.
    password = _run([
        'security', 'find-generic-password',
        '-D', 'AirPort network password',
        '-a', ssid, '-w',
    ])
    return password.strip() if password else None


def _detect_macos():
    ssid = None
    device = _macos_wifi_device()
    if device:
        ssid_output = _run(['networksetup', '-getairportnetwork', device])
        if ssid_output and ':' in ssid_output:
            ssid = ssid_output.split(':', 1)[1].strip()

    password = _get_macos_password(ssid) if ssid else None
    return ssid, password


def _list_macos_known_ssids():
    device = _macos_wifi_device()
    if not device:
        return []
    output = _run(['networksetup', '-listpreferredwirelessnetworks', device])
    if not output:
        return []
    # First line is a header ("Preferred networks on en0:"); the rest are
    # one indented SSID per line.
    return [line.strip() for line in output.splitlines()[1:] if line.strip()]


# --------------------------------------------------------------------------
# Linux (NetworkManager)
# --------------------------------------------------------------------------

def _get_linux_password(connection_name):
    password = _run([
        'nmcli', '-s', '-g', '802-11-wireless-security.psk',
        'connection', 'show', connection_name,
    ])
    return password.strip() if password else None


def _detect_linux():
    ssid = None
    active_output = _run(['nmcli', '-t', '-f', 'active,ssid', 'dev', 'wifi'])
    if active_output:
        for line in active_output.splitlines():
            if line.startswith('yes:'):
                ssid = line.split(':', 1)[1].strip()
                break

    password = _get_linux_password(ssid) if ssid else None
    return ssid, password


def _list_linux_known_ssids():
    output = _run(['nmcli', '-t', '-f', 'NAME,TYPE', 'connection', 'show'])
    if not output:
        return []
    ssids = []
    for line in output.splitlines():
        parts = line.split(':')
        if len(parts) >= 2 and parts[1] == '802-11-wireless' and parts[0] not in ssids:
            ssids.append(parts[0])
    return ssids


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def detect_current_wifi():
    """Return (ssid, password) for the currently connected network, best
    effort. Either value may be None if it could not be determined."""
    system = platform.system()
    try:
        if system == 'Windows':
            return _detect_windows()
        if system == 'Darwin':
            return _detect_macos()
        if system == 'Linux':
            return _detect_linux()
    except Exception:
        pass
    return None, None


def list_known_networks():
    """Return the SSIDs of every network this OS has a saved profile for
    (not just the currently connected one). Best effort, names only —
    passwords are fetched one at a time via get_saved_password()."""
    system = platform.system()
    try:
        if system == 'Windows':
            return _list_windows_known_ssids()
        if system == 'Darwin':
            return _list_macos_known_ssids()
        if system == 'Linux':
            return _list_linux_known_ssids()
    except Exception:
        pass
    return []


def get_saved_password(ssid):
    """Best-effort lookup of one specific known network's saved password."""
    system = platform.system()
    try:
        if system == 'Windows':
            return _get_windows_password(ssid)
        if system == 'Darwin':
            return _get_macos_password(ssid)
        if system == 'Linux':
            return _get_linux_password(ssid)
    except Exception:
        pass
    return None
