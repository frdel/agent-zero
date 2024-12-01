# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
# Attempt to move any conda entries in PATH to the front of it.
# IDEs have their own ideas about how PATH should be managed and
# they do dumb stuff like add /usr/bin to the front of it
# meaning conda takes a submissive role and the wrong stuff
# runs (when other conda prefixes get activated they replace
# the wrongly placed entries with newer wrongly placed entries).
#
# Note, there's still condabin to worry about here, and also should
# we not remove all traces of conda instead of just this fixup?
# Ideally we'd have two modes, 'removed' and 'fixed'. I have seen
# condabin come from an entirely different installation than
# CONDA_PREFIX too in some instances and that really needs fixing.
from __future__ import annotations

import os
import sys
import warnings
from logging import getLogger
from os.path import join
from pathlib import Path

from ..common.compat import on_win
from ..deprecations import deprecated
from .fixtures import (
    CondaCLIFixture,
    PathFactoryFixture,
    TmpChannelFixture,
    TmpEnvFixture,
    conda_cli,
    context_aware_monkeypatch,
    path_factory,
    tmp_channel,
    tmp_env,
    tmp_envs_dir,
    tmp_pkgs_dir,
)

log = getLogger(__name__)


@deprecated(
    "24.9",
    "25.3",
    addendum="It don't matter which environment the test suite is run from.",
)
def conda_ensure_sys_python_is_base_env_python():
    # Exit if we try to run tests from a non-base env. The tests end up installing
    # menuinst into the env they are called with and that breaks non-base env activation
    # as it emits a message to stderr:
    # WARNING menuinst_win32:<module>(157): menuinst called from non-root env
    # C:\opt\conda\envs\py27
    # So lets just sys.exit on that.

    if "CONDA_PYTHON_EXE" in os.environ:
        if (
            Path(os.environ["CONDA_PYTHON_EXE"]).resolve()
            != Path(sys.executable).resolve()
        ):
            warnings.warn(
                "ERROR :: Running tests from a non-base Python interpreter. "
                " Tests requires installing menuinst and that causes stderr "
                " output when activated.\n"
                f"- CONDA_PYTHON_EXE={os.environ['CONDA_PYTHON_EXE']}\n"
                f"- sys.executable={sys.executable}"
            )

            # menuinst only really matters on windows
            if on_win:
                sys.exit(-1)


def conda_move_to_front_of_PATH():
    if "CONDA_PREFIX" in os.environ:
        from ..activate import CmdExeActivator, PosixActivator

        if os.name == "nt":
            activator_cls = CmdExeActivator
        else:
            activator_cls = PosixActivator
        activator = activator_cls()
        # But why not just use _replace_prefix_in_path? => because moving
        # the entries to the front of PATH is the goal here, not swapping
        # x for x (which would be pointless anyway).
        p = None
        # It might be nice to have a parameterised fixture with choices of:
        # 'System default PATH',
        # 'IDE default PATH',
        # 'Fully activated conda',
        # 'PATHly activated conda'
        # This will do for now => Note, if you have conda activated multiple
        # times it could mask some test failures but _remove_prefix_from_path
        # cannot be used multiple times; it will only remove *one* conda
        # prefix from the *original* value of PATH, calling it N times will
        # just return the same value every time, even if you update PATH.
        p = activator._remove_prefix_from_path(os.environ["CONDA_PREFIX"])

        # Replace any non sys.prefix condabin with sys.prefix condabin
        new_p = []
        found_condabin = False
        for pe in p:
            if pe.endswith("condabin"):
                if not found_condabin:
                    found_condabin = True
                    if join(sys.prefix, "condabin") != pe:
                        condabin_path = join(sys.prefix, "condabin")
                        print(f"Incorrect condabin, swapping {pe} to {condabin_path}")
                        new_p.append(condabin_path)
                    else:
                        new_p.append(pe)
            else:
                new_p.append(pe)

        os.environ["PATH"] = os.pathsep.join(new_p)
        activator = activator_cls()
        p = activator._add_prefix_to_path(os.environ["CONDA_PREFIX"])
        os.environ["PATH"] = os.pathsep.join(p)


deprecated.constant(
    "25.3",
    "25.9",
    "CondaCLIFixture",
    CondaCLIFixture,
    addendum="Use `conda.testing.fixtures.CondaCLIFixture` instead.",
)
del CondaCLIFixture
deprecated.constant(
    "25.3",
    "25.9",
    "conda_cli",
    conda_cli,
    addendum="Use `conda.testing.fixtures.conda_cli` instead.",
)
del conda_cli
deprecated.constant(
    "25.3",
    "25.9",
    "PathFactoryFixture",
    PathFactoryFixture,
    addendum="Use `conda.testing.fixtures.PathFactoryFixture` instead.",
)
del PathFactoryFixture
deprecated.constant(
    "25.3",
    "25.9",
    "path_factory",
    path_factory,
    addendum="Use `conda.testing.fixtures.path_factory` instead.",
)
del path_factory
deprecated.constant(
    "25.3",
    "25.9",
    "TmpEnvFixture",
    TmpEnvFixture,
    addendum="Use `conda.testing.fixtures.TmpEnvFixture` instead.",
)
del TmpEnvFixture
deprecated.constant(
    "25.3",
    "25.9",
    "tmp_env",
    tmp_env,
    addendum="Use `conda.testing.fixtures.tmp_env` instead.",
)
del tmp_env
deprecated.constant(
    "25.3",
    "25.9",
    "TmpChannelFixture",
    TmpChannelFixture,
    addendum="Use `conda.testing.fixtures.TmpChannelFixture` instead.",
)
del TmpChannelFixture
deprecated.constant(
    "25.3",
    "25.9",
    "tmp_channel",
    tmp_channel,
    addendum="Use `conda.testing.fixtures.tmp_channel` instead.",
)
del tmp_channel
deprecated.constant(
    "25.3",
    "25.9",
    "context_aware_monkeypatch",
    context_aware_monkeypatch,
    addendum="Use `conda.testing.fixtures.context_aware_monkeypatch` instead.",
)
del context_aware_monkeypatch
deprecated.constant(
    "25.3",
    "25.9",
    "tmp_pkgs_dir",
    tmp_pkgs_dir,
    addendum="Use `conda.testing.fixtures.tmp_pkgs_dir` instead.",
)
del tmp_pkgs_dir
deprecated.constant(
    "25.3",
    "25.9",
    "tmp_envs_dir",
    tmp_envs_dir,
    addendum="Use `conda.testing.fixtures.tmp_envs_dir` instead.",
)
del tmp_envs_dir
