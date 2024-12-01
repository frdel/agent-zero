# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Common Windows path utilities."""

from __future__ import annotations

import ntpath
import os
import posixpath
import re
import subprocess
from logging import getLogger
from pathlib import Path
from shutil import which
from typing import TYPE_CHECKING

from ..compat import on_win
from ._cygpath import nt_to_posix, posix_to_nt, resolve_paths

if TYPE_CHECKING:
    from . import PathsType, PathType

log = getLogger(__name__)


def win_path_ok(path):
    return path.replace("/", "\\") if on_win else path


def win_path_double_escape(path):
    return path.replace("\\", "\\\\") if on_win else path


def win_path_backout(path):
    # replace all backslashes except those escaping spaces
    # if we pass a file url, something like file://\\unc\path\on\win, make sure
    #   we clean that up too
    return re.sub(r"(\\(?! ))", r"/", path).replace(":////", "://")


def _path_to(
    paths: PathType | PathsType | None,
    prefix: PathType | None = None,
    *,
    cygdrive: bool,
    to_unix: bool,
) -> str | tuple[str, ...] | None:
    if paths is None:
        return None

    # short-circuit if we don't get any paths
    paths = paths if isinstance(paths, (str, os.PathLike)) else tuple(paths)
    if not paths:
        return "." if isinstance(paths, (str, os.PathLike)) else ()

    if on_win and prefix is None:
        from ...base.context import context

        prefix = context.target_prefix

    if to_unix:
        from_pathsep = ntpath.pathsep
        cygpath_arg = "--unix"
        cygpath_fallback = nt_to_posix
        to_pathsep = posixpath.pathsep
        to_sep = posixpath.sep
    else:
        from_pathsep = posixpath.pathsep
        cygpath_arg = "--windows"
        cygpath_fallback = posix_to_nt
        to_pathsep = ntpath.pathsep
        to_sep = ntpath.sep

    # It is very easy to end up with a bash in one place and a cygpath in another due to e.g.
    # using upstream MSYS2 bash, but with a conda env that does not have bash but does have
    # cygpath.  When this happens, we have two different virtual POSIX machines, rooted at
    # different points in the Windows filesystem.  We do our path conversions with one and
    # expect the results to work with the other.  It does not.

    # TODO: search prefix for cygpath instead of deriving it from bash
    bash = which("bash")
    cygpath = str(Path(bash).parent / "cygpath") if bash else "cygpath"
    joined = (
        str(paths)
        if isinstance(paths, (str, os.PathLike))
        else from_pathsep.join(map(str, paths))
    )

    converted: str | None = None
    try:
        # if present, use cygpath to convert paths since its more reliable
        converted = subprocess.run(
            [cygpath, cygpath_arg, "--path", joined],
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
    except FileNotFoundError:
        # FileNotFoundError: cygpath not available, happens when conda is installed without anything else
        log.warning("cygpath is not available, fallback to manual path conversion")
    except subprocess.CalledProcessError as err:
        # CalledProcessError: cygpath failed for some reason
        log.error(
            "Unexpected cygpath error, fallback to manual path conversion\n  %s: %s\n  stdout: %s\n  stderr: %s",
            err.__class__.__name__,
            err,
            err.stdout.strip(),
            err.stderr.strip(),
        )
    except Exception as err:
        # Exception: unexpected error
        log.error(
            "Unexpected cygpath error, fallback to manual path conversion\n  %s: %s",
            err.__class__.__name__,
            err,
        )
    else:
        # cygpath doesn't always remove duplicate path seps
        converted = resolve_paths(converted, to_pathsep, to_sep)

    if converted is None:
        converted = cygpath_fallback(joined, prefix, cygdrive)

    if isinstance(paths, (str, os.PathLike)):
        return converted
    elif not converted:
        return ()
    else:
        return tuple(converted.split(to_pathsep))


def win_path_to_unix(
    paths: PathType | PathsType | None,
    prefix: PathType | None = None,
    *,
    cygdrive: bool = False,
) -> str | tuple[str, ...] | None:
    """Convert Windows paths to Unix paths.

    .. note::
        Produces unexpected results when run on Unix.

    Args:
        paths: The path(s) to convert.
        prefix: The (Windows path-style) prefix directory to use for the conversion.
              If not provided, no checks for prefix paths will be made.
        cygdrive: Whether to use the Cygwin-style drive prefix.
    """
    return _path_to(paths, prefix=prefix, cygdrive=cygdrive, to_unix=True)


def unix_path_to_win(
    paths: PathType | PathsType | None,
    prefix: PathType | None = None,
    *,
    cygdrive: bool = False,
) -> str | tuple[str, ...] | None:
    """Convert Unix paths to Windows paths.

    .. note::
        Produces unexpected results when run on Unix.

    Args:
        paths: The path(s) to convert.
        prefix: The (Windows path-style) prefix directory to use for the conversion.
              If not provided, no checks for prefix paths will be made.
        cygdrive: Unused. Present to keep the signature consistent with `win_path_to_unix`.
    """
    return _path_to(paths, prefix, cygdrive=cygdrive, to_unix=False)
