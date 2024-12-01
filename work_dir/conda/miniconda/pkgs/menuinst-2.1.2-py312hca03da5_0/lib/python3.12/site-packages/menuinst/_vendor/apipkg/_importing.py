from __future__ import annotations

import os
import sys


def _py_abspath(path: str) -> str:
    """
    special version of abspath
    that will leave paths from jython jars alone
    """
    if path.startswith("__pyclasspath__"):
        return path
    else:
        return os.path.abspath(path)


def distribution_version(name: str) -> str | None:
    """try to get the version of the named distribution,
    returns None on failure"""
    if sys.version_info >= (3, 8):
        from importlib.metadata import PackageNotFoundError, version
    else:
        from importlib_metadata import PackageNotFoundError, version
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def importobj(modpath: str, attrname: str | None) -> object:
    """imports a module, then resolves the attrname on it"""
    module = __import__(modpath, None, None, ["__doc__"])
    if not attrname:
        return module

    retval = module
    names = attrname.split(".")
    for x in names:
        retval = getattr(retval, x)
    return retval
