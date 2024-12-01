# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""
This module contains a subclass implementation of pluggy's
`PluginManager <https://pluggy.readthedocs.io/en/stable/api_reference.html#pluggy.PluginManager>`_.

Additionally, it contains a function we use to construct the ``PluginManager`` object and
register all plugins during conda's startup process.
"""

from __future__ import annotations

import functools
import logging
from importlib.metadata import distributions
from inspect import getmodule, isclass
from typing import TYPE_CHECKING, overload

import pluggy

from ..auxlib.ish import dals
from ..base.context import add_plugin_setting, context
from ..deprecations import deprecated
from ..exceptions import CondaValueError, PluginError
from . import post_solves, solvers, subcommands, virtual_packages
from .hookspec import CondaSpecs, spec_name
from .subcommands.doctor import health_checks

if TYPE_CHECKING:
    from typing import Literal

    from requests.auth import AuthBase

    from ..common.configuration import ParameterLoader
    from ..core.solve import Solver
    from ..models.match_spec import MatchSpec
    from ..models.records import PackageRecord
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

log = logging.getLogger(__name__)


class CondaPluginManager(pluggy.PluginManager):
    """
    The conda plugin manager to implement behavior additional to pluggy's default plugin manager.
    """

    #: Cached version of the :meth:`~conda.plugins.manager.CondaPluginManager.get_solver_backend`
    #: method.
    get_cached_solver_backend = None

    def __init__(self, project_name: str | None = None, *args, **kwargs) -> None:
        # Setting the default project name to the spec name for ease of use
        if project_name is None:
            project_name = spec_name
        super().__init__(project_name, *args, **kwargs)
        # Make the cache containers local to the instances so that the
        # reference from cache to the instance gets garbage collected with the instance
        self.get_cached_solver_backend = functools.lru_cache(maxsize=None)(
            self.get_solver_backend
        )

    def get_canonical_name(self, plugin: object) -> str:
        # detect the fully qualified module name
        prefix = "<unknown_module>"
        if (module := getmodule(plugin)) and module.__spec__:
            prefix = module.__spec__.name

        # return the fully qualified name for modules
        if module is plugin:
            return prefix

        # return the fully qualified name for classes
        elif isclass(plugin):
            return f"{prefix}.{plugin.__qualname__}"

        # return the fully qualified name for instances
        else:
            return f"{prefix}.{plugin.__class__.__qualname__}[{id(plugin)}]"

    def register(self, plugin, name: str | None = None) -> str | None:
        """
        Call :meth:`pluggy.PluginManager.register` and return the result or
        ignore errors raised, except ``ValueError``, which means the plugin
        had already been registered.
        """
        try:
            # register plugin but ignore ValueError since that means
            # the plugin has already been registered
            return super().register(plugin, name=name)
        except ValueError:
            return None
        except Exception as err:
            raise PluginError(
                f"Error while loading conda plugin: "
                f"{name or self.get_canonical_name(plugin)} ({err})"
            ) from err

    def load_plugins(self, *plugins) -> int:
        """
        Load the provided list of plugins and fail gracefully on error.
        The provided list of plugins can either be classes or modules with
        :attr:`~conda.plugins.hookimpl`.
        """
        count = 0
        for plugin in plugins:
            if self.register(plugin):
                count += 1
        return count

    def load_entrypoints(self, group: str, name: str | None = None) -> int:
        """Load modules from querying the specified setuptools ``group``.

        :param str group: Entry point group to load plugins.
        :param str name: If given, loads only plugins with the given ``name``.
        :rtype: int
        :return: The number of plugins loaded by this call.
        """
        count = 0
        for dist in distributions():
            for entry_point in dist.entry_points:
                # skip entry points that don't match the group/name
                if entry_point.group != group or (
                    name is not None and entry_point.name != name
                ):
                    continue

                # attempt to load plugin from entry point
                try:
                    plugin = entry_point.load()
                except Exception as err:
                    # not using exc_info=True here since the CLI loggers are
                    # set up after CLI initialization and argument parsing,
                    # meaning that it comes too late to properly render
                    # a traceback; instead we pass exc_info conditionally on
                    # context.verbosity
                    log.warning(
                        f"Error while loading conda entry point: {entry_point.name} ({err})",
                        exc_info=err if context.info else None,
                    )
                    continue

                if self.register(plugin):
                    count += 1
        return count

    @overload
    def get_hook_results(
        self, name: Literal["subcommands"]
    ) -> list[CondaSubcommand]: ...

    @overload
    def get_hook_results(
        self, name: Literal["virtual_packages"]
    ) -> list[CondaVirtualPackage]: ...

    @overload
    def get_hook_results(self, name: Literal["solvers"]) -> list[CondaSolver]: ...

    @overload
    def get_hook_results(
        self, name: Literal["pre_commands"]
    ) -> list[CondaPreCommand]: ...

    @overload
    def get_hook_results(
        self, name: Literal["post_commands"]
    ) -> list[CondaPostCommand]: ...

    @overload
    def get_hook_results(
        self, name: Literal["auth_handlers"]
    ) -> list[CondaAuthHandler]: ...

    @overload
    def get_hook_results(
        self, name: Literal["health_checks"]
    ) -> list[CondaHealthCheck]: ...

    @overload
    def get_hook_results(self, name: Literal["pre_solves"]) -> list[CondaPreSolve]: ...

    @overload
    def get_hook_results(
        self, name: Literal["post_solves"]
    ) -> list[CondaPostSolve]: ...

    @overload
    def get_hook_results(self, name: Literal["settings"]) -> list[CondaSetting]: ...

    def get_hook_results(self, name):
        """
        Return results of the plugin hooks with the given name and
        raise an error if there is a conflict.
        """
        specname = f"{self.project_name}_{name}"  # e.g. conda_solvers
        hook = getattr(self.hook, specname, None)
        if hook is None:
            raise PluginError(f"Could not find requested `{name}` plugins")

        plugins = [item for items in hook() for item in items]

        # Check for invalid names
        invalid = [plugin for plugin in plugins if not isinstance(plugin.name, str)]
        if invalid:
            raise PluginError(
                dals(
                    f"""
                    Invalid plugin names found:

                    {', '.join([str(plugin) for plugin in invalid])}

                    Please report this issue to the plugin author(s).
                    """
                )
            )
        plugins = sorted(plugins, key=lambda plugin: plugin.name)

        # Check for conflicts
        seen = set()
        conflicts = [
            plugin for plugin in plugins if plugin.name in seen or seen.add(plugin.name)
        ]
        if conflicts:
            raise PluginError(
                dals(
                    f"""
                    Conflicting `{name}` plugins found:

                    {', '.join([str(conflict) for conflict in conflicts])}

                    Multiple conda plugins are registered via the `{specname}` hook.
                    Please make sure that you don't have any incompatible plugins installed.
                    """
                )
            )
        return plugins

    def get_solvers(self) -> dict[str, CondaSolver]:
        """Return a mapping from solver name to solver class."""
        return {
            solver_plugin.name.lower(): solver_plugin
            for solver_plugin in self.get_hook_results("solvers")
        }

    def get_solver_backend(self, name: str | None = None) -> type[Solver]:
        """
        Get the solver backend with the given name (or fall back to the
        name provided in the context).

        See ``context.solver`` for more details.

        Please use the cached version of this method called
        :meth:`get_cached_solver_backend` for high-throughput code paths
        which is set up as a instance-specific LRU cache.
        """
        # Some light data validation in case name isn't given.
        if name is None:
            name = context.solver
        name = name.lower()

        solvers_mapping = self.get_solvers()

        # Look up the solver mapping and fail loudly if it can't
        # find the requested solver.
        solver_plugin = solvers_mapping.get(name, None)
        if solver_plugin is None:
            raise CondaValueError(
                f"You have chosen a non-default solver backend ({name}) "
                f"but it was not recognized. Choose one of: "
                f"{', '.join(solvers_mapping)}"
            )

        return solver_plugin.backend

    def get_auth_handler(self, name: str) -> type[AuthBase] | None:
        """
        Get the auth handler with the given name or None
        """
        auth_handlers = self.get_hook_results("auth_handlers")
        matches = tuple(
            item for item in auth_handlers if item.name.lower() == name.lower().strip()
        )

        if len(matches) > 0:
            return matches[0].handler
        return None

    def get_settings(self) -> dict[str, ParameterLoader]:
        """
        Return a mapping of plugin setting name to ParameterLoader class

        This method intentionally overwrites any duplicates that may be present
        """
        return {
            config_param.name.lower(): (config_param.parameter, config_param.aliases)
            for config_param in self.get_hook_results("settings")
        }

    def invoke_pre_commands(self, command: str) -> None:
        """
        Invokes ``CondaPreCommand.action`` functions registered with ``conda_pre_commands``.

        :param command: name of the command that is currently being invoked
        """
        for hook in self.get_hook_results("pre_commands"):
            if command in hook.run_for:
                hook.action(command)

    def invoke_post_commands(self, command: str) -> None:
        """
        Invokes ``CondaPostCommand.action`` functions registered with ``conda_post_commands``.

        :param command: name of the command that is currently being invoked
        """
        for hook in self.get_hook_results("post_commands"):
            if command in hook.run_for:
                hook.action(command)

    def disable_external_plugins(self) -> None:
        """
        Disables all currently registered plugins except built-in conda plugins
        """
        for name, plugin in self.list_name_plugin():
            if not name.startswith("conda.plugins.") and not self.is_blocked(name):
                self.set_blocked(name)

    def get_subcommands(self) -> dict[str, CondaSubcommand]:
        return {
            subcommand.name.lower(): subcommand
            for subcommand in self.get_hook_results("subcommands")
        }

    @deprecated(
        "25.3",
        "25.9",
        addendum="Use `conda.plugins.manager.get_virtual_package_records` instead.",
    )
    def get_virtual_packages(self) -> tuple[CondaVirtualPackage, ...]:
        return tuple(self.get_hook_results("virtual_packages"))

    def get_virtual_package_records(self) -> tuple[PackageRecord, ...]:
        return tuple(
            hook.to_virtual_package()
            for hook in self.get_hook_results("virtual_packages")
        )

    def invoke_health_checks(self, prefix: str, verbose: bool) -> None:
        for hook in self.get_hook_results("health_checks"):
            try:
                hook.action(prefix, verbose)
            except Exception as err:
                log.warning(f"Error running health check: {hook.name} ({err})")
                continue

    def invoke_pre_solves(
        self,
        specs_to_add: frozenset[MatchSpec],
        specs_to_remove: frozenset[MatchSpec],
    ) -> None:
        """
        Invokes ``CondaPreSolve.action`` functions registered with ``conda_pre_solves``.

        :param specs_to_add:
        :param specs_to_remove:
        """
        for hook in self.get_hook_results("pre_solves"):
            hook.action(specs_to_add, specs_to_remove)

    def invoke_post_solves(
        self,
        repodata_fn: str,
        unlink_precs: tuple[PackageRecord, ...],
        link_precs: tuple[PackageRecord, ...],
    ) -> None:
        """
        Invokes ``CondaPostSolve.action`` functions registered with ``conda_post_solves``.

        :param repodata_fn:
        :param unlink_precs:
        :param link_precs:
        """
        for hook in self.get_hook_results("post_solves"):
            hook.action(repodata_fn, unlink_precs, link_precs)

    def load_settings(self) -> None:
        """
        Iterates through all registered settings and adds them to the
        :class:`conda.common.configuration.PluginConfig` class.
        """
        for name, (parameter, aliases) in self.get_settings().items():
            add_plugin_setting(name, parameter, aliases)


@functools.lru_cache(maxsize=None)  # FUTURE: Python 3.9+, replace w/ functools.cache
def get_plugin_manager() -> CondaPluginManager:
    """
    Get a cached version of the :class:`~conda.plugins.manager.CondaPluginManager` instance,
    with the built-in and entrypoints provided by the plugins loaded.
    """
    plugin_manager = CondaPluginManager()
    plugin_manager.add_hookspecs(CondaSpecs)
    plugin_manager.load_plugins(
        solvers,
        *virtual_packages.plugins,
        *subcommands.plugins,
        health_checks,
        *post_solves.plugins,
    )
    plugin_manager.load_entrypoints(spec_name)
    return plugin_manager
