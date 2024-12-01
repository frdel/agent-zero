from __future__ import annotations

import importlib
import os
import sys
import typing

import pytest

from platformdirs import unix
from platformdirs.unix import Unix

if typing.TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


@pytest.mark.parametrize(
    "prop",
    [
        "user_documents_dir",
        "user_downloads_dir",
        "user_pictures_dir",
        "user_videos_dir",
        "user_music_dir",
        "user_desktop_dir",
    ],
)
def test_user_media_dir(mocker: MockerFixture, prop: str) -> None:
    example_path = "/home/example/ExampleMediaFolder"
    mock = mocker.patch("platformdirs.unix._get_user_dirs_folder")
    mock.return_value = example_path
    assert getattr(Unix(), prop) == example_path


@pytest.mark.parametrize(
    ("env_var", "prop"),
    [
        pytest.param("XDG_DOCUMENTS_DIR", "user_documents_dir", id="user_documents_dir"),
        pytest.param("XDG_DOWNLOAD_DIR", "user_downloads_dir", id="user_downloads_dir"),
        pytest.param("XDG_PICTURES_DIR", "user_pictures_dir", id="user_pictures_dir"),
        pytest.param("XDG_VIDEOS_DIR", "user_videos_dir", id="user_videos_dir"),
        pytest.param("XDG_MUSIC_DIR", "user_music_dir", id="user_music_dir"),
        pytest.param("XDG_DESKTOP_DIR", "user_desktop_dir", id="user_desktop_dir"),
    ],
)
def test_user_media_dir_env_var(mocker: MockerFixture, env_var: str, prop: str) -> None:
    # Mock media dir not being in user-dirs.dirs file
    mock = mocker.patch("platformdirs.unix._get_user_dirs_folder")
    mock.return_value = None

    example_path = "/home/example/ExampleMediaFolder"
    mocker.patch.dict(os.environ, {env_var: example_path})

    assert getattr(Unix(), prop) == example_path


@pytest.mark.parametrize(
    ("env_var", "prop", "default_abs_path"),
    [
        pytest.param("XDG_DOCUMENTS_DIR", "user_documents_dir", "/home/example/Documents", id="user_documents_dir"),
        pytest.param("XDG_DOWNLOAD_DIR", "user_downloads_dir", "/home/example/Downloads", id="user_downloads_dir"),
        pytest.param("XDG_PICTURES_DIR", "user_pictures_dir", "/home/example/Pictures", id="user_pictures_dir"),
        pytest.param("XDG_VIDEOS_DIR", "user_videos_dir", "/home/example/Videos", id="user_videos_dir"),
        pytest.param("XDG_MUSIC_DIR", "user_music_dir", "/home/example/Music", id="user_music_dir"),
        pytest.param("XDG_DESKTOP_DIR", "user_desktop_dir", "/home/example/Desktop", id="user_desktop_dir"),
    ],
)
def test_user_media_dir_default(mocker: MockerFixture, env_var: str, prop: str, default_abs_path: str) -> None:
    # Mock media dir not being in user-dirs.dirs file
    mock = mocker.patch("platformdirs.unix._get_user_dirs_folder")
    mock.return_value = None

    # Mock no XDG env variable being set
    mocker.patch.dict(os.environ, {env_var: ""})

    # Mock home directory
    mocker.patch.dict(os.environ, {"HOME": "/home/example"})
    # Mock home directory for running the test on Windows
    mocker.patch.dict(os.environ, {"USERPROFILE": "/home/example"})

    assert getattr(Unix(), prop) == default_abs_path


class XDGVariable(typing.NamedTuple):
    name: str
    default_value: str


