# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Tools for fetching the current index."""

from __future__ import annotations

from collections import UserDict
from itertools import chain
from logging import getLogger
from typing import TYPE_CHECKING

from boltons.setutils import IndexedSet

from ..base.context import context
from ..common.io import ThreadLimitedThreadPoolExecutor, time_recorder
from ..deprecations import deprecated
from ..exceptions import (
    ChannelDenied,
    ChannelNotAllowed,
    CondaKeyError,
    InvalidSpec,
    OperationNotAllowed,
    PackagesNotFoundError,
)
from ..models.channel import Channel, all_channel_urls
from ..models.match_spec import MatchSpec
from ..models.records import EMPTY_LINK, PackageCacheRecord, PackageRecord, PrefixRecord
from .package_cache_data import PackageCacheData
from .prefix_data import PrefixData
from .subdir_data import SubdirData

if TYPE_CHECKING:
    import os
    from pathlib import Path
    from typing import Any, Iterable, Self


log = getLogger(__name__)


def check_allowlist(channel_urls: list[str]) -> None:
    """
    Check if the given channel URLs are allowed by the context's allowlist.

    :param channel_urls: A list of channel URLs to check against the allowlist.
    :raises ChannelNotAllowed: If any URL is not in the allowlist.
    :raises ChannelDenied: If any URL is in the denylist.
    """
    allowlist_channel_urls = tuple(
        chain.from_iterable(
            Channel(allowlist_channel).base_urls
            for allowlist_channel in context.allowlist_channels
        )
    )
    denylist_channel_urls = tuple(
        chain.from_iterable(
            Channel(denylist_channel).base_urls
            for denylist_channel in context.denylist_channels
        )
    )
    if allowlist_channel_urls or denylist_channel_urls:
        for channel_url in channel_urls:
            channel = Channel(channel_url)
            for channel_base_url in channel.base_urls:
                if channel_base_url in denylist_channel_urls:
                    raise ChannelDenied(channel)
                if (
                    allowlist_channel_urls
                    and channel_base_url not in allowlist_channel_urls
                ):
                    raise ChannelNotAllowed(channel)


LAST_CHANNEL_URLS = []


