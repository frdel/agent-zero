# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Collection of conda's high-level APIs."""

from .base.constants import DepsModifier as _DepsModifier
from .base.constants import UpdateModifier as _UpdateModifier
from .base.context import context
from .common.constants import NULL
from .core.package_cache_data import PackageCacheData as _PackageCacheData
from .core.prefix_data import PrefixData as _PrefixData
from .core.subdir_data import SubdirData as _SubdirData
from .models.channel import Channel

#: Flags to enable alternate handling of dependencies.
DepsModifier = _DepsModifier

#: Flags to enable alternate handling for updates of existing packages in the environment.
UpdateModifier = _UpdateModifier


class Solver:
    """
    **Beta** While in beta, expect both major and minor changes across minor releases.

    A high-level API to conda's solving logic. Three public methods are provided to access a
    solution in various forms.

      * :meth:`solve_final_state`
      * :meth:`solve_for_diff`
      * :meth:`solve_for_transaction`

    """

    def __init__(
        self, prefix, channels, subdirs=(), specs_to_add=(), specs_to_remove=()
    ):
        """
        **Beta**

        Args:
            prefix (str):
                The conda prefix / environment location for which the :class:`Solver`
                is being instantiated.
            channels (Sequence[:class:`Channel`]):
                A prioritized list of channels to use for the solution.
            subdirs (Sequence[str]):
                A prioritized list of subdirs to use for the solution.
            specs_to_add (set[:class:`MatchSpec`]):
                The set of package specs to add to the prefix.
            specs_to_remove (set[:class:`MatchSpec`]):
                The set of package specs to remove from the prefix.

        """
        solver_backend = context.plugin_manager.get_cached_solver_backend()
        self._internal = solver_backend(
            prefix, channels, subdirs, specs_to_add, specs_to_remove
        )

    def solve_final_state(
        self,
        update_modifier=NULL,
        deps_modifier=NULL,
        prune=NULL,
        ignore_pinned=NULL,
        force_remove=NULL,
    ):
        """
        **Beta** While in beta, expect both major and minor changes across minor releases.

        Gives the final, solved state of the environment.

        Args:
            deps_modifier (DepsModifier):
                An optional flag indicating special solver handling for dependencies. The
                default solver behavior is to be as conservative as possible with dependency
                updates (in the case the dependency already exists in the environment), while
                still ensuring all dependencies are satisfied.  Options include
                * NO_DEPS
                * ONLY_DEPS
                * UPDATE_DEPS
                * UPDATE_DEPS_ONLY_DEPS
                * FREEZE_INSTALLED
            prune (bool):
                If ``True``, the solution will not contain packages that were
                previously brought into the environment as dependencies but are no longer
                required as dependencies and are not user-requested.
            ignore_pinned (bool):
                If ``True``, the solution will ignore pinned package configuration
                for the prefix.
            force_remove (bool):
                Forces removal of a package without removing packages that depend on it.

        Returns:
            tuple[PackageRef]:
                In sorted dependency order from roots to leaves, the package references for
                the solved state of the environment.

        """
        return self._internal.solve_final_state(
            update_modifier, deps_modifier, prune, ignore_pinned, force_remove
        )

    def solve_for_diff(
        self,
        update_modifier=NULL,
        deps_modifier=NULL,
        prune=NULL,
        ignore_pinned=NULL,
        force_remove=NULL,
        force_reinstall=False,
    ):
        """
        **Beta** While in beta, expect both major and minor changes across minor releases.

        Gives the package references to remove from an environment, followed by
        the package references to add to an environment.

        Args:
            deps_modifier (DepsModifier):
                See :meth:`solve_final_state`.
            prune (bool):
                See :meth:`solve_final_state`.
            ignore_pinned (bool):
                See :meth:`solve_final_state`.
            force_remove (bool):
                See :meth:`solve_final_state`.
            force_reinstall (bool):
                For requested specs_to_add that are already satisfied in the environment,
                instructs the solver to remove the package and spec from the environment,
                and then add it back--possibly with the exact package instance modified,
                depending on the spec exactness.

        Returns:
            tuple[PackageRef], tuple[PackageRef]:
                A two-tuple of PackageRef sequences.  The first is the group of packages to
                remove from the environment, in sorted dependency order from leaves to roots.
                The second is the group of packages to add to the environment, in sorted
                dependency order from roots to leaves.

        """
        return self._internal.solve_for_diff(
            update_modifier,
            deps_modifier,
            prune,
            ignore_pinned,
            force_remove,
            force_reinstall,
        )

    def solve_for_transaction(
        self,
        update_modifier=NULL,
        deps_modifier=NULL,
        prune=NULL,
        ignore_pinned=NULL,
        force_remove=NULL,
        force_reinstall=False,
    ):
        """
        **Beta** While in beta, expect both major and minor changes across minor releases.

        Gives an UnlinkLinkTransaction instance that can be used to execute the solution
        on an environment.

        Args:
            deps_modifier (DepsModifier):
                See :meth:`solve_final_state`.
            prune (bool):
                See :meth:`solve_final_state`.
            ignore_pinned (bool):
                See :meth:`solve_final_state`.
            force_remove (bool):
                See :meth:`solve_final_state`.
            force_reinstall (bool):
                See :meth:`solve_for_diff`.

        Returns:
            UnlinkLinkTransaction:

        """
        return self._internal.solve_for_transaction(
            update_modifier,
            deps_modifier,
            prune,
            ignore_pinned,
            force_remove,
            force_reinstall,
        )


