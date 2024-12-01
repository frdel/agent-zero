"""
apipkg: control the exported namespace of a Python package.

see https://pypi.python.org/pypi/apipkg

(c) holger krekel, 2009 - MIT license
"""
from __future__ import annotations

__all__ = ["initpkg", "ApiModule", "AliasModule", "__version__", "distribution_version"]
import sys
from typing import Any

from ._alias_module import AliasModule
from ._importing import distribution_version as distribution_version
from ._module import _initpkg
from ._module import ApiModule
from ._version import version as __version__


def initpkg(
    pkgname: str,
    exportdefs: dict[str, Any],
    attr: dict[str, object] | None = None,
    eager: bool = False,
) -> ApiModule:
    """initialize given package from the export definitions."""
    attr = attr or {}
    mod = sys.modules.get(pkgname)

    mod = _initpkg(mod, pkgname, exportdefs, attr=attr)

    # eagerload in bypthon to avoid their monkeypatching breaking packages
    if "bpython" in sys.modules or eager:
        for module in list(sys.modules.values()):
            if isinstance(module, ApiModule):
                getattr(module, "__dict__")

    return mod
