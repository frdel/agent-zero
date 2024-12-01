# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

import ntpath
import os
import posixpath
import re
from functools import partial
from typing import TYPE_CHECKING

from ...deprecations import deprecated

if TYPE_CHECKING:
    from . import PathType


def nt_to_posix(path: PathType, prefix: PathType | None, cygdrive: bool = False) -> str:
    """
    A fallback implementation of `cygpath --unix`.

    Args:
        path: The path to convert.
        prefix: The Windows style prefix directory to use for the conversion.
              If not provided, no checks for root paths will be made.
        cygdrive: Whether to use the Cygwin-style drive prefix.
    """
    path = os.fspath(path)
    prefix = os.fspath(prefix) if prefix else None

    if ntpath.pathsep in path:
        return posixpath.pathsep.join(
            converted
            for path in path.split(ntpath.pathsep)
            if (converted := nt_to_posix(path, prefix, cygdrive))
        )

    # cygpath drops empty strings
    if not path:
        return path

    # Revert in reverse order of the transformations in posix_to_nt:
    # 1. root filesystem forms:
    #      {prefix}\Library\root
    #    → /root
    # 2. mount forms:
    #      \\mount
    #    → //mount
    # 3. drive letter forms:
    #      X:\drive
    #      x:\drive
    #    → /x/drive
    #    → /cygdrive/x/drive
    # 4. anything else

    # continue performing substitutions until a match is found
    subs = 0

    # only absolute paths can be detected as root, mount, or drive formats
    # NOTE: C: & c: are absolute paths but ntpath.isabs doesn't recognize it
    if ntpath.isabs(path) or path in ("C:", "c:"):
        # only attempt to match root if prefix is defined
        if prefix:
            # normalize/resolve the path
            norm_path = ntpath.normpath(path)
            # ntpath.normpath strips trailing slashes, add them back
            if path[-1] in "/\\":
                norm_path += ntpath.sep
            # attempt to match root
            norm_path, subs = _get_RE_WIN_ROOT(prefix).subn(_to_unix_root, norm_path)
            # only keep the normalized path if the root was matched
            if subs:
                path = norm_path

        # attempt to match mount
        if not subs:
            path, subs = RE_WIN_MOUNT.subn(_to_unix_mount, path)

        # attempt to match drive
        if not subs:
            path = RE_WIN_DRIVE.sub(partial(_to_unix_drive, cygdrive=cygdrive), path)

    return _resolve_path(path, posixpath.sep)


def _get_root(prefix: str) -> str:
    # normalize path to remove duplicate slashes, .., and .
    prefix = ntpath.normpath(prefix)

    # MSYS2's root filesystem, /, is defined relative to this DLL:
    #   {root}\usr\lib\msys-2.0.dll
    # the conda community has chosen to install that DLL as:
    #   %CONDA_PREFIX%\Library\usr\lib\msys-2.0.dll
    # so we can infer the root path is:
    #   {prefix}\Library
    # ref: https://github.com/conda/conda/pull/14157#discussion_r1725384636
    return ntpath.join(prefix, "Library")


def _get_RE_WIN_ROOT(prefix: str) -> re.Pattern:
    root = _get_root(prefix)
    return re.compile(
        rf"""
        ^
        {re.escape(root)}
        (?P<path>.*)?
        $
        """,
        flags=re.VERBOSE,
    )


def _to_unix_root(match: re.Match) -> str:
    return match.group("path") or "/"


RE_WIN_MOUNT = re.compile(
    r"""
    ^
    [/\\]{2}(
        (?P<mount>[^/\\]+)
        (?P<path>.*)?
    )?
    $
    """,
    flags=re.VERBOSE,
)


def _to_unix_mount(match: re.Match) -> str:
    mount = match.group("mount") or ""
    path = match.group("path") or ""
    return f"//{mount}{path}"


RE_WIN_DRIVE = re.compile(
    r"""
    ^
    (?P<drive>[A-Za-z]):
    (?P<path>[/\\]+.*)?
    $
    """,
    flags=re.VERBOSE,
)


def _to_unix_drive(match: re.Match, cygdrive: bool) -> str:
    drive = match.group("drive").lower()
    path = match.group("path") or ""
    return f"{'/cygdrive' if cygdrive else ''}/{drive}{path}"


deprecated.constant(
    "25.3",
    "25.9",
    "RE_UNIX",
    re.compile(
        r"""
        (?P<drive>[A-Za-z]:)?
        (?P<path>[\/\\]+(?:[^:*?\"<>|;]+[\/\\]*)*)
        """,
        flags=re.VERBOSE,
    ),
    addendum="Use `conda.common.path._cygpath.RE_WIN_DRIVE` instead.",
)


