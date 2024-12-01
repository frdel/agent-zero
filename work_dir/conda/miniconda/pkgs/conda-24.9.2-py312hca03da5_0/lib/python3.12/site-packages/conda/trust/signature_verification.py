# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Interface between conda-content-trust and conda."""

from __future__ import annotations

import json
import os
import re
import warnings
from functools import lru_cache
from logging import getLogger
from pathlib import Path

try:
    from conda_content_trust.authentication import verify_delegation, verify_root
    from conda_content_trust.common import (
        SignatureError,
        load_metadata_from_file,
        write_metadata_to_file,
    )
    from conda_content_trust.signing import wrap_as_signable
except ImportError:
    # _SignatureVerification.enabled handles the rest of this state
    class SignatureError(Exception):
        pass


from typing import TYPE_CHECKING

from ..base.constants import CONDA_PACKAGE_EXTENSION_V1, CONDA_PACKAGE_EXTENSION_V2
from ..base.context import context
from ..common.url import join_url
from ..core.subdir_data import SubdirData
from ..gateways.connection import HTTPError, InsecureRequestWarning
from ..gateways.connection.session import get_session
from .constants import INITIAL_TRUST_ROOT, KEY_MGR_FILE

if TYPE_CHECKING:
    from ..models.records import PackageRecord

log = getLogger(__name__)


RE_ROOT_METADATA = re.compile(r"(?P<number>\d+)\.root\.json")


