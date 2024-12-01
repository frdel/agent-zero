# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Configure logging for conda."""

import logging
import re
import sys
from datetime import datetime
from functools import lru_cache, partial
from logging import (
    DEBUG,
    ERROR,
    INFO,
    WARN,
    Filter,
    Formatter,
    StreamHandler,
    getLogger,
)

from ..common.constants import TRACE
from ..common.io import _FORMATTER, attach_stderr_handler
from ..deprecations import deprecated

log = getLogger(__name__)

_VERBOSITY_LEVELS = {
    0: WARN,  # standard output
    1: WARN,  # -v, detailed output
    2: INFO,  # -vv, info logging
    3: DEBUG,  # -vvv, debug logging
    4: TRACE,  # -vvvv, trace logging
}


class TokenURLFilter(Filter):
    TOKEN_URL_PATTERN = re.compile(
        r"(|https?://)"  # \1  scheme
        r"(|\s"  # \2  space, or
        r"|(?:(?:\d{1,3}\.){3}\d{1,3})"  # ipv4, or
        r"|(?:"  # domain name
        r"(?:[a-zA-Z0-9-]{1,20}\.){0,10}"  # non-tld
        r"(?:[a-zA-Z]{2}[a-zA-Z0-9-]{0,18})"  # tld
        r"))"  # end domain name
        r"(|:\d{1,5})?"  # \3  port
        r"/t/[a-z0-9A-Z-]+/"  # token
    )
    TOKEN_REPLACE = partial(TOKEN_URL_PATTERN.sub, r"\1\2\3/t/<TOKEN>/")

    def filter(self, record):
        """
        Since Python 2's getMessage() is incapable of handling any
        strings that are not unicode when it interpolates the message
        with the arguments, we fix that here by doing it ourselves.

        At the same time we replace tokens in the arguments which was
        not happening until now.
        """
        if not isinstance(record.msg, str):
            # This should always be the case but it's not checked so
            # we avoid any potential logging errors.
            return True
        if record.args:
            record.msg = record.msg % record.args
            record.args = None
        record.msg = self.TOKEN_REPLACE(record.msg)
        return True


class StdStreamHandler(StreamHandler):
    """Log StreamHandler that always writes to the current sys stream."""

    terminator = "\n"

    def __init__(self, sys_stream):
        """
        Args:
            sys_stream: stream name, either "stdout" or "stderr" (attribute of module sys)
        """
        super().__init__(getattr(sys, sys_stream))
        self.sys_stream = sys_stream
        del self.stream

    def __getattr__(self, attr):
        # always get current sys.stdout/sys.stderr, unless self.stream has been set explicitly
        if attr == "stream":
            return getattr(sys, self.sys_stream)
        return super().__getattribute__(attr)

    """
    def emit(self, record):
        # in contrast to the Python 2.7 StreamHandler, this has no special Unicode handling;
        # however, this backports the Python >=3.2 terminator attribute and additionally makes it
        # further customizable by giving record an identically named attribute, e.g., via
        # logger.log(..., extra={"terminator": ""}) or LoggerAdapter(logger, {"terminator": ""}).
        try:
            msg = self.format(record)
            terminator = getattr(record, "terminator", self.terminator)
            stream = self.stream
            stream.write(msg)
            stream.write(terminator)
            self.flush()
        except Exception:
            self.handleError(record)

    """

    # Updated Python 2.7.15's stdlib, with terminator and unicode support.
    def emit(self, record):
        """
        Emit a record.

        If a formatter is specified, it is used to format the record.
        The record is then written to the stream with a trailing newline.  If
        exception information is present, it is formatted using
        traceback.print_exception and appended to the stream.  If the stream
        has an 'encoding' attribute, it is used to determine how to do the
        output to the stream.
        """
        try:
            msg = self.format(record)
            stream = self.stream
            fs = "%s"
            stream.write(fs % msg)
            terminator = getattr(record, "terminator", self.terminator)
            stream.write(terminator)
            self.flush()
        # How does conda handle Ctrl-C? Find out..
        # except (KeyboardInterrupt, SystemExit):
        #     raise
        except Exception:
            self.handleError(record)


