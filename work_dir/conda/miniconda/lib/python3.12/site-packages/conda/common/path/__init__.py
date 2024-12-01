# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Common path utilities."""

from __future__ import annotations

import os
import re
from functools import lru_cache
from logging import getLogger
from os.path import (
    abspath,
    basename,
    expanduser,
    expandvars,
    normcase,
    split,
)
from shutil import which
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from ... import CondaError
from ...deprecations import deprecated
from ..compat import on_win
from .directories import (
    explode_directories,
    get_all_directories,
    get_leaf_directories,
    tokenized_startswith,
)
from .python import (
    _VERSION_REGEX,
    get_major_minor_version,
    get_python_noarch_target_path,
    get_python_short_path,
    get_python_site_packages_short_path,
    missing_pyc_files,
    parse_entry_point_def,
    pyc_path,
)
from .windows import (
    unix_path_to_win,
    win_path_backout,
    win_path_double_escape,
    win_path_ok,
    win_path_to_unix,
)

if TYPE_CHECKING:
    from typing import Iterable, Union

    PathType = Union[str, os.PathLike[str]]
    PathsType = Iterable[PathType]

__all__ = [
    "explode_directories",
    "get_all_directories",
    "get_leaf_directories",
    "get_major_minor_version",
    "get_python_noarch_target_path",
    "get_python_short_path",
    "get_python_site_packages_short_path",
    "missing_pyc_files",
    "parse_entry_point_def",
    "pyc_path",
    "tokenized_startswith",
    "unix_path_to_win",
    "win_path_backout",
    "win_path_double_escape",
    "win_path_ok",
    "win_path_to_unix",
]

log = getLogger(__name__)

PATH_MATCH_REGEX = (
    r"\./"  # ./
    r"|\.\."  # ..
    r"|~"  # ~
    r"|/"  # /
    r"|[a-zA-Z]:[/\\]"  # drive letter, colon, forward or backslash
    r"|\\\\"  # windows UNC path
    r"|//"  # windows UNC path
)

# any other extension will be mangled by CondaSession.get() as it tries to find
# channel names from URLs, through strip_pkg_extension()
KNOWN_EXTENSIONS = (".conda", ".tar.bz2", ".json", ".jlap", ".json.zst")

deprecated.constant(
    "25.3",
    "25.9",
    "_VERSION_REGEX",
    _VERSION_REGEX,
    addendum="Use `conda.common.path.python._VERSION_REGEX` instead.",
)
del _VERSION_REGEX


def is_path(value):
    if "://" in value:
        return False
    return re.match(PATH_MATCH_REGEX, value)


def expand(path):
    return abspath(expanduser(expandvars(path)))


def paths_equal(path1, path2):
    """
    Examples:
        >>> paths_equal('/a/b/c', '/a/b/c/d/..')
        True

    """
    if on_win:
        return normcase(abspath(path1)) == normcase(abspath(path2))
    else:
        return abspath(path1) == abspath(path2)


@lru_cache(maxsize=None)
def url_to_path(url):
    """Convert a file:// URL to a path.

    Relative file URLs (i.e. `file:relative/path`) are not supported.
    """
    if is_path(url):
        return url
    if not url.startswith("file://"):  # pragma: no cover
        raise CondaError(
            f"You can only turn absolute file: urls into paths (not {url})"
        )
    _, netloc, path, _, _ = urlsplit(url)
    from ..url import percent_decode

    path = percent_decode(path)
    if netloc not in ("", "localhost", "127.0.0.1", "::1"):
        if not netloc.startswith("\\\\"):
            # The only net location potentially accessible is a Windows UNC path
            netloc = "//" + netloc
    else:
        netloc = ""
        # Handle Windows drive letters if present
        if re.match("^/([a-z])[:|]", path, re.I):
            path = path[1] + ":" + path[3:]
    return netloc + path


BIN_DIRECTORY = "Scripts" if on_win else "bin"


@deprecated("25.3", "25.9", addendum="Use `conda.common.path.BIN_DIRECTORY` instead.")
def get_bin_directory_short_path():
    return BIN_DIRECTORY


def ensure_pad(name, pad="_"):
    """

    Examples:
        >>> ensure_pad('conda')
        '_conda_'
        >>> ensure_pad('_conda')
        '__conda_'
        >>> ensure_pad('')
        ''

    """
    if not name or name[0] == name[-1] == pad:
        return name
    else:
        return f"{pad}{name}{pad}"


@deprecated("25.3", "25.9")
def is_private_env_name(env_name):
    """

    Examples:
        >>> is_private_env_name("_conda")
        False
        >>> is_private_env_name("_conda_")
        True

    """
    return env_name and env_name[0] == env_name[-1] == "_"


@deprecated("25.3", "25.9")
def is_private_env_path(env_path):
    """

    Examples:
        >>> is_private_env_path('/some/path/to/envs/_conda_')
        True
        >>> is_private_env_path('/not/an/envs_dir/_conda_')
        False

    """
    if env_path is not None:
        envs_directory, env_name = split(env_path)
        if basename(envs_directory) != "envs":
            return False
        return is_private_env_name(env_name)
    return False


def right_pad_os_sep(path):
    return path if path.endswith(os.sep) else path + os.sep


def split_filename(path_or_url):
    dn, fn = split(path_or_url)
    return (dn or None, fn) if "." in fn else (path_or_url, None)


deprecated.constant(
    "25.3",
    "25.9",
    "which",
    which,
    addendum="Use builtin `shutil.which` instead.",
)
del which


def strip_pkg_extension(path: str):
    """
    Examples:
        >>> strip_pkg_extension("/path/_license-1.1-py27_1.tar.bz2")
        ('/path/_license-1.1-py27_1', '.tar.bz2')
        >>> strip_pkg_extension("/path/_license-1.1-py27_1.conda")
        ('/path/_license-1.1-py27_1', '.conda')
        >>> strip_pkg_extension("/path/_license-1.1-py27_1")
        ('/path/_license-1.1-py27_1', None)
    """
    # NOTE: not using CONDA_TARBALL_EXTENSION_V1 or CONDA_TARBALL_EXTENSION_V2 to comply with
    #       import rules and to avoid a global lookup.
    for extension in KNOWN_EXTENSIONS:
        if path.endswith(extension):
            return path[: -len(extension)], extension
    return path, None


def is_package_file(path):
    """
    Examples:
        >>> is_package_file("/path/_license-1.1-py27_1.tar.bz2")
        True
        >>> is_package_file("/path/_license-1.1-py27_1.conda")
        True
        >>> is_package_file("/path/_license-1.1-py27_1")
        False
    """
    # NOTE: not using CONDA_TARBALL_EXTENSION_V1 or CONDA_TARBALL_EXTENSION_V2 to comply with
    #       import rules and to avoid a global lookup.
    return path[-6:] == ".conda" or path[-8:] == ".tar.bz2"


def path_identity(paths: PathType | PathsType | None) -> str | tuple[str, ...] | None:
    if paths is None:
        return None
    elif isinstance(paths, (str, os.PathLike)):
        return os.path.normpath(paths)
    else:
        return tuple(os.path.normpath(path) for path in paths)
