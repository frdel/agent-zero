# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Register the classic conda solver."""

from ..base.constants import CLASSIC_SOLVER
from . import CondaSolver, hookimpl


@hookimpl(tryfirst=True)  # make sure the classic solver can't be overwritten
def conda_solvers():
    """The classic solver as shipped by default in conda."""
    from ..core.solve import Solver

    yield CondaSolver(
        name=CLASSIC_SOLVER,
        backend=Solver,
    )
