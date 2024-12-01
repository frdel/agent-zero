# Copyright (C) 2022 Anaconda, Inc
# Copyright (C) 2023 conda
# SPDX-License-Identifier: BSD-3-Clause
"""
Solver-agnostic logic to compose the requests passed to the solver
and accumulate its results.

The state exposed to the solver is handled by two objects whose primary
function is to serve read-only information to the solver and its other helpers.

- ``SolverInputState``: fully solver agnostic. It handles:
    - The local state on disk, namely the prefix state. This includes the
      already installed packages in the prefix (if any), the explicit requests
      made in that prefix in the past (history), its pinned specs, packages
      configured as aggressive updates and others.
    - The runtime context, determined by the configuration file(s),
      `CONDA_*` environment variables, command line flags and the requested
      specs (if any).
- ``IndexHelper``: can be subclassed to add solver-specific logic
  (e.g. custom index building). It should, provide, at least, a method to
  query the index for the _explicit pool_ of packages for a given spec (e.g.
  its potential dependency tree). Note that the IndexHelper might need
  pieces of ``SolverInputState`` to build the index (e.g. installed packages,
  configured channels and subdirs...)

.. todo::

    Embed IndexHelper in SolverInputState?

Since ``conda`` follows an iterative approach to solve a request,
in addition the _input_ state, the Solver itself can store additional state
in a separate helper: the ``SolverOutputState`` object. This is meant to help
accumulate the following pieces of data:

- ``specs``: a mapping of package names to its corresponding ``MatchSpec``
  objects. These objects are passed to the actual Solver, hoping it will return
  a solution.
- ``records``: a mapping of package names to ``PackageRecord`` objects. It will
  end up containing the list of package records that will compose the final state
  of the prefix (the _solution_). Its default value is set to the currently installed
  packages in the prefix. The solver will alter this list as needed to accommodate
  the final solution.

If the algorithm was not iterative, the sole purpose of the solver would be to turn
the ``specs`` into ``records``. However, ``conda``'s logic will try to constrain the
solution to mimic the initial state as much as possible to reduce the amount of
changes in the prefix. Sometimes, the initial request is too constrained, which results
in a number of conflicts. These conflicts are then stored in the ``conflicts`` mapping,
which will determine which ``specs`` are relaxed in the next attempt. Additionally,
``conda`` stores other solve artifacts:

- ``for_history``: The explicitly requested specs in the command-line should end up
  in the history. Some modifier flags can affect how this mapping is populated (e.g.
  ``--update-deps``.)
- ``neutered``: Pieces of history that were found to be conflicting in the future and
  were annotated as such to avoid falling in the same conflict again.

The mappings stored in ``SolverOutputState`` are backed by ``TrackedMap`` objects,
which allow to keep the reasons _why_ those specs or records were added to the mappings,
as well as richer logging for each action.
"""

# TODO: This module could be part of conda-core once if we refactor the classic logic

import logging
from os import PathLike
from types import MappingProxyType
from typing import Dict, Iterable, Optional, Tuple, Type, Union

from boltons.setutils import IndexedSet
from conda.auxlib import NULL
from conda.base.constants import DepsModifier, UpdateModifier
from conda.base.context import context
from conda.common.path import paths_equal
from conda.core.index import _supplement_index_with_system
from conda.core.prefix_data import PrefixData
from conda.core.solve import get_pinned_specs
from conda.exceptions import PackagesNotFoundError, SpecsConfigurationConflictError
from conda.history import History
from conda.models.channel import Channel
from conda.models.match_spec import MatchSpec
from conda.models.prefix_graph import PrefixGraph
from conda.models.records import PackageRecord

from .utils import EnumAsBools, compatible_specs

log = logging.getLogger(f"conda.{__name__}")


class IndexHelper:
    """
    The _index_ refers to the combination of all configured channels and their
    platform-corresponding subdirectories. It provides the sources for available
    packages that can become part of a prefix state, eventually.

    Subclass this helper to add custom repodata fetching if needed.
    """

    def explicit_pool(self, specs: Iterable[MatchSpec]) -> Iterable[str]:
        raise NotImplementedError