class Index(UserDict):
    """The ``Index`` provides information about available packages from all relevant sources.

    There are four types of sources for package information, namely

    Channels
        represent packages available from standard sources identified with a url, mostly online,
        but can also be on a local filesystem using the ``file://`` scheme.
        Programatically, channels are represented by :class:`conda.models.channel.Channel`, their data
        is fetched using :class:`conda.core.subdir_data.SubdirData`.

        For more information see :ref:`concepts-channels`.

        Individual packages from channels are usually represented by :class:`conda.models.records.PackageRecord`.

    Prefix
        represents packages that are already installed. Every :class:`Index` can be associated
        with exactly one Prefix, which is the location of one of the conda :ref:`concepts-conda-environments`.
        The package information about the installed packages is represented by :class:`conda.core.prefix_data.PrefixData`.

        Individual packages from prefixes are usually represented by :class:`conda.models.records.PrefixRecord`.

    Package Cache
        represents packages that are locally unpacked, but may not be installed in the environment
        associated with this index. These are usually packages that have been installed in any environment
        of the local conda installation, but may have been removed from all environments by now.

        Individual packages from the package are usually represented by :class:`conda.models.records.PackageCacheRecord`.

    Virtual Packages
        represent properties of the system, not actual conda packages in the normal sense. These are,
        for example, system packages that inform the solver about the operating system in use, or
        track features that can be used to steer package priority.

        Individual virtual packages are represented by special :class:`conda.models.records.PackageRecord`,
        see :meth:`conda.models.records.PackageRecord.virtual_package` and
        :meth:`conda.models.records.PackageRecord.feature`.
    """

    def __init__(
        self,
        channels: Iterable[str | Channel] = (),
        prepend: bool = True,
        platform: str | None = None,
        subdirs: tuple[str, ...] | None = None,
        use_local: bool = False,
        use_cache: bool | None = None,
        prefix: str | os.PathLike[str] | Path | PrefixData | None = None,
        repodata_fn: str | None = context.repodata_fns[-1],
        use_system: bool = False,
    ) -> None:
        """Initializes a new index with the desired components.

        Args:
          channels: channels identified by canonical names or URLS or Channel objects;
            for more details, see :meth:`conda.models.channel.Channel.from_value`
          prepend: if ``True`` (default), add configured channel with higher priority than passed channels;
            if ``False``, do *not* add configured channels.
          platform: see ``subdirs``.
          subdirs: platform and subdirs determine the selection of subdirs in the channels;
            if both are ``None``, subdirs is taken from the configuration;
            if both are given, ``subdirs`` takes precedence and ``platform`` is ignored;
            if only ``platform`` is given, subdirs will be ``(platform, "noarch")``;
            if ``subdirs`` is given, subdirs will be ``subdirs``.
          use_local: if ``True``, add the special "local" channel for locally built packages with lowest priority.
          use_cache: if ``True``, add packages from the package cache.
          prefix: associate prefix with this index and add its packages.
          repodata_fn: filename of the repodata, default taken from config, almost always "repodata.json".
          use_system: if ``True``, add system packages, that is virtual packages defined by plugins, usually used
            to make intrinsic information about the system, such as cpu architecture or operating system, available
            to the solver.
        """
        channels = list(channels)
        if use_local:
            channels = ["local", *channels]
        if prepend:
            channels += context.channels
        self._channels = IndexedSet(channels)
        if subdirs:
            if platform:
                log.warning("subdirs is %s, ignoring platform %s", subdirs, platform)
        else:
            subdirs = (platform, "noarch") if platform is not None else context.subdirs
        self._subdirs = subdirs
        self._repodata_fn = repodata_fn
        self.channels = {}
        self.expanded_channels = IndexedSet()
        for channel in self._channels:
            urls = Channel(channel).urls(True, subdirs)
            check_allowlist(urls)
            expanded_channels = [Channel(url) for url in urls]
            self.channels[channel] = [
                SubdirData(expanded_channel, repodata_fn=repodata_fn)
                for expanded_channel in expanded_channels
            ]
            self.expanded_channels.update(expanded_channels)
        # LAST_CHANNEL_URLS is still used in conda-build and must be maintained for the moment.
        LAST_CHANNEL_URLS.clear()
        LAST_CHANNEL_URLS.extend(self.expanded_channels)
        if prefix is None:
            self.prefix_data = None
        elif isinstance(prefix, PrefixData):
            self.prefix_data = prefix
        else:
            self.prefix_data = PrefixData(prefix)
        self.use_cache = True if use_cache is None and context.offline else use_cache
        self.use_system = use_system

    @property
    def cache_entries(self) -> tuple[PackageCacheRecord, ...]:
        """Contents of the package cache if active.

        Returns:
          All packages available from the package cache.
        """
        try:
            return self._cache_entries
        except AttributeError:
            self.reload(cache=True)
        return self._cache_entries

    @property
    def system_packages(self) -> dict[PackageRecord, PackageRecord]:
        """System packages provided by plugins.

        Returns:
          Identity mapping of the available system packages in a ``dict``.
        """
        try:
            return self._system_packages
        except AttributeError:
            self.reload(system=True)
        return self._system_packages

    @property
    def features(self) -> dict[PackageRecord, PackageRecord]:
        """Active tracking features.

        Returns:
          Identity mapping of the local tracking features in a ``dict``.
        """
        try:
            return self._features
        except AttributeError:
            self.reload(features=True)
        return self._features

    def reload(
        self,
        *,
        prefix: bool = False,
        cache: bool = False,
        features: bool = False,
        system: bool = False,
    ) -> None:
        """Reload one or more of the index components.

        Can be used to refresh the index with new information, for example after a new
        package has been installed into the index.

        Args:
          prefix: if ``True``, reload the prefix data.
          cache: if ``True``, reload the package cache.
          features: if ``True``, reload the tracking features.
          system: if ``True``, reload the system packages.
        """
        has_data = hasattr(self, "_data")
        if prefix:
            if self.prefix_data:
                self.prefix_data.reload()
            if has_data:
                self._supplement_index_dict_with_prefix()
        if cache:
            self._cache_entries = PackageCacheData.get_all_extracted_entries()
            if has_data:
                self._supplement_index_dict_with_cache()
        if features:
            self._features = {
                (rec := PackageRecord.feature(track_feature)): rec
                for track_feature in context.track_features
            }
            if has_data:
                self._data.update(self.features)
        if system:
            self._system_packages = {
                package: package
                for package in context.plugin_manager.get_virtual_package_records()
            }
            if has_data:
                self._data.update(self.system_packages)

    def __repr__(self) -> str:
        channels = ", ".join(self.channels.keys())
        return f"<{self.__class__.__name__}(channels=[{channels}])>"

    def get_reduced_index(self, specs: Iterable[MatchSpec]) -> ReducedIndex:
        """Create a reduced index with a subset of packages.

        Can be used to create a reduced index as a subset from an existing index.

        Args:
          specs: the specs that span the subset.

        Returns:
          a reduced index with the same sources as this index, but limited to ``specs``
          and their dependency graph.
        """
        return ReducedIndex(
            specs=specs,
            channels=self._channels,
            prepend=False,
            subdirs=self._subdirs,
            use_local=False,
            use_cache=self.use_cache,
            prefix=self.prefix_data,
            repodata_fn=self._repodata_fn,
            use_system=self.use_system,
        )

    @property
    def data(self) -> dict[PackageRecord, PackageRecord]:
        """The entire index as a dict; avoid if possible.

        Warning:
          This returns the entire contents of the index as a single identity mapping in
          a ``dict``. This may be convenient, but it comes at a cost because all sources
          must be fully loaded at significant overhead for :class:`~conda.models.records.PackageRecord`
          construction for **every** package.

          Hence, all uses of :attr:`data`, including all iteration over the entire index,
          is strongly discouraged.
        """
        try:
            return self._data
        except AttributeError:
            self._realize()
            return self._data

    @data.setter
    def data(self, value: dict[PackageRecord, PackageRecord]) -> None:
        self._data = value

    def _supplement_index_dict_with_prefix(self) -> None:
        """
        Supplement the index with information from its prefix.
        """
        if self.prefix_data is None:
            return

        # supplement index with information from prefix/conda-meta
        for prefix_record in self.prefix_data.iter_records():
            if prefix_record in self._data:
                current_record = self._data[prefix_record]
                if current_record.channel == prefix_record.channel:
                    # The downloaded repodata takes priority, so we do not overwrite.
                    # We do, however, copy the link information so that the solver (i.e. resolve)
                    # knows this package is installed.
                    link = prefix_record.get("link") or EMPTY_LINK
                    self._data[prefix_record] = PrefixRecord.from_objects(
                        current_record, prefix_record, link=link
                    )
                else:
                    # If the local packages channel information does not agree with
                    # the channel information in the index then they are most
                    # likely referring to different packages.  This can occur if a
                    # multi-channel changes configuration, e.g. defaults with and
                    # without the free channel. In this case we need to fake the
                    # channel data for the existing package.
                    prefix_channel = prefix_record.channel
                    prefix_channel._Channel__canonical_name = prefix_channel.url()
                    del prefix_record._PackageRecord__pkey
                    self._data[prefix_record] = prefix_record
            else:
                # If the package is not in the repodata, use the local data.
                # If the channel is known but the package is not in the index, it
                # is because 1) the channel is unavailable offline, or 2) it no
                # longer contains this package. Either way, we should prefer any
                # other version of the package to this one. On the other hand, if
                # it is in a channel we don't know about, assign it a value just
                # above the priority of all known channels.
                self._data[prefix_record] = prefix_record

    def _supplement_index_dict_with_cache(self) -> None:
        # supplement index with packages from the cache
        for pcrec in self.cache_entries:
            if pcrec in self._data:
                # The downloaded repodata takes priority
                current_record = self._data[pcrec]
                self._data[pcrec] = PackageCacheRecord.from_objects(
                    current_record, pcrec
                )
            else:
                self._data[pcrec] = pcrec

    def _realize(self) -> None:
        self._data = {}
        for subdir_datas in self.channels.values():
            for subdir_data in subdir_datas:
                self._data.update((prec, prec) for prec in subdir_data.iter_records())
        self._supplement_index_dict_with_prefix()
        if self.use_cache:
            self._supplement_index_dict_with_cache()
        self._data.update(self.features)
        if self.use_system:
            self._data.update(self.system_packages)

    def _retrieve_from_channels(self, key: PackageRecord) -> PackageRecord | None:
        for subdir_datas in reversed(self.channels.values()):
            for subdir_data in subdir_datas:
                if key.subdir != subdir_data.channel.subdir:
                    continue
                prec_candidates = list(subdir_data.query(key))
                if not prec_candidates:
                    continue
                if len(prec_candidates) > 1:
                    raise CondaKeyError(
                        key, "More than one matching package found in channels."
                    )
                prec = prec_candidates[0]
                if prec:
                    return prec
        return None

    def _retrieve_all_from_channels(self, key: PackageRecord) -> list[PackageRecord]:
        precs = []
        for subdir_datas in reversed(self.channels.values()):
            for subdir_data in subdir_datas:
                if hasattr(key, "subdir") and key.subdir != subdir_data.channel.subdir:
                    continue
                precs.extend(subdir_data.query(key))
        return precs

    def _update_from_prefix(
        self, key: PackageRecord, prec: PackageRecord | None
    ) -> PackageRecord | None:
        prefix_prec = self.prefix_data.get(key.name, None) if self.prefix_data else None
        if prefix_prec and prefix_prec == prec:
            if prec:
                if prec.channel == prefix_prec.channel:
                    link = prefix_prec.get("link") or EMPTY_LINK
                    prec = PrefixRecord.from_objects(prec, prefix_prec, link=link)
                else:
                    prefix_channel = prefix_prec.channel
                    prefix_channel._Channel__canonical_name = prefix_channel.url()
                    del prefix_prec._PackageRecord__pkey
                    prec = prefix_prec
            else:
                prec = prefix_prec
        return prec

    def _update_from_cache(
        self, key: PackageRecord, prec: PackageRecord | None
    ) -> PackageRecord | None:
        for pcrec in self.cache_entries:
            if pcrec == key:
                if prec:
                    # The downloaded repodata takes priority
                    return PackageCacheRecord.from_objects(prec, pcrec)
                else:
                    return pcrec
        return prec

    def __getitem__(self, key: PackageRecord) -> PackageRecord:
        if not isinstance(key, PackageRecord):
            raise TypeError(
                "Can only retrieve PackageRecord objects. Got {}.", type(key)
            )
        try:
            return self._data[key]
        except AttributeError:
            pass
        if key.name.startswith("__"):
            try:
                return self.system_packages[key]
            except KeyError:
                pass
        if key.name.endswith("@"):
            try:
                return self.features[key]
            except KeyError:
                pass
        prec = self._retrieve_from_channels(key)
        prec = self._update_from_prefix(key, prec)
        if self.use_cache:
            prec = self._update_from_cache(key, prec)
        if prec is None:
            raise KeyError((key,))
        return prec

    def __contains__(self, key: PackageRecord) -> bool:
        try:
            _ = self[key]
            return True
        except (PackagesNotFoundError, KeyError):
            return False

    def __copy__(self) -> Self:
        inst = self.__class__.__new__(self.__class__)
        inst.__dict__.update(self.__dict__)
        if "_data" in self.__dict__:
            inst.__dict__["_data"] = self.__dict__["_data"].copy()
        return inst


