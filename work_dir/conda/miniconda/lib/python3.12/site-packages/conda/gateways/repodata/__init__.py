# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Repodata interface."""

from __future__ import annotations

import abc
import datetime
import errno
import hashlib
import json
import logging
import os
import pathlib
import re
import time
import warnings
from collections import UserDict
from contextlib import contextmanager
from os.path import dirname
from typing import TYPE_CHECKING

from ... import CondaError
from ...auxlib.logz import stringify
from ...base.constants import CONDA_HOMEPAGE_URL, REPODATA_FN
from ...base.context import context
from ...common.url import join_url, maybe_unquote
from ...core.package_cache_data import PackageCacheData
from ...exceptions import (
    CondaDependencyError,
    CondaHTTPError,
    CondaSSLError,
    NotWritableError,
    ProxyError,
    UnavailableInvalidChannel,
)
from ...models.channel import Channel
from ..connection import (
    ChunkedEncodingError,
    ConnectionError,
    HTTPError,
    InsecureRequestWarning,
    InvalidSchema,
    RequestsProxyError,
    SSLError,
)
from ..connection.session import get_session
from ..disk import mkdir_p_sudo_safe
from ..disk.lock import lock

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any

    from ..connection import Response

log = logging.getLogger(__name__)
stderrlog = logging.getLogger("conda.stderrlog")


# if repodata.json.zst or repodata.jlap were unavailable, check again later.
CHECK_ALTERNATE_FORMAT_INTERVAL = datetime.timedelta(days=7)

# repodata.info/state.json keys to keep up with the CEP
LAST_MODIFIED_KEY = "mod"
ETAG_KEY = "etag"
CACHE_CONTROL_KEY = "cache_control"
URL_KEY = "url"
CACHE_STATE_SUFFIX = ".info.json"

# show some unparseable json in error
ERROR_SNIPPET_LENGTH = 32


class RepodataIsEmpty(UnavailableInvalidChannel):
    """
    Subclass used to determine when empty repodata should be cached, e.g. for a
    channel that doesn't provide current_repodata.json
    """


class RepodataOnDisk(Exception):
    """
    Indicate that RepoInterface.repodata() successfully wrote repodata to disk,
    instead of returning a string.
    """


class RepoInterface(abc.ABC):
    # TODO: Support async operations
    # TODO: Support progress bars
    def repodata(self, state: dict) -> str:
        """
        Given a mutable state dictionary with information about the cache,
        return repodata.json (or current_repodata.json) as a str. This function
        also updates state, which is expected to be saved by the caller.
        """
        ...


class Response304ContentUnchanged(Exception):
    pass


def get_repo_interface() -> type[RepoInterface]:
    if "jlap" in context.experimental:
        try:
            from .jlap.interface import JlapRepoInterface

            return JlapRepoInterface
        except ImportError as e:  # pragma: no cover
            warnings.warn(
                "Could not load the configured jlap repo interface. "
                f"Is the required jsonpatch package installed?  {e}"
            )

    if context.repodata_use_zst:
        try:
            from .jlap.interface import ZstdRepoInterface

            return ZstdRepoInterface
        except ImportError:  # pragma: no cover
            pass

    return CondaRepoInterface


