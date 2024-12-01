# Copyright (C) 2022 Anaconda, Inc
# Copyright (C) 2023 conda
# SPDX-License-Identifier: BSD-3-Clause
"""
This module provides a convenient interface between `libmamba.Solver`
and conda's `PrefixData`. In other words, it allows to expose channels
loaded in `conda` to the `libmamba` machinery without using the
`libmamba` networking stack.

Internally, the `libmamba`'s index is made of:

- A 'Pool' object, exposed to libsolv.
- The pool is made of `Repo` objects.
- Each repo corresponds to a repodata.json file.
- Each repodata comes from a channel+subdir combination.

Some notes about channels
-------------------------

In a way, conda channels are an abstraction over a collection of
channel subdirs. For example, when the user wants 'conda-forge', it
actually means 'repodata.json' files from the configured platform subdir
and 'noarch'. Some channels are actually 'MultiChannel', which provide
a collection of channels. The most common example is 'defaults', which
includes 'main', 'r' and 'msys2'.

So, for conda-forge on Linux amd64 we get:

- https://conda.anaconda.org/conda-forge/linux-64
- https://conda.anaconda.org/conda-forge/noarch

For defaults on macOS with Apple Silicon (M1 and friends):

- https://repo.anaconda.org/main/osx-arm64
- https://repo.anaconda.org/main/noarch
- https://repo.anaconda.org/r/osx-arm64
- https://repo.anaconda.org/r/noarch
- https://repo.anaconda.org/msys2/osx-arm64
- https://repo.anaconda.org/msys2/noarch

However, users will just say 'defaults' or 'conda-forge', for convenience.
This means that we need to deal with several formats of channel information,
which ultimately lead to a collection of subdir-specific URLs:

- Channel names from the CLI or configuration files / env-vars
- Channel URLs if names are not available (channel not served in anaconda.org)
- conda.models.channel.Channel objects

Their origins can be:

- Specified by the user on the command-line (-c arguments)
- Specified by the configuration files (.condarc) or environment vars (context object)
- Added from channel-specific MatchSpec (e.g. `conda-forge::python`)
- Added from installed packages in target environment (e.g. a package that was installed
  from a non-default channel remembers where it comes from)

Also note that a channel URL might have authentication in the form:

- https://user:password@server.com/channel
- https://server.com/t/your_token_goes_here/channel

Finally, a channel can be mounted in a local directory and referred to via
a regular path, or a file:// URL, with or without normalization on Windows.

The approach
------------
We pass the subdir-specific, authenticated URLs to conda's 'SubdirData.repo_patch',
which download the JSON files but do not process them to PackageRecords.
Once the cache has been populated, we can instantiate 'libmamba.Repo' objects directly.
We maintain a map of subdir-specific URLs to `conda.model.channel.Channel`
and `libmamba.Repo` objects.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from functools import lru_cache, partial
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Iterable

import libmambapy as api
from conda import __version__ as conda_version
from conda.base.constants import REPODATA_FN
from conda.base.context import context, reset_context
from conda.common.io import DummyExecutor, ThreadLimitedThreadPoolExecutor, env_var
from conda.common.serialize import json_dump, json_load
from conda.common.url import percent_decode, remove_auth, split_anaconda_token
from conda.core.package_cache_data import PackageCacheData
from conda.core.subdir_data import SubdirData
from conda.models.channel import Channel
from conda.models.match_spec import MatchSpec
from conda.models.records import PackageRecord
from conda.models.version import VersionOrder

from .mamba_utils import set_channel_priorities
from .state import IndexHelper
from .utils import escape_channel_url

log = logging.getLogger(f"conda.{__name__}")


@dataclass(frozen=True)
class _ChannelRepoInfo:
    "A dataclass mapping conda Channels, libmamba Repos and URLs"
    channel: Channel
    repo: api.Repo
    full_url: str
    noauth_url: str


class LibMambaIndexHelper(IndexHelper):
    def __init__(
        self,
        installed_records: Iterable[PackageRecord] = (),
        channels: Iterable[Channel | str] | None = None,
        subdirs: Iterable[str] | None = None,
        repodata_fn: str = REPODATA_FN,
        query_format=api.QueryFormat.JSON,
        load_pkgs_cache: bool = False,
    ):
        self._channels = context.channels if channels is None else channels
        self._subdirs = context.subdirs if subdirs is None else subdirs
        self._repodata_fn = repodata_fn

        self._repos = []
        self._pool = api.Pool()

        installed_repo = self._load_installed(installed_records)
        self._repos.append(installed_repo)

        if load_pkgs_cache:
            self._repos.extend(self._load_pkgs_cache())

        self._index = self._load_channels()
        self._repos += [info.repo for info in self._index.values()]

        self._query = api.Query(self._pool)
        self._format = query_format

    def get_info(self, key: str) -> _ChannelRepoInfo:
        orig_key = key
        if not key.startswith("file://"):
            # The conda functions (specifically remove_auth) assume the input
            # is a url; a file uri on windows with a drive letter messes them up.
            # For the rest, we remove all forms of authentication
            key = split_anaconda_token(remove_auth(key))[0]
        try:
            return self._index[key]
        except KeyError as exc:
            # some libmamba versions return encoded URLs
            try:
                return self._index[percent_decode(key)]
            except KeyError:
                pass  # raise original error below
            raise KeyError(
                f"Channel info for {orig_key} ({key}) not found. "
                f"Available keys: {list(self._index)}"
            ) from exc

    def reload_local_channels(self):
        """
        Reload a channel that was previously loaded from a local directory.
        """
        for noauth_url, info in self._index.items():
            if noauth_url.startswith("file://") or info.channel.scheme == "file":
                url, json_path = self._fetch_channel(info.full_url)
                repo_position = self._repos.index(info.repo)
                info.repo.clear(True)
                new = self._json_path_to_repo_info(url, json_path, try_solv=False)
                self._repos[repo_position] = new.repo
                self._index[noauth_url] = new
        set_channel_priorities(self._index)

    def _repo_from_records(
        self, pool: api.Pool, repo_name: str, records: Iterable[PackageRecord] = ()
    ) -> api.Repo:
        """
        Build a libmamba 'Repo' object from conda 'PackageRecord' objects.

        This is done by rebuilding a repodata.json-like dictionary, which is
        then exported to a temporary file that will be loaded with 'libmambapy.Repo'.
        """
        exported = {"packages": {}, "packages.conda": {}}
        additional_infos = {}
        for record in records:
            record_data = dict(record.dump())
            # These fields are expected by libmamba, but they don't always appear
            # in the record.dump() dict (e.g. exporting from S3 channels)
            # ref: https://github.com/mamba-org/mamba/blob/ad46f318b/libmamba/src/core/package_info.cpp#L276-L318  # noqa
            for field in (
                "sha256",
                "track_features",
                "license",
                "size",
                "url",
                "noarch",
                "platform",
                "timestamp",
            ):
                if field in record_data:
                    continue  # do not overwrite
                value = getattr(record, field, None)
                if value is not None:
                    if field == "timestamp" and value:
                        value = int(value * 1000)  # from s to ms
                    record_data[field] = value
            if record.fn.endswith(".conda"):
                exported["packages.conda"][record.fn] = record_data
            else:
                exported["packages"][record.fn] = record_data

            # extra info for libmamba
            info = api.ExtraPkgInfo()
            if record.noarch:
                info.noarch = record.noarch.value
            if record.channel and record.channel.subdir_url:
                info.repo_url = record.channel.subdir_url
            additional_infos[record.fn] = info

        with NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            f.write(json_dump(exported))

        try:
            repo = api.Repo(pool, repo_name, f.name, "")
            repo.add_extra_pkg_info(additional_infos)
            return repo
        finally:
            os.unlink(f.name)

    def _fetch_channel(self, url: str) -> tuple[str, os.PathLike]:
        channel = Channel.from_url(url)
        if not channel.subdir:
            raise ValueError(f"Channel URLs must specify a subdir! Provided: {url}")

        if "PYTEST_CURRENT_TEST" in os.environ:
            # Workaround some testing issues - TODO: REMOVE
            # Fix conda.testing.helpers._patch_for_local_exports by removing last line
            for key, cached in list(SubdirData._cache_.items()):
                if not isinstance(key, tuple):
                    continue  # should not happen, but avoid IndexError just in case
                if key[:2] == (url, self._repodata_fn) and cached._mtime == float("inf"):
                    del SubdirData._cache_[key]
            # /Workaround

        log.debug("Fetching %s with SubdirData.repo_fetch", channel)
        subdir_data = SubdirData(channel, repodata_fn=self._repodata_fn)
        if context.offline or context.use_index_cache:
            # This might not exist (yet, anymore), but that's ok because we'll check
            # for existence later and safely ignore if needed
            json_path = subdir_data.cache_path_json
        else:
            json_path, _ = subdir_data.repo_fetch.fetch_latest_path()

        return url, json_path

    def _json_path_to_repo_info(
        self, url: str, json_path: str, try_solv: bool = True
    ) -> _ChannelRepoInfo | None:
        channel = Channel.from_url(url)
        noauth_url = channel.urls(with_credentials=False, subdirs=(channel.subdir,))[0]
        json_path = Path(json_path)
        try:
            json_stat = json_path.stat()
        except OSError as exc:
            log.debug("Failed to stat %s", json_path, exc_info=exc)
            json_stat = None
        if try_solv:
            try:
                solv_path = json_path.parent / f"{json_path.stem}.solv"
                solv_stat = solv_path.stat()
            except OSError as exc:
                log.debug("Failed to stat %s", solv_path, exc_info=exc)
                solv_stat = None
        else:
            solv_path = None
            solv_stat = None

        if solv_stat is None and json_stat is None:
            log.warning(
                "No repodata found for channel %s. Solve will fail.", channel.canonical_name
            )
            return
        if solv_stat is None:
            path_to_use = json_path
        elif json_stat is None:
            path_to_use = solv_path  # better than nothing
        elif json_stat.st_mtime <= solv_stat.st_mtime:
            # use solv file if it's newer than the json file
            path_to_use = solv_path
        else:
            path_to_use = json_path

        repo = api.Repo(self._pool, noauth_url, str(path_to_use), escape_channel_url(noauth_url))
        return _ChannelRepoInfo(
            repo=repo,
            channel=channel,
            full_url=url,
            noauth_url=noauth_url,
        )

    def _load_channels(self) -> dict[str, _ChannelRepoInfo]:
        # 1. Obtain and deduplicate URLs from channels
        urls = []
        seen_noauth = set()
        for _c in self._channels:
            # When .platform is defined, .urls() will ignore subdirs kw. Remove!
            c = Channel(**{k: v for k, v in Channel(_c).dump().items() if k != "platform"})
            noauth_urls = c.urls(with_credentials=False, subdirs=self._subdirs)
            if seen_noauth.issuperset(noauth_urls):
                continue
            auth_urls = c.urls(with_credentials=True, subdirs=self._subdirs)
            if noauth_urls != auth_urls:  # authed channel always takes precedence
                urls += auth_urls
                seen_noauth.update(noauth_urls)
                continue
            # at this point, we are handling an unauthed channel; in some edge cases,
            # an auth'd variant of the same channel might already be present in `urls`.
            # we only add them if we haven't seen them yet
            for url in noauth_urls:
                if url not in seen_noauth:
                    urls.append(url)
                    seen_noauth.add(url)

        urls = tuple(dict.fromkeys(urls))  # de-duplicate

        # 2. Fetch URLs (if needed)
        Executor = (
            DummyExecutor
            if context.debug or context.repodata_threads == 1
            else partial(ThreadLimitedThreadPoolExecutor, max_workers=context.repodata_threads)
        )
        with Executor() as executor:
            jsons = {url: str(path) for (url, path) in executor.map(self._fetch_channel, urls)}

        # 3. Create repos in same order as `urls`
        index = {}
        for url in urls:
            info = self._json_path_to_repo_info(url, jsons[url])
            if info is not None:
                index[info.noauth_url] = info

        # 4. Configure priorities
        set_channel_priorities(index)

        return index

    def _load_pkgs_cache(self, pkgs_dirs=None) -> Iterable[api.Repo]:
        if pkgs_dirs is None:
            pkgs_dirs = context.pkgs_dirs
        repos = []
        for path in pkgs_dirs:
            package_cache_data = PackageCacheData(path)
            package_cache_data.load()
            repo = self._repo_from_records(self._pool, path, package_cache_data.values())
            repos.append(repo)
        return repos

    def _load_installed(self, records: Iterable[PackageRecord]) -> api.Repo:
        repo = self._repo_from_records(self._pool, "installed", records)
        repo.set_installed()
        return repo

    def whoneeds(
        self, query: str | MatchSpec, records=True
    ) -> Iterable[PackageRecord] | dict | str:
        result_str = self._query.whoneeds(self._prepare_query(query), self._format)
        if self._format == api.QueryFormat.JSON:
            return self._process_query_result(result_str, records=records)
        return result_str

    def depends(
        self, query: str | MatchSpec, records=True
    ) -> Iterable[PackageRecord] | dict | str:
        result_str = self._query.depends(self._prepare_query(query), self._format)
        if self._format == api.QueryFormat.JSON:
            return self._process_query_result(result_str, records=records)
        return result_str

    def search(self, query: str | MatchSpec, records=True) -> Iterable[PackageRecord] | dict | str:
        result_str = self._query.find(self._prepare_query(query), self._format)
        if self._format == api.QueryFormat.JSON:
            return self._process_query_result(result_str, records=records)
        return result_str

    def explicit_pool(self, specs: Iterable[MatchSpec]) -> Iterable[str]:
        """
        Returns all the package names that (might) depend on the passed specs
        """
        explicit_pool = set()
        for spec in specs:
            pkg_records = self.depends(spec.dist_str())
            for record in pkg_records:
                explicit_pool.add(record.name)
        return tuple(explicit_pool)

    def _prepare_query(self, query: str | MatchSpec) -> str:
        if isinstance(query, str):
            if "[" not in query:
                return query
            query = MatchSpec(query)
        # libmambapy.Query only supports some matchspec syntax
        # https://github.com/conda/conda-libmamba-solver/issues/327
        # NOTE: Channel specs are currently ignored by libmambapy.Query searches
        # if query.get_raw_value("channel"):
        #     result = f"{query.get_raw_value('channel')}::{query.name}"
        #     if query.version and query.get_raw_value("version").startswith((">", "<", "!", "=")):
        #         result += query.get_raw_value("version")
        #     elif query.version:
        #         result += f"={query.get_raw_value('version')}"
        #     else:
        #         result += "=*"
        #     if query.get_raw_value("build"):
        #         result += f"={query.get_raw_value('build')}"
        #     return result
        if not query.get_raw_value("version"):
            query = MatchSpec(query, version="*")
        return query.conda_build_form()

    def _process_query_result(
        self,
        result_str,
        records=True,
    ) -> Iterable[PackageRecord] | dict:
        result = json_load(result_str)
        if result.get("result", {}).get("status") != "OK":
            query_type = result.get("query", {}).get("type", "<Unknown>")
            query = result.get("query", {}).get("query", "<Unknown>")
            error_msg = result.get("result", {}).get("msg", f"Faulty response: {result_str}")
            raise ValueError(f"{query_type} query '{query}' failed: {error_msg}")
        if records:
            pkg_records = []
            for pkg in result["result"]["pkgs"]:
                record = PackageRecord(**pkg)
                pkg_records.append(record)
            return pkg_records
        return result


@lru_cache(maxsize=None)
class _LibMambaIndexForCondaBuild(LibMambaIndexHelper):
    """
    See https://github.com/conda/conda-libmamba-solver/issues/386

    conda-build needs to operate offline so the index doesn't get updated
    accidentally during long build phases. However, this is only guaranteed
    to work if https://github.com/conda/conda/pull/13357 is applied. Otherwise
    the condarc configuration might be ignored, resulting in bad index configuration
    and missing packages anyway.
    """

    def __init__(self, *args, **kwargs):
        if VersionOrder(conda_version) <= VersionOrder("23.10.0"):
            log.warning(
                "conda-build requires conda >=23.11.0 for offline index support. "
                "Falling back to online index. This might result in KeyError messages, "
                "specially if the remote repodata is updated during the build phase. "
                "See https://github.com/conda/conda-libmamba-solver/issues/386."
            )
            super().__init__(*args, **kwargs)
        else:
            with env_var("CONDA_OFFLINE", "true", callback=reset_context):
                super().__init__(*args, **kwargs)
