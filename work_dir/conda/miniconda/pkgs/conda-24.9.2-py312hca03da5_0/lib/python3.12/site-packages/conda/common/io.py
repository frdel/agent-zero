# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Common I/O utilities."""

import json
import logging
import os
import signal
import sys
from collections import defaultdict
from concurrent.futures import Executor, Future, ThreadPoolExecutor, _base, as_completed
from concurrent.futures.thread import _WorkItem
from contextlib import contextmanager
from enum import Enum
from errno import EPIPE, ESHUTDOWN
from functools import partial, wraps
from io import BytesIO, StringIO
from itertools import cycle
from logging import CRITICAL, WARN, Formatter, StreamHandler, getLogger
from os.path import dirname, isdir, isfile, join
from threading import Event, Lock, RLock, Thread
from time import sleep, time

from ..auxlib.decorators import memoizemethod
from ..auxlib.logz import NullHandler
from ..auxlib.type_coercion import boolify
from .compat import encode_environment, on_win
from .constants import NULL
from .path import expand

log = getLogger(__name__)
IS_INTERACTIVE = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


class DeltaSecondsFormatter(Formatter):
    """
    Logging formatter with additional attributes for run time logging.

    Attributes:
      `delta_secs`:
        Elapsed seconds since last log/format call (or creation of logger).
      `relative_created_secs`:
        Like `relativeCreated`, time relative to the initialization of the
        `logging` module but conveniently scaled to seconds as a `float` value.
    """

    def __init__(self, fmt=None, datefmt=None):
        self.prev_time = time()
        super().__init__(fmt=fmt, datefmt=datefmt)

    def format(self, record):
        now = time()
        prev_time = self.prev_time
        self.prev_time = max(self.prev_time, now)
        record.delta_secs = now - prev_time
        record.relative_created_secs = record.relativeCreated / 1000
        return super().format(record)


if boolify(os.environ.get("CONDA_TIMED_LOGGING")):
    _FORMATTER = DeltaSecondsFormatter(
        "%(relative_created_secs) 7.2f %(delta_secs) 7.2f "
        "%(levelname)s %(name)s:%(funcName)s(%(lineno)d): %(message)s"
    )
else:
    _FORMATTER = Formatter(
        "%(levelname)s %(name)s:%(funcName)s(%(lineno)d): %(message)s"
    )


def dashlist(iterable, indent=2):
    return "".join("\n" + " " * indent + "- " + str(x) for x in iterable)


class ContextDecorator:
    """Base class for a context manager class (implementing __enter__() and __exit__()) that also
    makes it a decorator.
    """

    # TODO: figure out how to improve this pattern so e.g. swallow_broken_pipe doesn't have to be instantiated  # NOQA

    def __call__(self, f):
        @wraps(f)
        def decorated(*args, **kwds):
            with self:
                return f(*args, **kwds)

        return decorated


class SwallowBrokenPipe(ContextDecorator):
    # Ignore BrokenPipeError and errors related to stdout or stderr being
    # closed by a downstream program.

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        if (
            exc_val
            and isinstance(exc_val, EnvironmentError)
            and getattr(exc_val, "errno", None)
            and exc_val.errno in (EPIPE, ESHUTDOWN)
        ):
            return True


swallow_broken_pipe = SwallowBrokenPipe()


class CaptureTarget(Enum):
    """Constants used for contextmanager captured.

    Used similarly like the constants PIPE, STDOUT for stdlib's subprocess.Popen.
    """

    STRING = -1
    STDOUT = -2


@contextmanager
def env_vars(var_map=None, callback=None, stack_callback=None):
    if var_map is None:
        var_map = {}

    new_var_map = encode_environment(var_map)
    saved_vars = {}
    for name, value in new_var_map.items():
        saved_vars[name] = os.environ.get(name, NULL)
        os.environ[name] = value
    try:
        if callback:
            callback()
        if stack_callback:
            stack_callback(True)
        yield
    finally:
        for name, value in saved_vars.items():
            if value is NULL:
                del os.environ[name]
            else:
                os.environ[name] = value
        if callback:
            callback()
        if stack_callback:
            stack_callback(False)


@contextmanager
def env_var(name, value, callback=None, stack_callback=None):
    d = {name: value}
    with env_vars(d, callback=callback, stack_callback=stack_callback) as es:
        yield es


