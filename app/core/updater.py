"""Checks GitHub Releases for a newer version and, if the user agrees,
downloads it and relaunches the app running the new version instead of
the old one.

Self-replacing a running executable only makes sense for a packaged
(PyInstaller) build — when running from source via `uv run main.py` there
is no single binary to swap, so download_and_relaunch() refuses and points
the caller at the releases page instead.

Windows note: a running .exe's file cannot simply be overwritten in place
(verified empirically — os.replace() onto the live file raises
PermissionError even though the file has already been closed by other
handles). The reliable approach, used here, is the classic one: download
the new build next to the current executable, then hand off to a tiny
detached helper script that waits for *this* process's PID to fully exit
before renaming the new file over the old one and starting it again.
"""
import functools
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from ..version import __version__

REPO = "UniQlow17/wifi_qr_generator"
RELEASES_API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE_URL = f"https://github.com/{REPO}/releases/latest"
USER_AGENT = "wifi-qr-generator-update-check"

ASSET_NAME_BY_PLATFORM = {
    "Windows": "wifi_qr_generator-windows.exe",
    "Darwin": "wifi_qr_generator-macos",
    "Linux": "wifi_qr_generator-linux",
}


def _parse_version(text):
    """Best-effort parse of a "vX.Y.Z" / "X.Y.Z" string into a tuple of
    ints for ordering comparisons. Returns None if unparseable."""
    if not text:
        return None
    match = re.match(r'v?(\d+)\.(\d+)\.(\d+)', text.strip())
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def is_newer(latest_tag, current_version=None):
    latest = _parse_version(latest_tag)
    current = _parse_version(current_version if current_version is not None else __version__)
    if latest is None or current is None:
        return False
    return latest > current


def fetch_latest_release(timeout=5):
    """Return the GitHub API JSON for the latest release, or None on any
    network/parsing failure (offline, rate-limited, no releases yet, ...)."""
    try:
        request = urllib.request.Request(
            RELEASES_API_URL,
            headers={'Accept': 'application/vnd.github+json', 'User-Agent': USER_AGENT},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode('utf-8'))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None


def find_asset_for_this_platform(release_info):
    asset_name = ASSET_NAME_BY_PLATFORM.get(platform.system())
    if not asset_name or not release_info:
        return None
    for asset in release_info.get('assets', []):
        if asset.get('name') == asset_name:
            return asset
    return None


def check_for_update():
    """Return (tag_name, asset_dict) if a newer release with a matching
    platform asset is available, else None. Best effort/never raises."""
    try:
        release_info = fetch_latest_release()
        if not release_info:
            return None
        tag_name = release_info.get('tag_name', '')
        if not is_newer(tag_name):
            return None
        asset = find_asset_for_this_platform(release_info)
        if not asset:
            return None
        return tag_name, asset
    except Exception:
        return None


def is_frozen():
    return getattr(sys, 'frozen', False)


def download_and_relaunch(asset, on_progress=None):
    """Download `asset` next to the running executable and hand off to a
    detached helper that swaps it in and restarts the app once this
    process exits. Raises RuntimeError with a user-facing message on
    failure. On success, does not return — the caller must exit the app
    immediately afterwards so the helper can finish the swap."""
    if not is_frozen():
        raise RuntimeError(
            "Автообновление доступно только в собранном приложении. "
            f"Скачайте новую версию вручную: {RELEASES_PAGE_URL}"
        )

    current_path = Path(sys.executable)
    new_path = current_path.with_name(current_path.name + '.update')

    _download(asset, new_path, on_progress=on_progress)

    if platform.system() != 'Windows':
        os.chmod(new_path, 0o755)

    _spawn_swap_helper(pid=os.getpid(), new_path=new_path, target_path=current_path)


