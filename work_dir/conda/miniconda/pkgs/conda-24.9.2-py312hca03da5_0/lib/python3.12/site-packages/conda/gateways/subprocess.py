# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Helpler functions for subprocess."""

from __future__ import annotations

import os
import sys
from collections import namedtuple
from logging import getLogger
from os.path import abspath
from subprocess import PIPE, CalledProcessError, Popen
from typing import TYPE_CHECKING

from .. import ACTIVE_SUBPROCESSES
from ..auxlib.compat import shlex_split_unicode
from ..auxlib.ish import dals
from ..base.context import context
from ..common.compat import encode_environment, isiterable
from ..common.constants import TRACE
from ..gateways.disk.delete import rm_rf
from ..utils import wrap_subprocess_call

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Sequence

log = getLogger(__name__)
Response = namedtuple("Response", ("stdout", "stderr", "rc"))


def _format_output(command_str, cwd, rc, stdout, stderr):
    return dals(
        """
    $ %s
    ==> cwd: %s <==
    ==> exit code: %d <==
    ==> stdout <==
    %s
    ==> stderr <==
    %s
    """
    ) % (command_str, cwd, rc, stdout, stderr)


def any_subprocess(args, prefix, env=None, cwd=None):
    script_caller, command_args = wrap_subprocess_call(
        context.root_prefix,
        prefix,
        context.dev,
        context.debug,
        args,
    )
    process = Popen(
        command_args,
        cwd=cwd or prefix,
        universal_newlines=False,
        stdout=PIPE,
        stderr=PIPE,
        env=env,
    )
    stdout, stderr = process.communicate()
    if script_caller is not None:
        if "CONDA_TEST_SAVE_TEMPS" not in os.environ:
            rm_rf(script_caller)
        else:
            log.warning(
                f"CONDA_TEST_SAVE_TEMPS :: retaining pip run_script {script_caller}"
            )
    if hasattr(stdout, "decode"):
        stdout = stdout.decode("utf-8", errors="replace")
    if hasattr(stderr, "decode"):
        stderr = stderr.decode("utf-8", errors="replace")
    return stdout, stderr, process.returncode


def subprocess_call(
    command: str | os.PathLike | Path | Sequence[str | os.PathLike | Path],
    env: dict[str, str] | None = None,
    path: str | os.PathLike | Path | None = None,
    stdin: str | None = None,
    raise_on_error: bool = True,
    capture_output: bool = True,
):
    """This utility function should be preferred for all conda subprocessing.
    It handles multiple tricky details.
    """
    env = encode_environment(env or os.environ)
    cwd = sys.prefix if path is None else abspath(path)
    if not isiterable(command):
        command = shlex_split_unicode(command)
    try:
        command_str = os.fspath(command)
    except TypeError:
        # TypeError: command is not a str or PathLike
        command_str = " ".join(map(os.fspath, command))
    log.debug("executing>> %s", command_str)

    pipe = None
    if capture_output:
        pipe = PIPE
    elif stdin:
        raise ValueError("When passing stdin, output needs to be captured")
    else:
        stdin = None

    # spawn subprocess
    process = Popen(
        command,
        cwd=cwd,
        stdin=pipe,
        stdout=pipe,
        stderr=pipe,
        env=env,
        text=True,  # open streams in text mode so that we don't have to decode
        errors="replace",
    )
    ACTIVE_SUBPROCESSES.add(process)

    # decode output, if not PIPE, stdout/stderr will be None
    stdout, stderr = process.communicate(input=stdin)
    rc = process.returncode
    ACTIVE_SUBPROCESSES.remove(process)

    if (raise_on_error and rc != 0) or log.isEnabledFor(TRACE):
        formatted_output = _format_output(command_str, cwd, rc, stdout, stderr)
    if raise_on_error and rc != 0:
        log.info(formatted_output)
        raise CalledProcessError(rc, command, output=formatted_output)
    if log.isEnabledFor(TRACE):
        log.log(TRACE, formatted_output)

    return Response(stdout, stderr, int(rc))


def _subprocess_clean_env(env, clean_python=True, clean_conda=True):
    dels = []
    if clean_python:
        dels.extend(("PYTHONPATH", "PYTHONHOME"))
    if clean_conda:
        dels.extend(
            ("CONDA_ROOT", "CONDA_PROMPT_MODIFIER", "CONDA_EXE", "CONDA_DEFAULT_ENV")
        )
    for key in dels:
        if key in env:
            del env[key]


def subprocess_call_with_clean_env(
    command,
    path=None,
    stdin=None,
    raise_on_error=True,
    clean_python=True,
    clean_conda=True,
):
    # Any of these env vars are likely to mess the whole thing up.
    # This has been seen to be the case with PYTHONPATH.
    env = os.environ.copy()
    _subprocess_clean_env(env, clean_python, clean_conda)
    # env['CONDA_DLL_SEARCH_MODIFICATION_ENABLE'] = '1'
    return subprocess_call(
        command, env=env, path=path, stdin=stdin, raise_on_error=raise_on_error
    )