@deprecated(
    "25.3",
    "25.9",
    addendum="Use `conda.common.path._cygpath._to_unix_drive` instead.",
)
def translate_unix(match: re.Match) -> str:
    return "/" + (
        ((match.group("drive") or "").lower() + match.group("path"))
        .replace("\\", "/")
        .replace(":", "")  # remove drive letter delimiter
        .replace("//", "/")
        .rstrip("/")
    )


def posix_to_nt(path: PathType, prefix: PathType | None, cygdrive: bool = False) -> str:
    """
    A fallback implementation of `cygpath --windows`.

    Args:
        path: The path to convert.
        prefix: The Windows style prefix directory to use for the conversion.
              If not provided, no checks for root paths will be made.
        cygdrive: Unused. Present to keep the signature consistent with `nt_to_posix`.
    """
    path = os.fspath(path)
    prefix = os.fspath(prefix) if prefix else None

    if posixpath.pathsep in path:
        return ntpath.pathsep.join(
            posix_to_nt(path, prefix) for path in path.split(posixpath.pathsep)
        )

    # cygpath converts a "" to "."
    if not path:
        return "."

    # Reverting a Unix path means unpicking MSYS2/Cygwin
    # conventions -- in order!
    # 1. drive letter forms:
    #      /x/drive (MSYS2)
    #      /cygdrive/x/drive (Cygwin)
    #    → X:\drive
    # 2. mount forms:
    #      //mount
    #    → \\mount
    # 3. root filesystem forms:
    #      /root
    #    → {prefix}\Library\root
    # 3. anything else

    # only absolute paths can be detected as drive, mount, or root formats
    if posixpath.isabs(path):
        # continue performing substitutions until a match is found
        subs = 0

        # attempt to match drive
        path, subs = RE_UNIX_DRIVE.subn(_to_win_drive, path)

        # attempt to match mount
        if not subs:
            path, subs = RE_UNIX_MOUNT.subn(_to_win_mount, path)

        # only attempt to match root if prefix is defined
        if prefix and not subs:
            root = _get_root(prefix)
            path = RE_UNIX_ROOT.sub(partial(_to_win_root, root=root), path)

    return _resolve_path(path, ntpath.sep)


RE_UNIX_DRIVE = re.compile(
    r"""
    ^
    (/cygdrive)?
    /(?P<drive>[A-Za-z])
    (/+(?P<path>.*)?)?
    $
    """,
    flags=re.VERBOSE,
)


def _to_win_drive(match: re.Match) -> str:
    drive = match.group("drive").upper()
    path = match.group("path") or ""
    return f"{drive}:\\{path}"


deprecated.constant(
    "25.3",
    "25.9",
    "RE_DRIVE",
    RE_UNIX_DRIVE,
    addendum="Use `conda.common.path._cygpath.RE_UNIX_DRIVE` instead.",
)
deprecated.constant(
    "25.3",
    "25.9",
    "translation_drive",
    _to_win_drive,
    addendum="Use `conda.common.path._cygpath._to_win_drive` instead.",
)


RE_UNIX_MOUNT = re.compile(
    r"""
    ^
    /{2}(
        (?P<mount>[^/]+)
        (?P<path>/+.*)?
    )?
    $
    """,
    flags=re.VERBOSE,
)


def _to_win_mount(match: re.Match) -> str:
    mount = match.group("mount") or ""
    path = match.group("path") or ""
    return f"\\\\{mount}{path}"


deprecated.constant(
    "25.3",
    "25.9",
    "RE_MOUNT",
    RE_UNIX_MOUNT,
    addendum="Use `conda.common.path._cygpath.RE_UNIX_MOUNT` instead.",
)
deprecated.constant(
    "25.3",
    "25.9",
    "translation_mount",
    _to_win_mount,
    addendum="Use `conda.common.path._cygpath._to_win_mount` instead.",
)


RE_UNIX_ROOT = re.compile(
    r"""
    ^
    (?P<path>/.*)
    $
    """,
    flags=re.VERBOSE,
)


def _to_win_root(match: re.Match, root: str) -> str:
    path = match.group("path")
    return f"{root}{path}"


deprecated.constant(
    "25.3",
    "25.9",
    "RE_ROOT",
    RE_UNIX_ROOT,
    addendum="Use `conda.common.path._cygpath.RE_UNIX_ROOT` instead.",
)
deprecated.constant(
    "25.3",
    "25.9",
    "translation_root",
    _to_win_root,
    addendum="Use `conda.common.path._cygpath._to_win_root` instead.",
)


def _resolve_path(path: str, sep: str) -> str:
    leading = ""
    if match := re.match(r"^([/\\]+)(.*)$", path):
        leading, path = match.groups()
    sep = re.escape(sep)
    return re.sub(r"[/\\]", sep, leading) + re.sub(r"[/\\]+", sep, path)


def resolve_paths(paths: str, pathsep: str, sep: str) -> str:
    return pathsep.join(_resolve_path(path, sep) for path in paths.split(pathsep))