def _download(asset, dest_path, on_progress=None):
    download_url = asset['browser_download_url']
    expected_size = asset.get('size')

    try:
        request = urllib.request.Request(download_url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(request, timeout=30) as response:
            total = int(response.headers.get('Content-Length') or expected_size or 0)
            downloaded = 0
            with open(dest_path, 'wb') as out_file:
                while True:
                    chunk = response.read(1024 * 256)
                    if not chunk:
                        break
                    out_file.write(chunk)
                    downloaded += len(chunk)
                    if on_progress and total:
                        on_progress(downloaded, total)
    except Exception as exc:
        dest_path.unlink(missing_ok=True)
        raise RuntimeError(f"Не удалось скачать обновление: {exc}") from exc

    if expected_size and dest_path.stat().st_size != expected_size:
        dest_path.unlink(missing_ok=True)
        raise RuntimeError("Скачанный файл повреждён (размер не совпадает с ожидаемым).")


def _spawn_swap_helper(pid, new_path, target_path):
    if platform.system() == 'Windows':
        _spawn_windows_swap_helper(pid, new_path, target_path)
    else:
        _spawn_posix_swap_helper(pid, new_path, target_path)


def _spawn_windows_swap_helper(pid, new_path, target_path):
    # A batch (.bat) helper relying on `tasklist | find` was tried first, but
    # on machines where Git for Windows' Unix tools precede System32 on PATH
    # (a common dev setup), `find` silently resolves to Git's own find.exe
    # instead of the Windows string-search tool, breaking the wait loop
    # forever — verified empirically. PowerShell's own cmdlets (Get-Process,
    # Move-Item, Start-Process) sidestep that whole class of PATH shadowing.
    script_path = Path(tempfile.gettempdir()) / 'wifi_qr_generator_update.ps1'
    new_path_escaped = str(new_path).replace("'", "''")
    target_path_escaped = str(target_path).replace("'", "''")
    script_path_escaped = str(script_path).replace("'", "''")
    script_path.write_text(
        f"while (Get-Process -Id {pid} -ErrorAction SilentlyContinue) {{\n"
        "    Start-Sleep -Seconds 1\n"
        "}\n"
        f"$newFile = '{new_path_escaped}'\n"
        f"$target = '{target_path_escaped}'\n"
        "$retries = 0\n"
        "while (Test-Path -LiteralPath $newFile) {\n"
        "    try {\n"
        "        Move-Item -LiteralPath $newFile -Destination $target -Force -ErrorAction Stop\n"
        "        break\n"
        "    } catch {\n"
        "        $retries++\n"
        "        if ($retries -ge 15) { break }\n"
        "        Start-Sleep -Seconds 1\n"
        "    }\n"
        "}\n"
        # $target always exists at this point — either the newly moved
        # build, or (if the move kept failing) the untouched old one — so
        # the app reliably comes back up either way instead of vanishing.
        "Start-Process -FilePath $target\n"
        f"Remove-Item -LiteralPath '{script_path_escaped}' -Force\n",
        encoding='utf-8',
    )
    powershell_exe = str(
        Path(os.environ.get('SystemRoot', r'C:\Windows'))
        / 'System32' / 'WindowsPowerShell' / 'v1.0' / 'powershell.exe'
    )
    # DETACHED_PROCESS (no console at all) was tried first but made
    # powershell.exe exit immediately without running anything — verified
    # empirically. CREATE_NO_WINDOW (hidden console, still allocated) is
    # what actually keeps it alive after this process exits.
    subprocess.Popen(
        [powershell_exe, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script_path)],
        creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
    )


def _spawn_posix_swap_helper(pid, new_path, target_path):
    script_path = Path(tempfile.gettempdir()) / 'wifi_qr_generator_update.sh'
    script_path.write_text(
        "#!/bin/sh\n"
        f"while kill -0 {pid} 2>/dev/null; do sleep 0.5; done\n"
        "retries=0\n"
        f'while [ -f "{new_path}" ]; do\n'
        f'    mv -f "{new_path}" "{target_path}" 2>/dev/null && break\n'
        "    retries=$((retries + 1))\n"
        "    if [ \"$retries\" -ge 15 ]; then break; fi\n"
        "    sleep 1\n"
        "done\n"
        f'chmod +x "{target_path}"\n'
        f'"{target_path}" &\n'
        f'rm -f "{script_path}"\n',
        encoding='utf-8',
    )
    os.chmod(script_path, 0o755)
    subprocess.Popen(['/bin/sh', str(script_path)], start_new_session=True, close_fds=True)