class ReducedIndex(Index):
    """Index that contains a subset of available packages.

    Like :class:`Index`, this makes information about packages from the same four
    sources available. However, the contents of the reduced index is limited to
    a subset of packages relevant to a given specification.
    This works by taking into account all packages that match the given specification
    together with their dependencies and their dependencies dependencies, etc.

    Note:
        See :meth:`Index.get_reduced_index` for convenient construction.
    """

    def __init__(
        self,
        specs: Iterable[MatchSpec],
        channels: tuple[str, ...] = (),
        prepend: bool = True,
        platform: str | None = None,
        subdirs: tuple[str, ...] | None = None,
        use_local: bool = False,
        use_cache: bool | None = None,
        prefix: str | os.PathLike[str] | Path | PrefixData | None = None,
        repodata_fn: str | None = context.repodata_fns[-1],
        use_system: bool = False,
    ) -> None:
        """Initialize a new reduced index.

        Args:
          specs: the collection of specifications that span the subset of packages.
          all other args: see :class:`Index`.
        """
        super().__init__(
            channels,
            prepend,
            platform,
            subdirs,
            use_local,
            use_cache,
            prefix,
            repodata_fn,
            use_system,
        )
        self.specs = specs
        self._derive_reduced_index()

    def __repr__(self) -> str:
        channels = ", ".join(self.channels.keys())
        return f"<{self.__class__.__name__}(spec={self.specs}, channels=[{channels}])>"

    def _derive_reduced_index(self) -> None:
        records = IndexedSet()
        collected_names = set()
        collected_track_features = set()
        pending_names = set()
        pending_track_features = set()

        def push_specs(*specs: MatchSpec | str) -> None:
            """
            Add a package name or track feature from a MatchSpec to the pending set.

            :param spec: The MatchSpec to process.
            """
            for spec in map(MatchSpec, specs):
                name = spec.get_raw_value("name")
                if name and name not in collected_names:
                    pending_names.add(name)
                track_features = spec.get_raw_value("track_features")
                if track_features:
                    for ftr_name in track_features:
                        if ftr_name not in collected_track_features:
                            pending_track_features.add(ftr_name)

        def push_records(*records: PackageRecord) -> None:
            """
            Process a package record to collect its dependencies and features.

            :param record: The package record to process.
            """
            for record in records:
                try:
                    combined_depends = record.combined_depends
                except InvalidSpec as e:
                    log.warning(
                        "Skipping %s due to InvalidSpec: %s",
                        record.record_id(),
                        e._kwargs["invalid_spec"],
                    )
                    return
                push_specs(
                    record.name,
                    *combined_depends,
                    *(
                        MatchSpec(track_features=ftr_name)
                        for ftr_name in record.track_features
                    ),
                )

        if self.prefix_data:
            push_records(*self.prefix_data.iter_records())
        push_specs(*self.specs)

        while pending_names or pending_track_features:
            while pending_names:
                name = pending_names.pop()
                collected_names.add(name)
                spec = MatchSpec(name)
                # new_records = SubdirData.query_all(
                #     spec, channels=channels, subdirs=subdirs, repodata_fn=repodata_fn
                # )
                new_records = self._retrieve_all_from_channels(spec)
                push_records(*new_records)
                records.update(new_records)

            while pending_track_features:
                feature_name = pending_track_features.pop()
                collected_track_features.add(feature_name)
                spec = MatchSpec(track_features=feature_name)
                # new_records = SubdirData.query_all(
                #     spec, channels=channels, subdirs=subdirs, repodata_fn=repodata_fn
                # )
                new_records = self._retrieve_all_from_channels(spec)
                push_records(*new_records)
                records.update(new_records)

        self._data = {rec: rec for rec in records}

        self._supplement_index_dict_with_prefix()

        if self.use_cache:
            self._supplement_index_dict_with_cache()

        # add feature records for the solver
        known_features = set()
        for rec in self._data.values():
            known_features.update((*rec.track_features, *rec.features))
        known_features.update(context.track_features)
        for known_feature in known_features:
            rec = PackageRecord.feature(known_feature)
            self._data[rec] = rec

        self._data.update(self.system_packages)


