# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""PEP 621 compatible entry point used when `conda init` has not updated the user shell profile."""

import os
import sys
from logging import getLogger

log = getLogger(__name__)


def pip_installed_post_parse_hook(args, p):
    from .. import CondaError

    if args.cmd not in ("init", "info"):
        raise CondaError(
            "Conda has not been initialized.\n"
            "\n"
            "To enable full conda functionality, please run 'conda init'.\n"
            "For additional information, see 'conda init --help'.\n"
        )


def main(*args, **kwargs):
    from .main import main

    os.environ["CONDA_PIP_UNINITIALIZED"] = "true"
    kwargs["post_parse_hook"] = pip_installed_post_parse_hook
    return main(*args, **kwargs)


if __name__ == "__main__":
    sys.exit(main())
