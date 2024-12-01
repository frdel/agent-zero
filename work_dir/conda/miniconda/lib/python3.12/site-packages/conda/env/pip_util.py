# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""
Functions related to core conda functionality that relates to pip

NOTE: This modules used to in conda, as conda/pip.py
"""

import os
import re
import sys
from logging import getLogger

from ..base.context import context
from ..common.compat import on_win
from ..exceptions import CondaEnvException
from ..gateways.subprocess import any_subprocess

log = getLogger(__name__)


def pip_subprocess(args, prefix, cwd):
    """Run pip in a subprocess"""
    if on_win:
        python_path = os.path.join(prefix, "python.exe")
    else:
        python_path = os.path.join(prefix, "bin", "python")
    run_args = [python_path, "-m", "pip"] + args
    stdout, stderr, rc = any_subprocess(run_args, prefix, cwd=cwd)
    if not context.quiet and not context.json:
        print("Ran pip subprocess with arguments:")
        print(run_args)
        print("Pip subprocess output:")
        print(stdout)
    if rc != 0:
        print("Pip subprocess error:", file=sys.stderr)
        print(stderr, file=sys.stderr)
        raise CondaEnvException("Pip failed")

    return stdout, stderr


def get_pip_installed_packages(stdout):
    """Return the list of pip packages installed based on the command output"""
    m = re.search(r"Successfully installed\ (.*)", stdout)
    if m:
        return m.group(1).strip().split()
    else:
        return None