class SolverInputState:
    """
    Helper object to provide the input data needed to compute the state that will be
    exposed to the solver.

    Parameters
    ----------
    prefix
        Path to the prefix we are operating on. This will be used to expose
        ``PrefixData``, ``History``, pinned specs, among others.
    requested
        The MatchSpec objects required by the user (either in the command line or
        through the Python API).
    update_modifier
        A value of ``UpdateModifier``, which has an effect on which specs are added
        to the final list. The default value here must match the default value in the
        ``context`` object.
    deps_modifier
        A value of ``DepsModifier``, which has an effect on which specs are added
        to the final list. The default value here must match the default value in the
        ``context`` object.
    ignore_pinned
        Whether pinned specs can be ignored or not. The default value here must match
        the default value in the ``context`` object.
    force_remove
        Remove the specs without solving the environment (which would also remove their)
        dependencies. The default value here must match the default value in the
        ``context`` object.
    force_reinstall
        Uninstall and install the computed records even if they were already satisfied
        in the given prefix. The default value here must match the default value in the
        ``context`` object.
    prune
        Remove dangling dependencies that ended up orphan. The default value here must
        match the default value in the ``context`` object.
    command
        The subcommand used to invoke this operation (e.g. ``create``, ``install``, ``remove``...).
        It can have an effect on the computed list of records.
    _pip_interop_enabled
        Internal only. Whether ``PrefixData`` will also expose packages not installed by
        ``conda`` (e.g. ``pip`` and others can put Python packages in the prefix).
    """

    _ENUM_STR_MAP = {
        "NOT_SET": DepsModifier.NOT_SET,
        "NO_DEPS": DepsModifier.NO_DEPS,
        "ONLY_DEPS": DepsModifier.ONLY_DEPS,
        "SPECS_SATISFIED_SKIP_SOLVE": UpdateModifier.SPECS_SATISFIED_SKIP_SOLVE,
        "FREEZE_INSTALLED": UpdateModifier.FREEZE_INSTALLED,
        "UPDATE_DEPS": UpdateModifier.UPDATE_DEPS,
        "UPDATE_SPECS": UpdateModifier.UPDATE_SPECS,
        "UPDATE_ALL": UpdateModifier.UPDATE_ALL,
    }
    _DO_NOT_REMOVE_NAMES = (
        "anaconda",
        "conda",
        "conda-build",
        "python.app",
        "console_shortcut",
        "powershell_shortcut",
    )

    def __init__(
        self,
        prefix: Union[str, bytes, PathLike],
        requested: Optional[Iterable[Union[str, MatchSpec]]] = (),
        update_modifier: Optional[UpdateModifier] = UpdateModifier.UPDATE_SPECS,
        deps_modifier: Optional[DepsModifier] = DepsModifier.NOT_SET,
        ignore_pinned: Optional[bool] = None,
        force_remove: Optional[bool] = False,
        force_reinstall: Optional[bool] = False,
        prune: Optional[bool] = False,
        command: Optional[str] = None,
        _pip_interop_enabled: Optional[bool] = None,
    ):
        self.prefix = prefix
        self._prefix_data = PrefixData(prefix, pip_interop_enabled=_pip_interop_enabled)
        self._pip_interop_enabled = _pip_interop_enabled
        self._history = History(prefix).get_requested_specs_map()
        self._pinned = {spec.name: spec for spec in get_pinned_specs(prefix)}
        self._aggressive_updates = {spec.name: spec for spec in context.aggressive_update_packages}

        virtual = {}
        _supplement_index_with_system(virtual)
        self._virtual = {record.name: record for record in virtual}

        self._requested = {}
        for spec in requested:
            spec = MatchSpec(spec)
            self._requested[spec.name] = spec

        self._update_modifier = self._default_to_context_if_null(
            "update_modifier", update_modifier
        )
        if prune and self._update_modifier == UpdateModifier.FREEZE_INSTALLED:
            self._update_modifier = UpdateModifier.UPDATE_SPECS  # revert to default
        self._deps_modifier = self._default_to_context_if_null("deps_modifier", deps_modifier)
        self._ignore_pinned = self._default_to_context_if_null("ignore_pinned", ignore_pinned)
        self._force_remove = self._default_to_context_if_null("force_remove", force_remove)
        self._force_reinstall = self._default_to_context_if_null(
            "force_reinstall", force_reinstall
        )
        self._prune = prune
        self._command = command

        # special cases
        self._do_not_remove = {p: MatchSpec(p) for p in self._DO_NOT_REMOVE_NAMES}

    def _default_to_context_if_null(self, name, value, context=context):
        "Obtain default value from the context if value is set to NULL; otherwise leave as is"
        return getattr(context, name) if value is NULL else self._ENUM_STR_MAP.get(value, value)

    @property
    def prefix_data(self) -> PrefixData:
        """
        A direct reference to the ``PrefixData`` object for the given ``prefix``.
        You will usually use this object through the ``installed`` property.
        """
        return self._prefix_data

    # Prefix state pools

    @property
    def installed(self) -> Dict[str, PackageRecord]:
        """
        This exposes the installed packages in the prefix. Note that a ``PackageRecord``
        can generate an equivalent ``MatchSpec`` object with ``.to_match_spec()``.
        Records are toposorted.
        """
        return MappingProxyType(dict(sorted(self.prefix_data._prefix_records.items())))

    @property
    def history(self) -> Dict[str, MatchSpec]:
        """
        These are the specs that the user explicitly asked for in previous operations
        on the prefix. See :class:`History` for more details.
        """
        return MappingProxyType(self._history)

    @property
    def pinned(self) -> Dict[str, MatchSpec]:
        """
        These specs represent hard constrains on what package versions can be installed
        on the environment. The packages here returned don't need to be already installed.

        If ``ignore_pinned`` is True, this returns an empty dictionary.
        """
        if self.ignore_pinned:
            return MappingProxyType({})
        return MappingProxyType(self._pinned)

    @property
    def virtual(self) -> Dict[str, MatchSpec]:
        """
        System properties exposed as virtual packages (e.g. ``__glibc=2.17``). These packages
        cannot be (un)installed, they only represent constrains for other packages. By convention,
        their names start with a double underscore.
        """
        return MappingProxyType(dict(sorted(self._virtual.items())))

    @property
    def aggressive_updates(self) -> Dict[str, MatchSpec]:
        """
        Packages that the solver will always try to update. As such, they will never have an
        associated version or build constrain. Note that the packages here returned do not need to
        be installed.
        """
        return MappingProxyType(self._aggressive_updates)

    @property
    def always_update(self) -> Dict[str, MatchSpec]:
        """
        Merged lists of packages that should always be updated, depending on the flags, including:
        - aggressive_updates
        - conda if auto_update_conda is true and we are on the base env
        - almost all packages if update_all is true
        - etc
        """
        installed = self.installed
        pinned = self.pinned
        pkgs = {pkg: MatchSpec(pkg) for pkg in self.aggressive_updates if pkg in installed}
        if context.auto_update_conda and paths_equal(self.prefix, context.root_prefix):
            pkgs.setdefault("conda", MatchSpec("conda"))
        if self.update_modifier.UPDATE_ALL:
            for pkg in installed:
                if pkg != "python" and pkg not in pinned:
                    pkgs.setdefault(pkg, MatchSpec(pkg))
        return MappingProxyType(pkgs)

    @property
    def do_not_remove(self) -> Dict[str, MatchSpec]:
        """
        Packages that are protected by the solver so they are not accidentally removed. This list
        is not configurable, but hardcoded for legacy reasons.
        """
        return MappingProxyType(self._do_not_remove)

    @property
    def requested(self) -> Dict[str, MatchSpec]:
        """
        Packages that the user has explicitly asked for in this operation.
        """
        return MappingProxyType(self._requested)

    # Types of commands

    @property
    def is_installing(self) -> bool:
        """
        True if the used subcommand was ``install``.
        """
        return self._command == "install"

    @property
    def is_updating(self) -> bool:
        """
        True if the used subcommand was ``update``.
        """
        return self._command == "update"

    @property
    def is_creating(self) -> bool:
        """
        True if the used subcommand was ``create``.
        """
        return self._command == "create"

    @property
    def is_removing(self) -> bool:
        """
        True if the used subcommand was ``remove``.
        """
        return self._command == "remove"

    # modifiers

    @property
    def update_modifier(self) -> EnumAsBools:
        """
        Use attribute access to test whether the modifier is set to that value

        >>> update_modifier = EnumAsBools(context.update_modifier)
        >>> update_modifier.UPDATE_SPECS
            True
        >>> update_modifier.UPDATE_DEPS
            False
        """
        return EnumAsBools(self._update_modifier)

    @property
    def deps_modifier(self) -> EnumAsBools:
        """
        Use attribute access to test whether the modifier is set to that value

        >>> deps_modifier = EnumAsBools(context.deps_modifier)
        >>> deps_modifier.NOT_SET
            True
        >>> deps_modifier.DEPS_ONLY
            False
        """
        return EnumAsBools(self._deps_modifier)

    # Other flags

    @property
    def ignore_pinned(self) -> bool:
        return self._ignore_pinned

    @property
    def force_remove(self) -> bool:
        return self._force_remove

    @property
    def force_reinstall(self) -> bool:
        return self._force_reinstall

    @property
    def prune(self) -> bool:
        return self._prune

    #  Utility methods

    def channels_from_specs(self) -> Iterable[Channel]:
        """
        Collect all channels added with the `channel::package=*` syntax. For now,
        we only collect those specifically requested by the user in the current command
        (same as conda), but we should investigate whether history keeps channels around
        too.
        """
        for spec in self.requested.values():
            channel = spec.get_exact_value("channel")
            if channel:
                if spec.original_spec_str and spec.original_spec_str.startswith("file://"):
                    # Handle MatchSpec roundtrip issue with local channels
                    channel = Channel(spec.original_spec_str.split("::")[0])
                yield channel

    def channels_from_installed(self, seen=None) -> Iterable[Channel]:
        seen_urls = set(seen or [])
        # See https://github.com/conda/conda/issues/11790
        for record in self.installed.values():
            if record.channel.auth or record.channel.token:
                # skip if the channel has authentication info, because
                # it might cause issues with expired tokens and what not
                continue
            if record.channel.name in ("@", "<develop>", "pypi"):
                # These "channels" are not really channels, more like
                # metadata placeholders
                continue
            if record.channel.base_url is None:
                continue
            if record.channel.subdir_url in seen_urls:
                continue
            seen_urls.add(record.channel.subdir_url)
            yield record.channel

    def maybe_free_channel(self) -> Iterable[Channel]:
        if context.restore_free_channel:
            yield Channel.from_url("https://repo.anaconda.com/pkgs/free")