@time_recorder("get_index")
@deprecated("25.3", "25.9", addendum="Use `conda.core.Index` instead.")
def get_index(
    channel_urls: Iterable[str | Channel] = (),
    prepend: bool = True,
    platform: str | None = None,
    use_local: bool = False,
    use_cache: bool = False,
    unknown: bool | None = None,
    prefix: str | None = None,
    repodata_fn: str = context.repodata_fns[-1],
) -> Index:
    """
    Return the index of packages available on the channels

    If prepend=False, only the channels passed in as arguments are used.
    If platform=None, then the current platform is used.
    If prefix is supplied, then the packages installed in that prefix are added.

    :param channel_urls: Channels to include in the index.
    :param prepend: If False, only the channels passed in are used.
    :param platform: Target platform for the index.
    :param use_local: Whether to use local channels.
    :param use_cache: Whether to use cached index information.
    :param unknown: Include unknown packages.
    :param prefix: Path to environment prefix to include in the index.
    :param repodata_fn: Filename of the repodata file.
    :return: A dictionary representing the package index.
    """
    return Index(
        channel_urls,
        prepend,
        platform,
        None,
        use_local,
        unknown,
        prefix,
        repodata_fn,
    )


@deprecated("25.3", "25.9", addendum="Use `conda.core.Index` instead.")
def fetch_index(
    channel_urls: list[str],
    use_cache: bool = False,
    index: dict | None = None,
    repodata_fn: str = context.repodata_fns[-1],
) -> dict:
    """
    Fetch the package index from the specified channels.

    :param channel_urls: A list of channel URLs to fetch the index from.
    :param use_cache: Whether to use the cached index data.
    :param index: An optional pre-existing index to update.
    :param repodata_fn: The name of the repodata file.
    :return: A dictionary representing the fetched or updated package index.
    """
    log.debug("channel_urls=" + repr(channel_urls))
    index = {}
    with ThreadLimitedThreadPoolExecutor() as executor:
        subdir_instantiator = lambda url: SubdirData(
            Channel(url), repodata_fn=repodata_fn
        )
        for f in executor.map(subdir_instantiator, channel_urls):
            index.update((rec, rec) for rec in f.iter_records())
    return index