class CondaRepoInterface(RepoInterface):
    """Provides an interface for retrieving repodata data from channels."""

    #: Channel URL
    _url: str

    #: Filename of the repodata file; defaults to value of conda.base.constants.REPODATA_FN
    _repodata_fn: str

    def __init__(self, url: str, repodata_fn: str | None, **kwargs) -> None:
        log.debug("Using CondaRepoInterface")
        self._url = url
        self._repodata_fn = repodata_fn or REPODATA_FN

    def repodata(self, state: RepodataState) -> str | None:
        if not context.ssl_verify:
            warnings.simplefilter("ignore", InsecureRequestWarning)

        session = get_session(self._url)

        headers = {}
        etag = state.etag
        last_modified = state.mod
        if etag:
            headers["If-None-Match"] = str(etag)
        if last_modified:
            headers["If-Modified-Since"] = str(last_modified)
        filename = self._repodata_fn

        url = join_url(self._url, filename)

        with conda_http_errors(self._url, filename):
            timeout = (
                context.remote_connect_timeout_secs,
                context.remote_read_timeout_secs,
            )
            response: Response = session.get(
                url, headers=headers, proxies=session.proxies, timeout=timeout
            )
            if log.isEnabledFor(logging.DEBUG):
                log.debug(stringify(response, content_max_len=256))
            response.raise_for_status()

        if response.status_code == 304:
            # should we save cache-control to state here to put another n
            # seconds on the "make a remote request" clock and/or touch cache
            # mtime
            raise Response304ContentUnchanged()

        json_str = response.text

        # We no longer add these tags to the large `resp.content` json
        saved_fields = {"_url": self._url}
        _add_http_value_to_dict(response, "Etag", saved_fields, "_etag")
        _add_http_value_to_dict(response, "Last-Modified", saved_fields, "_mod")
        _add_http_value_to_dict(
            response, "Cache-Control", saved_fields, "_cache_control"
        )

        state.clear()
        state.update(saved_fields)

        return json_str


def _add_http_value_to_dict(resp, http_key, d, dict_key):
    value = resp.headers.get(http_key)
    if value:
        d[dict_key] = value


@contextmanager
def conda_http_errors(url, repodata_fn):
    """Use in a with: statement to translate requests exceptions to conda ones."""
    try:
        yield
    except RequestsProxyError:
        raise ProxyError()  # see #3962

    except InvalidSchema as e:
        if "SOCKS" in str(e):
            message = """\
Requests has identified that your current working environment is configured
to use a SOCKS proxy, but pysocks is not installed.  To proceed, remove your
proxy configuration, run `conda install pysocks`, and then you can re-enable
your proxy configuration.
"""
            raise CondaDependencyError(message)
        else:
            raise

    except SSLError as e:
        # SSLError: either an invalid certificate or OpenSSL is unavailable
        try:
            import ssl  # noqa: F401
        except ImportError:
            raise CondaSSLError(
                f"""\
OpenSSL appears to be unavailable on this machine. OpenSSL is required to
download and install packages.

Exception: {e}
"""
            )
        else:
            raise CondaSSLError(
                f"""\
Encountered an SSL error. Most likely a certificate verification issue.

Exception: {e}
"""
            )

    except (ConnectionError, HTTPError, ChunkedEncodingError) as e:
        status_code = getattr(e.response, "status_code", None)
        if status_code in (403, 404):
            if not url.endswith("/noarch"):
                log.info(
                    "Unable to retrieve repodata (response: %d) for %s",
                    status_code,
                    url + "/" + repodata_fn,
                )
                raise RepodataIsEmpty(
                    Channel(dirname(url)),
                    status_code,
                    response=e.response,
                )
            else:
                if context.allow_non_channel_urls:
                    stderrlog.warning(
                        "Unable to retrieve repodata (response: %d) for %s",
                        status_code,
                        url + "/" + repodata_fn,
                    )
                    raise RepodataIsEmpty(
                        Channel(dirname(url)),
                        status_code,
                        response=e.response,
                    )
                else:
                    raise UnavailableInvalidChannel(
                        Channel(dirname(url)),
                        status_code,
                        response=e.response,
                    )

        elif status_code == 401:
            channel = Channel(url)
            if channel.token:
                help_message = """\
The token '{}' given for the URL is invalid.

If this token was pulled from anaconda-client, you will need to use
anaconda-client to reauthenticate.

If you supplied this token to conda directly, you will need to adjust your
conda configuration to proceed.

Use `conda config --show` to view your configuration's current state.
Further configuration help can be found at <{}>.
""".format(
                    channel.token,
                    join_url(CONDA_HOMEPAGE_URL, "docs/config.html"),
                )

            elif context.channel_alias.location in url:
                # Note, this will not trigger if the binstar configured url does
                # not match the conda configured one.
                help_message = """\
The remote server has indicated you are using invalid credentials for this channel.

If the remote site is anaconda.org or follows the Anaconda Server API, you
will need to
    (a) remove the invalid token from your system with `anaconda logout`, optionally
        followed by collecting a new token with `anaconda login`, or
    (b) provide conda with a valid token directly.

Further configuration help can be found at <{}>.
""".format(join_url(CONDA_HOMEPAGE_URL, "docs/config.html"))

            else:
                help_message = """\
The credentials you have provided for this URL are invalid.

You will need to modify your conda configuration to proceed.
Use `conda config --show` to view your configuration's current state.
Further configuration help can be found at <{}>.
""".format(join_url(CONDA_HOMEPAGE_URL, "docs/config.html"))

        elif status_code is not None and 500 <= status_code < 600:
            help_message = """\
A remote server error occurred when trying to retrieve this URL.

A 500-type error (e.g. 500, 501, 502, 503, etc.) indicates the server failed to
fulfill a valid request.  The problem may be spurious, and will resolve itself if you
try your request again.  If the problem persists, consider notifying the maintainer
of the remote server.
"""

        else:
            if url.startswith("https://repo.anaconda.com/"):
                help_message = f"""\
An HTTP error occurred when trying to retrieve this URL.
HTTP errors are often intermittent, and a simple retry will get you on your way.

If your current network has https://repo.anaconda.com blocked, please file
a support request with your network engineering team.

{maybe_unquote(repr(url))}
"""

            else:
                help_message = f"""\
An HTTP error occurred when trying to retrieve this URL.
HTTP errors are often intermittent, and a simple retry will get you on your way.
{maybe_unquote(repr(url))}
"""

        raise CondaHTTPError(
            help_message,
            join_url(url, repodata_fn),
            status_code,
            getattr(e.response, "reason", None),
            getattr(e.response, "elapsed", None),
            e.response,
            caused_by=e,
        )


