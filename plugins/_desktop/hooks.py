from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any

from helpers import files, state_migration, system_packages

LIBREOFFICE_RUNTIME_PACKAGES = (
    "libreoffice-core",
    "libreoffice-writer",
    "libreoffice-calc",
    "libreoffice-impress",
    "libreoffice-gtk3",
    "python3-uno",
)
XPRA_SOURCE_FILE = Path("/etc/apt/sources.list.d/xpra.sources")
XPRA_KEYRING_FILE = Path("/usr/share/keyrings/xpra.asc")
XPRA_KEY_URL = "https://xpra.org/xpra.asc"
XPRA_VERSION = "6.5.2-r0-1"
GTK_RUNTIME_PACKAGE = "gir1.2-gtk-3.0"
ATK_VERSION = "2.60.3-1"
ATK_RUNTIME_PACKAGES = (
    "at-spi2-common",
    "libatk1.0-0t64",
    "libatk-bridge2.0-0t64",
    "libatspi2.0-0t64",
    "gir1.2-atk-1.0",
)
ATK_OPTIONAL_PACKAGES = ("at-spi2-core", "gir1.2-atspi-2.0")
XPRA_VERSIONED_RUNTIME_PACKAGES = frozenset(
    {
        "xpra-common",
        "xpra-server",
        "xpra-client",
        "xpra-client-gtk3",
        "xpra-x11",
    }
)
RUNTIME_PACKAGES = (
    *LIBREOFFICE_RUNTIME_PACKAGES,
    GTK_RUNTIME_PACKAGE,
    "xpra-common",
    "xpra-server",
    "xpra-client",
    "xpra-client-gtk3",
    "xpra-x11",
    "xpra-html5",
    "xfce4-session",
    "xfwm4",
    "xfce4-panel",
    "xfdesktop4",
    "xfce4-settings",
    "thunar",
    "gvfs",
    "libglib2.0-bin",
    "xfce4-terminal",
    "x11-xserver-utils",
    "x11-utils",
    "x11-apps",
    "xdotool",
    "xclip",
    "xauth",
    "dbus-x11",
    "python3-pil",
    "fonts-dejavu",
    "fonts-liberation",
    "fonts-crosextra-caladea",
    "fonts-crosextra-carlito",
    "fonts-noto-core",
    "fonts-noto-cjk",
    "fonts-noto-color-emoji",
)
RETIRED_RUNTIME_PACKAGES = (
    "firefox-esr",
)
PLUGIN_NAME = "_desktop"
STATE_DIR = Path(files.get_abs_path("usr", "plugins", PLUGIN_NAME))
RETIRED_STATE_DIR = Path(files.get_abs_path("usr", PLUGIN_NAME))
_preparation_lock = threading.RLock()
_preparation_state: dict[str, Any] = {
    "preparing": False,
    "active_count": 0,
    "started_at": 0.0,
    "completed_at": 0.0,
    "result": None,
    "error": "",
}


def cleanup_stale_runtime_state(force: bool = False) -> dict[str, Any]:
    """Prepare the Linux Desktop runtime and reap stale Desktop sessions."""

    _begin_runtime_preparation()
    result: dict[str, Any] | None = None
    error = ""
    try:
        installed: list[str] = []
        removed: list[str] = []
        migrated: list[str] = []
        warnings: list[str] = []
        errors: list[str] = []

        _migrate_retired_plugin_state(migrated, warnings, errors)
        _remove_persisted_screenshots(warnings, errors)

        retired_packages = _installed_packages(RETIRED_RUNTIME_PACKAGES)
        if retired_packages:
            _purge_packages(removed, errors, installed_packages=retired_packages)

        _ensure_runtime_dependencies(installed, errors)
        _cleanup_desktop_sessions(errors)

        result = {
            "ok": not errors,
            "skipped": False,
            "removed": removed,
            "installed": installed,
            "migrated": migrated,
            "warnings": warnings,
            "errors": errors,
        }
        return result
    except Exception as exc:
        error = str(exc)
        raise
    finally:
        _finish_runtime_preparation(result=result, error=error)


def runtime_preparation_status() -> dict[str, Any]:
    with _preparation_lock:
        return {
            "preparing": bool(_preparation_state["preparing"]),
            "active_count": int(_preparation_state["active_count"]),
            "started_at": float(_preparation_state["started_at"]),
            "completed_at": float(_preparation_state["completed_at"]),
            "result": _preparation_state["result"],
            "error": str(_preparation_state["error"]),
        }