def dist_str_in_index(index: dict[Any, Any], dist_str: str) -> bool:
    """
    Check if a distribution string matches any package in the index.

    :param index: The package index.
    :param dist_str: The distribution string to match against the index.
    :return: True if there is a match; False otherwise.
    """
    match_spec = MatchSpec.from_dist_str(dist_str)
    return any(match_spec.match(prec) for prec in index.values())


@deprecated("25.3", "25.9", addendum="Use `conda.core.Index.reload` instead.")
def _supplement_index_with_prefix(
    index: Index | dict[Any, Any],
    prefix: str | os.PathLike[str] | Path | PrefixData,
) -> None:
    """
    Supplement the given index with information from the specified environment prefix.

    :param index: The package index to supplement.
    :param prefix: The path to the environment prefix.
    """
    # supplement index with information from prefix/conda-meta
    prefix_data = prefix if isinstance(prefix, PrefixData) else PrefixData(prefix)
    if isinstance(index, Index):
        if index.prefix_data != prefix_data:
            raise OperationNotAllowed(
                "An index can only be supplemented with its own prefix."
            )
        index.reload(prefix=True)
        return

    for prefix_record in prefix_data.iter_records():
        if prefix_record in index:
            current_record = index[prefix_record]
            if current_record.channel == prefix_record.channel:
                # The downloaded repodata takes priority, so we do not overwrite.
                # We do, however, copy the link information so that the solver (i.e. resolve)
                # knows this package is installed.
                link = prefix_record.get("link") or EMPTY_LINK
                index[prefix_record] = PrefixRecord.from_objects(
                    current_record, prefix_record, link=link
                )
            else:
                # If the local packages channel information does not agree with
                # the channel information in the index then they are most
                # likely referring to different packages.  This can occur if a
                # multi-channel changes configuration, e.g. defaults with and
                # without the free channel. In this case we need to fake the
                # channel data for the existing package.
                prefix_channel = prefix_record.channel
                prefix_channel._Channel__canonical_name = prefix_channel.url()
                del prefix_record._PackageRecord__pkey
                index[prefix_record] = prefix_record
        else:
            # If the package is not in the repodata, use the local data.
            # If the channel is known but the package is not in the index, it
            # is because 1) the channel is unavailable offline, or 2) it no
            # longer contains this package. Either way, we should prefer any
            # other version of the package to this one. On the other hand, if
            # it is in a channel we don't know about, assign it a value just
            # above the priority of all known channels.
            index[prefix_record] = prefix_record


