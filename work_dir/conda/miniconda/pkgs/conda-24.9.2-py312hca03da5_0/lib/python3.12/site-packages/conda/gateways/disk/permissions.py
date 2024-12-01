# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Disk utility functions for modifying file and directory permissions."""

from errno import EACCES, ENOENT, EPERM, EROFS
from itertools import chain
from logging import getLogger
from os import X_OK, access, chmod, lstat, walk
from os.path import isdir, isfile, join
from stat import S_IEXEC, S_IMODE, S_ISDIR, S_ISREG, S_IWRITE, S_IXGRP, S_IXOTH, S_IXUSR

from ...common.compat import on_win
from ...common.constants import TRACE
from . import MAX_TRIES, exp_backoff_fn
from .link import islink, lchmod

log = getLogger(__name__)


def make_writable(path):
    try:
        mode = lstat(path).st_mode
        if S_ISDIR(mode):
            chmod(path, S_IMODE(mode) | S_IWRITE | S_IEXEC)
        elif islink(path):
            lchmod(path, S_IMODE(mode) | S_IWRITE)
        elif S_ISREG(mode):
            chmod(path, S_IMODE(mode) | S_IWRITE)
        else:
            log.debug("path cannot be made writable: %s", path)
        return True
    except Exception as e:
        eno = getattr(e, "errno", None)
        if eno in (ENOENT,):
            log.debug("tried to make writable, but didn't exist: %s", path)
            raise
        elif eno in (EACCES, EPERM, EROFS):
            log.debug("tried make writable but failed: %s\n%r", path, e)
            return False
        else:
            log.warning("Error making path writable: %s\n%r", path, e)
            raise


def make_read_only(path):
    mode = lstat(path).st_mode
    if S_ISDIR(mode):
        chmod(path, S_IMODE(mode) & ~S_IWRITE)
    elif islink(path):
        lchmod(path, S_IMODE(mode) & ~S_IWRITE)
    elif S_ISREG(mode):
        chmod(path, S_IMODE(mode) & ~S_IWRITE)
    else:
        log.debug("path cannot be made read only: %s", path)
    return True


def recursive_make_writable(path, max_tries=MAX_TRIES):
    # The need for this function was pointed out at
    #   https://github.com/conda/conda/issues/3266#issuecomment-239241915
    # Especially on windows, file removal will often fail because it is marked read-only
    if isdir(path):
        for root, dirs, files in walk(path):
            for path in chain.from_iterable((files, dirs)):
                try:
                    exp_backoff_fn(make_writable, join(root, path), max_tries=max_tries)
                except OSError as e:
                    if e.errno == ENOENT:
                        log.debug("no such file or directory: %s", path)
                    else:
                        raise
    else:
        exp_backoff_fn(make_writable, path, max_tries=max_tries)


def make_executable(path):
    if isfile(path):
        mode = lstat(path).st_mode
        log.log(TRACE, "chmod +x %s", path)
        chmod(path, S_IMODE(mode) | S_IXUSR | S_IXGRP | S_IXOTH)
    else:
        log.error("Cannot make path '%s' executable", path)


def is_executable(path):
    if isfile(path):  # for now, leave out `and not islink(path)`
        return path.endswith((".exe", ".bat")) if on_win else access(path, X_OK)
    return False