def _migrate_retired_plugin_state(
    migrated: list[str],
    warnings: list[str],
    errors: list[str],
) -> None:
    state_migration.migrate_retired_state_tree(
        source=RETIRED_STATE_DIR,
        destination=STATE_DIR,
        owner="Desktop",
        migrated=migrated,
        warnings=warnings,
        errors=errors,
    )


def _remove_persisted_screenshots(
    warnings: list[str],
    errors: list[str],
) -> None:
    screenshots_dir = STATE_DIR / "screenshots"
    if not screenshots_dir.exists():
        return
    try:
        shutil.rmtree(screenshots_dir)
        warnings.append(f"Removed retired persistent Desktop screenshots: {screenshots_dir}")
    except Exception as exc:
        errors.append(f"Failed to remove retired persistent Desktop screenshots at {screenshots_dir}: {exc}")


def _begin_runtime_preparation() -> None:
    with _preparation_lock:
        if not _preparation_state["active_count"]:
            _preparation_state["preparing"] = True
            _preparation_state["started_at"] = time.time()
            _preparation_state["completed_at"] = 0.0
            _preparation_state["result"] = None
            _preparation_state["error"] = ""
        _preparation_state["active_count"] = int(_preparation_state["active_count"]) + 1


def _finish_runtime_preparation(
    *,
    result: dict[str, Any] | None = None,
    error: str = "",
) -> None:
    with _preparation_lock:
        active_count = max(0, int(_preparation_state["active_count"]) - 1)
        _preparation_state["active_count"] = active_count
        if result is not None:
            _preparation_state["result"] = result
        if error:
            _preparation_state["error"] = error
        if active_count:
            return
        _preparation_state["preparing"] = False
        _preparation_state["completed_at"] = time.time()


def _installed_packages(packages: tuple[str, ...]) -> list[str]:
    if not shutil.which("dpkg-query"):
        return []
    return [package for package in packages if _package_installed(package)]


def _package_installed(package: str) -> bool:
    result = subprocess.run(
        ["dpkg-query", "-W", "-f=${Status}", package],
        check=False,
        text=True,
        capture_output=True,
        timeout=8,
    )
    return result.returncode == 0 and "install ok installed" in result.stdout


