# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""
Record locking to manage potential repodata / repodata metadata file contention
between conda processes. Try to acquire a lock on a single byte in the metadat
file; modify both files; then release the lock.
"""

import time
import warnings
from contextlib import contextmanager

from ...base.context import context

LOCK_BYTE = 21  # mamba interop
LOCK_ATTEMPTS = 10
LOCK_SLEEP = 1


@contextmanager
def _lock_noop(fd):
    """When locking is not available."""
    yield


try:  # pragma: no cover
    import msvcrt

    @contextmanager
    def _lock_impl(fd):  # type: ignore
        tell = fd.tell()
        fd.seek(LOCK_BYTE)
        msvcrt.locking(fd.fileno(), msvcrt.LK_LOCK, 1)  # type: ignore
        try:
            fd.seek(tell)
            yield
        finally:
            fd.seek(LOCK_BYTE)
            msvcrt.locking(fd.fileno(), msvcrt.LK_UNLCK, 1)  # type: ignore

except ImportError:
    try:
        import fcntl
    except ImportError:  # pragma: no cover
        # "fcntl Availibility: not Emscripten, not WASI."
        warnings.warn("file locking not available")

        _lock_impl = _lock_noop  # type: ignore

    else:

        class _lock_impl:
            def __init__(self, fd):
                self.fd = fd

            def __enter__(self):
                for attempt in range(LOCK_ATTEMPTS):
                    try:
                        # msvcrt locking does something similar
                        fcntl.lockf(
                            self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB, 1, LOCK_BYTE
                        )
                        break
                    except OSError:
                        if attempt > LOCK_ATTEMPTS - 2:
                            raise
                        time.sleep(LOCK_SLEEP)

            def __exit__(self, *exc):
                fcntl.lockf(self.fd, fcntl.LOCK_UN, 1, LOCK_BYTE)


def lock(fd):
    if not context.no_lock:
        # locking required for jlap, now default for all
        return _lock_impl(fd)
    return _lock_noop(fd)
