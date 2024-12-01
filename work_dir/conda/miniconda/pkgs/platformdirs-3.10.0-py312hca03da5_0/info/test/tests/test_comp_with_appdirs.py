from __future__ import annotations

import sys
from inspect import getmembers, isfunction
from typing import Any

import appdirs
import pytest

import platformdirs


def test_has_backward_compatible_class() -> None:
    from platformdirs import AppDirs

    assert AppDirs is platformdirs.PlatformDirs


def test_has_all_functions() -> None:
    # Get all public function names from appdirs
    appdirs_function_names = [f[0] for f in getmembers(appdirs, isfunction) if not f[0].startswith("_")]

    # Exception will be raised if any appdirs functions aren't in platformdirs.
    for function_name in appdirs_function_names:
        getattr(platformdirs, function_name)


def test_has_all_properties() -> None:
    # Get names of all the properties of appdirs.AppDirs
    appdirs_property_names = [p[0] for p in getmembers(appdirs.AppDirs, lambda member: isinstance(member, property))]

    # Exception will be raised if any appdirs.AppDirs properties aren't in platformdirs.AppDirs
    for property_name in appdirs_property_names:
        getattr(platformdirs.AppDirs, property_name)


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"appname": "foo"},
        {"appname": "foo", "appauthor": "bar"},
        {"appname": "foo", "appauthor": "bar", "version": "v1.0"},
    ],
    ids=[
        "no_args",
        "app_name",
        "app_name_with_app_author",
        "app_name_author_version",
    ],
)
def test_compatibility(params: dict[str, Any], func: str) -> None:
    # Only test functions that are part of appdirs
    if getattr(appdirs, func, None) is None:
        pytest.skip(f"`{func}` does not exist in `appdirs`")

    if sys.platform == "darwin":
        msg = {  # pragma: no cover
            "user_log_dir": "without appname produces NoneType error",
        }
        if func in msg:  # pragma: no cover
            pytest.skip(f"`appdirs.{func}` {msg[func]} on macOS")  # pragma: no cover
    elif sys.platform != "win32":
        msg = {  # pragma: no cover
            "user_log_dir": "Uses XDG_STATE_DIR instead of appdirs.user_data_dir per the XDG spec",
        }
        if func in msg:  # pragma: no cover
            pytest.skip(f"`appdirs.{func}` {msg[func]} on Unix")  # pragma: no cover

    new = getattr(platformdirs, func)(*params)
    old = getattr(appdirs, func)(*params)

    assert new == old.rstrip("/")