@deprecated("25.3", "25.9", addendum="Use `conda.core.Index.reload` instead.")
def _supplement_index_with_cache(index: dict[Any, Any]) -> None:
    """
    Supplement the given index with packages from the cache.

    :param index: The package index to supplement.
    """
    # supplement index with packages from the cache
    for pcrec in PackageCacheData.get_all_extracted_entries():
        if pcrec in index:
            # The downloaded repodata takes priority
            current_record = index[pcrec]
            index[pcrec] = PackageCacheRecord.from_objects(current_record, pcrec)
        else:
            index[pcrec] = pcrec


@deprecated(
    "25.3",
    "25.9",
    addendum="Use `conda.core.models.records.PackageRecord.virtual_package` instead.",
)
def _make_virtual_package(
    name: str, version: str | None = None, build_string: str | None = None
) -> PackageRecord:
    """
    Create a virtual package record.

    :param name: The name of the virtual package.
    :param version: The version of the virtual package, defaults to "0".
    :param build_string: The build string of the virtual package, defaults to "0".
    :return: A PackageRecord representing the virtual package.
    """
    return PackageRecord.virtual_package(name, version, build_string)


@deprecated(
    "25.3",
    "25.9",
    addendum="Use :meth:`~conda.core.Index.reload(features=True)` instead.",
)
def _supplement_index_with_features(
    index: dict[PackageRecord, PackageRecord], features: list[str] = []
) -> None:
    """
    Supplement the given index with virtual feature records.

    :param index: The package index to supplement.
    :param features: A list of feature names to add to the index.
    """
    for feature in chain(context.track_features, features):
        rec = PackageRecord.feature(feature)
        index[rec] = rec