# Don't use initialize_logging/initialize_root_logger/set_conda_log_level in
# cli.python_api! There we want the user to have control over their logging,
# e.g., using their own levels, handlers, formatters and propagation settings.


@lru_cache(maxsize=None)
def initialize_logging():
    # 'conda' gets level WARN and does not propagate to root.
    getLogger("conda").setLevel(WARN)
    set_conda_log_level()
    initialize_std_loggers()


def initialize_std_loggers():
    # Set up special loggers 'conda.stdout'/'conda.stderr' which output directly to the
    # corresponding sys streams, filter token urls and don't propagate.
    formatter = Formatter("%(message)s")

    for stream in ("stdout", "stderr"):
        logger = getLogger(f"conda.{stream}")
        logger.handlers = []
        logger.setLevel(INFO)
        handler = StdStreamHandler(stream)
        handler.setLevel(INFO)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.addFilter(TokenURLFilter())
        logger.propagate = False

        stdlog_logger = getLogger(f"conda.{stream}log")
        stdlog_logger.handlers = []
        stdlog_logger.setLevel(DEBUG)
        stdlog_handler = StdStreamHandler(stream)
        stdlog_handler.terminator = ""
        stdlog_handler.setLevel(DEBUG)
        stdlog_handler.setFormatter(formatter)
        stdlog_logger.addHandler(stdlog_handler)
        stdlog_logger.propagate = False

    verbose_logger = getLogger("conda.stdout.verbose")
    verbose_logger.handlers = []
    verbose_logger.setLevel(INFO)
    verbose_handler = StdStreamHandler("stdout")
    verbose_handler.setLevel(INFO)
    verbose_handler.setFormatter(formatter)
    verbose_handler.addFilter(TokenURLFilter())
    verbose_logger.addHandler(verbose_handler)
    verbose_logger.propagate = False


@deprecated("25.3", "25.9", addendum="Unused.")
def initialize_root_logger(level=ERROR):
    attach_stderr_handler(level=level, filters=[TokenURLFilter()])


def set_conda_log_level(level=WARN):
    attach_stderr_handler(level=level, logger_name="conda", filters=[TokenURLFilter()])


def set_all_logger_level(level=DEBUG):
    formatter = Formatter("%(message)s\n") if level >= INFO else None
    attach_stderr_handler(level, formatter=formatter, filters=[TokenURLFilter()])
    set_conda_log_level(level)
    # 'requests' loggers get their own handlers so that they always output messages in long format
    # regardless of the level.
    attach_stderr_handler(level, "requests", filters=[TokenURLFilter()])
    attach_stderr_handler(
        level, "requests.packages.urllib3", filters=[TokenURLFilter()]
    )


@lru_cache(maxsize=None)
def set_file_logging(logger_name=None, level=DEBUG, path=None):
    if path is None:
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        path = f".conda.{timestamp}.log"

    conda_logger = getLogger(logger_name)
    handler = logging.FileHandler(path)
    handler.setFormatter(_FORMATTER)
    handler.setLevel(level)
    conda_logger.addHandler(handler)


def set_log_level(log_level: int):
    set_all_logger_level(log_level)
    log.debug("log_level set to %d", log_level)


@deprecated(
    "24.9",
    "25.3",
    addendum="Use `logging.getLogger(__name__)(conda.common.constants.TRACE, ...)` instead.",
)
def trace(self, message, *args, **kwargs):
    if self.isEnabledFor(TRACE):
        self._log(TRACE, message, args, **kwargs)


logging.addLevelName(TRACE, "TRACE")
logging.Logger.trace = trace  # type: ignore[attr-defined]
