from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

import platformdirs
from platformdirs.android import Android


def test_package_metadata() -> None:
    assert hasattr(platformdirs, "__version__")
    assert hasattr(platformdirs, "__version_info__")


def test_method_result_is_str(func: str) -> None:
    method = getattr(platformdirs, func)
    result = method()
    assert isinstance(result, str)


def test_property_result_is_str(func: str) -> None:
    dirs = platformdirs.PlatformDirs("MyApp", "MyCompany", version="1.0")
    result = getattr(dirs, func)
    assert isinstance(result, str)


def test_method_result_is_path(func_path: str) -> None:
    method = getattr(platformdirs, func_path)
    result = method()
    assert isinstance(result, Path)


def test_property_result_is_path(func_path: str) -> None:
    dirs = platformdirs.PlatformDirs("MyApp", "MyCompany", version="1.0")
    result = getattr(dirs, func_path)
    assert isinstance(result, Path)


def test_function_interface_is_in_sync(func: str) -> None:
    function_dir = getattr(platformdirs, func)
    function_path = getattr(platformdirs, func.replace("_dir", "_path"))
    assert inspect.isfunction(function_dir)
    assert inspect.isfunction(function_path)
    function_dir_signature = inspect.Signature.from_callable(function_dir)
    function_path_signature = inspect.Signature.from_callable(function_path)
    assert function_dir_signature.parameters == function_path_signature.parameters


@pytest.mark.parametrize("root", ["A", "/system", None])
@pytest.mark.parametrize("data", ["D", "/data", None])
@pytest.mark.parametrize("path", ["/data/data/a/files", "/C"])
@pytest.mark.parametrize("shell", ["/data/data/com.app/files/usr/bin/sh", "/usr/bin/sh", None])
@pytest.mark.parametrize("prefix", ["/data/data/com.termux/files/usr", None])
def test_android_active(  # noqa: PLR0913
    monkeypatch: pytest.MonkeyPatch,
    root: str | None,
    data: str | None,
    path: str,
    shell: str | None,
    prefix: str | None,
) -> None:
    for env_var, value in {"ANDROID_DATA": data, "ANDROID_ROOT": root, "SHELL": shell, "PREFIX": prefix}.items():
        if value is None:
            monkeypatch.delenv(env_var, raising=False)
        else:
            monkeypatch.setenv(env_var, value)

    from platformdirs.android import _android_folder

    _android_folder.cache_clear()
    monkeypatch.setattr(sys, "path", ["/A", "/B", path])

    expected = (
        root == "/system" and data == "/data" and shell is None and prefix is None and _android_folder() is not None
    )
    if expected:
        assert platformdirs._set_platform_dir_class() is Android  # noqa: SLF001
    else:
        assert platformdirs._set_platform_dir_class() is not Android  # noqa: SLF001
