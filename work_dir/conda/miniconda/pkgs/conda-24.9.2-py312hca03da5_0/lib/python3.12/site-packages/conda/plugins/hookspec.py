# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""
Pluggy hook specifications ("hookspecs") to register conda plugins.

Each hookspec defined in :class:`~conda.plugins.hookspec.CondaSpecs` contains
an example of how to use it.

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pluggy

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .types import (
        CondaAuthHandler,
        CondaHealthCheck,
        CondaPostCommand,
        CondaPostSolve,
        CondaPreCommand,
        CondaPreSolve,
        CondaSetting,
        CondaSolver,
        CondaSubcommand,
        CondaVirtualPackage,
    )

spec_name = "conda"
"""Name used for organizing conda hook specifications"""

_hookspec = pluggy.HookspecMarker(spec_name)
"""
The conda plugin hook specifications, to be used by developers
"""

hookimpl = pluggy.HookimplMarker(spec_name)
"""
Decorator used to mark plugin hook implementations
"""


class CondaSpecs:
    """The conda plugin hookspecs, to be used by developers."""

    @_hookspec
    def conda_solvers(self) -> Iterable[CondaSolver]:
        """
        Register solvers in conda.

        **Example:**

        .. code-block:: python

            import logging

            from conda import plugins
            from conda.core import solve

            log = logging.getLogger(__name__)


            class VerboseSolver(solve.Solver):
                def solve_final_state(self, *args, **kwargs):
                    log.info("My verbose solver!")
                    return super().solve_final_state(*args, **kwargs)


            @plugins.hookimpl
            def conda_solvers():
                yield plugins.CondaSolver(
                    name="verbose-classic",
                    backend=VerboseSolver,
                )

        :return: An iterable of solver entries.
        """

    @_hookspec
    def conda_subcommands(self) -> Iterable[CondaSubcommand]:
        """
        Register external subcommands in conda.

        **Example:**

        .. code-block:: python

            from conda import plugins


            def example_command(args):
                print("This is an example command!")


            @plugins.hookimpl
            def conda_subcommands():
                yield plugins.CondaSubcommand(
                    name="example",
                    summary="example command",
                    action=example_command,
                )

        :return: An iterable of subcommand entries.
        """

    @_hookspec
    def conda_virtual_packages(self) -> Iterable[CondaVirtualPackage]:
        """
        Register virtual packages in Conda.

        **Example:**

        .. code-block:: python

            from conda import plugins


            @plugins.hookimpl
            def conda_virtual_packages():
                yield plugins.CondaVirtualPackage(
                    name="my_custom_os",
                    version="1.2.3",
                    build="x86_64",
                )

        :return: An iterable of virtual package entries.
        """

    @_hookspec
    def conda_pre_commands(self) -> Iterable[CondaPreCommand]:
        """
        Register pre-command functions in conda.

        **Example:**

        .. code-block:: python

           from conda import plugins


           def example_pre_command(command):
               print("pre-command action")


           @plugins.hookimpl
           def conda_pre_commands():
               yield plugins.CondaPreCommand(
                   name="example-pre-command",
                   action=example_pre_command,
                   run_for={"install", "create"},
               )
        """

    @_hookspec
    def conda_post_commands(self) -> Iterable[CondaPostCommand]:
        """
        Register post-command functions in conda.

        **Example:**

        .. code-block:: python

           from conda import plugins


           def example_post_command(command):
               print("post-command action")


           @plugins.hookimpl
           def conda_post_commands():
               yield plugins.CondaPostCommand(
                   name="example-post-command",
                   action=example_post_command,
                   run_for={"install", "create"},
               )
        """

    @_hookspec
    def conda_auth_handlers(self) -> Iterable[CondaAuthHandler]:
        """
        Register a conda auth handler derived from the requests API.

        This plugin hook allows attaching requests auth handler subclasses,
        e.g. when authenticating requests against individual channels hosted
        at HTTP/HTTPS services.

        **Example:**

        .. code-block:: python

            import os
            from conda import plugins
            from requests.auth import AuthBase


            class EnvironmentHeaderAuth(AuthBase):
                def __init__(self, *args, **kwargs):
                    self.username = os.environ["EXAMPLE_CONDA_AUTH_USERNAME"]
                    self.password = os.environ["EXAMPLE_CONDA_AUTH_PASSWORD"]

                def __call__(self, request):
                    request.headers["X-Username"] = self.username
                    request.headers["X-Password"] = self.password
                    return request


            @plugins.hookimpl
            def conda_auth_handlers():
                yield plugins.CondaAuthHandler(
                    name="environment-header-auth",
                    auth_handler=EnvironmentHeaderAuth,
                )
        """

    @_hookspec
    def conda_health_checks(self) -> Iterable[CondaHealthCheck]:
        """
        Register health checks for conda doctor.

        This plugin hook allows you to add more "health checks" to conda doctor
        that you can write to diagnose problems in your conda environment.
        Check out the health checks already shipped with conda for inspiration.

        **Example:**

        .. code-block:: python

            from conda import plugins


            def example_health_check(prefix: str, verbose: bool):
                print("This is an example health check!")


            @plugins.hookimpl
            def conda_health_checks():
                yield plugins.CondaHealthCheck(
                    name="example-health-check",
                    action=example_health_check,
                )
        """

    @_hookspec
    def conda_pre_solves(self) -> Iterable[CondaPreSolve]:
        """
        Register pre-solve functions in conda that are used in the
        general solver API, before the solver processes the package specs in
        search of a solution.

        **Example:**

        .. code-block:: python

           from conda import plugins
           from conda.models.match_spec import MatchSpec


           def example_pre_solve(
               specs_to_add: frozenset[MatchSpec],
               specs_to_remove: frozenset[MatchSpec],
           ):
               print(f"Adding {len(specs_to_add)} packages")
               print(f"Removing {len(specs_to_remove)} packages")


           @plugins.hookimpl
           def conda_pre_solves():
               yield plugins.CondaPreSolve(
                   name="example-pre-solve",
                   action=example_pre_solve,
               )
        """

    @_hookspec
    def conda_post_solves(self) -> Iterable[CondaPostSolve]:
        """
        Register post-solve functions in conda that are used in the
        general solver API, after the solver has provided the package
        records to add or remove from the conda environment.

        **Example:**

        .. code-block:: python

           from conda import plugins
           from conda.models.records import PackageRecord


           def example_post_solve(
               repodata_fn: str,
               unlink_precs: tuple[PackageRecord, ...],
               link_precs: tuple[PackageRecord, ...],
           ):
               print(f"Uninstalling {len(unlink_precs)} packages")
               print(f"Installing {len(link_precs)} packages")


           @plugins.hookimpl
           def conda_post_solves():
               yield plugins.CondaPostSolve(
                   name="example-post-solve",
                   action=example_post_solve,
               )
        """

    @_hookspec
    def conda_settings(self) -> Iterable[CondaSetting]:
        """
        Register new setting

        The example below defines a simple string type parameter

        **Example:**

        .. code-block:: python

           from conda import plugins
           from conda.common.configuration import PrimitiveParameter, SequenceParameter


           @plugins.hookimpl
           def conda_settings():
               yield plugins.CondaSetting(
                   name="example_option",
                   description="This is an example option",
                   parameter=PrimitiveParameter("default_value", element_type=str),
                   aliases=("example_option_alias",),
               )
        """
