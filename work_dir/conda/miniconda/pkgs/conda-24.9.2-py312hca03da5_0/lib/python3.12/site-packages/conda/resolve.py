# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Low-level SAT solver wrapper/interface for the classic solver.

See conda.core.solver.Solver for the high-level API.
"""

from __future__ import annotations

import copy
import itertools
from collections import defaultdict, deque
from functools import lru_cache
from logging import DEBUG, getLogger

from tqdm import tqdm

from .auxlib.decorators import memoizemethod
from .base.constants import MAX_CHANNEL_PRIORITY, ChannelPriority, SatSolverChoice
from .base.context import context
from .common.compat import on_win
from .common.io import dashlist, time_recorder
from .common.iterators import groupby_to_dict as groupby
from .common.logic import (
    TRUE,
    Clauses,
    PycoSatSolver,
    PyCryptoSatSolver,
    PySatSolver,
    minimal_unsatisfiable_subset,
)
from .common.toposort import toposort
from .exceptions import (
    CondaDependencyError,
    InvalidSpec,
    ResolvePackageNotFound,
    UnsatisfiableError,
)
from .models.channel import Channel, MultiChannel
from .models.enums import NoarchType, PackageType
from .models.match_spec import MatchSpec
from .models.records import PackageRecord
from .models.version import VersionOrder

try:
    from frozendict import frozendict
except ImportError:
    from ._vendor.frozendict import FrozenOrderedDict as frozendict

log = getLogger(__name__)
stdoutlog = getLogger("conda.stdoutlog")

# used in conda build
Unsatisfiable = UnsatisfiableError
ResolvePackageNotFound = ResolvePackageNotFound

_sat_solvers = {
    SatSolverChoice.PYCOSAT: PycoSatSolver,
    SatSolverChoice.PYCRYPTOSAT: PyCryptoSatSolver,
    SatSolverChoice.PYSAT: PySatSolver,
}


@lru_cache(maxsize=None)
def _get_sat_solver_cls(sat_solver_choice=SatSolverChoice.PYCOSAT):
    def try_out_solver(sat_solver):
        c = Clauses(sat_solver=sat_solver)
        required = {c.new_var(), c.new_var()}
        c.Require(c.And, *required)
        solution = set(c.sat())
        if not required.issubset(solution):
            raise RuntimeError(f"Wrong SAT solution: {solution}. Required: {required}")

    sat_solver = _sat_solvers[sat_solver_choice]
    try:
        try_out_solver(sat_solver)
    except Exception as e:
        log.warning(
            "Could not run SAT solver through interface '%s'.", sat_solver_choice
        )
        log.debug("SAT interface error due to: %s", e, exc_info=True)
    else:
        log.debug("Using SAT solver interface '%s'.", sat_solver_choice)
        return sat_solver
    for sat_solver in _sat_solvers.values():
        try:
            try_out_solver(sat_solver)
        except Exception as e:
            log.debug(
                "Attempted SAT interface '%s' but unavailable due to: %s",
                sat_solver_choice,
                e,
            )
        else:
            log.debug("Falling back to SAT solver interface '%s'.", sat_solver_choice)
            return sat_solver
    raise CondaDependencyError(
        "Cannot run solver. No functioning SAT implementations available."
    )


def exactness_and_number_of_deps(resolve_obj, ms):
    """Sorting key to emphasize packages that have more strict
    requirements. More strict means the reduced index can be reduced
    more, so we want to consider these more constrained deps earlier in
    reducing the index.
    """
    if ms.strictness == 3:
        prec = resolve_obj.find_matches(ms)
        value = 3
        if prec:
            for dep in prec[0].depends:
                value += MatchSpec(dep).strictness
    else:
        value = ms.strictness
    return value


class Resolve:
    def __init__(self, index, processed=False, channels=()):
        self.index = index

        self.channels = channels
        self._channel_priorities_map = (
            self._make_channel_priorities(channels) if channels else {}
        )
        self._channel_priority = context.channel_priority
        self._solver_ignore_timestamps = context.solver_ignore_timestamps

        groups = groupby(lambda x: x.name, index.values())
        trackers = defaultdict(list)

        for name in groups:
            unmanageable_precs = [prec for prec in groups[name] if prec.is_unmanageable]
            if unmanageable_precs:
                log.debug("restricting to unmanageable packages: %s", name)
                groups[name] = unmanageable_precs
            tf_precs = (prec for prec in groups[name] if prec.track_features)
            for prec in tf_precs:
                for feature_name in prec.track_features:
                    trackers[feature_name].append(prec)

        self.groups = groups  # dict[package_name, list[PackageRecord]]
        self.trackers = trackers  # dict[track_feature, set[PackageRecord]]
        self._cached_find_matches = {}  # dict[MatchSpec, set[PackageRecord]]
        self.ms_depends_ = {}  # dict[PackageRecord, list[MatchSpec]]
        self._reduced_index_cache = {}
        self._pool_cache = {}
        self._strict_channel_cache = {}

        self._system_precs = {
            _
            for _ in index
            if (
                hasattr(_, "package_type")
                and _.package_type == PackageType.VIRTUAL_SYSTEM
            )
        }

        # sorting these in reverse order is effectively prioritizing
        # constraint behavior from newer packages. It is applying broadening
        # reduction based on the latest packages, which may reduce the space
        # more, because more modern packages utilize constraints in more sane
        # ways (for example, using run_exports in conda-build 3)
        for name, group in self.groups.items():
            self.groups[name] = sorted(group, key=self.version_key, reverse=True)

    def __hash__(self):
        return (
            super().__hash__()
            ^ hash(frozenset(self.channels))
            ^ hash(frozendict(self._channel_priorities_map))
            ^ hash(self._channel_priority)
            ^ hash(self._solver_ignore_timestamps)
            ^ hash(frozendict((k, tuple(v)) for k, v in self.groups.items()))
            ^ hash(frozendict((k, tuple(v)) for k, v in self.trackers.items()))
            ^ hash(frozendict((k, tuple(v)) for k, v in self.ms_depends_.items()))
        )

    def default_filter(self, features=None, filter=None):
        if filter is None:
            filter = {}
        else:
            filter.clear()

        filter.update(
            {PackageRecord.feature(name): False for name in self.trackers.keys()}
        )
        if features:
            filter.update({PackageRecord.feature(name): True for name in features})
        return filter

    def valid(self, spec_or_prec, filter, optional=True):
        """Tests if a package, MatchSpec, or a list of both has satisfiable
        dependencies, assuming cyclic dependencies are always valid.

        Args:
            spec_or_prec: a package record, a MatchSpec, or an iterable of these.
            filter: a dictionary of (fkey,valid) pairs, used to consider a subset
                of dependencies, and to eliminate repeated searches.
            optional: if True (default), do not enforce optional specifications
                when considering validity. If False, enforce them.

        Returns:
            True if the full set of dependencies can be satisfied; False otherwise.
            If filter is supplied and update is True, it will be updated with the
            search results.
        """

        def v_(spec):
            return v_ms_(spec) if isinstance(spec, MatchSpec) else v_fkey_(spec)

        def v_ms_(ms):
            return (
                optional
                and ms.optional
                or any(v_fkey_(fkey) for fkey in self.find_matches(ms))
            )

        def v_fkey_(prec):
            val = filter.get(prec)
            if val is None:
                filter[prec] = True
                try:
                    depends = self.ms_depends(prec)
                except InvalidSpec:
                    val = filter[prec] = False
                else:
                    val = filter[prec] = all(v_ms_(ms) for ms in depends)
            return val

        result = v_(spec_or_prec)
        return result

    def valid2(self, spec_or_prec, filter_out, optional=True):
        def is_valid(_spec_or_prec):
            if isinstance(_spec_or_prec, MatchSpec):
                return is_valid_spec(_spec_or_prec)
            else:
                return is_valid_prec(_spec_or_prec)

        @memoizemethod
        def is_valid_spec(_spec):
            return (
                optional
                and _spec.optional
                or any(is_valid_prec(_prec) for _prec in self.find_matches(_spec))
            )

        def is_valid_prec(prec):
            val = filter_out.get(prec)
            if val is None:
                filter_out[prec] = False
                try:
                    has_valid_deps = all(
                        is_valid_spec(ms) for ms in self.ms_depends(prec)
                    )
                except InvalidSpec:
                    val = filter_out[prec] = "invalid dep specs"
                else:
                    val = filter_out[prec] = (
                        False if has_valid_deps else "invalid depends specs"
                    )
            return not val

        return is_valid(spec_or_prec)

    def invalid_chains(self, spec, filter, optional=True):
        """Constructs a set of 'dependency chains' for invalid specs.

        A dependency chain is a tuple of MatchSpec objects, starting with
        the requested spec, proceeding down the dependency tree, ending at
        a specification that cannot be satisfied.

        Args:
            spec: a package key or MatchSpec
            filter: a dictionary of (prec, valid) pairs to be used when
                testing for package validity.

        Returns:
            A tuple of tuples, empty if the MatchSpec is valid.
        """

        def chains_(spec, names):
            if spec.name in names:
                return
            names.add(spec.name)
            if self.valid(spec, filter, optional):
                return
            precs = self.find_matches(spec)
            found = False

            conflict_deps = set()
            for prec in precs:
                for m2 in self.ms_depends(prec):
                    for x in chains_(m2, names):
                        found = True
                        yield (spec,) + x
                    else:
                        conflict_deps.add(m2)
            if not found:
                conflict_groups = groupby(lambda x: x.name, conflict_deps)
                for group in conflict_groups.values():
                    yield (spec,) + MatchSpec.union(group)

        return chains_(spec, set())

    def verify_specs(self, specs):
        """Perform a quick verification that specs and dependencies are reasonable.

        Args:
            specs: An iterable of strings or MatchSpec objects to be tested.

        Returns:
            Nothing, but if there is a conflict, an error is thrown.

        Note that this does not attempt to resolve circular dependencies.
        """
        non_tf_specs = []
        bad_deps = []
        feature_names = set()
        for ms in specs:
            _feature_names = ms.get_exact_value("track_features")
            if _feature_names:
                feature_names.update(_feature_names)
            else:
                non_tf_specs.append(ms)
        bad_deps.extend(
            (spec,)
            for spec in non_tf_specs
            if (not spec.optional and not self.find_matches(spec))
        )
        if bad_deps:
            raise ResolvePackageNotFound(bad_deps)
        return tuple(non_tf_specs), feature_names

    def _classify_bad_deps(
        self, bad_deps, specs_to_add, history_specs, strict_channel_priority
    ):
        classes = {
            "python": set(),
            "request_conflict_with_history": set(),
            "direct": set(),
            "virtual_package": set(),
        }
        specs_to_add = {MatchSpec(_) for _ in specs_to_add or []}
        history_specs = {MatchSpec(_) for _ in history_specs or []}
        for chain in bad_deps:
            # sometimes chains come in as strings
            if (
                len(chain) > 1
                and chain[-1].name == "python"
                and not any(_.name == "python" for _ in specs_to_add)
                and any(_[0] for _ in bad_deps if _[0].name == "python")
            ):
                python_first_specs = [_[0] for _ in bad_deps if _[0].name == "python"]
                if python_first_specs:
                    python_spec = python_first_specs[0]
                    if not (
                        set(self.find_matches(python_spec))
                        & set(self.find_matches(chain[-1]))
                    ):
                        classes["python"].add(
                            (
                                tuple([chain[0], chain[-1]]),
                                str(MatchSpec(python_spec, target=None)),
                            )
                        )
            elif chain[-1].name.startswith("__"):
                version = [_ for _ in self._system_precs if _.name == chain[-1].name]
                virtual_package_version = (
                    version[0].version if version else "not available"
                )
                classes["virtual_package"].add((tuple(chain), virtual_package_version))
            elif chain[0] in specs_to_add:
                match = False
                for spec in history_specs:
                    if spec.name == chain[-1].name:
                        classes["request_conflict_with_history"].add(
                            (tuple(chain), str(MatchSpec(spec, target=None)))
                        )
                        match = True

                if not match:
                    classes["direct"].add(
                        (tuple(chain), str(MatchSpec(chain[0], target=None)))
                    )
            else:
                if len(chain) > 1 or any(
                    len(c) >= 1 and c[0] == chain[0] for c in bad_deps
                ):
                    classes["direct"].add(
                        (tuple(chain), str(MatchSpec(chain[0], target=None)))
                    )

        if classes["python"]:
            # filter out plain single-entry python conflicts.  The python section explains these.
            classes["direct"] = [
                _
                for _ in classes["direct"]
                if _[1].startswith("python ") or len(_[0]) > 1
            ]
        return classes

    def find_matches_with_strict(self, ms, strict_channel_priority):
        matches = self.find_matches(ms)
        if not strict_channel_priority:
            return matches
        sole_source_channel_name = self._get_strict_channel(ms.name)
        return tuple(f for f in matches if f.channel.name == sole_source_channel_name)

    def find_conflicts(self, specs, specs_to_add=None, history_specs=None):
        if context.unsatisfiable_hints:
            if not context.json:
                print(
                    "\nFound conflicts! Looking for incompatible packages.\n"
                    "This can take several minutes.  Press CTRL-C to abort."
                )
            bad_deps = self.build_conflict_map(specs, specs_to_add, history_specs)
        else:
            bad_deps = {}
        strict_channel_priority = context.channel_priority == ChannelPriority.STRICT
        raise UnsatisfiableError(bad_deps, strict=strict_channel_priority)

    def breadth_first_search_for_dep_graph(
        self, root_spec, target_name, dep_graph, num_targets=1
    ):
        """Return shorted path from root_spec to target_name"""
        queue = []
        queue.append([root_spec])
        visited = []
        target_paths = []
        while queue:
            path = queue.pop(0)
            node = path[-1]
            if node in visited:
                continue
            visited.append(node)
            if node.name == target_name:
                if len(target_paths) == 0:
                    target_paths.append(path)
                if len(target_paths[-1]) == len(path):
                    last_spec = MatchSpec.union((path[-1], target_paths[-1][-1]))[0]
                    target_paths[-1][-1] = last_spec
                else:
                    target_paths.append(path)

                found_all_targets = len(target_paths) == num_targets and any(
                    len(_) != len(path) for _ in queue
                )
                if len(queue) == 0 or found_all_targets:
                    return target_paths
            sub_graph = dep_graph
            for p in path[0:-1]:
                sub_graph = sub_graph[p]
            children = [_ for _ in sub_graph.get(node, {})]
            if children is None:
                continue
            for adj in children:
                if len(target_paths) < num_targets:
                    new_path = list(path)
                    new_path.append(adj)
                    queue.append(new_path)
        return target_paths

    def build_graph_of_deps(self, spec):
        dep_graph = {spec: {}}
        all_deps = set()
        queue = [[spec]]
        while queue:
            path = queue.pop(0)
            sub_graph = dep_graph
            for p in path:
                sub_graph = sub_graph[p]
            parent_node = path[-1]
            matches = self.find_matches(parent_node)
            for mat in matches:
                if len(mat.depends) > 0:
                    for i in mat.depends:
                        new_node = MatchSpec(i)
                        sub_graph.update({new_node: {}})
                        all_deps.add(new_node)
                        new_path = list(path)
                        new_path.append(new_node)
                        if len(new_path) <= context.unsatisfiable_hints_check_depth:
                            queue.append(new_path)
        return dep_graph, all_deps

    def build_conflict_map(self, specs, specs_to_add=None, history_specs=None):
        """Perform a deeper analysis on conflicting specifications, by attempting
        to find the common dependencies that might be the cause of conflicts.

        Args:
            specs: An iterable of strings or MatchSpec objects to be tested.
            It is assumed that the specs conflict.

        Returns:
            bad_deps: A list of lists of bad deps

        Strategy:
            If we're here, we know that the specs conflict. This could be because:
            - One spec conflicts with another; e.g.
                  ['numpy 1.5*', 'numpy >=1.6']
            - One spec conflicts with a dependency of another; e.g.
                  ['numpy 1.5*', 'scipy 0.12.0b1']
            - Each spec depends on *the same package* but in a different way; e.g.,
                  ['A', 'B'] where A depends on numpy 1.5, and B on numpy 1.6.
            Technically, all three of these cases can be boiled down to the last
            one if we treat the spec itself as one of the "dependencies". There
            might be more complex reasons for a conflict, but this code only
            considers the ones above.

            The purpose of this code, then, is to identify packages (like numpy
            above) that all of the specs depend on *but in different ways*. We
            then identify the dependency chains that lead to those packages.
        """
        # if only a single package matches the spec use the packages depends
        # rather than the spec itself
        strict_channel_priority = context.channel_priority == ChannelPriority.STRICT

        specs = set(specs) | (specs_to_add or set())
        # Remove virtual packages
        specs = {spec for spec in specs if not spec.name.startswith("__")}
        if len(specs) == 1:
            matches = self.find_matches(next(iter(specs)))
            if len(matches) == 1:
                specs = set(self.ms_depends(matches[0]))
        specs.update({_.to_match_spec() for _ in self._system_precs})
        for spec in specs:
            self._get_package_pool((spec,))

        dep_graph = {}
        dep_list = {}
        with tqdm(
            total=len(specs),
            desc="Building graph of deps",
            leave=False,
            disable=context.json,
        ) as t:
            for spec in specs:
                t.set_description(f"Examining {spec}")
                t.update()
                dep_graph_for_spec, all_deps_for_spec = self.build_graph_of_deps(spec)
                dep_graph.update(dep_graph_for_spec)
                if dep_list.get(spec.name):
                    dep_list[spec.name].append(spec)
                else:
                    dep_list[spec.name] = [spec]
                for dep in all_deps_for_spec:
                    if dep_list.get(dep.name):
                        dep_list[dep.name].append(spec)
                    else:
                        dep_list[dep.name] = [spec]

        chains = []
        conflicting_pkgs_pkgs = {}
        for k, v in dep_list.items():
            set_v = frozenset(v)
            # Packages probably conflicts if many specs depend on it
            if len(set_v) > 1:
                if conflicting_pkgs_pkgs.get(set_v) is None:
                    conflicting_pkgs_pkgs[set_v] = [k]
                else:
                    conflicting_pkgs_pkgs[set_v].append(k)
            # Conflict if required virtual package is not present
            elif k.startswith("__") and any(s for s in set_v if s.name != k):
                conflicting_pkgs_pkgs[set_v] = [k]

        with tqdm(
            total=len(specs),
            desc="Determining conflicts",
            leave=False,
            disable=context.json,
        ) as t:
            for roots, nodes in conflicting_pkgs_pkgs.items():
                t.set_description(
                    "Examining conflict for {}".format(" ".join(_.name for _ in roots))
                )
                t.update()
                lroots = [_ for _ in roots]
                current_shortest_chain = []
                shortest_node = None
                requested_spec_unsat = frozenset(nodes).intersection(
                    {_.name for _ in roots}
                )
                if requested_spec_unsat:
                    chains.append([_ for _ in roots if _.name in requested_spec_unsat])
                    shortest_node = chains[-1][0]
                    for root in roots:
                        if root != chains[0][0]:
                            search_node = shortest_node.name
                            num_occurances = dep_list[search_node].count(root)
                            c = self.breadth_first_search_for_dep_graph(
                                root, search_node, dep_graph, num_occurances
                            )
                            chains.extend(c)
                else:
                    for node in nodes:
                        num_occurances = dep_list[node].count(lroots[0])
                        chain = self.breadth_first_search_for_dep_graph(
                            lroots[0], node, dep_graph, num_occurances
                        )
                        chains.extend(chain)
                        if len(current_shortest_chain) == 0 or len(chain) < len(
                            current_shortest_chain
                        ):
                            current_shortest_chain = chain
                            shortest_node = node
                    for root in lroots[1:]:
                        num_occurances = dep_list[shortest_node].count(root)
                        c = self.breadth_first_search_for_dep_graph(
                            root, shortest_node, dep_graph, num_occurances
                        )
                        chains.extend(c)

        bad_deps = self._classify_bad_deps(
            chains, specs_to_add, history_specs, strict_channel_priority
        )
        return bad_deps

    def _get_strict_channel(self, package_name):
        channel_name = None
        try:
            channel_name = self._strict_channel_cache[package_name]
        except KeyError:
            if package_name in self.groups:
                all_channel_names = {
                    prec.channel.name for prec in self.groups[package_name]
                }
                by_cp = {
                    self._channel_priorities_map.get(cn, 1): cn
                    for cn in all_channel_names
                }
                highest_priority = sorted(by_cp)[
                    0
                ]  # highest priority is the lowest number
                channel_name = self._strict_channel_cache[package_name] = by_cp[
                    highest_priority
                ]
        return channel_name

    @memoizemethod
    def _broader(self, ms, specs_by_name):
        """Prevent introduction of matchspecs that broaden our selection of choices."""
        if not specs_by_name:
            return False
        return ms.strictness < specs_by_name[0].strictness

    def _get_package_pool(self, specs):
        specs = frozenset(specs)
        if specs in self._pool_cache:
            pool = self._pool_cache[specs]
        else:
            pool = self.get_reduced_index(specs)
            grouped_pool = groupby(lambda x: x.name, pool)
            pool = {k: set(v) for k, v in grouped_pool.items()}
            self._pool_cache[specs] = pool
        return pool

    @time_recorder(module_name=__name__)
    def get_reduced_index(
        self, explicit_specs, sort_by_exactness=True, exit_on_conflict=False
    ):
        strict_channel_priority = context.channel_priority == ChannelPriority.STRICT

        cache_key = strict_channel_priority, tuple(explicit_specs)
        if cache_key in self._reduced_index_cache:
            return self._reduced_index_cache[cache_key]

        if log.isEnabledFor(DEBUG):
            log.debug(
                "Retrieving packages for: %s",
                dashlist(sorted(str(s) for s in explicit_specs)),
            )

        explicit_specs, features = self.verify_specs(explicit_specs)
        filter_out = {
            prec: False if val else "feature not enabled"
            for prec, val in self.default_filter(features).items()
        }
        snames = set()
        top_level_spec = None
        cp_filter_applied = set()  # values are package names
        if sort_by_exactness:
            # prioritize specs that are more exact.  Exact specs will evaluate to 3,
            #    constrained specs will evaluate to 2, and name only will be 1
            explicit_specs = sorted(
                list(explicit_specs),
                key=lambda x: (exactness_and_number_of_deps(self, x), x.dist_str()),
                reverse=True,
            )
        # tuple because it needs to be hashable
        explicit_specs = tuple(explicit_specs)

        explicit_spec_package_pool = {}
        for s in explicit_specs:
            explicit_spec_package_pool[s.name] = explicit_spec_package_pool.get(
                s.name, set()
            ) | set(self.find_matches(s))

        def filter_group(_specs):
            # all _specs should be for the same package name
            name = next(iter(_specs)).name
            group = self.groups.get(name, ())

            # implement strict channel priority
            if group and strict_channel_priority and name not in cp_filter_applied:
                sole_source_channel_name = self._get_strict_channel(name)
                for prec in group:
                    if prec.channel.name != sole_source_channel_name:
                        filter_out[prec] = "removed due to strict channel priority"
                cp_filter_applied.add(name)

            # Prune packages that don't match any of the patterns,
            # have unsatisfiable dependencies, or conflict with the explicit specs
            nold = nnew = 0
            for prec in group:
                if not filter_out.setdefault(prec, False):
                    nold += 1
                    if (not self.match_any(_specs, prec)) or (
                        explicit_spec_package_pool.get(name)
                        and prec not in explicit_spec_package_pool[name]
                    ):
                        filter_out[prec] = (
                            f"incompatible with required spec {top_level_spec}"
                        )
                        continue
                    unsatisfiable_dep_specs = set()
                    for ms in self.ms_depends(prec):
                        if not ms.optional and not any(
                            rec
                            for rec in self.find_matches(ms)
                            if not filter_out.get(rec, False)
                        ):
                            unsatisfiable_dep_specs.add(ms)
                    if unsatisfiable_dep_specs:
                        filter_out[prec] = "unsatisfiable dependencies {}".format(
                            " ".join(str(s) for s in unsatisfiable_dep_specs)
                        )
                        continue
                    filter_out[prec] = False
                    nnew += 1

            reduced = nnew < nold
            if reduced:
                log.debug("%s: pruned from %d -> %d" % (name, nold, nnew))
            if any(ms.optional for ms in _specs):
                return reduced
            elif nnew == 0:
                # Indicates that a conflict was found; we can exit early
                return None

            # Perform the same filtering steps on any dependencies shared across
            # *all* packages in the group. Even if just one of the packages does
            # not have a particular dependency, it must be ignored in this pass.
            # Otherwise, we might do more filtering than we should---and it is
            # better to have extra packages here than missing ones.
            if reduced or name not in snames:
                snames.add(name)

                _dep_specs = groupby(
                    lambda s: s.name,
                    (
                        dep_spec
                        for prec in group
                        if not filter_out.get(prec, False)
                        for dep_spec in self.ms_depends(prec)
                        if not dep_spec.optional
                    ),
                )
                _dep_specs.pop("*", None)  # discard track_features specs

                for deps_name, deps in sorted(
                    _dep_specs.items(), key=lambda x: any(_.optional for _ in x[1])
                ):
                    if len(deps) >= nnew:
                        res = filter_group(set(deps))
                        if res:
                            reduced = True
                        elif res is None:
                            # Indicates that a conflict was found; we can exit early
                            return None

            return reduced

        # Iterate on pruning until no progress is made. We've implemented
        # what amounts to "double-elimination" here; packages get one additional
        # chance after their first "False" reduction. This catches more instances
        # where one package's filter affects another. But we don't have to be
        # perfect about this, so performance matters.
        pruned_to_zero = set()
        for _ in range(2):
            snames.clear()
            slist = deque(explicit_specs)
            while slist:
                s = slist.popleft()
                if filter_group([s]):
                    slist.append(s)
                else:
                    pruned_to_zero.add(s)

        if pruned_to_zero and exit_on_conflict:
            return {}

        # Determine all valid packages in the dependency graph
        reduced_index2 = {
            prec: prec for prec in (PackageRecord.feature(name) for name in features)
        }
        specs_by_name_seed = {}
        for s in explicit_specs:
            specs_by_name_seed[s.name] = specs_by_name_seed.get(s.name, []) + [s]
        for explicit_spec in explicit_specs:
            add_these_precs2 = tuple(
                prec
                for prec in self.find_matches(explicit_spec)
                if prec not in reduced_index2 and self.valid2(prec, filter_out)
            )

            if strict_channel_priority and add_these_precs2:
                strict_channel_name = self._get_strict_channel(add_these_precs2[0].name)

                add_these_precs2 = tuple(
                    prec
                    for prec in add_these_precs2
                    if prec.channel.name == strict_channel_name
                )
            reduced_index2.update((prec, prec) for prec in add_these_precs2)

            for pkg in add_these_precs2:
                # what we have seen is only relevant within the context of a single package
                #    that is picked up because of an explicit spec.  We don't want the
                #    broadening check to apply across packages at the explicit level; only
                #    at the level of deps below that explicit package.
                seen_specs = set()
                specs_by_name = copy.deepcopy(specs_by_name_seed)

                dep_specs = set(self.ms_depends(pkg))
                for dep in dep_specs:
                    specs = specs_by_name.get(dep.name, [])
                    if dep not in specs and (
                        not specs or dep.strictness >= specs[0].strictness
                    ):
                        specs.insert(0, dep)
                    specs_by_name[dep.name] = specs

                while dep_specs:
                    # used for debugging
                    # size_index = len(reduced_index2)
                    # specs_added = []
                    ms = dep_specs.pop()
                    seen_specs.add(ms)
                    for dep_pkg in (
                        _ for _ in self.find_matches(ms) if _ not in reduced_index2
                    ):
                        if not self.valid2(dep_pkg, filter_out):
                            continue

                        # expand the reduced index if not using strict channel priority,
                        #    or if using it and this package is in the appropriate channel
                        if not strict_channel_priority or (
                            self._get_strict_channel(dep_pkg.name)
                            == dep_pkg.channel.name
                        ):
                            reduced_index2[dep_pkg] = dep_pkg

                            # recurse to deps of this dep
                            new_specs = set(self.ms_depends(dep_pkg)) - seen_specs
                            for new_ms in new_specs:
                                # We do not pull packages into the reduced index due
                                # to a track_features dependency. Remember, a feature
                                # specifies a "soft" dependency: it must be in the
                                # environment, but it is not _pulled_ in. The SAT
                                # logic doesn't do a perfect job of capturing this
                                # behavior, but keeping these packags out of the
                                # reduced index helps. Of course, if _another_
                                # package pulls it in by dependency, that's fine.
                                if "track_features" not in new_ms and not self._broader(
                                    new_ms,
                                    tuple(specs_by_name.get(new_ms.name, ())),
                                ):
                                    dep_specs.add(new_ms)
                                    # if new_ms not in dep_specs:
                                    #     specs_added.append(new_ms)
                                else:
                                    seen_specs.add(new_ms)
                    # debugging info - see what specs are bringing in the largest blobs
                    # if size_index != len(reduced_index2):
                    #     print("MS {} added {} pkgs to index".format(ms,
                    #           len(reduced_index2) - size_index))
                    # if specs_added:
                    #     print("MS {} added {} specs to further examination".format(ms,
                    #                                                                specs_added))

        reduced_index2 = frozendict(reduced_index2)
        self._reduced_index_cache[cache_key] = reduced_index2
        return reduced_index2

    def match_any(self, mss, prec):
        return any(ms.match(prec) for ms in mss)

    def find_matches(self, spec: MatchSpec) -> tuple[PackageRecord]:
        res = self._cached_find_matches.get(spec, None)
        if res is not None:
            return res

        spec_name = spec.get_exact_value("name")
        if spec_name:
            candidate_precs = self.groups.get(spec_name, ())
        elif spec.get_exact_value("track_features"):
            feature_names = spec.get_exact_value("track_features")
            candidate_precs = itertools.chain.from_iterable(
                self.trackers.get(feature_name, ()) for feature_name in feature_names
            )
        else:
            candidate_precs = self.index.values()

        res = tuple(p for p in candidate_precs if spec.match(p))
        self._cached_find_matches[spec] = res
        return res

    def ms_depends(self, prec: PackageRecord) -> list[MatchSpec]:
        deps = self.ms_depends_.get(prec)
        if deps is None:
            deps = [MatchSpec(d) for d in prec.combined_depends]
            deps.extend(MatchSpec(track_features=feat) for feat in prec.features)
            self.ms_depends_[prec] = deps
        return deps

    def version_key(self, prec, vtype=None):
        channel = prec.channel
        channel_priority = self._channel_priorities_map.get(
            channel.name, 1
        )  # TODO: ask @mcg1969 why the default value is 1 here  # NOQA
        valid = 1 if channel_priority < MAX_CHANNEL_PRIORITY else 0
        version_comparator = VersionOrder(prec.get("version", ""))
        build_number = prec.get("build_number", 0)
        build_string = prec.get("build")
        noarch = -int(prec.subdir == "noarch")
        if self._channel_priority != ChannelPriority.DISABLED:
            vkey = [valid, -channel_priority, version_comparator, build_number, noarch]
        else:
            vkey = [valid, version_comparator, -channel_priority, build_number, noarch]
        if self._solver_ignore_timestamps:
            vkey.append(build_string)
        else:
            vkey.extend((prec.get("timestamp", 0), build_string))
        return vkey

    @staticmethod
    def _make_channel_priorities(channels):
        priorities_map = {}
        for priority_counter, chn in enumerate(
            itertools.chain.from_iterable(
                (Channel(cc) for cc in c._channels)
                if isinstance(c, MultiChannel)
                else (c,)
                for c in (Channel(c) for c in channels)
            )
        ):
            channel_name = chn.name
            if channel_name in priorities_map:
                continue
            priorities_map[channel_name] = min(
                priority_counter, MAX_CHANNEL_PRIORITY - 1
            )
        return priorities_map

    def get_pkgs(self, ms, emptyok=False):  # pragma: no cover
        # legacy method for conda-build
        ms = MatchSpec(ms)
        precs = self.find_matches(ms)
        if not precs and not emptyok:
            raise ResolvePackageNotFound([(ms,)])
        return sorted(precs, key=self.version_key)

    @staticmethod
    def to_sat_name(val):
        # val can be a PackageRecord or MatchSpec
        if isinstance(val, PackageRecord):
            return val.dist_str()
        elif isinstance(val, MatchSpec):
            return "@s@" + str(val) + ("?" if val.optional else "")
        else:
            raise NotImplementedError()

    @staticmethod
    def to_feature_metric_id(prec_dist_str, feat):
        return f"@fm@{prec_dist_str}@{feat}"

    def push_MatchSpec(self, C, spec):
        spec = MatchSpec(spec)
        sat_name = self.to_sat_name(spec)
        m = C.from_name(sat_name)
        if m is not None:
            # the spec has already been pushed onto the clauses stack
            return sat_name

        simple = spec._is_single()
        nm = spec.get_exact_value("name")
        tf = frozenset(
            _tf
            for _tf in (f.strip() for f in spec.get_exact_value("track_features") or ())
            if _tf
        )

        if nm:
            tgroup = libs = self.groups.get(nm, [])
        elif tf:
            assert len(tf) == 1
            k = next(iter(tf))
            tgroup = libs = self.trackers.get(k, [])
        else:
            tgroup = libs = self.index.keys()
            simple = False
        if not simple:
            libs = [fkey for fkey in tgroup if spec.match(fkey)]
        if len(libs) == len(tgroup):
            if spec.optional:
                m = TRUE
            elif not simple:
                ms2 = MatchSpec(track_features=tf) if tf else MatchSpec(nm)
                m = C.from_name(self.push_MatchSpec(C, ms2))
        if m is None:
            sat_names = [self.to_sat_name(prec) for prec in libs]
            if spec.optional:
                ms2 = MatchSpec(track_features=tf) if tf else MatchSpec(nm)
                sat_names.append("!" + self.to_sat_name(ms2))
            m = C.Any(sat_names)
        C.name_var(m, sat_name)
        return sat_name

    @time_recorder(module_name=__name__)
    def gen_clauses(self):
        C = Clauses(sat_solver=_get_sat_solver_cls(context.sat_solver))
        for name, group in self.groups.items():
            group = [self.to_sat_name(prec) for prec in group]
            # Create one variable for each package
            for sat_name in group:
                C.new_var(sat_name)
            # Create one variable for the group
            m = C.new_var(self.to_sat_name(MatchSpec(name)))

            # Exactly one of the package variables, OR
            # the negation of the group variable, is true
            C.Require(C.ExactlyOne, group + [C.Not(m)])

        # If a package is installed, its dependencies must be as well
        for prec in self.index.values():
            nkey = C.Not(self.to_sat_name(prec))
            for ms in self.ms_depends(prec):
                # Virtual packages can't be installed, we ignore them
                if not ms.name.startswith("__"):
                    C.Require(C.Or, nkey, self.push_MatchSpec(C, ms))

        if log.isEnabledFor(DEBUG):
            log.debug(
                "gen_clauses returning with clause count: %d", C.get_clause_count()
            )
        return C

    def generate_spec_constraints(self, C, specs):
        result = [(self.push_MatchSpec(C, ms),) for ms in specs]
        if log.isEnabledFor(DEBUG):
            log.debug(
                "generate_spec_constraints returning with clause count: %d",
                C.get_clause_count(),
            )
        return result

    def generate_feature_count(self, C):
        result = {
            self.push_MatchSpec(C, MatchSpec(track_features=name)): 1
            for name in self.trackers.keys()
        }
        if log.isEnabledFor(DEBUG):
            log.debug(
                "generate_feature_count returning with clause count: %d",
                C.get_clause_count(),
            )
        return result

    def generate_update_count(self, C, specs):
        return {
            "!" + ms.target: 1 for ms in specs if ms.target and C.from_name(ms.target)
        }

    def generate_feature_metric(self, C):
        eq = {}  # a C.minimize() objective: dict[varname, coeff]
        # Given a pair (prec, feature), assign a "1" score IF:
        # - The prec is installed
        # - The prec does NOT require the feature
        # - At least one package in the group DOES require the feature
        # - A package that tracks the feature is installed
        for name, group in self.groups.items():
            prec_feats = {self.to_sat_name(prec): set(prec.features) for prec in group}
            active_feats = set.union(*prec_feats.values()).intersection(self.trackers)
            for feat in active_feats:
                clause_id_for_feature = self.push_MatchSpec(
                    C, MatchSpec(track_features=feat)
                )
                for prec_sat_name, features in prec_feats.items():
                    if feat not in features:
                        feature_metric_id = self.to_feature_metric_id(
                            prec_sat_name, feat
                        )
                        C.name_var(
                            C.And(prec_sat_name, clause_id_for_feature),
                            feature_metric_id,
                        )
                        eq[feature_metric_id] = 1
        return eq

    def generate_removal_count(self, C, specs):
        return {"!" + self.push_MatchSpec(C, ms.name): 1 for ms in specs}

    def generate_install_count(self, C, specs):
        return {self.push_MatchSpec(C, ms.name): 1 for ms in specs if ms.optional}

    def generate_package_count(self, C, missing):
        return {self.push_MatchSpec(C, nm): 1 for nm in missing}

    def generate_version_metrics(self, C, specs, include0=False):
        # each of these are weights saying how well packages match the specs
        #    format for each: a C.minimize() objective: dict[varname, coeff]
        eqc = {}  # channel
        eqv = {}  # version
        eqb = {}  # build number
        eqa = {}  # arch/noarch
        eqt = {}  # timestamp

        sdict = {}  # dict[package_name, PackageRecord]

        for s in specs:
            s = MatchSpec(s)  # needed for testing
            sdict.setdefault(s.name, [])
            # # TODO: this block is important! can't leave it commented out
            # rec = sdict.setdefault(s.name, [])
            # if s.target:
            #     dist = Dist(s.target)
            #     if dist in self.index:
            #         if self.index[dist].get('priority', 0) < MAX_CHANNEL_PRIORITY:
            #             rec.append(dist)

        for name, targets in sdict.items():
            pkgs = [(self.version_key(p), p) for p in self.groups.get(name, [])]
            pkey = None
            # keep in mind that pkgs is already sorted according to version_key (a tuple,
            #    so composite sort key).  Later entries in the list are, by definition,
            #    greater in some way, so simply comparing with != suffices.
            for version_key, prec in pkgs:
                if targets and any(prec == t for t in targets):
                    continue
                if pkey is None:
                    ic = iv = ib = it = ia = 0
                # valid package, channel priority
                elif pkey[0] != version_key[0] or pkey[1] != version_key[1]:
                    ic += 1
                    iv = ib = it = ia = 0
                # version
                elif pkey[2] != version_key[2]:
                    iv += 1
                    ib = it = ia = 0
                # build number
                elif pkey[3] != version_key[3]:
                    ib += 1
                    it = ia = 0
                # arch/noarch
                elif pkey[4] != version_key[4]:
                    ia += 1
                    it = 0
                elif not self._solver_ignore_timestamps and pkey[5] != version_key[5]:
                    it += 1

                prec_sat_name = self.to_sat_name(prec)
                if ic or include0:
                    eqc[prec_sat_name] = ic
                if iv or include0:
                    eqv[prec_sat_name] = iv
                if ib or include0:
                    eqb[prec_sat_name] = ib
                if ia or include0:
                    eqa[prec_sat_name] = ia
                if it or include0:
                    eqt[prec_sat_name] = it
                pkey = version_key

        return eqc, eqv, eqb, eqa, eqt

    def dependency_sort(
        self,
        must_have: dict[str, PackageRecord],
    ) -> list[PackageRecord]:
        assert isinstance(must_have, dict)

        digraph = {}  # dict[str, set[dependent_package_names]]
        for package_name, prec in must_have.items():
            if prec in self.index:
                digraph[package_name] = {ms.name for ms in self.ms_depends(prec)}

        # There are currently at least three special cases to be aware of.
        # 1. The `toposort()` function, called below, contains special case code to remove
        #    any circular dependency between python and pip.
        # 2. conda/plan.py has special case code for menuinst
        #       Always link/unlink menuinst first/last on windows in case a subsequent
        #       package tries to import it to create/remove a shortcut
        # 3. On windows, python noarch packages need an implicit dependency on conda added, if
        #    conda is in the list of packages for the environment.  Python noarch packages
        #    that have entry points use conda's own conda.exe python entry point binary. If conda
        #    is going to be updated during an operation, the unlink / link order matters.
        #    See issue #6057.

        if on_win and "conda" in digraph:
            for package_name, dist in must_have.items():
                record = self.index.get(prec)
                if hasattr(record, "noarch") and record.noarch == NoarchType.python:
                    digraph[package_name].add("conda")

        sorted_keys = toposort(digraph)
        must_have = must_have.copy()
        # Take all of the items in the sorted keys
        # Don't fail if the key does not exist
        result = [must_have.pop(key) for key in sorted_keys if key in must_have]
        # Take any key that were not sorted
        result.extend(must_have.values())
        return result

    def environment_is_consistent(self, installed):
        log.debug("Checking if the current environment is consistent")
        if not installed:
            return None, []
        sat_name_map = {}  # dict[sat_name, PackageRecord]
        specs = []
        for prec in installed:
            sat_name_map[self.to_sat_name(prec)] = prec
            specs.append(MatchSpec(f"{prec.name} {prec.version} {prec.build}"))
        r2 = Resolve({prec: prec for prec in installed}, True, channels=self.channels)
        C = r2.gen_clauses()
        constraints = r2.generate_spec_constraints(C, specs)
        solution = C.sat(constraints)
        return bool(solution)

    def get_conflicting_specs(self, specs, explicit_specs):
        if not specs:
            return ()

        all_specs = set(specs) | set(explicit_specs)
        reduced_index = self.get_reduced_index(all_specs)

        # Check if satisfiable
        def mysat(specs, add_if=False):
            constraints = r2.generate_spec_constraints(C, specs)
            return C.sat(constraints, add_if)

        if reduced_index:
            r2 = Resolve(reduced_index, True, channels=self.channels)
            C = r2.gen_clauses()
            solution = mysat(all_specs, True)
        else:
            solution = None

        if solution:
            final_unsat_specs = ()
        elif context.unsatisfiable_hints:
            r2 = Resolve(self.index, True, channels=self.channels)
            C = r2.gen_clauses()
            # This first result is just a single unsatisfiable core. There may be several.
            final_unsat_specs = tuple(
                minimal_unsatisfiable_subset(
                    specs, sat=mysat, explicit_specs=explicit_specs
                )
            )
        else:
            final_unsat_specs = None
        return final_unsat_specs

    def bad_installed(self, installed, new_specs):
        log.debug("Checking if the current environment is consistent")
        if not installed:
            return None, []
        sat_name_map = {}  # dict[sat_name, PackageRecord]
        specs = []
        for prec in installed:
            sat_name_map[self.to_sat_name(prec)] = prec
            specs.append(MatchSpec(f"{prec.name} {prec.version} {prec.build}"))
        new_index = {prec: prec for prec in sat_name_map.values()}
        name_map = {p.name: p for p in new_index}
        if "python" in name_map and "pip" not in name_map:
            python_prec = new_index[name_map["python"]]
            if "pip" in python_prec.depends:
                # strip pip dependency from python if not installed in environment
                new_deps = [d for d in python_prec.depends if d != "pip"]
                python_prec.depends = new_deps
        r2 = Resolve(new_index, True, channels=self.channels)
        C = r2.gen_clauses()
        constraints = r2.generate_spec_constraints(C, specs)
        solution = C.sat(constraints)
        limit = xtra = None
        if not solution or xtra:

            def get_(name, snames):
                if name not in snames:
                    snames.add(name)
                    for fn in self.groups.get(name, []):
                        for ms in self.ms_depends(fn):
                            get_(ms.name, snames)

            # New addition: find the largest set of installed packages that
            # are consistent with each other, and include those in the
            # list of packages to maintain consistency with
            snames = set()
            eq_optional_c = r2.generate_removal_count(C, specs)
            solution, _ = C.minimize(eq_optional_c, C.sat())
            snames.update(
                sat_name_map[sat_name]["name"]
                for sat_name in (C.from_index(s) for s in solution)
                if sat_name and sat_name[0] != "!" and "@" not in sat_name
            )
            # Existing behavior: keep all specs and their dependencies
            for spec in new_specs:
                get_(MatchSpec(spec).name, snames)
            if len(snames) < len(sat_name_map):
                limit = snames
                xtra = [
                    rec
                    for sat_name, rec in sat_name_map.items()
                    if rec["name"] not in snames
                ]
                log.debug(
                    "Limiting solver to the following packages: %s", ", ".join(limit)
                )
        if xtra:
            log.debug("Packages to be preserved: %s", xtra)
        return limit, xtra

    def restore_bad(self, pkgs, preserve):
        if preserve:
            sdict = {prec.name: prec for prec in pkgs}
            pkgs.extend(p for p in preserve if p.name not in sdict)

    def install_specs(self, specs, installed, update_deps=True):
        specs = list(map(MatchSpec, specs))
        snames = {s.name for s in specs}
        log.debug("Checking satisfiability of current install")
        limit, preserve = self.bad_installed(installed, specs)
        for prec in installed:
            if prec not in self.index:
                continue
            name, version, build = prec.name, prec.version, prec.build
            schannel = prec.channel.canonical_name
            if name in snames or limit is not None and name not in limit:
                continue
            # If update_deps=True, set the target package in MatchSpec so that
            # the solver can minimize the version change. If update_deps=False,
            # fix the version and build so that no change is possible.
            if update_deps:
                # TODO: fix target here
                spec = MatchSpec(name=name, target=prec.dist_str())
            else:
                spec = MatchSpec(
                    name=name, version=version, build=build, channel=schannel
                )
            specs.insert(0, spec)
        return tuple(specs), preserve

    def install(self, specs, installed=None, update_deps=True, returnall=False):
        specs, preserve = self.install_specs(specs, installed or [], update_deps)
        pkgs = []
        if specs:
            pkgs = self.solve(specs, returnall=returnall, _remove=False)
        self.restore_bad(pkgs, preserve)
        return pkgs

    def remove_specs(self, specs, installed):
        nspecs = []
        # There's an imperfect thing happening here. "specs" nominally contains
        # a list of package names or track_feature values to be removed. But
        # because of add_defaults_to_specs it may also contain version constraints
        # like "python 2.7*", which are *not* asking for python to be removed.
        # We need to separate these two kinds of specs here.
        for s in map(MatchSpec, specs):
            # Since '@' is an illegal version number, this ensures that all of
            # these matches will never match an actual package. Combined with
            # optional=True, this has the effect of forcing their removal.
            if s._is_single():
                nspecs.append(MatchSpec(s, version="@", optional=True))
            else:
                nspecs.append(MatchSpec(s, optional=True))
        snames = {s.name for s in nspecs if s.name}
        limit, _ = self.bad_installed(installed, nspecs)
        preserve = []
        for prec in installed:
            nm, ver = prec.name, prec.version
            if nm in snames:
                continue
            elif limit is not None:
                preserve.append(prec)
            else:
                # TODO: fix target here
                nspecs.append(
                    MatchSpec(
                        name=nm,
                        version=">=" + ver if ver else None,
                        optional=True,
                        target=prec.dist_str(),
                    )
                )
        return nspecs, preserve

    def remove(self, specs, installed):
        specs, preserve = self.remove_specs(specs, installed)
        pkgs = self.solve(specs, _remove=True)
        self.restore_bad(pkgs, preserve)
        return pkgs

    @time_recorder(module_name=__name__)
    def solve(
        self,
        specs: list,
        returnall: bool = False,
        _remove=False,
        specs_to_add=None,
        history_specs=None,
        should_retry_solve=False,
    ) -> list[PackageRecord]:
        if specs and not isinstance(specs[0], MatchSpec):
            specs = tuple(MatchSpec(_) for _ in specs)

        specs = set(specs)
        if log.isEnabledFor(DEBUG):
            dlist = dashlist(
                str("%i: %s target=%s optional=%s" % (i, s, s.target, s.optional))
                for i, s in enumerate(specs)
            )
            log.debug("Solving for: %s", dlist)

        if not specs:
            return ()

        # Find the compliant packages
        log.debug("Solve: Getting reduced index of compliant packages")
        len0 = len(specs)

        reduced_index = self.get_reduced_index(
            specs, exit_on_conflict=not context.unsatisfiable_hints
        )
        if not reduced_index:
            # something is intrinsically unsatisfiable - either not found or
            # not the right version
            not_found_packages = set()
            wrong_version_packages = set()
            for s in specs:
                if not self.find_matches(s):
                    if s.name in self.groups:
                        wrong_version_packages.add(s)
                    else:
                        not_found_packages.add(s)
            if not_found_packages:
                raise ResolvePackageNotFound(not_found_packages)
            elif wrong_version_packages:
                raise UnsatisfiableError(
                    [[d] for d in wrong_version_packages], chains=False
                )
            if should_retry_solve:
                # We don't want to call find_conflicts until our last try.
                # This jumps back out to conda/cli/install.py, where the
                # retries happen
                raise UnsatisfiableError({})
            else:
                self.find_conflicts(specs, specs_to_add, history_specs)

        # Check if satisfiable
        log.debug("Solve: determining satisfiability")

        def mysat(specs, add_if=False):
            constraints = r2.generate_spec_constraints(C, specs)
            return C.sat(constraints, add_if)

        # Return a solution of packages
        def clean(sol):
            return [
                q
                for q in (C.from_index(s) for s in sol)
                if q and q[0] != "!" and "@" not in q
            ]

        def is_converged(solution):
            """Determine if the SAT problem has converged to a single solution.

            This is determined by testing for a SAT solution with the current
            clause set and a clause in which at least one of the packages in
            the current solution is excluded. If a solution exists the problem
            has not converged as multiple solutions still exist.
            """
            psolution = clean(solution)
            nclause = tuple(C.Not(C.from_name(q)) for q in psolution)
            if C.sat((nclause,), includeIf=False) is None:
                return True
            return False

        r2 = Resolve(reduced_index, True, channels=self.channels)
        C = r2.gen_clauses()
        solution = mysat(specs, True)
        if not solution:
            if should_retry_solve:
                # we don't want to call find_conflicts until our last try
                raise UnsatisfiableError({})
            else:
                self.find_conflicts(specs, specs_to_add, history_specs)

        speco = []  # optional packages
        specr = []  # requested packages
        speca = []  # all other packages
        specm = set(r2.groups)  # missing from specs
        for k, s in enumerate(specs):
            if s.name in specm:
                specm.remove(s.name)
            if not s.optional:
                (speca if s.target or k >= len0 else specr).append(s)
            elif any(r2.find_matches(s)):
                s = MatchSpec(s.name, optional=True, target=s.target)
                speco.append(s)
                speca.append(s)
        speca.extend(MatchSpec(s) for s in specm)

        if log.isEnabledFor(DEBUG):
            log.debug("Requested specs: %s", dashlist(sorted(str(s) for s in specr)))
            log.debug("Optional specs: %s", dashlist(sorted(str(s) for s in speco)))
            log.debug("All other specs: %s", dashlist(sorted(str(s) for s in speca)))
            log.debug("missing specs: %s", dashlist(sorted(str(s) for s in specm)))

        # Removed packages: minimize count
        log.debug("Solve: minimize removed packages")
        if _remove:
            eq_optional_c = r2.generate_removal_count(C, speco)
            solution, obj7 = C.minimize(eq_optional_c, solution)
            log.debug("Package removal metric: %d", obj7)

        # Requested packages: maximize versions
        log.debug("Solve: maximize versions of requested packages")
        eq_req_c, eq_req_v, eq_req_b, eq_req_a, eq_req_t = r2.generate_version_metrics(
            C, specr
        )
        solution, obj3a = C.minimize(eq_req_c, solution)
        solution, obj3 = C.minimize(eq_req_v, solution)
        log.debug("Initial package channel/version metric: %d/%d", obj3a, obj3)

        # Track features: minimize feature count
        log.debug("Solve: minimize track_feature count")
        eq_feature_count = r2.generate_feature_count(C)
        solution, obj1 = C.minimize(eq_feature_count, solution)
        log.debug("Track feature count: %d", obj1)

        # Featured packages: minimize number of featureless packages
        # installed when a featured alternative is feasible.
        # For example, package name foo exists with two built packages. One with
        # 'track_features: 'feat1', and one with 'track_features': 'feat2'.
        # The previous "Track features" minimization pass has chosen 'feat1' for the
        # environment, but not 'feat2'. In this case, the 'feat2' version of foo is
        # considered "featureless."
        eq_feature_metric = r2.generate_feature_metric(C)
        solution, obj2 = C.minimize(eq_feature_metric, solution)
        log.debug("Package misfeature count: %d", obj2)

        # Requested packages: maximize builds
        log.debug("Solve: maximize build numbers of requested packages")
        solution, obj4 = C.minimize(eq_req_b, solution)
        log.debug("Initial package build metric: %d", obj4)

        # prefer arch packages where available for requested specs
        log.debug("Solve: prefer arch over noarch for requested packages")
        solution, noarch_obj = C.minimize(eq_req_a, solution)
        log.debug("Noarch metric: %d", noarch_obj)

        # Optional installations: minimize count
        if not _remove:
            log.debug("Solve: minimize number of optional installations")
            eq_optional_install = r2.generate_install_count(C, speco)
            solution, obj49 = C.minimize(eq_optional_install, solution)
            log.debug("Optional package install metric: %d", obj49)

        # Dependencies: minimize the number of packages that need upgrading
        log.debug("Solve: minimize number of necessary upgrades")
        eq_u = r2.generate_update_count(C, speca)
        solution, obj50 = C.minimize(eq_u, solution)
        log.debug("Dependency update count: %d", obj50)

        # Remaining packages: maximize versions, then builds
        log.debug(
            "Solve: maximize versions and builds of indirect dependencies.  "
            "Prefer arch over noarch where equivalent."
        )
        eq_c, eq_v, eq_b, eq_a, eq_t = r2.generate_version_metrics(C, speca)
        solution, obj5a = C.minimize(eq_c, solution)
        solution, obj5 = C.minimize(eq_v, solution)
        solution, obj6 = C.minimize(eq_b, solution)
        solution, obj6a = C.minimize(eq_a, solution)
        log.debug(
            "Additional package channel/version/build/noarch metrics: %d/%d/%d/%d",
            obj5a,
            obj5,
            obj6,
            obj6a,
        )

        # Prune unnecessary packages
        log.debug("Solve: prune unnecessary packages")
        eq_c = r2.generate_package_count(C, specm)
        solution, obj7 = C.minimize(eq_c, solution, trymax=True)
        log.debug("Weak dependency count: %d", obj7)

        if not is_converged(solution):
            # Maximize timestamps
            eq_t.update(eq_req_t)
            solution, obj6t = C.minimize(eq_t, solution)
            log.debug("Timestamp metric: %d", obj6t)

        log.debug("Looking for alternate solutions")
        nsol = 1
        psolutions = []
        psolution = clean(solution)
        psolutions.append(psolution)
        while True:
            nclause = tuple(C.Not(C.from_name(q)) for q in psolution)
            solution = C.sat((nclause,), True)
            if solution is None:
                break
            nsol += 1
            if nsol > 10:
                log.debug("Too many solutions; terminating")
                break
            psolution = clean(solution)
            psolutions.append(psolution)

        if nsol > 1:
            psols2 = list(map(set, psolutions))
            common = set.intersection(*psols2)
            diffs = [sorted(set(sol) - common) for sol in psols2]
            if not context.json:
                stdoutlog.info(
                    "\nWarning: {} possible package resolutions "
                    "(only showing differing packages):{}{}".format(
                        ">10" if nsol > 10 else nsol,
                        dashlist(", ".join(diff) for diff in diffs),
                        "\n  ... and others" if nsol > 10 else "",
                    )
                )

        # def stripfeat(sol):
        #     return sol.split('[')[0]

        new_index = {self.to_sat_name(prec): prec for prec in self.index.values()}

        if returnall:
            if len(psolutions) > 1:
                raise RuntimeError()
            # TODO: clean up this mess
            # return [sorted(Dist(stripfeat(dname)) for dname in psol) for psol in psolutions]
            # return [sorted((new_index[sat_name] for sat_name in psol), key=lambda x: x.name)
            #         for psol in psolutions]

            # return sorted(Dist(stripfeat(dname)) for dname in psolutions[0])
        return sorted(
            (new_index[sat_name] for sat_name in psolutions[0]), key=lambda x: x.name
        )