class RepodataState(UserDict):
    """Load/save info file that accompanies cached `repodata.json`."""

    # Accept old keys for new serialization
    _aliased = {
        "_mod": LAST_MODIFIED_KEY,
        "_etag": ETAG_KEY,
        "_cache_control": CACHE_CONTROL_KEY,
        "_url": URL_KEY,
    }

    # Enforce string type on these keys
    _strings = {"mod", "etag", "cache_control", "url"}

    def __init__(
        self,
        cache_path_json: Path | str = "",
        cache_path_state: Path | str = "",
        repodata_fn="",
        dict=None,
    ):
        # dict is a positional-only argument in UserDict.
        super().__init__(dict)
        self.cache_path_json = pathlib.Path(cache_path_json)
        self.cache_path_state = pathlib.Path(cache_path_state)
        # XXX may not be that useful/used compared to the full URL
        self.repodata_fn = repodata_fn

    @property
    def mod(self) -> str:
        """
        Last-Modified header or ""
        """
        return self.get(LAST_MODIFIED_KEY) or ""

    @mod.setter
    def mod(self, value):
        self[LAST_MODIFIED_KEY] = value or ""

    @property
    def etag(self) -> str:
        """
        Etag header or ""
        """
        return self.get(ETAG_KEY) or ""

    @etag.setter
    def etag(self, value):
        self[ETAG_KEY] = value or ""

    @property
    def cache_control(self) -> str:
        """
        Cache-Control header or ""
        """
        return self.get(CACHE_CONTROL_KEY) or ""

    @cache_control.setter
    def cache_control(self, value):
        self[CACHE_CONTROL_KEY] = value or ""

    def has_format(self, format: str) -> tuple[bool, datetime.datetime | None]:
        # "has_zst": {
        #     // UTC RFC3999 timestamp of when we last checked whether the file is available or not
        #     // in this case the `repodata.json.zst` file
        #     // Note: same format as conda TUF spec
        #     "last_checked": "2023-01-08T11:45:44Z",
        #     // false = unavailable, true = available
        #     "value": BOOLEAN
        # },

        key = f"has_{format}"
        if key not in self:
            return (True, None)  # we want to check by default

        try:
            obj = self[key]
            last_checked_str = obj["last_checked"]
            if last_checked_str.endswith("Z"):
                last_checked_str = f"{last_checked_str[:-1]}+00:00"
            last_checked = datetime.datetime.fromisoformat(last_checked_str)
            value = bool(obj["value"])
            return (value, last_checked)
        except (KeyError, ValueError, TypeError) as e:
            log.warning(
                f"error parsing `has_` object from `<cache key>{CACHE_STATE_SUFFIX}`",
                exc_info=e,
            )
            self.pop(key)

        return False, datetime.datetime.now(tz=datetime.timezone.utc)

    def set_has_format(self, format: str, value: bool):
        key = f"has_{format}"
        self[key] = {
            "last_checked": datetime.datetime.now(tz=datetime.timezone.utc).isoformat()[
                : -len("+00:00")
            ]
            + "Z",
            "value": value,
        }

    def clear_has_format(self, format: str):
        """Remove 'has_{format}' instead of setting to False."""
        key = f"has_{format}"
        self.pop(key, None)

    def should_check_format(self, format: str) -> bool:
        """Return True if named format should be attempted."""
        has, when = self.has_format(format)
        return (
            has is True
            or isinstance(when, datetime.datetime)
            and datetime.datetime.now(tz=datetime.timezone.utc) - when
            > CHECK_ALTERNATE_FORMAT_INTERVAL
        )

    def __contains__(self, key: str) -> bool:
        key = self._aliased.get(key, key)
        return super().__contains__(key)

    def __setitem__(self, key: str, item: Any) -> None:
        key = self._aliased.get(key, key)
        if key in self._strings and not isinstance(item, str):
            log.debug('Replaced non-str RepodataState[%s] with ""', key)
            item = ""
        return super().__setitem__(key, item)

    def __getitem__(self, key: str) -> Any:
        key = self._aliased.get(key, key)
        return super().__getitem__(key)


