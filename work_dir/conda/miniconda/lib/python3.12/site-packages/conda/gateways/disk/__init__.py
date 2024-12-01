# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
import os
import sys
from errno import EACCES, EEXIST, ENOENT, ENOTEMPTY, EPERM, errorcode
from logging import getLogger
from os.path import basename, dirname, isdir
from subprocess import CalledProcessError
from time import sleep

from ...common.compat import on_win
from ...common.constants import TRACE

log = getLogger(__name__)

MAX_TRIES = 7


def exp_backoff_fn(fn, *args, **kwargs):
    """Mostly for retrying file operations that fail on Windows due to virus scanners"""
    max_tries = kwargs.pop("max_tries", MAX_TRIES)
    if not on_win:
        return fn(*args, **kwargs)

    import random

    # with max_tries = 6, max total time ~= 3.2 sec
    # with max_tries = 7, max total time ~= 6.5 sec

    def sleep_some(n, exc):
        if n == max_tries - 1:
            raise
        sleep_time = ((2**n) + random.random()) * 0.1
        caller_frame = sys._getframe(1)
        log.log(
            TRACE,
            "retrying %s/%s %s() in %g sec",
            basename(caller_frame.f_code.co_filename),
            caller_frame.f_lineno,
            fn.__name__,
            sleep_time,
        )
        sleep(sleep_time)

    for n in range(max_tries):
        try:
            result = fn(*args, **kwargs)
        except OSError as e:
            log.log(TRACE, repr(e))
            if e.errno in (EPERM, EACCES):
                sleep_some(n, e)
            elif e.errno in (ENOENT, ENOTEMPTY):
                # errno.ENOENT File not found error / No such file or directory
                # errno.ENOTEMPTY OSError(41, 'The directory is not empty')
                raise
            else:
                log.warning(
                    "Uncaught backoff with errno %s %d", errorcode[e.errno], e.errno
                )
                raise
        except CalledProcessError as e:
            sleep_some(n, e)
        else:
            return result


def mkdir_p(path):
    # putting this here to help with circular imports
    try:
        log.log(TRACE, "making directory %s", path)
        if path:
            os.makedirs(path)
            return isdir(path) and path
    except OSError as e:
        if e.errno == EEXIST and isdir(path):
            return path
        else:
            raise


def mkdir_p_sudo_safe(path):
    if isdir(path):
        return
    base_dir = dirname(path)
    if not isdir(base_dir):
        mkdir_p_sudo_safe(base_dir)
    log.log(TRACE, "making directory %s", path)
    try:
        os.mkdir(path)
    except OSError as e:
        if not (e.errno == EEXIST and isdir(path)):
            raise
    # # per the following issues, removing this code as of 4.6.0:
    # #   - https://github.com/conda/conda/issues/6569
    # #   - https://github.com/conda/conda/issues/6576
    # #   - https://github.com/conda/conda/issues/7109
    # if not on_win and os.environ.get('SUDO_UID') is not None:
    #     uid = int(os.environ['SUDO_UID'])
    #     gid = int(os.environ.get('SUDO_GID', -1))
    #     log.log(TRACE, "chowning %s:%s %s", uid, gid, path)
    #     os.chown(path, uid, gid)
    if not on_win:
        # set newly-created directory permissions to 02775
        # https://github.com/conda/conda/issues/6610#issuecomment-354478489
        try:
            os.chmod(path, 0o2775)
        except OSError as e:
            log.log(
                TRACE,
                "Failed to set permissions to 2775 on %s (%d %d)",
                path,
                e.errno,
                errorcode[e.errno],
            )
            pass
