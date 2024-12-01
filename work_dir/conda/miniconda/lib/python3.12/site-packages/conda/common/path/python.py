# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Common Python specific path utilities."""

from __future__ import annotations

import re
from logging import getLogger
from os.path import join, split, splitext

from ..compat import on_win

log = getLogger(__name__)


def pyc_path(py_path, python_major_minor_version):
    """
    This must not return backslashes on Windows as that will break
    tests and leads to an eventual need to make url_to_path return
    backslashes too and that may end up changing files on disc or
    to the result of comparisons with the contents of them.
    """
    pyver_string = python_major_minor_version.replace(".", "")
    if pyver_string.startswith("2"):
        return py_path + "c"
    else:
        directory, py_file = split(py_path)
        basename_root, extension = splitext(py_file)
        pyc_file = (
            "__pycache__" + "/" + f"{basename_root}.cpython-{pyver_string}{extension}c"
        )
        return "{}{}{}".format(directory, "/", pyc_file) if directory else pyc_file


def missing_pyc_files(python_major_minor_version, files):
    # returns a tuple of tuples, with the inner tuple being the .py file and the missing .pyc file
    py_files = (f for f in files if f.endswith(".py"))
    pyc_matches = (
        (py_file, pyc_path(py_file, python_major_minor_version)) for py_file in py_files
    )
    result = tuple(match for match in pyc_matches if match[1] not in files)
    return result


def parse_entry_point_def(ep_definition):
    cmd_mod, func = ep_definition.rsplit(":", 1)
    command, module = cmd_mod.rsplit("=", 1)
    command, module, func = command.strip(), module.strip(), func.strip()
    return command, module, func


def get_python_short_path(python_version=None):
    if on_win:
        return "python.exe"
    if python_version and "." not in python_version:
        python_version = ".".join(python_version)
    return join("bin", "python%s" % (python_version or ""))


def get_python_site_packages_short_path(python_version):
    if python_version is None:
        return None
    elif on_win:
        return "Lib/site-packages"
    else:
        py_ver = get_major_minor_version(python_version)
        return f"lib/python{py_ver}/site-packages"


_VERSION_REGEX = re.compile(r"[0-9]+\.[0-9]+")


def get_major_minor_version(string, with_dot=True):
    # returns None if not found, otherwise two digits as a string
    # should work for
    #   - 3.5.2
    #   - 27
    #   - bin/python2.7
    #   - lib/python34/site-packages/
    # the last two are dangers because windows doesn't have version information there
    assert isinstance(string, str)
    if string.startswith("lib/python"):
        pythonstr = string.split("/")[1]
        start = len("python")
        if len(pythonstr) < start + 2:
            return None
        maj_min = pythonstr[start], pythonstr[start + 1 :]
    elif string.startswith("bin/python"):
        pythonstr = string.split("/")[1]
        start = len("python")
        if len(pythonstr) < start + 3:
            return None
        assert pythonstr[start + 1] == "."
        maj_min = pythonstr[start], pythonstr[start + 2 :]
    else:
        match = _VERSION_REGEX.match(string)
        if match:
            version = match.group(0).split(".")
            maj_min = version[0], version[1]
        else:
            digits = "".join([c for c in string if c.isdigit()])
            if len(digits) < 2:
                return None
            maj_min = digits[0], digits[1:]

    return ".".join(maj_min) if with_dot else "".join(maj_min)


def get_python_noarch_target_path(source_short_path, target_site_packages_short_path):
    if source_short_path.startswith("site-packages/"):
        sp_dir = target_site_packages_short_path
        return source_short_path.replace("site-packages", sp_dir, 1)
    elif source_short_path.startswith("python-scripts/"):
        from . import BIN_DIRECTORY

        return source_short_path.replace("python-scripts", BIN_DIRECTORY, 1)
    else:
        return source_short_path