class SubdirData:
    """
    **Beta** While in beta, expect both major and minor changes across minor releases.

    High-level management and usage of repodata.json for subdirs.
    """

    def __init__(self, channel):
        """
        **Beta** While in beta, expect both major and minor changes across minor releases.

        Args:
            channel (str or Channel):
                The target subdir for the instance. Must either be a url that includes a subdir
                or a :obj:`Channel` that includes a subdir. e.g.:
                    * 'https://repo.anaconda.com/pkgs/main/linux-64'
                    * Channel('https://repo.anaconda.com/pkgs/main/linux-64')
                    * Channel('conda-forge/osx-64')
        """
        channel = Channel(channel)
        assert channel.subdir
        self._internal = _SubdirData(channel)

    def query(self, package_ref_or_match_spec):
        """
        **Beta** While in beta, expect both major and minor changes across minor releases.

        Run a query against this specific instance of repodata.

        Args:
            package_ref_or_match_spec (PackageRef or MatchSpec or str):
                Either an exact :obj:`PackageRef` to match against, or a :obj:`MatchSpec`
                query object.  A :obj:`str` will be turned into a :obj:`MatchSpec` automatically.

        Returns:
            tuple[PackageRecord]

        """
        return tuple(self._internal.query(package_ref_or_match_spec))

    @staticmethod
    def query_all(package_ref_or_match_spec, channels=None, subdirs=None):
        """
        **Beta** While in beta, expect both major and minor changes across minor releases.

        Run a query against all repodata instances in channel/subdir matrix.

        Args:
            package_ref_or_match_spec (PackageRef or MatchSpec or str):
                Either an exact :obj:`PackageRef` to match against, or a :obj:`MatchSpec`
                query object.  A :obj:`str` will be turned into a :obj:`MatchSpec` automatically.
            channels (Iterable[Channel or str] or None):
                An iterable of urls for channels or :obj:`Channel` objects. If None, will fall
                back to context.channels.
            subdirs (Iterable[str] or None):
                If None, will fall back to context.subdirs.

        Returns:
            tuple[PackageRecord]

        """
        return tuple(
            _SubdirData.query_all(package_ref_or_match_spec, channels, subdirs)
        )

    def iter_records(self):
        """
        **Beta** While in beta, expect both major and minor changes across minor releases.

        Returns:
            Iterable[PackageRecord]: A generator over all records contained in the repodata.json
                instance.  Warning: this is a generator that is exhausted on first use.

        """
        return self._internal.iter_records()

    def reload(self):
        """
        **Beta** While in beta, expect both major and minor changes across minor releases.

        Update the instance with new information. Backing information (i.e. repodata.json)
        is lazily downloaded/loaded on first use by the other methods of this class. You
        should only use this method if you are *sure* you have outdated data.

        Returns:
            SubdirData

        """
        self._internal = self._internal.reload()
        return self