class RepodataCache:
    """
    Handle caching for a single repodata.json + repodata.info.json
    (<hex-string>*.json inside `dir`)

    Avoid race conditions while loading, saving repodata.json and cache state.
    """

    def __init__(self, base, repodata_fn):
        """
        base: directory and filename prefix for cache, e.g. /cache/dir/abc123;
        writes /cache/dir/abc123.json
        """
        cache_path_base = pathlib.Path(base)
        self.cache_dir = cache_path_base.parent
        self.name = cache_path_base.name
        # XXX can we skip repodata_fn or include the full url for debugging
        self.repodata_fn = repodata_fn
        self.state = RepodataState(
            self.cache_path_json, self.cache_path_state, repodata_fn
        )

    @property
    def cache_path_json(self):
        return pathlib.Path(
            self.cache_dir,
            self.name + ("1" if context.use_only_tar_bz2 else "") + ".json",
        )

    @property
    def cache_path_state(self):
        """Out-of-band etag and other state needed by the RepoInterface."""
        return self.cache_path_json.with_suffix(CACHE_STATE_SUFFIX)

    def load(self, *, state_only=False) -> str:
        # read state and repodata.json with locking

        # lock {CACHE_STATE_SUFFIX} file
        # read {CACHE_STATES_SUFFIX} file
        # read repodata.json
        # check stat, if wrong clear cache information

        with self.lock("r+") as state_file:
            # cannot use pathlib.read_text / write_text on any locked file, as
            # it will release the lock early
            state = json.loads(state_file.read())

            # json and state files should match. must read json before checking
            # stat (if json_data is to be trusted)
            if state_only:
                json_data = ""
            else:
                json_data = self.cache_path_json.read_text()

            json_stat = self.cache_path_json.stat()
            if not (
                state.get("mtime_ns") == json_stat.st_mtime_ns
                and state.get("size") == json_stat.st_size
            ):
                # clear mod, etag, cache_control to encourage re-download
                state.update(
                    {
                        ETAG_KEY: "",
                        LAST_MODIFIED_KEY: "",
                        CACHE_CONTROL_KEY: "",
                        "size": 0,
                    }
                )
            self.state.clear()
            self.state.update(
                state
            )  # will aliased _mod, _etag (not cleared above) pass through as mod, etag?

        return json_data

        # check repodata.json stat(); mtime_ns must equal value in
        # {CACHE_STATE_SUFFIX} file, or it is stale.
        # read repodata.json
        # check repodata.json stat() again: st_size, st_mtime_ns must be equal

        # repodata.json is okay - use it somewhere

        # repodata.json is not okay - maybe use it, but don't allow cache updates

        # unlock {CACHE_STATE_SUFFIX} file

        # also, add refresh_ns instead of touching repodata.json file

    def load_state(self):
        """
        Update self.state without reading repodata.json.

        Return self.state.
        """
        try:
            self.load(state_only=True)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            if isinstance(e, json.JSONDecodeError):
                log.warning(f"{e.__class__.__name__} loading {self.cache_path_state}")
            self.state.clear()
        return self.state

    def save(self, data: str):
        """Write data to <repodata>.json cache path, synchronize state."""
        temp_path = self.cache_dir / f"{self.name}.{os.urandom(2).hex()}.tmp"

        try:
            with temp_path.open("x") as temp:  # exclusive mode, error if exists
                temp.write(data)

            return self.replace(temp_path)

        finally:
            try:
                temp_path.unlink()
            except OSError:
                pass

    def replace(self, temp_path: Path):
        """
        Rename path onto <repodata>.json path, synchronize state.

        Relies on path's mtime not changing on move. `temp_path` should be
        adjacent to `self.cache_path_json` to be on the same filesystem.
        """
        with self.lock() as state_file:
            # "a+" creates the file if necessary, does not trunctate file.
            state_file.seek(0)
            state_file.truncate()
            stat = temp_path.stat()
            # XXX make sure self.state has the correct etag, etc. for temp_path.
            # UserDict has inscrutable typing, which we ignore
            self.state["mtime_ns"] = stat.st_mtime_ns  # type: ignore
            self.state["size"] = stat.st_size  # type: ignore
            self.state["refresh_ns"] = time.time_ns()  # type: ignore
            try:
                temp_path.rename(self.cache_path_json)
            except FileExistsError:  # Windows
                self.cache_path_json.unlink()
                temp_path.rename(self.cache_path_json)
            state_file.write(json.dumps(dict(self.state), indent=2))

    def refresh(self, refresh_ns=0):
        """
        Update access time in cache info file to indicate a HTTP 304 Not Modified response.
        """
        # Note this is not thread-safe.
        with self.lock() as state_file:
            # "a+" creates the file if necessary, does not trunctate file.
            state_file.seek(0)
            state_file.truncate()
            self.state["refresh_ns"] = refresh_ns or time.time_ns()
            state_file.write(json.dumps(dict(self.state), indent=2))

    @contextmanager
    def lock(self, mode="a+"):
        """
        Lock .info.json file. Hold lock while modifying related files.

        mode: "a+" then seek(0) to write/create; "r+" to read.
        """
        with self.cache_path_state.open(mode) as state_file, lock(state_file):
            yield state_file

    def stale(self):
        """
        Compare state refresh_ns against cache control header and
        context.local_repodata_ttl.
        """
        if context.local_repodata_ttl > 1:
            max_age = context.local_repodata_ttl
        elif context.local_repodata_ttl == 1:
            max_age = get_cache_control_max_age(self.state.cache_control)
        else:
            max_age = 0

        max_age *= 10**9  # nanoseconds
        now = time.time_ns()
        refresh = self.state.get("refresh_ns", 0)
        return (now - refresh) > max_age

    def timeout(self):
        """
        Return number of seconds until cache times out (<= 0 if already timed
        out).
        """
        if context.local_repodata_ttl > 1:
            max_age = context.local_repodata_ttl
        elif context.local_repodata_ttl == 1:
            max_age = get_cache_control_max_age(self.state.cache_control)
        else:
            max_age = 0

        max_age *= 10**9  # nanoseconds
        now = time.time_ns()
        refresh = self.state.get("refresh_ns", 0)
        return ((now - refresh) + max_age) / 1e9


