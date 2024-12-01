# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Register signature verification as a post-solve plugin."""

from .. import CondaPostSolve, hookimpl


@hookimpl
def conda_post_solves():
    from ...trust.signature_verification import signature_verification

    yield CondaPostSolve(
        name="signature-verification",
        action=signature_verification,
    )
