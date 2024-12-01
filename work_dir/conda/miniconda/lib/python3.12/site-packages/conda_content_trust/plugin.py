# Copyright (C) 2019 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
import conda.plugins

from .cli import cli


@conda.plugins.hookimpl
def conda_subcommands():
    yield conda.plugins.CondaSubcommand(
        name="content-trust",
        summary="Signing and verification tools for Conda",
        action=cli,
    )