class RepodataFetch:
    """
    Combine RepodataCache and RepoInterface to provide subdir_data.SubdirData()
    with what it needs.

    Provide a variety of formats since some ``RepoInterface`` have to
    ``json.loads(...)`` anyway, and some clients don't need the Python data
    structure at all.
    """

    cache_path_base: Path
    channel: Channel
    repodata_fn: str
    url_w_subdir: str
    url_w_credentials: str
    repo_interface_cls: Any

    def __init__(
        self,
        cache_path_base: Path,
        channel: Channel,
        repodata_fn: str,
        *,
        repo_interface_cls,
    ):
        self.cache_path_base = cache_path_base
        self.channel = channel
        self.repodata_fn = repodata_fn

        self.url_w_subdir = self.channel.url(with_credentials=False) or ""
        self.url_w_credentials = self.channel.url(with_credentials=True) or ""

        self.repo_interface_cls = repo_interface_cls

    def fetch_latest_parsed(self) -> tuple[dict, RepodataState]:
        """
        Retrieve parsed latest or latest-cached repodata as a dict; update
        cache.

        :return: (repodata contents, state including cache headers)
        """
        parsed, state = self.fetch_latest()
        if isinstance(parsed, str):
            try:
                return json.loads(parsed), state
            except json.JSONDecodeError as e:
                e.args = (
                    f'{e.args[0]}; got "{parsed[:ERROR_SNIPPET_LENGTH]}"',
                    *e.args[1:],
                )
                raise
        else:
            return parsed, state

    def fetch_latest_path(self) -> tuple[Path, RepodataState]:
        """
        Retrieve latest or latest-cached repodata; update cache.

        :return: (pathlib.Path to uncompressed repodata contents, RepodataState)
        """
        _, state = self.fetch_latest()
        return self.cache_path_json, state

    @property
    def url_w_repodata_fn(self):
        return self.url_w_subdir + "/" + self.repodata_fn

    @property
    def cache_path_json(self):
        return self.repo_cache.cache_path_json

    @property
    def cache_path_state(self):
        """
        Out-of-band etag and other state needed by the RepoInterface.
        """
        return self.repo_cache.cache_path_state

    @property
    def repo_cache(self) -> RepodataCache:
        return RepodataCache(self.cache_path_base, self.repodata_fn)

    @property
    def _repo(self) -> RepoInterface:
        """
        Changes as we mutate self.repodata_fn.
        """
        return self.repo_interface_cls(
            self.url_w_credentials,
            repodata_fn=self.repodata_fn,
            cache=self.repo_cache,
        )

    def fetch_latest(self) -> tuple[dict | str, RepodataState]:
        """
        Return up-to-date repodata and cache information. Fetch repodata from
        remote if cache has expired; return cached data if cache has not
        expired; return stale cached data or dummy data if in offline mode.
        """
        cache = self.repo_cache
        cache.load_state()

        # XXX cache_path_json and cache_path_state must exist; just try loading
        # it and fall back to this on error?
        if not cache.cache_path_json.exists():
            log.debug(
                "No local cache found for %s at %s",
                self.url_w_repodata_fn,
                self.cache_path_json,
            )
            if context.use_index_cache or (
                context.offline and not self.url_w_subdir.startswith("file://")
            ):
                log.debug(
                    "Using cached data for %s at %s forced. Returning empty repodata.",
                    self.url_w_repodata_fn,
                    self.cache_path_json,
                )
                return (
                    {},
                    cache.state,
                )  # XXX basic properties like info, packages, packages.conda? instead of {}?

        else:
            if context.use_index_cache:
                log.debug(
                    "Using cached repodata for %s at %s because use_cache=True",
                    self.url_w_repodata_fn,
                    self.cache_path_json,
                )

                _internal_state = self.read_cache()
                return _internal_state

            stale = cache.stale()
            if (not stale or context.offline) and not self.url_w_subdir.startswith(
                "file://"
            ):
                timeout = cache.timeout()
                log.debug(
                    "Using cached repodata for %s at %s. Timeout in %d sec",
                    self.url_w_repodata_fn,
                    self.cache_path_json,
                    timeout,
                )
                _internal_state = self.read_cache()
                return _internal_state

            log.debug(
                "Local cache timed out for %s at %s",
                self.url_w_repodata_fn,
                self.cache_path_json,
            )

        try:
            try:
                repo = self._repo
                if hasattr(repo, "repodata_parsed"):
                    raw_repodata = repo.repodata_parsed(cache.state)  # type: ignore
                else:
                    raw_repodata = repo.repodata(cache.state)  # type: ignore
            except RepodataIsEmpty:
                if self.repodata_fn != REPODATA_FN:
                    raise  # is UnavailableInvalidChannel subclass
                # the surrounding try/except/else will cache "{}"
                raw_repodata = None
            except RepodataOnDisk:
                # used as a sentinel, not the raised exception object
                raw_repodata = RepodataOnDisk

        except Response304ContentUnchanged:
            log.debug(
                "304 NOT MODIFIED for '%s'. Updating mtime and loading from disk",
                self.url_w_repodata_fn,
            )
            cache.refresh()
            _internal_state = self.read_cache()
            return _internal_state
        else:
            try:
                if raw_repodata is RepodataOnDisk:
                    # this is handled very similar to a 304. Can the cases be merged?
                    # we may need to read_bytes() and compare a hash to the state, instead.
                    # XXX use self._repo_cache.load() or replace after passing temp path to jlap
                    raw_repodata = self.cache_path_json.read_text()
                    stat = self.cache_path_json.stat()
                    cache.state["size"] = stat.st_size  # type: ignore
                    mtime_ns = stat.st_mtime_ns
                    cache.state["mtime_ns"] = mtime_ns  # type: ignore
                    cache.refresh()
                elif isinstance(raw_repodata, dict):
                    # repo implementation cached it, and parsed it
                    # XXX check size upstream for locking reasons
                    stat = self.cache_path_json.stat()
                    cache.state["size"] = stat.st_size
                    mtime_ns = stat.st_mtime_ns
                    cache.state["mtime_ns"] = mtime_ns  # type: ignore
                    cache.refresh()
                elif isinstance(raw_repodata, (str, type(None))):
                    # Can we pass this information in state or with a sentinel/special exception?
                    if raw_repodata is None:
                        raw_repodata = "{}"
                    cache.save(raw_repodata)
                else:  # pragma: no cover
                    # it can be a dict?
                    assert False, f"Unreachable {raw_repodata}"
            except OSError as e:
                if e.errno in (errno.EACCES, errno.EPERM, errno.EROFS):
                    raise NotWritableError(self.cache_path_json, e.errno, caused_by=e)
                else:
                    raise

            return raw_repodata, cache.state

    def read_cache(self) -> tuple[str, RepodataState]:
        """
        Read repodata from disk, without trying to fetch a fresh version.
        """
        # pickled data is bad or doesn't exist; load cached json
        log.debug(
            "Loading raw json for %s at %s",
            self.url_w_repodata_fn,
            self.cache_path_json,
        )

        cache = self.repo_cache

        try:
            raw_repodata_str = cache.load()
            return raw_repodata_str, cache.state
        except ValueError as e:
            # OSError (locked) may happen here
            # ValueError: Expecting object: line 11750 column 6 (char 303397)
            log.debug("Error for cache path: '%s'\n%r", self.cache_path_json, e)
            message = """An error occurred when loading cached repodata.  Executing
`conda clean --index-cache` will remove cached repodata files
so they can be downloaded again."""
            raise CondaError(message)


