try:
    import ctypes
except ImportError:
    ctypes = None
import os
import pathlib
import platform
import sys
import types
import warnings

import pretend
import pytest

from packaging import _manylinux
from packaging._manylinux import (
    _get_glibc_version,
    _glibc_version_string,
    _glibc_version_string_confstr,
    _glibc_version_string_ctypes,
    _is_compatible,
    _parse_elf,
    _parse_glibc_version,
)


@pytest.fixture(autouse=True)
def clear_lru_cache():
    yield
    _get_glibc_version.cache_clear()


@pytest.fixture
def manylinux_module(monkeypatch):
    monkeypatch.setattr(_manylinux, "_get_glibc_version", lambda *args: (2, 20))
    module_name = "_manylinux"
    module = types.ModuleType(module_name)
    monkeypatch.setitem(sys.modules, module_name, module)
    return module


@pytest.mark.parametrize("tf", (True, False))
@pytest.mark.parametrize(
    "attribute,glibc", (("1", (2, 5)), ("2010", (2, 12)), ("2014", (2, 17)))
)
def test_module_declaration(monkeypatch, manylinux_module, attribute, glibc, tf):
    manylinux = f"manylinux{attribute}_compatible"
    monkeypatch.setattr(manylinux_module, manylinux, tf, raising=False)
    res = _is_compatible("x86_64", glibc)
    assert tf is res


@pytest.mark.parametrize(
    "attribute,glibc", (("1", (2, 5)), ("2010", (2, 12)), ("2014", (2, 17)))
)
def test_module_declaration_missing_attribute(
    monkeypatch, manylinux_module, attribute, glibc
):
    manylinux = f"manylinux{attribute}_compatible"
    monkeypatch.delattr(manylinux_module, manylinux, raising=False)
    assert _is_compatible("x86_64", glibc)


@pytest.mark.parametrize(
    "version,compatible", (((2, 0), True), ((2, 5), True), ((2, 10), False))
)
def test_is_manylinux_compatible_glibc_support(version, compatible, monkeypatch):
    monkeypatch.setitem(sys.modules, "_manylinux", None)
    monkeypatch.setattr(_manylinux, "_get_glibc_version", lambda: (2, 5))
    assert bool(_is_compatible("any", version)) == compatible


@pytest.mark.parametrize("version_str", ["glibc-2.4.5", "2"])
def test_check_glibc_version_warning(version_str):
    with warnings.catch_warnings(record=True) as w:
        _parse_glibc_version(version_str)
        assert len(w) == 1
        assert issubclass(w[0].category, RuntimeWarning)


@pytest.mark.skipif(not ctypes, reason="requires ctypes")
@pytest.mark.parametrize(
    "version_str,expected",
    [
        # Be very explicit about bytes and Unicode for Python 2 testing.
        (b"2.4", "2.4"),
        ("2.4", "2.4"),
    ],
)
def test_glibc_version_string(version_str, expected, monkeypatch):
    class LibcVersion:
        def __init__(self, version_str):
            self.version_str = version_str

        def __call__(self):
            return version_str

    class ProcessNamespace:
        def __init__(self, libc_version):
            self.gnu_get_libc_version = libc_version

    process_namespace = ProcessNamespace(LibcVersion(version_str))
    monkeypatch.setattr(ctypes, "CDLL", lambda _: process_namespace)
    monkeypatch.setattr(_manylinux, "_glibc_version_string_confstr", lambda: False)

    assert _glibc_version_string() == expected

    del process_namespace.gnu_get_libc_version
    assert _glibc_version_string() is None


def test_glibc_version_string_confstr(monkeypatch):
    monkeypatch.setattr(os, "confstr", lambda x: "glibc 2.20", raising=False)
    assert _glibc_version_string_confstr() == "2.20"


def test_glibc_version_string_fail(monkeypatch):
    monkeypatch.setattr(os, "confstr", lambda x: None, raising=False)
    monkeypatch.setitem(sys.modules, "ctypes", None)
    assert _glibc_version_string() is None
    assert _get_glibc_version() == (-1, -1)


@pytest.mark.parametrize(
    "failure",
    [pretend.raiser(ValueError), pretend.raiser(OSError), lambda x: "XXX"],
)
def test_glibc_version_string_confstr_fail(monkeypatch, failure):
    monkeypatch.setattr(os, "confstr", failure, raising=False)
    assert _glibc_version_string_confstr() is None


def test_glibc_version_string_confstr_missing(monkeypatch):
    monkeypatch.delattr(os, "confstr", raising=False)
    assert _glibc_version_string_confstr() is None


def test_glibc_version_string_ctypes_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "ctypes", None)
    assert _glibc_version_string_ctypes() is None


@pytest.mark.xfail(ctypes is None, reason="ctypes not available")
def test_glibc_version_string_ctypes_raise_oserror(monkeypatch):
    def patched_cdll(name):
        raise OSError("Dynamic loading not supported")

    monkeypatch.setattr(ctypes, "CDLL", patched_cdll)
    assert _glibc_version_string_ctypes() is None


@pytest.mark.skipif(platform.system() != "Linux", reason="requires Linux")
def test_is_manylinux_compatible_old():
    # Assuming no one is running this test with a version of glibc released in
    # 1997.
    assert _is_compatible("any", (2, 0))


def test_is_manylinux_compatible(monkeypatch):
    monkeypatch.setattr(_manylinux, "_glibc_version_string", lambda: "2.4")
    assert _is_compatible("any", (2, 4))


def test_glibc_version_string_none(monkeypatch):
    monkeypatch.setattr(_manylinux, "_glibc_version_string", lambda: None)
    assert not _is_compatible("any", (2, 4))


@pytest.mark.parametrize(
    "content", [None, "invalid-magic", "invalid-class", "invalid-data", "too-short"]
)
def test_parse_elf_bad_executable(monkeypatch, content):
    if content:
        path = pathlib.Path(__file__).parent / "manylinux" / f"hello-world-{content}"
        path = os.fsdecode(path)
    else:
        path = None
    with _parse_elf(path) as ef:
        assert ef is None