@deprecated("25.3", "25.9", addendum="Use `conda.core.Index.reload` instead.")
def _supplement_index_with_system(index: dict[PackageRecord, PackageRecord]) -> None:
    """
    Loads and populates virtual package records from conda plugins
    and adds them to the provided index, unless there is a naming
    conflict.

    :param index: The package index to supplement.
    """
    if isinstance(index, Index):
        return
    for package in context.plugin_manager.get_virtual_package_records():
        index[package] = package


def get_archspec_name() -> str | None:
    """
    Determine the architecture specification name for the current environment.

    :return: The architecture name if available, otherwise None.
    """
    from ..base.context import _arch_names, non_x86_machines

    target_plat, target_arch = context.subdir.split("-")
    # This has to reverse what Context.subdir is doing
    if target_arch in non_x86_machines:
        machine = target_arch
    elif target_arch == "zos":
        return None
    elif target_arch.isdigit():
        machine = _arch_names[int(target_arch)]
    else:
        return None

    native_subdir = context._native_subdir()

    if native_subdir != context.subdir:
        return machine
    else:
        import archspec.cpu

        return str(archspec.cpu.host())


def calculate_channel_urls(
    channel_urls: tuple[str] = (),
    prepend: bool = True,
    platform: str | None = None,
    use_local: bool = False,
) -> list[str]:
    """
    Calculate the full list of channel URLs to use based on the given parameters.

    :param channel_urls: Initial list of channel URLs.
    :param prepend: Whether to prepend default channels to the list.
    :param platform: The target platform for the channels.
    :param use_local: Whether to include the local channel.
    :return: The calculated list of channel URLs.
    """
    if use_local:
        channel_urls = ["local"] + list(channel_urls)
    if prepend:
        channel_urls += context.channels

    subdirs = (platform, "noarch") if platform is not None else context.subdirs
    return all_channel_urls(channel_urls, subdirs=subdirs)


@deprecated(
    "25.3",
    "25.9",
    addendum="Use `conda.core.ReducedIndex` or `conda.core.Index.get_reduced_index` instead.",
)
def get_reduced_index(
    prefix: str | None,
    channels: list[str],
    subdirs: list[str],
    specs: list[MatchSpec],
    repodata_fn: str,
) -> dict:
    """
    Generate a reduced package index based on the given specifications.

    This function is useful for optimizing the solver by reducing the amount
    of data it needs to consider.

    :param prefix: Path to an environment prefix to include installed packages.
    :param channels: A list of channel names to include in the index.
    :param subdirs: A list of subdirectories to consider for each channel.
    :param specs: A list of MatchSpec objects to filter the packages.
    :param repodata_fn: Filename of the repodata file to use.
    :return: A dictionary representing the reduced package index.
    """

    return ReducedIndex(
        specs,
        channels=channels,
        prepend=False,
        subdirs=subdirs,
        use_local=False,
        use_cache=None,
        prefix=prefix,
        repodata_fn=repodata_fn,
        use_system=True,
    )