class _SignatureVerification:
    # FUTURE: Python 3.8+, replace with functools.cached_property
    @property
    @lru_cache(maxsize=None)
    def enabled(self) -> bool:
        # safety checks must be enabled
        if not context.extra_safety_checks:
            return False

        # signing url must be defined
        if not context.signing_metadata_url_base:
            log.warning(
                "metadata signature verification requested, "
                "but no metadata URL base has not been specified."
            )
            return False

        # conda_content_trust must be installed
        try:
            import conda_content_trust  # noqa: F401
        except ImportError:
            log.warning(
                "metadata signature verification requested, "
                "but `conda-content-trust` is not installed."
            )
            return False

        # ensure artifact verification directory exists
        Path(context.av_data_dir).mkdir(parents=True, exist_ok=True)

        # ensure the trusted_root exists
        if self.trusted_root is None:
            log.warning(
                "could not find trusted_root data for metadata signature verification"
            )
            return False

        # ensure the key_mgr exists
        if self.key_mgr is None:
            log.warning(
                "could not find key_mgr data for metadata signature verification"
            )
            return False

        # signature verification is enabled
        return True

    # FUTURE: Python 3.8+, replace with functools.cached_property
    @property
    @lru_cache(maxsize=None)
    def trusted_root(self) -> dict:
        # TODO: formalize paths for `*.root.json` and `key_mgr.json` on server-side
        trusted: dict | None = None

        # Load latest trust root metadata from filesystem
        try:
            paths = {
                int(m.group("number")): entry
                for entry in os.scandir(context.av_data_dir)
                if (m := RE_ROOT_METADATA.match(entry.name))
            }
        except (FileNotFoundError, NotADirectoryError, PermissionError):
            # FileNotFoundError: context.av_data_dir does not exist
            # NotADirectoryError: context.av_data_dir is not a directory
            # PermsissionError: context.av_data_dir is not readable
            pass
        else:
            for _, entry in sorted(paths.items(), reverse=True):
                log.info(f"Loading root metadata from {entry}.")
                try:
                    trusted = load_metadata_from_file(entry)
                except (IsADirectoryError, FileNotFoundError, PermissionError):
                    # IsADirectoryError: entry is not a file
                    # FileNotFoundError: entry does not exist
                    # PermsissionError: entry is not readable
                    continue
                else:
                    break

        # Fallback to default root metadata if unable to fetch any
        if not trusted:
            log.debug(
                f"No root metadata in {context.av_data_dir}. "
                "Using built-in root metadata."
            )
            trusted = INITIAL_TRUST_ROOT

        # Refresh trust root metadata
        while True:
            # TODO: caching mechanism to reduce number of refresh requests
            fname = f"{trusted['signed']['version'] + 1}.root.json"
            path = Path(context.av_data_dir, fname)

            try:
                # TODO: support fetching root data with credentials
                untrusted = self._fetch_channel_signing_data(
                    context.signing_metadata_url_base,
                    fname,
                )

                verify_root(trusted, untrusted)
            except HTTPError as err:
                # HTTP 404 implies no updated root.json is available, which is
                # not really an "error" and does not need to be logged.
                if err.response.status_code != 404:
                    log.error(err)
                break
            except Exception as err:
                # TODO: more error handling
                log.error(err)
                break
            else:
                # New trust root metadata checks out
                write_metadata_to_file(trusted := untrusted, path)

        return trusted

    # FUTURE: Python 3.8+, replace with functools.cached_property
    @property
    @lru_cache(maxsize=None)
    def key_mgr(self) -> dict | None:
        trusted: dict | None = None

        # Refresh key manager metadata
        fname = KEY_MGR_FILE
        path = Path(context.av_data_dir, fname)

        try:
            untrusted = self._fetch_channel_signing_data(
                context.signing_metadata_url_base,
                fname,
            )

            verify_delegation("key_mgr", untrusted, self.trusted_root)
        except ConnectionError as err:
            log.warning(err)
        except HTTPError as err:
            # sometimes the HTTPError message is blank, when that occurs include the
            # HTTP status code
            log.warning(
                str(err) or f"{err.__class__.__name__} ({err.response.status_code})"
            )
        else:
            # New key manager metadata checks out
            write_metadata_to_file(trusted := untrusted, path)

        # If key_mgr is unavailable from server, fall back to copy on disk
        if not trusted and path.exists():
            trusted = load_metadata_from_file(path)

        return trusted

    def _fetch_channel_signing_data(
        self, signing_data_url: str, filename: str, etag=None, mod_stamp=None
    ) -> dict:
        session = get_session(signing_data_url)

        if not context.ssl_verify:
            warnings.simplefilter("ignore", InsecureRequestWarning)

        headers = {
            "Accept-Encoding": "gzip, deflate, compress, identity",
            "Content-Type": "application/json",
        }
        if etag:
            headers["If-None-Match"] = etag
        if mod_stamp:
            headers["If-Modified-Since"] = mod_stamp

        saved_token_setting = context.add_anaconda_token
        try:
            # Assume trust metadata is intended to be "generally available",
            # and specifically, _not_ protected by a conda/binstar token.
            # Seems reasonable, since we (probably) don't want the headaches of
            # dealing with protected, per-channel trust metadata.
            #
            # Note: Setting `auth=None` here does allow trust metadata to be
            # protected using standard HTTP basic auth mechanisms, with the
            # login information being provided in the user's netrc file.
            context.add_anaconda_token = False
            resp = session.get(
                join_url(signing_data_url, filename),
                headers=headers,
                proxies=session.proxies,
                auth=None,
                timeout=(
                    context.remote_connect_timeout_secs,
                    context.remote_read_timeout_secs,
                ),
            )
            # TODO: maybe add more sensible error handling
            resp.raise_for_status()
        finally:
            context.add_anaconda_token = saved_token_setting

        # In certain cases (e.g., using `-c` access anaconda.org channels), the
        # `CondaSession.get()` retry logic combined with the remote server's
        # behavior can result in non-JSON content being returned.  Parse returned
        # content here (rather than directly in the return statement) so callers of
        # this function only have to worry about a ValueError being raised.
        try:
            return resp.json()
        except json.decoder.JSONDecodeError as err:  # noqa
            # TODO: additional loading and error handling improvements?
            raise ValueError(
                f"Invalid JSON returned from {signing_data_url}/{filename}"
            )

    def verify(self, repodata_fn: str, record: PackageRecord):
        repodata, _ = SubdirData(
            record.channel,
            repodata_fn=repodata_fn,
        ).repo_fetch.fetch_latest_parsed()

        # short-circuit if no signatures are defined
        if "signatures" not in repodata:
            record.metadata.add(
                f"(no signatures found for {record.channel.canonical_name})"
            )
            return
        signatures = repodata["signatures"]

        # short-circuit if no signature is defined for this package
        if record.fn not in signatures:
            record.metadata.add(f"(no signatures found for {record.fn})")
            return
        signature = signatures[record.fn]

        # extract metadata to be verified
        if record.fn.endswith(CONDA_PACKAGE_EXTENSION_V1):
            info = repodata["packages"][record.fn]
        elif record.fn.endswith(CONDA_PACKAGE_EXTENSION_V2):
            info = repodata["packages.conda"][record.fn]
        else:
            raise ValueError("unknown package extension")

        # create a signable envelope (a dict with the info and signatures)
        envelope = wrap_as_signable(info)
        envelope["signatures"] = signature

        try:
            verify_delegation("pkg_mgr", envelope, self.key_mgr)
        except SignatureError:
            log.warning(f"invalid signature for {record.fn}")
            record.metadata.add("(package metadata is UNTRUSTED)")
        else:
            log.info(f"valid signature for {record.fn}")
            record.metadata.add("(package metadata is TRUSTED)")

    def __call__(
        self,
        repodata_fn: str,
        unlink_precs: tuple[PackageRecord, ...],
        link_precs: tuple[PackageRecord, ...],
    ) -> None:
        if not self.enabled:
            return

        for prec in link_precs:
            self.verify(repodata_fn, prec)

    @classmethod
    def cache_clear(cls) -> None:
        cls.enabled.fget.cache_clear()
        cls.trusted_root.fget.cache_clear()
        cls.key_mgr.fget.cache_clear()


# singleton for caching
signature_verification = _SignatureVerification()