try:
    hashlib.md5(b"", usedforsecurity=False)

    def _md5_not_for_security(data):
        return hashlib.md5(data, usedforsecurity=False)

except TypeError:  # pragma: no cover
    # Python < 3.9
    def _md5_not_for_security(data):
        return hashlib.md5(data)


def cache_fn_url(url, repodata_fn=REPODATA_FN):
    # url must be right-padded with '/' to not invalidate any existing caches
    if not url.endswith("/"):
        url += "/"
    # add the repodata_fn in for uniqueness, but keep it off for standard stuff.
    #    It would be more sane to add it for everything, but old programs (Navigator)
    #    are looking for the cache under keys without this.
    if repodata_fn != REPODATA_FN:
        url += repodata_fn

    md5 = _md5_not_for_security(url.encode("utf-8"))
    return f"{md5.hexdigest()[:8]}.json"


def get_cache_control_max_age(cache_control_value: str | None):
    cache_control_value = cache_control_value or ""
    max_age = re.search(r"max-age=(\d+)", cache_control_value)
    return int(max_age.groups()[0]) if max_age else 0


def create_cache_dir():
    cache_dir = os.path.join(PackageCacheData.first_writable().pkgs_dir, "cache")
    mkdir_p_sudo_safe(cache_dir)
    return cache_dir
