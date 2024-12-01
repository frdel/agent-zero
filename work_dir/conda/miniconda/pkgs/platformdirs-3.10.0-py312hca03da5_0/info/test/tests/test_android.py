from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

from platformdirs.android import Android

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"appname": "foo"},
        {"appname": "foo", "appauthor": "bar"},
        {"appname": "foo", "appauthor": "bar", "version": "v1.0"},
        {"appname": "foo", "appauthor": "bar", "version": "v1.0", "opinion": False},
    ],
    ids=[
        "no_args",
        "app_name",
        "app_name_with_app_author",
        "app_name_author_version",
        "app_name_author_version_false_opinion",
    ],
)
def test_android(mocker: MockerFixture, params: dict[str, Any], func: str) -> None:
    mocker.patch("platformdirs.android._android_folder", return_value="/data/data/com.example", autospec=True)
    mocker.patch("platformdirs.android.os.path.join", lambda *args: "/".join(args))
    result = getattr(Android(**params), func)

    suffix_elements = []
    if "appname" in params:
        suffix_elements.append(params["appname"])
    if "version" in params:
        suffix_elements.append(params["version"])
    if suffix_elements:
        suffix_elements.insert(0, "")
    suffix = "/".join(suffix_elements)

    val = "/tmp"  # noqa: S108
    expected_map = {
        "user_data_dir": f"/data/data/com.example/files{suffix}",
        "site_data_dir": f"/data/data/com.example/files{suffix}",
        "user_config_dir": f"/data/data/com.example/shared_prefs{suffix}",
        "site_config_dir": f"/data/data/com.example/shared_prefs{suffix}",
        "user_cache_dir": f"/data/data/com.example/cache{suffix}",
        "site_cache_dir": f"/data/data/com.example/cache{suffix}",
        "user_state_dir": f"/data/data/com.example/files{suffix}",
        "user_log_dir": f"/data/data/com.example/cache{suffix}{'' if params.get('opinion', True) is False else '/log'}",
        "user_documents_dir": "/storage/emulated/0/Documents",
        "user_downloads_dir": "/storage/emulated/0/Downloads",
        "user_pictures_dir": "/storage/emulated/0/Pictures",
        "user_videos_dir": "/storage/emulated/0/DCIM/Camera",
        "user_music_dir": "/storage/emulated/0/Music",
        "user_desktop_dir": "/storage/emulated/0/Desktop",
        "user_runtime_dir": f"/data/data/com.example/cache{suffix}{'' if not params.get('opinion', True) else val}",
        "site_runtime_dir": f"/data/data/com.example/cache{suffix}{'' if not params.get('opinion', True) else val}",
    }
    expected = expected_map[func]

    assert result == expected


def test_android_folder_from_jnius(mocker: MockerFixture) -> None:
    from platformdirs import PlatformDirs
    from platformdirs.android import _android_folder

    _android_folder.cache_clear()

    if PlatformDirs is Android:
        import jnius  # pragma: no cover

        autoclass = mocker.spy(jnius, "autoclass")  # pragma: no cover
    else:
        parent = MagicMock(return_value=MagicMock(getAbsolutePath=MagicMock(return_value="/A")))  # pragma: no cover
        context = MagicMock(getFilesDir=MagicMock(return_value=MagicMock(getParentFile=parent)))  # pragma: no cover
        autoclass = MagicMock(return_value=context)  # pragma: no cover
        mocker.patch.dict(sys.modules, {"jnius": MagicMock(autoclass=autoclass)})  # pragma: no cover

    result = _android_folder()
    assert result == "/A"
    assert autoclass.call_count == 1

    assert autoclass.call_args[0] == ("android.content.Context",)

    assert _android_folder() is result
    assert autoclass.call_count == 1


@pytest.mark.parametrize(
    "path",
    [
        "/data/user/1/a/files",
        "/data/data/a/files",
    ],
)
def test_android_folder_from_sys_path(mocker: MockerFixture, path: str, monkeypatch: pytest.MonkeyPatch) -> None:
    mocker.patch.dict(sys.modules, {"jnius": MagicMock(autoclass=MagicMock(side_effect=ModuleNotFoundError))})

    from platformdirs.android import _android_folder

    _android_folder.cache_clear()
    monkeypatch.setattr(sys, "path", ["/A", "/B", path])

    result = _android_folder()
    assert result == path[: -len("/files")]


def test_android_folder_not_found(mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    mocker.patch.dict(sys.modules, {"jnius": MagicMock(autoclass=MagicMock(side_effect=ModuleNotFoundError))})

    from platformdirs.android import _android_folder

    _android_folder.cache_clear()
    monkeypatch.setattr(sys, "path", [])
    assert _android_folder() is None
