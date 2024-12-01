# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Wrapper for running conda CLI commands as a Python API."""

from logging import getLogger

from ..base.constants import SEARCH_PATH
from ..base.context import context
from ..common.io import CaptureTarget, argv, captured
from ..deprecations import deprecated
from ..exceptions import conda_exception_handler
from ..gateways.logging import initialize_std_loggers
from .conda_argparse import do_call, generate_parser

deprecated.module("24.3", "25.9", addendum="Use `conda.testing.conda_cli` instead.")

log = getLogger(__name__)


class Commands:
    CLEAN = "clean"
    CONFIG = "config"
    CREATE = "create"
    INFO = "info"
    INSTALL = "install"
    LIST = "list"
    REMOVE = "remove"
    SEARCH = "search"
    UPDATE = "update"
    RUN = "run"
    NOTICES = "notices"


STRING = CaptureTarget.STRING
STDOUT = CaptureTarget.STDOUT


# Note, a deviated copy of this code appears in tests/test_create.py
def run_command(command, *arguments, **kwargs):
    """Runs a conda command in-process with a given set of command-line interface arguments.

    Differences from the command-line interface:
        Always uses --yes flag, thus does not ask for confirmation.

    Args:
        command: one of the Commands.
        *arguments: instructions you would normally pass to the conda command on the command line
                    see below for examples. Be very careful to delimit arguments exactly as you
                    want them to be delivered. No 'combine then split at spaces' or other
                    information destroying processing gets performed on the arguments.
        **kwargs: special instructions for programmatic overrides

    Keyword Args:
        use_exception_handler: defaults to False. False will let the code calling
          `run_command` handle all exceptions.  True won't raise when an exception
          has occurred, and instead give a non-zero return code
        search_path: an optional non-standard search path for configuration information
          that overrides the default SEARCH_PATH
        stdout: Define capture behavior for stream sys.stdout. Defaults to STRING.
          STRING captures as a string.  None leaves stream untouched.
          Otherwise redirect to file-like object stdout.
        stderr: Define capture behavior for stream sys.stderr. Defaults to STRING.
          STRING captures as a string.  None leaves stream untouched.
          STDOUT redirects to stdout target and returns None as stderr value.
          Otherwise redirect to file-like object stderr.

    Returns:
        a tuple of stdout, stderr, and return_code.
        stdout, stderr are either strings, None or the corresponding file-like function argument.

    Examples:
        >>> run_command(Commands.CREATE, "-n", "newenv", "python=3", "flask", \
                        use_exception_handler=True)
        >>> run_command(Commands.CREATE, "-n", "newenv", "python=3", "flask")
        >>> run_command(Commands.CREATE, ["-n", "newenv", "python=3", "flask"], search_path=())
    """
    initialize_std_loggers()
    use_exception_handler = kwargs.pop("use_exception_handler", False)
    configuration_search_path = kwargs.pop("search_path", SEARCH_PATH)
    stdout = kwargs.pop("stdout", STRING)
    stderr = kwargs.pop("stderr", STRING)
    p = generate_parser()

    if arguments and isinstance(arguments[0], list):
        arguments = arguments[0]

    arguments = list(arguments)
    arguments.insert(0, command)

    args = p.parse_args(arguments)
    args.yes = True  # always skip user confirmation, force setting context.always_yes
    context.__init__(
        search_path=configuration_search_path,
        argparse_args=args,
    )

    from subprocess import list2cmdline

    log.debug("executing command >>>  conda %s", list2cmdline(arguments))

    is_run = arguments[0] == "run"
    if is_run:
        cap_args = (None, None)
    else:
        cap_args = (stdout, stderr)
    try:
        with argv(["python_api", *arguments]), captured(*cap_args) as c:
            if use_exception_handler:
                result = conda_exception_handler(do_call, args, p)
            else:
                result = do_call(args, p)
        if is_run:
            stdout = result.stdout
            stderr = result.stderr
            result = result.rc
        else:
            stdout = c.stdout
            stderr = c.stderr
    except Exception as e:
        log.debug("\n  stdout: %s\n  stderr: %s", stdout, stderr)
        e.stdout, e.stderr = stdout, stderr
        raise e
    return_code = result or 0
    log.debug(
        "\n  stdout: %s\n  stderr: %s\n  return_code: %s", stdout, stderr, return_code
    )
    return stdout, stderr, return_code
