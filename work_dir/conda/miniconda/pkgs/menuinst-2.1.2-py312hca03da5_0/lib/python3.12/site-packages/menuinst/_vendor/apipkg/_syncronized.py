from __future__ import annotations

import functools
import threading


def _synchronized(wrapped_function):
    """Decorator to synchronise __getattr__ calls."""

    # Lock shared between all instances of ApiModule to avoid possible deadlocks
    lock = threading.RLock()

    @functools.wraps(wrapped_function)
    def synchronized_wrapper_function(*args, **kwargs):
        with lock:
            return wrapped_function(*args, **kwargs)

    return synchronized_wrapper_function
