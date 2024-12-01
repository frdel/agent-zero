# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Common compatiblity code."""
# Try to keep compat small because it's imported by everything
# What is compat, and what isn't?
# If a piece of code is "general" and used in multiple modules, it goes here.
# If it's only used in one module, keep it in that module, preferably near the top.
# This module should contain ONLY stdlib imports.

import builtins
import sys

from ..deprecations import deprecated

on_win = bool(sys.platform == "win32")
on_mac = bool(sys.platform == "darwin")
on_linux = bool(sys.platform == "linux")

deprecated.constant(
    "25.3",
    "25.9",
    "FILESYSTEM_ENCODING",
    _FILESYSTEM_ENCODING := sys.getfilesystemencoding(),
)

# Control some tweakables that will be removed finally.
ENCODE_ENVIRONMENT = True


def encode_for_env_var(value) -> str:
    """Environment names and values need to be string."""
    if isinstance(value, str):
        return value
    elif isinstance(value, bytes):
        return value.decode()
    return str(value)


def encode_environment(env):
    if ENCODE_ENVIRONMENT:
        env = {encode_for_env_var(k): encode_for_env_var(v) for k, v in env.items()}
    return env


@deprecated("24.9", "25.3")
def encode_arguments(arguments):
    return arguments


from collections.abc import Iterable


def isiterable(obj):
    return not isinstance(obj, str) and isinstance(obj, Iterable)


# #############################
# other
# #############################

from collections import OrderedDict as odict  # noqa: F401


def open_utf8(
    file, mode="r", buffering=-1, encoding=None, errors=None, newline=None, closefd=True
):
    if "b" in mode:
        return builtins.open(
            file,
            str(mode),
            buffering=buffering,
            errors=errors,
            newline=newline,
            closefd=closefd,
        )
    else:
        return builtins.open(
            file,
            str(mode),
            buffering=buffering,
            encoding=encoding or "utf-8",
            errors=errors,
            newline=newline,
            closefd=closefd,
        )


@deprecated("25.3", "25.9", addendum="Use `conda.common.compat.open_utf8` instead.")
def open(
    file, mode="r", buffering=-1, encoding=None, errors=None, newline=None, closefd=True
):
    return open_utf8(file, mode, buffering, encoding, errors, newline, closefd)


@deprecated(
    "25.3",
    "25.9",
    addendum="Use class' `metaclass=` keyword argument instead.",
)
def six_with_metaclass(meta, *bases):
    """Create a base class with a metaclass."""

    # This requires a bit of explanation: the basic idea is to make a dummy
    # metaclass for one level of class instantiation that replaces itself with
    # the actual metaclass.
    class metaclass(type):
        def __new__(cls, name, this_bases, d):
            return meta(name, bases, d)

        @classmethod
        def __prepare__(cls, name, this_bases):
            return meta.__prepare__(name, bases)

    return type.__new__(metaclass, "temporary_class", (), {})


NoneType = type(None)
primitive_types = (str, int, float, complex, bool, NoneType)


def ensure_binary(value):
    try:
        return value.encode("utf-8")
    except AttributeError:  # pragma: no cover
        # AttributeError: '<>' object has no attribute 'encode'
        # In this case assume already binary type and do nothing
        return value


def ensure_text_type(value) -> str:
    try:
        return value.decode("utf-8")
    except AttributeError:  # pragma: no cover
        # AttributeError: '<>' object has no attribute 'decode'
        # In this case assume already text_type and do nothing
        return value
    except UnicodeDecodeError:  # pragma: no cover
        from charset_normalizer import from_bytes

        return str(from_bytes(value).best())
    except UnicodeEncodeError:  # pragma: no cover
        # it's already str, so ignore?
        # not sure, surfaced with tests/models/test_match_spec.py test_tarball_match_specs
        # using py27
        return value


@deprecated("25.3", "25.9")
def ensure_unicode(value):
    try:
        return value.decode("unicode_escape")
    except AttributeError:  # pragma: no cover
        # AttributeError: '<>' object has no attribute 'decode'
        # In this case assume already unicode and do nothing
        return value


@deprecated("25.3", "25.9")
def ensure_fs_path_encoding(value):
    try:
        return value.encode(_FILESYSTEM_ENCODING)
    except AttributeError:
        return value
    except UnicodeEncodeError:
        return value


def ensure_utf8_encoding(value):
    try:
        return value.encode("utf-8")
    except AttributeError:
        return value
    except UnicodeEncodeError:
        return value