@contextmanager
def env_unmodified(callback=None):
    with env_vars(callback=callback) as es:
        yield es


@contextmanager
def captured(stdout=CaptureTarget.STRING, stderr=CaptureTarget.STRING):
    r"""Capture outputs of sys.stdout and sys.stderr.

    If stdout is STRING, capture sys.stdout as a string,
    if stdout is None, do not capture sys.stdout, leaving it untouched,
    otherwise redirect sys.stdout to the file-like object given by stdout.

    Behave correspondingly for stderr with the exception that if stderr is STDOUT,
    redirect sys.stderr to stdout target and set stderr attribute of yielded object to None.

    .. code-block:: pycon

       >>> from conda.common.io import captured
       >>> with captured() as c:
       ...     print("hello world!")
       ...
       >>> c.stdout
       'hello world!\n'

    Args:
        stdout: capture target for sys.stdout, one of STRING, None, or file-like object
        stderr: capture target for sys.stderr, one of STRING, STDOUT, None, or file-like object

    Yields:
        CapturedText: has attributes stdout, stderr which are either strings, None or the
            corresponding file-like function argument.
    """

    def write_wrapper(self, to_write):
        # NOTE: This function is not thread-safe.  Using within multi-threading may cause spurious
        # behavior of not returning sys.stdout and sys.stderr back to their 'proper' state
        # This may have to deal with a *lot* of text.
        if hasattr(self, "mode") and "b" in self.mode:
            wanted = bytes
        elif isinstance(self, BytesIO):
            wanted = bytes
        else:
            wanted = str
        if not isinstance(to_write, wanted):
            if hasattr(to_write, "decode"):
                decoded = to_write.decode("utf-8")
                self.old_write(decoded)
            elif hasattr(to_write, "encode"):
                b = to_write.encode("utf-8")
                self.old_write(b)
        else:
            self.old_write(to_write)

    class CapturedText:
        pass

    # sys.stdout.write(u'unicode out')
    # sys.stdout.write(bytes('bytes out', encoding='utf-8'))
    # sys.stdout.write(str('str out'))
    saved_stdout, saved_stderr = sys.stdout, sys.stderr
    if stdout == CaptureTarget.STRING:
        outfile = StringIO()
        outfile.old_write = outfile.write
        outfile.write = partial(write_wrapper, outfile)
        sys.stdout = outfile
    else:
        outfile = stdout
        if outfile is not None:
            sys.stdout = outfile
    if stderr == CaptureTarget.STRING:
        errfile = StringIO()
        errfile.old_write = errfile.write
        errfile.write = partial(write_wrapper, errfile)
        sys.stderr = errfile
    elif stderr == CaptureTarget.STDOUT:
        sys.stderr = errfile = outfile
    else:
        errfile = stderr
        if errfile is not None:
            sys.stderr = errfile
    c = CapturedText()
    log.debug("overtaking stderr and stdout")
    try:
        yield c
    finally:
        if stdout == CaptureTarget.STRING:
            c.stdout = outfile.getvalue()
        else:
            c.stdout = outfile
        if stderr == CaptureTarget.STRING:
            c.stderr = errfile.getvalue()
        elif stderr == CaptureTarget.STDOUT:
            c.stderr = None
        else:
            c.stderr = errfile
        sys.stdout, sys.stderr = saved_stdout, saved_stderr
        log.debug("stderr and stdout yielding back")


@contextmanager
def argv(args_list):
    saved_args = sys.argv
    sys.argv = args_list
    try:
        yield
    finally:
        sys.argv = saved_args


@contextmanager
def _logger_lock():
    logging._acquireLock()
    try:
        yield
    finally:
        logging._releaseLock()


@contextmanager
def disable_logger(logger_name):
    logr = getLogger(logger_name)
    _lvl, _dsbld, _prpgt = logr.level, logr.disabled, logr.propagate
    null_handler = NullHandler()
    with _logger_lock():
        logr.addHandler(null_handler)
        logr.setLevel(CRITICAL + 1)
        logr.disabled, logr.propagate = True, False
    try:
        yield
    finally:
        with _logger_lock():
            logr.removeHandler(null_handler)  # restore list logr.handlers
            logr.level, logr.disabled = _lvl, _dsbld
            logr.propagate = _prpgt