def _func_to_path(func: str) -> XDGVariable | None:
    mapping = {
        "user_data_dir": XDGVariable("XDG_DATA_HOME", "~/.local/share"),
        "site_data_dir": XDGVariable("XDG_DATA_DIRS", f"/usr/local/share{os.pathsep}/usr/share"),
        "user_config_dir": XDGVariable("XDG_CONFIG_HOME", "~/.config"),
        "site_config_dir": XDGVariable("XDG_CONFIG_DIRS", "/etc/xdg"),
        "user_cache_dir": XDGVariable("XDG_CACHE_HOME", "~/.cache"),
        "user_state_dir": XDGVariable("XDG_STATE_HOME", "~/.local/state"),
        "user_log_dir": XDGVariable("XDG_STATE_HOME", "~/.local/state"),
        "user_runtime_dir": XDGVariable("XDG_RUNTIME_DIR", "/run/user/1234"),
        "site_runtime_dir": XDGVariable("XDG_RUNTIME_DIR", "/run"),
    }
    return mapping.get(func)


@pytest.fixture()
def dirs_instance() -> Unix:
    return Unix(multipath=True, opinion=False)


@pytest.fixture()
def _getuid(mocker: MockerFixture) -> None:
    mocker.patch("platformdirs.unix.getuid", return_value=1234)


@pytest.mark.usefixtures("_getuid")
def test_xdg_variable_not_set(monkeypatch: pytest.MonkeyPatch, dirs_instance: Unix, func: str) -> None:
    xdg_variable = _func_to_path(func)
    if xdg_variable is None:
        return

    monkeypatch.delenv(xdg_variable.name, raising=False)
    result = getattr(dirs_instance, func)
    assert result == os.path.expanduser(xdg_variable.default_value)  # noqa: PTH111


@pytest.mark.usefixtures("_getuid")
def test_xdg_variable_empty_value(monkeypatch: pytest.MonkeyPatch, dirs_instance: Unix, func: str) -> None:
    xdg_variable = _func_to_path(func)
    if xdg_variable is None:
        return

    monkeypatch.setenv(xdg_variable.name, "")
    result = getattr(dirs_instance, func)
    assert result == os.path.expanduser(xdg_variable.default_value)  # noqa: PTH111


@pytest.mark.usefixtures("_getuid")
def test_xdg_variable_custom_value(monkeypatch: pytest.MonkeyPatch, dirs_instance: Unix, func: str) -> None:
    xdg_variable = _func_to_path(func)
    if xdg_variable is None:
        return

    monkeypatch.setenv(xdg_variable.name, "/custom-dir")
    result = getattr(dirs_instance, func)
    assert result == "/custom-dir"


@pytest.mark.usefixtures("_getuid")
@pytest.mark.parametrize("platform", ["freebsd", "openbsd", "netbsd"])
def test_platform_on_bsd(monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture, platform: str) -> None:
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    mocker.patch("sys.platform", platform)

    assert Unix().site_runtime_dir == "/var/run"

    mocker.patch("pathlib.Path.exists", return_value=True)
    assert Unix().user_runtime_dir == "/var/run/user/1234"

    mocker.patch("pathlib.Path.exists", return_value=False)
    assert Unix().user_runtime_dir == "/tmp/runtime-1234"  # noqa: S108


def test_platform_on_win32(monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    mocker.patch("sys.platform", "win32")
    prev_unix = unix
    importlib.reload(unix)
    try:
        with pytest.raises(RuntimeError, match="should only be used on Unix"):
            unix.Unix().user_runtime_dir  # noqa: B018
    finally:
        sys.modules["platformdirs.unix"] = prev_unix


def test_ensure_exists_creates_folder(mocker: MockerFixture, tmp_path: Path) -> None:
    mocker.patch.dict(os.environ, {"XDG_DATA_HOME": str(tmp_path)})
    data_path = Unix(appname="acme", ensure_exists=True).user_data_path
    assert data_path.exists()


def test_folder_not_created_without_ensure_exists(mocker: MockerFixture, tmp_path: Path) -> None:
    mocker.patch.dict(os.environ, {"XDG_DATA_HOME": str(tmp_path)})
    data_path = Unix(appname="acme", ensure_exists=False).user_data_path
    assert not data_path.exists()
