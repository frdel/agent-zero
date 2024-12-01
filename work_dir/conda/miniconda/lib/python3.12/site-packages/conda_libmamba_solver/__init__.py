# Copyright (C) 2022 Anaconda, Inc
# Copyright (C) 2023 conda
# SPDX-License-Identifier: BSD-3-Clause
try:
    from ._version import version as __version__
except ImportError:
    try:
        from importlib.metadata import version

        __version__ = version("conda_libmamba_solver")
        del version
    except ImportError:
        __version__ = "0.0.0.unknown"

from warnings import warn as _warn

from .solver import LibMambaSolver


def get_solver_class(key="libmamba"):
    if key == "libmamba":
        return LibMambaSolver
    if key == "libmamba-draft":
        _warn(
            "The 'libmamba-draft' solver has been deprecated. "
            "The 'libmamba' solver will be used instead. "
            "Please consider updating your code to remove this warning. "
            "Using 'libmamba-draft' will result in an error in a future release.",
        )
        return LibMambaSolver
    raise ValueError("Key must be 'libmamba'")