class PackageCacheData:
    """
    **Beta** While in beta, expect both major and minor changes across minor releases.

    High-level management and usage of package caches.
    """

    def __init__(self, pkgs_dir):
        """
        **Beta** While in beta, expect both major and minor changes across minor releases.

        Args:
            pkgs_dir (str):
        """
        self._internal = _PackageCacheData(pkgs_dir)

    def get(self, package_ref, default=NULL):
        """
        **Beta** While in beta, expect both major and minor changes across minor releases.

        Args:
            package_ref (PackageRef):
                A :obj:`PackageRef` instance representing the key for the
                :obj:`PackageCacheRecord` being sought.
            default: The default value to return if the record does not exist. If not
                specified and no record exists, :exc:`KeyError` is raised.

        Returns:
            PackageCacheRecord

        """
        return self._internal.get(package_ref, default)

    def query(self, package_ref_or_match_spec):
        """
        **Beta** While in beta, expect both major and minor changes across minor releases.

        Run a query against this specific package cache instance.

        Args:
            package_ref_or_match_spec (PackageRef or MatchSpec or str):
                Either an exact :obj:`PackageRef` to match against, or a :obj:`MatchSpec`
                query object.  A :obj:`str` will be turned into a :obj:`MatchSpec` automatically.

        Returns:
            tuple[PackageCacheRecord]

        """
        return tuple(self._internal.query(package_ref_or_match_spec))

    @staticmethod
    def query_all(package_ref_or_match_spec, pkgs_dirs=None):
        """
        **Beta** While in beta, expect both major and minor changes across minor releases.

        Run a query against all package caches.

        Args:
            package_ref_or_match_spec (PackageRef or MatchSpec or str):
                Either an exact :obj:`PackageRef` to match against, or a :obj:`MatchSpec`
                query object.  A :obj:`str` will be turned into a :obj:`MatchSpec` automatically.
            pkgs_dirs (Iterable[str] or None):
                If None, will fall back to context.pkgs_dirs.

        Returns:
            tuple[PackageCacheRecord]

        """
        return tuple(_PackageCacheData.query_all(package_ref_or_match_spec, pkgs_dirs))

    def iter_records(self):
        """
        **Beta** While in beta, expect both major and minor changes across minor releases.

        Returns:
            Iterable[PackageCacheRecord]: A generator over all records contained in the package
                cache instance.  Warning: this is a generator that is exhausted on first use.

        """
        return self._internal.iter_records()

    @property
    def is_writable(self):
        """
        **Beta** While in beta, expect both major and minor changes across minor releases.

        Indicates if the package cache location is writable or read-only.

        Returns:
            bool

        """
        return self._internal.is_writable

    @staticmethod
    def first_writable(pkgs_dirs=None):
        """
        **Beta** While in beta, expect both major and minor changes across minor releases.

        Get an instance object for the first writable package cache.

        Args:
            pkgs_dirs (Iterable[str]):
                If None, will fall back to context.pkgs_dirs.

        Returns:
            PackageCacheData:
                An instance for the first writable package cache.

        """
        return PackageCacheData(_PackageCacheData.first_writable(pkgs_dirs).pkgs_dir)

    def reload(self):
        """
        **Beta** While in beta, expect both major and minor changes across minor releases.

        Update the instance with new information. Backing information (i.e. contents of
        the pkgs_dir) is lazily loaded on first use by the other methods of this class. You
        should only use this method if you are *sure* you have outdated data.

        Returns:
            PackageCacheData

        """
        self._internal = self._internal.reload()
        return self


class PrefixData:
    """
    **Beta** While in beta, expect both major and minor changes across minor releases.

    High-level management and usage of conda environment prefixes.
    """

    def __init__(self, prefix_path):
        """
        **Beta** While in beta, expect both major and minor changes across minor releases.

        Args:
            prefix_path (str):
        """
        self._internal = _PrefixData(prefix_path)

    def get(self, package_ref, default=NULL):
        """
        **Beta** While in beta, expect both major and minor changes across minor releases.

        Args:
            package_ref (PackageRef):
                A :obj:`PackageRef` instance representing the key for the
                :obj:`PrefixRecord` being sought.
            default: The default value to return if the record does not exist. If not
                specified and no record exists, :exc:`KeyError` is raised.

        Returns:
            PrefixRecord

        """
        return self._internal.get(package_ref.name, default)

    def query(self, package_ref_or_match_spec):
        """
        **Beta** While in beta, expect both major and minor changes across minor releases.

        Run a query against this specific prefix instance.

        Args:
            package_ref_or_match_spec (PackageRef or MatchSpec or str):
                Either an exact :obj:`PackageRef` to match against, or a :obj:`MatchSpec`
                query object.  A :obj:`str` will be turned into a :obj:`MatchSpec` automatically.

        Returns:
            tuple[PrefixRecord]

        """
        return tuple(self._internal.query(package_ref_or_match_spec))

    def iter_records(self):
        """
        **Beta** While in beta, expect both major and minor changes across minor releases.

        Returns:
            Iterable[PrefixRecord]: A generator over all records contained in the prefix.
                Warning: this is a generator that is exhausted on first use.

        """
        return self._internal.iter_records()

    @property
    def is_writable(self):
        """
        **Beta** While in beta, expect both major and minor changes across minor releases.

        Indicates if the prefix is writable or read-only.

        Returns:
            bool or None:
                True if the prefix is writable.  False if read-only.  None if the prefix
                does not exist as a conda environment.

        """
        return self._internal.is_writable

    def reload(self):
        """
        **Beta** While in beta, expect both major and minor changes across minor releases.

        Update the instance with new information. Backing information (i.e. contents of
        the conda-meta directory) is lazily loaded on first use by the other methods of this
        class. You should only use this method if you are *sure* you have outdated data.

        Returns:
            PrefixData

        """
        self._internal = self._internal.reload()
        return self
