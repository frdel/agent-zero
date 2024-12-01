# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""JLAP interface for repodata."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from ....base.context import context
from ...connection.download import disable_ssl_verify_warning
from ...connection.session import get_session
from .. import (
    CACHE_CONTROL_KEY,
    ETAG_KEY,
    LAST_MODIFIED_KEY,
    URL_KEY,
    RepodataOnDisk,
    RepodataState,
    RepoInterface,
    Response304ContentUnchanged,
    conda_http_errors,
)
from . import fetch

if TYPE_CHECKING:
    from .. import RepodataCache

log = logging.getLogger(__name__)


class JlapRepoInterface(RepoInterface):
    def __init__(
        self,
        url: str,
        repodata_fn: str | None,
        *,
        cache: RepodataCache,
        **kwargs,
    ) -> None:
        log.debug("Using %s", self.__class__.__name__)

        self._cache = cache

        self._url = url
        self._repodata_fn = repodata_fn

        self._log = logging.getLogger(__name__)
        self._stderrlog = logging.getLogger("conda.stderrlog")

    def repodata(self, state: dict | RepodataState) -> str | None:
        """
        Fetch newest repodata if necessary.

        Always writes to ``cache_path_json``.
        """
        self.repodata_parsed(state)
        raise RepodataOnDisk()

    def repodata_parsed(self, state: dict | RepodataState) -> dict | None:
        """
        JLAP has to parse the JSON anyway.

        Use this to avoid a redundant parse when repodata is updated.

        When repodata is not updated, it doesn't matter whether this function or
        the caller reads from a file.
        """
        session = get_session(self._url)

        if not context.ssl_verify:
            disable_ssl_verify_warning()

        repodata_url = f"{self._url}/{self._repodata_fn}"

        # XXX won't modify caller's state dict
        state_ = self._repodata_state_copy(state)

        # at this point, self._cache.state == state == state_

        temp_path = (
            self._cache.cache_dir / f"{self._cache.name}.{os.urandom(2).hex()}.tmp"
        )
        try:
            with conda_http_errors(self._url, self._repodata_fn):
                repodata_json_or_none = fetch.request_url_jlap_state(
                    repodata_url,
                    state_,
                    session=session,
                    cache=self._cache,
                    temp_path=temp_path,
                )

                # update caller's state dict-or-RepodataState. Do this before
                # the self._cache.replace() call which also writes state, then
                # signal not to write state to caller.
                state.update(state_)

                state[URL_KEY] = self._url
                headers = state.get("jlap", {}).get(
                    "headers"
                )  # XXX overwrite headers in jlapper.request_url_jlap_state
                if headers:
                    state[ETAG_KEY] = headers.get("etag")
                    state[LAST_MODIFIED_KEY] = headers.get("last-modified")
                    state[CACHE_CONTROL_KEY] = headers.get("cache-control")

                self._cache.state.update(state)

            if temp_path.exists():
                self._cache.replace(temp_path)
        except fetch.Jlap304NotModified:
            raise Response304ContentUnchanged()
        finally:
            # Clean up the temporary file. In the successful case it raises
            # OSError as self._cache_replace() removed temp_file.
            try:
                temp_path.unlink()
            except OSError:
                pass

        if repodata_json_or_none is None:  # common
            # Indicate that subdir_data mustn't rewrite cache_path_json
            raise RepodataOnDisk()
        else:
            return repodata_json_or_none

    def _repodata_state_copy(self, state: dict | RepodataState):
        return RepodataState(dict=state)


class RepodataStateSkipFormat(RepodataState):
    skip_formats: set[str]

    def __init__(self, *args, skip_formats=set(), **kwargs):
        super().__init__(*args, **kwargs)
        self.skip_formats = set(skip_formats)

    def should_check_format(self, format):
        if format in self.skip_formats:
            return False
        return super().should_check_format(format)


class ZstdRepoInterface(JlapRepoInterface):
    """
    Support repodata.json.zst (if available) without checking .jlap
    """

    def _repodata_state_copy(self, state: dict | RepodataState):
        return RepodataStateSkipFormat(dict=state, skip_formats=["jlap"])