class SolverOutputState:
    """
    This is the main mutable object we will massage before passing the result of the computation
    (the ``specs`` mapping) to the solver. It will also store the result of the solve (in
    ``records``).

    Parameters
    ----------
    solver_input_state
        This instance provides the initial state for the output.
    records
        Dict of package names to ``PackageRecord`` objects. If not provided, it will be
        initialized from the ``installed`` records in ``solver_input_state``.
    for_history
        Dict of package names to ``MatchSpec`` objects. These specs will be written to
        the prefix history once the solve is complete. Its default initial value is taken from the
        explicitly requested packages in the ``solver_input_state`` instance.
    neutered
        Dict of package names to ``MatchSpec`` objects. These specs are also written to
        the prefix history, as part of the neutered specs. If not provided, their default value is
        a blank mapping.
    conflicts
        If a solve attempt is not successful, conflicting specs are kept here for further
        relaxation of the version and build constrains. If not provided, their default value is a
        blank mapping.
    pins
        Packages that ended up being pinned. Mostly used for reporting and debugging.

    Notes
    -----
    Almost all the attributes in this object map package names (``str``) to ``MatchSpec``
    (_specs_ in short) objects. The only mapping with different values is ``records``, which
    stores ``PackageRecord`` objects. A quick note on these objects:

    * ``MatchSpec`` objects are a query language for packages, based on the ``PackageRecord``
      schema. ``PackageRecord`` objects is how packages that are already installed are
      represented. This is what you get from ``PrefixData.iter_records()``. Since they are
      related, ``MatchSpec`` objects can be created from a ``PackageRecord`` with
      ``.to_match_spec()``.
    * ``MatchSpec`` objects also feature fields like ``target`` and ``optional``. These are,
      essentially, used by the low-level classic solver (:class:`conda.resolve.Resolve`) to
      mark specs as items it can optionally play with to satisfy the solver constrains. A
      ``target`` marked spec is _soft-pinned_ in the sense that the solver will try to satisfy
      that but it will stop trying if it gets in the way, so you might end up a different
      version or build. ``optional`` seems to be in the same lines, but maybe the entire spec
      can be dropped from the request? The key idea here is that these two fields might not be
      directly usable by the solver, but it might need some custom adaptation. For example, for
      ``libmamba`` we might need a separate pool that can be configured as a flexible task. See
      more details in the first comment of ``conda.core.solve.classic.Solver._add_specs``
    """

    def __init__(
        self,
        *,
        solver_input_state: SolverInputState,
        records: Optional[Dict[str, PackageRecord]] = None,
        for_history: Optional[Dict[str, MatchSpec]] = None,
        neutered: Optional[Dict[str, MatchSpec]] = None,
        conflicts: Optional[Dict[str, MatchSpec]] = None,
        pins: Optional[Dict[str, MatchSpec]] = None,
    ):
        self.solver_input_state: SolverInputState = solver_input_state
        self.records: Dict[str, PackageRecord] = records or dict(solver_input_state.installed)
        self.for_history: Dict[str, MatchSpec] = for_history or dict(solver_input_state.requested)
        self.neutered: Dict[str, MatchSpec] = neutered or {}
        self.conflicts: Dict[str, MatchSpec] = conflicts or {}
        self.pins: Dict[str, MatchSpec] = pins or {}

    @property
    def current_solution(self):
        """
        Massage currently stored records so they can be returned as the type expected by the
        solver API. This is what you should return in ``Solver.solve_final_state()``.
        """
        return IndexedSet(PrefixGraph(self.records.values()).graph)

    @property
    def specs(self):
        """
        Merge all possible sources of input package specs, sorted by their input category and
        strictness. It's just meant to be an enumeration of all possible inputs, not a ready-to-use
        list of specs for a solver.
        """
        sis = self.solver_input_state
        specs_by_strictness = {}
        for group in (
            "requested",
            "pinned",
            "history",
            "aggressive_updates",
        ):
            for name, spec in sorted(
                getattr(sis, group).items(),
                key=sort_by_spec_strictness,
                reverse=True,
            ):
                specs_by_strictness.setdefault(name, spec)
        for record_group in ("installed", "virtual"):
            for name, record in getattr(sis, record_group).items():
                specs_by_strictness.setdefault(name, record.to_match_spec())
        return specs_by_strictness

    @property
    def real_specs(self):
        """
        Specs that are _not_ virtual.
        """
        return {name: spec for name, spec in self.specs.items() if not name.startswith("__")}

    @property
    def virtual_specs(self):
        """
        Specs that are virtual.
        """
        return {name: spec for name, spec in self.specs.items() if name.startswith("__")}

    def early_exit(self) -> Dict[str, PackageRecord]:
        """
        Operations that do not need a solver and might result in returning
        early are collected here.
        """
        sis = self.solver_input_state
        if sis.is_removing:
            # Make sure that requested packages to be removed match
            # an installed record. Otherwise, raise an error.
            # When 'remove --force' is set, remove the package without solving.
            if sis.force_remove:
                force_remove_solution = self.current_solution
            not_installed = []
            for name, spec in sis.requested.items():
                for record in sis.installed.values():
                    if spec.match(record):
                        if sis.force_remove:
                            force_remove_solution.remove(record)
                        break
                else:
                    not_installed.append(spec)

            if not_installed:
                exc = PackagesNotFoundError(not_installed)
                exc.allow_retry = False
                raise exc

            if sis.force_remove:
                return force_remove_solution

        if sis.update_modifier.SPECS_SATISFIED_SKIP_SOLVE and not sis.is_removing:
            for name, spec in sis.requested.items():
                if name not in sis.installed:
                    break
            else:
                # All specs match a package in the current environment.
                # Return early, with the current solution (at this point, .records is set
                # to the map of installed packages)
                return self.current_solution

    def check_for_pin_conflicts(self, index):
        """
        Last part of the logic, common to addition and removal of packages. Originally,
        the legacy logic will also minimize the conflicts here by doing a pre-solve
        analysis, but so far we have opted for a different approach in libmamba: let the
        solver try, fail with conflicts, and annotate those as such so they are unconstrained.

        Now, this method only ensures that the pins do not cause conflicts.
        """
        # ## Inconsistency analysis ###
        # here we would call conda.core.solve.classic.Solver._find_inconsistent_packages()

        # ## Check pin and requested are compatible
        sis = self.solver_input_state
        requested_and_pinned = set(sis.requested).intersection(sis.pinned)
        for name in requested_and_pinned:
            requested = sis.requested[name]
            pin = sis.pinned[name]
            installed = sis.installed.get(name)
            if (
                # name-only pins lock to installed; requested spec must match it
                (pin.is_name_only_spec and installed and not requested.match(installed))
                # otherwise, the pin needs to be compatible with the requested spec
                or not compatible_specs(index, (requested, pin))
            ):
                pinned_specs = [
                    (sis.installed.get(name, pin) if pin.is_name_only_spec else pin)
                    for name, pin in sorted(sis.pinned.items())
                ]
                exc = SpecsConfigurationConflictError(
                    requested_specs=sorted(sis.requested.values(), key=lambda x: x.name),
                    pinned_specs=pinned_specs,
                    prefix=sis.prefix,
                )
                exc.allow_retry = False
                raise exc

    def post_solve(self, solver: Type["Solver"]):
        """
        These tasks are performed _after_ the solver has done its work. It essentially
        post-processes the ``records`` mapping.

        Parameters
        ----------
        solver_cls
            The class used to instantiate the Solver. If not provided, defaults to the one
            specified in the context configuration.

        Notes
        -----
        This method could be solver-agnostic  but unfortunately ``--update-deps`` requires a
        second solve; that's why this method needs a solver class to be passed as an argument.
        """
        # After a solve, we still need to do some refinement
        sis = self.solver_input_state

        # ## Record history ###
        # user requested specs need to be annotated in history
        # we control that in .for_history
        self.for_history.update(sis.requested)

        # ## Neutered ###
        # annotate overridden history specs so they are written to disk
        for name, spec in sis.history.items():
            record = self.records.get(name)
            if record and not spec.match(record):
                self.neutered[name] = MatchSpec(name, version=record.version)

        # ## Add inconsistent packages back ###
        # direct result of the inconsistency analysis above

        # ## Deps modifier ###
        # handle the different modifiers (NO_DEPS, ONLY_DEPS, UPDATE_DEPS)
        # this might mean removing different records by hand or even calling
        # the solver a 2nd time

        if sis.deps_modifier.NO_DEPS:
            # In the NO_DEPS case, we need to start with the original list of packages in the
            # environment, and then only modify packages that match the requested specs
            #
            # Help information notes that use of NO_DEPS is expected to lead to broken
            # environments.
            original_state = dict(sis.installed)
            only_change_these = {}
            for name, spec in sis.requested.items():
                for record in self.records.values():
                    if spec.match(record):
                        only_change_these[name] = record

            if sis.is_removing:
                # TODO: This could be a pre-solve task to save time in forced removes?
                for name in only_change_these:
                    del original_state[name]
            else:
                for name, record in only_change_these.items():
                    original_state[name] = record

            self.records.clear()
            self.records.update(original_state)

        elif sis.deps_modifier.ONLY_DEPS and not sis.update_modifier.UPDATE_DEPS:
            # Using a special instance of PrefixGraph to remove youngest child nodes that match
            # the original requested specs.  It's important to remove only the *youngest* child
            # nodes, because a typical use might be `conda install --only-deps python=2 flask`,
            # and in that case we'd want to keep python.
            #
            # What are we supposed to do if flask was already in the environment?
            # We can't be removing stuff here that's already in the environment.
            #
            # What should be recorded for the user-requested specs in this case? Probably all
            # direct dependencies of flask.

            graph = PrefixGraph(self.records.values(), sis.requested.values())
            # this method below modifies the graph inplace _and_ returns the removed nodes
            # (like dict.pop())
            would_remove = graph.remove_youngest_descendant_nodes_with_specs()

            # We need to distinguish the behavior between `conda remove` and the rest
            to_remove = []
            if sis.is_removing:
                for record in would_remove:
                    # do not remove records that were not requested but were installed
                    if record.name not in sis.requested and record.name in sis.installed:
                        continue
                    to_remove.append(record.name)
            else:
                for record in would_remove:
                    for dependency in record.depends:
                        spec = MatchSpec(dependency)
                        if spec.name not in self.specs:
                            # following https://github.com/conda/conda/pull/8766
                            self.for_history[spec.name] = spec
                    to_remove.append(record.name)

            for name in to_remove:
                installed = sis.installed.get(name)
                if installed:
                    self.records[name] = installed
                else:
                    self.records.pop(record.name)

        elif sis.update_modifier.UPDATE_DEPS:
            # Here we have to SAT solve again :(  It's only now that we know the dependency
            # chain of specs_to_add.
            #
            # UPDATE_DEPS is effectively making each spec in the dependency chain a
            # user-requested spec. For all other specs, we drop all information but name, drop
            # target, and add them to `requested` so it gets recorded in the history file.
            #
            # It's like UPDATE_ALL, but only for certain dependency chains.
            new_specs = {}

            graph = PrefixGraph(self.records.values())
            for name, spec in sis.requested.items():
                record = graph.get_node_by_name(name)
                for ancestor in graph.all_ancestors(record):
                    new_specs[ancestor.name] = MatchSpec(ancestor.name)

            # Remove pinned_specs
            for name, spec in sis.pinned.items():
                new_specs.pop(name, None)
            # Follow major-minor pinning business rule for python
            if "python" in new_specs:
                record = sis.installed["python"]
                version = ".".join(record.version.split(".")[:2]) + ".*"
                new_specs["python"] = MatchSpec(name="python", version=version)
            # Add in the original `requested` on top.
            new_specs.update(sis.requested)

            if sis.is_removing:
                specs_to_add = ()
                specs_to_remove = list(new_specs.keys())
            else:
                specs_to_add = list(new_specs.values())
                specs_to_remove = ()

            with context._override("quiet", False):
                # Create a new solver instance to perform a 2nd solve with deps added We do it
                # like this to avoid overwriting state accidentally. Instead, we will import
                # the needed state bits manually.
                records = solver.__class__(
                    prefix=solver.prefix,
                    channels=solver.channels,
                    subdirs=solver.subdirs,
                    specs_to_add=specs_to_add,
                    specs_to_remove=specs_to_remove,
                    command="recursive_call_for_update_deps",
                ).solve_final_state(
                    update_modifier=UpdateModifier.UPDATE_SPECS,  # avoid recursion!
                    deps_modifier=sis._deps_modifier,
                    ignore_pinned=sis.ignore_pinned,
                    force_remove=sis.force_remove,
                    prune=sis.prune,
                )
                records = {record.name: record for record in records}

            self.records.clear()
            self.records.update(records)
            self.for_history.clear()
            self.for_history.update(new_specs)

            # Disable pruning regardless the original value
            # TODO: Why? Dive in https://github.com/conda/conda/pull/7719
            sis._prune = False

        # ## Prune ###
        # remove orphan leaves in the graph
        if sis.prune:
            graph = PrefixGraph(list(self.records.values()), list(sis.requested.values()))
            graph.prune()
            self.records.clear()
            self.records.update({record.name: record for record in graph.graph})


def sort_by_spec_strictness(key_value_tuple: Tuple[str, MatchSpec]):
    """
    Helper function to sort a list of (key, value) tuples by spec strictness
    """
    name, spec = key_value_tuple
    return getattr(spec, "strictness", 0), name