@contextmanager
def stderr_log_level(level, logger_name=None):
    logr = getLogger(logger_name)
    _hndlrs, _lvl, _dsbld, _prpgt = (
        logr.handlers,
        logr.level,
        logr.disabled,
        logr.propagate,
    )
    handler = StreamHandler(sys.stderr)
    handler.name = "stderr"
    handler.setLevel(level)
    handler.setFormatter(_FORMATTER)
    with _logger_lock():
        logr.setLevel(level)
        logr.handlers, logr.disabled, logr.propagate = [], False, False
        logr.addHandler(handler)
        logr.setLevel(level)
    try:
        yield
    finally:
        with _logger_lock():
            logr.handlers, logr.level, logr.disabled = _hndlrs, _lvl, _dsbld
            logr.propagate = _prpgt


def attach_stderr_handler(
    level=WARN,
    logger_name=None,
    propagate=False,
    formatter=None,
    filters=None,
):
    """Attach a new `stderr` handler to the given logger and configure both.

    This function creates a new StreamHandler that writes to `stderr` and attaches it
    to the logger given by `logger_name` (which maybe `None`, in which case the root
    logger is used). If the logger already has a handler by the name of `stderr`, it is
    removed first.

    The given `level` is set **for the handler**, not for the logger; however, this
    function also sets the level of the given logger to the minimum of its current
    effective level and the new handler level, ensuring that the handler will receive the
    required log records, while minimizing the number of unnecessary log events. It also
    sets the loggers `propagate` property according to the `propagate` argument.
    The `formatter` argument can be used to set the formatter of the handler.
    """
    # get old stderr logger
    logr = getLogger(logger_name)
    old_stderr_handler = next(
        (handler for handler in logr.handlers if handler.name == "stderr"), None
    )

    # create new stderr logger
    new_stderr_handler = StreamHandler(sys.stderr)
    new_stderr_handler.name = "stderr"
    new_stderr_handler.setLevel(level)
    new_stderr_handler.setFormatter(formatter or _FORMATTER)
    for filter_ in filters or ():
        new_stderr_handler.addFilter(filter_)

    # do the switch
    with _logger_lock():
        if old_stderr_handler:
            logr.removeHandler(old_stderr_handler)
        logr.addHandler(new_stderr_handler)
        if level < logr.getEffectiveLevel():
            logr.setLevel(level)
        logr.propagate = propagate


def timeout(timeout_secs, func, *args, default_return=None, **kwargs):
    """Enforce a maximum time for a callable to complete.
    Not yet implemented on Windows.
    """
    if on_win:
        # Why does Windows have to be so difficult all the time? Kind of gets old.
        # Guess we'll bypass Windows timeouts for now.
        try:
            return func(*args, **kwargs)
        except KeyboardInterrupt:  # pragma: no cover
            return default_return
    else:

        class TimeoutException(Exception):
            pass

        def interrupt(signum, frame):
            raise TimeoutException()

        signal.signal(signal.SIGALRM, interrupt)
        signal.alarm(timeout_secs)

        try:
            ret = func(*args, **kwargs)
            signal.alarm(0)
            return ret
        except (TimeoutException, KeyboardInterrupt):  # pragma: no cover
            return default_return


class Spinner:
    """
    Args:
        message (str):
            A message to prefix the spinner with. The string ': ' is automatically appended.
        enabled (bool):
            If False, usage is a no-op.
        json (bool):
           If True, will not output non-json to stdout.

    """

    # spinner_cycle = cycle("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏")
    spinner_cycle = cycle("/-\\|")

    def __init__(self, message, enabled=True, json=False, fail_message="failed\n"):
        self.message = message
        self.enabled = enabled
        self.json = json

        self._stop_running = Event()
        self._spinner_thread = Thread(target=self._start_spinning)
        self._indicator_length = len(next(self.spinner_cycle)) + 1
        self.fh = sys.stdout
        self.show_spin = enabled and not json and IS_INTERACTIVE
        self.fail_message = fail_message

    def start(self):
        if self.show_spin:
            self._spinner_thread.start()
        elif not self.json:
            self.fh.write("...working... ")
            self.fh.flush()

    def stop(self):
        if self.show_spin:
            self._stop_running.set()
            self._spinner_thread.join()
            self.show_spin = False

    def _start_spinning(self):
        try:
            while not self._stop_running.is_set():
                self.fh.write(next(self.spinner_cycle) + " ")
                self.fh.flush()
                sleep(0.10)
                self.fh.write("\b" * self._indicator_length)
        except OSError as e:
            if e.errno in (EPIPE, ESHUTDOWN):
                self.stop()
            else:
                raise

    @swallow_broken_pipe
    def __enter__(self):
        if not self.json:
            sys.stdout.write(f"{self.message}: ")
            sys.stdout.flush()
        self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        if not self.json:
            with swallow_broken_pipe:
                if exc_type or exc_val:
                    sys.stdout.write(self.fail_message)
                else:
                    sys.stdout.write("done\n")
                sys.stdout.flush()