def _package_version(package: str) -> str:
    result = subprocess.run(
        ["dpkg-query", "-W", "-f=${Version}", package],
        check=False,
        text=True,
        capture_output=True,
        timeout=8,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _purge_packages(
    removed: list[str],
    errors: list[str],
    *,
    installed_packages: list[str] | None = None,
) -> None:
    if os.geteuid() != 0 or not shutil.which("apt-get") or not shutil.which("dpkg-query"):
        return
    installed = installed_packages if installed_packages is not None else []
    if not installed:
        return
    result = _run_apt_command(["apt-get", "purge", "-y", *installed], timeout=180)
    if result.returncode == 0:
        removed.extend(installed)
        return
    errors.append((result.stderr or result.stdout or "apt-get purge failed").strip())


def _ensure_runtime_dependencies(installed: list[str], errors: list[str]) -> None:
    if os.geteuid() != 0 or not shutil.which("apt-get") or not shutil.which("dpkg-query"):
        return
    missing = [package for package in RUNTIME_PACKAGES if not _package_installed(package)]
    if not missing:
        return

    if not _apt_update(errors):
        return
    if not _ensure_kali_gtk_runtime(installed, errors):
        return
    missing = [package for package in missing if not _package_installed(package)]

    required_xpra_missing = [package for package in missing if package.startswith("xpra")]
    if required_xpra_missing and not _package_candidates_available(required_xpra_missing):
        previous_error_count = len(errors)
        _ensure_xpra_repository(installed, errors)
        if len(errors) > previous_error_count or not _apt_update(errors, xpra_only=True):
            return
        missing = [package for package in RUNTIME_PACKAGES if not _package_installed(package)]
        if not missing:
            return

    if missing:
        _install_runtime_packages(missing, installed, errors)


def _ensure_kali_gtk_runtime(installed: list[str], errors: list[str]) -> bool:
    if (
        GTK_RUNTIME_PACKAGE not in RUNTIME_PACKAGES
        or _package_installed(GTK_RUNTIME_PACKAGE)
        or _read_os_release().get("ID") != "kali"
        or _package_installed("gir1.2-atk-1.0")
    ):
        return True

    packages = [
        *ATK_RUNTIME_PACKAGES,
        *(package for package in ATK_OPTIONAL_PACKAGES if _package_installed(package)),
    ]
    # Keep ATK's version-locked libraries together when repairing older rolling bases.
    result = _run_apt_command(
        [
            "apt-get", "install", "-y", "--no-install-recommends", "--allow-downgrades",
            *(f"{package}={ATK_VERSION}" for package in packages),
            GTK_RUNTIME_PACKAGE,
        ],
        timeout=900,
    )
    if result.returncode == 0:
        installed.append(GTK_RUNTIME_PACKAGE)
        return True
    errors.append((result.stderr or result.stdout or "GTK runtime install failed").strip())
    return False


def _install_runtime_packages(
    packages: list[str],
    installed: list[str],
    errors: list[str],
) -> bool:
    xpra_version = ""
    if any(package in XPRA_VERSIONED_RUNTIME_PACKAGES for package in packages):
        xpra_version = _package_version("xpra-common") or XPRA_VERSION
    package_specs = [
        f"{package}={xpra_version}" if package in XPRA_VERSIONED_RUNTIME_PACKAGES else package
        for package in packages
    ]
    result = _run_apt_command(
        ["apt-get", "install", "-y", "--no-install-recommends", *package_specs],
        timeout=900,
    )
    if result.returncode == 0:
        installed.extend(packages)
        return True
    output = (result.stderr or result.stdout or "apt-get install failed").strip()
    errors.append(output)
    return False


def _apt_update(errors: list[str], *, xpra_only: bool = False) -> bool:
    command = (
        ["bash", files.get_abs_path("plugins/_desktop/helpers/refresh_xpra_index.sh"), str(XPRA_SOURCE_FILE)]
        if xpra_only else ["apt-get", "update"]
    )
    result = _run_apt_command(command, timeout=300)
    if result.returncode == 0:
        return True
    errors.append((result.stderr or result.stdout or "apt-get update failed").strip())
    return False


def _package_candidate_available(package: str) -> bool:
    if not shutil.which("apt-cache"):
        return True
    result = subprocess.run(
        ["apt-cache", "policy", package],
        check=False,
        text=True,
        capture_output=True,
        timeout=15,
    )
    if result.returncode != 0:
        return True
    if not result.stdout.strip():
        return False
    return "Candidate: (none)" not in result.stdout


def _package_candidates_available(packages: list[str]) -> bool:
    return all(_package_candidate_available(package) for package in packages)


def _ensure_xpra_repository(installed: list[str], errors: list[str]) -> None:
    if not _package_installed("ca-certificates"):
        result = _run_apt_command(
            ["apt-get", "install", "-y", "--no-install-recommends", "ca-certificates"],
            timeout=180,
        )
        if result.returncode != 0:
            errors.append((result.stderr or result.stdout or "apt-get install ca-certificates failed").strip())
            return
        installed.append("ca-certificates")

    try:
        key = _download(XPRA_KEY_URL)
        XPRA_KEYRING_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not XPRA_KEYRING_FILE.exists() or XPRA_KEYRING_FILE.read_bytes() != key:
            XPRA_KEYRING_FILE.write_bytes(key)

        XPRA_SOURCE_FILE.parent.mkdir(parents=True, exist_ok=True)
        source = _xpra_repository_source()
        if not XPRA_SOURCE_FILE.exists() or XPRA_SOURCE_FILE.read_text(encoding="utf-8") != source:
            XPRA_SOURCE_FILE.write_text(source, encoding="utf-8")
    except Exception as exc:
        errors.append(f"Xpra repository setup failed: {exc}")


def _download(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=45) as response:
        return response.read()


def _run_apt_command(command: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
    return system_packages.run_runtime_apt(command, timeout=timeout)


def _xpra_repository_source() -> str:
    os_release = _read_os_release()
    os_id = os_release.get("ID", "")
    codename = os_release.get("VERSION_CODENAME", "")
    arch = _dpkg_architecture()

    uri = "https://xpra.org"
    suite = "trixie" if os_id == "kali" or codename in {"sid", "forky"} else codename or "trixie"

    return (
        f"Types: deb\n"
        f"URIs: {uri}\n"
        f"Suites: {suite}\n"
        f"Components: main\n"
        f"Signed-By: {XPRA_KEYRING_FILE}\n"
        f"Architectures: {arch}\n"
    )


def _read_os_release() -> dict[str, str]:
    path = Path("/etc/os-release")
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value.strip().strip('"')
    return values


def _dpkg_architecture() -> str:
    result = subprocess.run(
        ["dpkg", "--print-architecture"],
        check=False,
        text=True,
        capture_output=True,
        timeout=8,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return "amd64"


def _cleanup_desktop_sessions(errors: list[str]) -> None:
    try:
        from plugins._desktop.helpers import desktop_session

        result = desktop_session.cleanup_stale_runtime_state()
        errors.extend(str(item) for item in result.get("errors") or [])
    except Exception as exc:
        errors.append(f"Desktop cleanup failed: {exc}")
