# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Intercept signals and handle them gracefully."""

import signal
import threading
from contextlib import contextmanager
from logging import getLogger

log = getLogger(__name__)

INTERRUPT_SIGNALS = (
    "SIGABRT",
    "SIGINT",
    "SIGTERM",
    "SIGQUIT",
    "SIGBREAK",
)


def get_signal_name(signum):
    """
    Examples:
        >>> from signal import SIGINT
        >>> get_signal_name(SIGINT)
        'SIGINT'

    """
    return next(
        (
            k
            for k, v in signal.__dict__.items()
            if v == signum and k.startswith("SIG") and not k.startswith("SIG_")
        ),
        None,
    )


@contextmanager
def signal_handler(handler):
    # TODO: test and fix windows
    #   https://danielkaes.wordpress.com/2009/06/04/how-to-catch-kill-events-with-python/
    _thread_local = threading.local()
    _thread_local.previous_handlers = []
    for signame in INTERRUPT_SIGNALS:
        sig = getattr(signal, signame, None)
        if sig:
            log.debug("registering handler for %s", signame)
            try:
                prev_handler = signal.signal(sig, handler)
                _thread_local.previous_handlers.append((sig, prev_handler))
            except ValueError as e:  # pragma: no cover
                # ValueError: signal only works in main thread
                log.debug("%r", e)
    try:
        yield
    finally:
        standard_handlers = signal.SIG_IGN, signal.SIG_DFL
        for sig, previous_handler in _thread_local.previous_handlers:
            if callable(previous_handler) or previous_handler in standard_handlers:
                log.debug("de-registering handler for %s", sig)
                signal.signal(sig, previous_handler)