class ProgressBar:
    @classmethod
    def get_lock(cls):
        # Used only for --json (our own sys.stdout.write/flush calls).
        if not hasattr(cls, "_lock"):
            cls._lock = RLock()
        return cls._lock

    def __init__(
        self, description, enabled=True, json=False, position=None, leave=True
    ):
        """
        Args:
            description (str):
                The name of the progress bar, shown on left side of output.
            enabled (bool):
                If False, usage is a no-op.
            json (bool):
                If true, outputs json progress to stdout rather than a progress bar.
                Currently, the json format assumes this is only used for "fetch", which
                maintains backward compatibility with conda 4.3 and earlier behavior.
        """
        self.description = description
        self.enabled = enabled
        self.json = json

        if json:
            pass
        elif enabled:
            if IS_INTERACTIVE:
                bar_format = "{desc}{bar} | {percentage:3.0f}% "
                try:
                    self.pbar = self._tqdm(
                        desc=description,
                        bar_format=bar_format,
                        ascii=True,
                        total=1,
                        file=sys.stdout,
                        position=position,
                        leave=leave,
                    )
                except OSError as e:
                    if e.errno in (EPIPE, ESHUTDOWN):
                        self.enabled = False
                    else:
                        raise
            else:
                self.pbar = None
                sys.stdout.write(f"{description} ...working...")

    def update_to(self, fraction):
        try:
            if self.enabled:
                if self.json:
                    with self.get_lock():
                        sys.stdout.write(
                            f'{{"fetch":"{self.description}","finished":false,"maxval":1,"progress":{fraction:f}}}\n\0'
                        )
                elif IS_INTERACTIVE:
                    self.pbar.update(fraction - self.pbar.n)
                elif fraction == 1:
                    sys.stdout.write(" done\n")
        except OSError as e:
            if e.errno in (EPIPE, ESHUTDOWN):
                self.enabled = False
            else:
                raise

    def finish(self):
        self.update_to(1)

    def refresh(self):
        """Force refresh i.e. once 100% has been reached"""
        if self.enabled and not self.json and IS_INTERACTIVE:
            self.pbar.refresh()

    @swallow_broken_pipe
    def close(self):
        if self.enabled:
            if self.json:
                with self.get_lock():
                    sys.stdout.write(
                        f'{{"fetch":"{self.description}","finished":true,"maxval":1,"progress":1}}\n\0'
                    )
                    sys.stdout.flush()
            elif IS_INTERACTIVE:
                self.pbar.close()
            else:
                sys.stdout.write(" done\n")

    @staticmethod
    def _tqdm(*args, **kwargs):
        """Deferred import so it doesn't hit the `conda activate` paths."""
        from tqdm.auto import tqdm

        return tqdm(*args, **kwargs)


# use this for debugging, because ProcessPoolExecutor isn't pdb/ipdb friendly
class DummyExecutor(Executor):
    def __init__(self):
        self._shutdown = False
        self._shutdownLock = Lock()

    def submit(self, fn, *args, **kwargs):
        with self._shutdownLock:
            if self._shutdown:
                raise RuntimeError("cannot schedule new futures after shutdown")

            f = Future()
            try:
                result = fn(*args, **kwargs)
            except BaseException as e:
                f.set_exception(e)
            else:
                f.set_result(result)

            return f

    def map(self, func, *iterables):
        for iterable in iterables:
            for thing in iterable:
                yield func(thing)

    def shutdown(self, wait=True):
        with self._shutdownLock:
            self._shutdown = True


class ThreadLimitedThreadPoolExecutor(ThreadPoolExecutor):
    def __init__(self, max_workers=10):
        super().__init__(max_workers)

    def submit(self, fn, *args, **kwargs):
        """
        This is an exact reimplementation of the `submit()` method on the parent class, except
        with an added `try/except` around `self._adjust_thread_count()`.  So long as there is at
        least one living thread, this thread pool will not throw an exception if threads cannot
        be expanded to `max_workers`.

        In the implementation, we use "protected" attributes from concurrent.futures (`_base`
        and `_WorkItem`). Consider vendoring the whole concurrent.futures library
        as an alternative to these protected imports.

        https://github.com/agronholm/pythonfutures/blob/3.2.0/concurrent/futures/thread.py#L121-L131  # NOQA
        https://github.com/python/cpython/blob/v3.6.4/Lib/concurrent/futures/thread.py#L114-L124
        """
        with self._shutdown_lock:
            if self._shutdown:
                raise RuntimeError("cannot schedule new futures after shutdown")

            f = _base.Future()
            w = _WorkItem(f, fn, args, kwargs)

            self._work_queue.put(w)
            try:
                self._adjust_thread_count()
            except RuntimeError:
                # RuntimeError: can't start new thread
                # See https://github.com/conda/conda/issues/6624
                if len(self._threads) > 0:
                    # It's ok to not be able to start new threads if we already have at least
                    # one thread alive.
                    pass
                else:
                    raise
            return f


as_completed = as_completed


def get_instrumentation_record_file():
    default_record_file = join("~", ".conda", "instrumentation-record.csv")
    return expand(
        os.environ.get("CONDA_INSTRUMENTATION_RECORD_FILE", default_record_file)
    )


class time_recorder(ContextDecorator):  # pragma: no cover
    record_file = get_instrumentation_record_file()
    start_time = None
    total_call_num = defaultdict(int)
    total_run_time = defaultdict(float)

    def __init__(self, entry_name=None, module_name=None):
        self.entry_name = entry_name
        self.module_name = module_name

    def _set_entry_name(self, f):
        if self.entry_name is None:
            if hasattr(f, "__qualname__"):
                entry_name = f.__qualname__
            else:
                entry_name = ":" + f.__name__
            if self.module_name:
                entry_name = ".".join((self.module_name, entry_name))
            self.entry_name = entry_name

    def __call__(self, f):
        self._set_entry_name(f)
        return super().__call__(f)

    def __enter__(self):
        enabled = os.environ.get("CONDA_INSTRUMENTATION_ENABLED")
        if enabled and boolify(enabled):
            self.start_time = time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            entry_name = self.entry_name
            end_time = time()
            run_time = end_time - self.start_time
            self.total_call_num[entry_name] += 1
            self.total_run_time[entry_name] += run_time
            self._ensure_dir()
            with open(self.record_file, "a") as fh:
                fh.write(f"{entry_name},{run_time:f}\n")
            # total_call_num = self.total_call_num[entry_name]
            # total_run_time = self.total_run_time[entry_name]
            # log.debug('%s %9.3f %9.3f %d', entry_name, run_time, total_run_time, total_call_num)

    @classmethod
    def log_totals(cls):
        enabled = os.environ.get("CONDA_INSTRUMENTATION_ENABLED")
        if not (enabled and boolify(enabled)):
            return
        log.info("=== time_recorder total time and calls ===")
        for entry_name in sorted(cls.total_run_time.keys()):
            log.info(
                "TOTAL %9.3f % 9d %s",
                cls.total_run_time[entry_name],
                cls.total_call_num[entry_name],
                entry_name,
            )

    @memoizemethod
    def _ensure_dir(self):
        if not isdir(dirname(self.record_file)):
            os.makedirs(dirname(self.record_file))


def print_instrumentation_data():  # pragma: no cover
    record_file = get_instrumentation_record_file()

    grouped_data = defaultdict(list)
    final_data = {}

    if not isfile(record_file):
        return

    with open(record_file) as fh:
        for line in fh:
            entry_name, total_time = line.strip().split(",")
            grouped_data[entry_name].append(float(total_time))

    for entry_name in sorted(grouped_data):
        all_times = grouped_data[entry_name]
        counts = len(all_times)
        total_time = sum(all_times)
        average_time = total_time / counts
        final_data[entry_name] = {
            "counts": counts,
            "total_time": total_time,
            "average_time": average_time,
        }

    print(json.dumps(final_data, sort_keys=True, indent=2, separators=(",", ": ")))


if __name__ == "__main__":
    print_instrumentation_data()
