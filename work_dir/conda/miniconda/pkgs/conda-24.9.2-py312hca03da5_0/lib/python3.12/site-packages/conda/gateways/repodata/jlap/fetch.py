# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""JLAP consumer."""

from __future__ import annotations

import io
import json
import logging
import pprint
import re
import time
from contextlib import contextmanager
from hashlib import blake2b
from typing import TYPE_CHECKING

import jsonpatch
import zstandard
from requests import HTTPError

from conda.common.url import mask_anaconda_token

from ....base.context import context
from .. import ETAG_KEY, LAST_MODIFIED_KEY, RepodataState
from .core import JLAP

if TYPE_CHECKING:
    import pathlib
    from typing import Iterator

    from ...connection import Response, Session
    from .. import RepodataCache

log = logging.getLogger(__name__)


DIGEST_SIZE = 32  # 256 bits

JLAP_KEY = "jlap"
HEADERS = "headers"
NOMINAL_HASH = "blake2_256_nominal"
ON_DISK_HASH = "blake2_256"
LATEST = "latest"

# save these headers. at least etag, last-modified, cache-control plus a few
# useful extras.
STORE_HEADERS = {
    "etag",
    "last-modified",
    "cache-control",
    "content-range",
    "content-length",
    "date",
    "content-type",
    "content-encoding",
}


def hash():
    """Ordinary hash."""
    return blake2b(digest_size=DIGEST_SIZE)


class Jlap304NotModified(Exception):
    pass


class JlapSkipZst(Exception):
    pass


class JlapPatchNotFound(LookupError):
    pass


def process_jlap_response(response: Response, pos=0, iv=b""):
    # if response is 304 Not Modified, could return a buffer with only the
    # cached footer...
    if response.status_code == 304:
        raise Jlap304NotModified()

    def lines() -> Iterator[bytes]:
        yield from response.iter_lines(delimiter=b"\n")  # type: ignore

    buffer = JLAP.from_lines(lines(), iv, pos)

    # new iv == initial iv if nothing changed
    pos, footer, _ = buffer[-2]
    footer = json.loads(footer)

    new_state = {
        # we need to save etag, last-modified, cache-control
        "headers": {
            k.lower(): v
            for k, v in response.headers.items()
            if k.lower() in STORE_HEADERS
        },
        "iv": buffer[-3][-1],
        "pos": pos,
        "footer": footer,
    }

    return buffer, new_state


def fetch_jlap(url, pos=0, etag=None, iv=b"", ignore_etag=True, session=None):
    response = request_jlap(
        url, pos=pos, etag=etag, ignore_etag=ignore_etag, session=session
    )
    return process_jlap_response(response, pos=pos, iv=iv)


def request_jlap(
    url, pos=0, etag=None, ignore_etag=True, session: Session | None = None
):
    """Return the part of the remote .jlap file we are interested in."""
    headers = {}
    if pos:
        headers["range"] = f"bytes={pos}-"
    if etag and not ignore_etag:
        headers["if-none-match"] = etag

    log.debug("%s %s", mask_anaconda_token(url), headers)

    assert session is not None

    timeout = context.remote_connect_timeout_secs, context.remote_read_timeout_secs
    response = session.get(url, stream=True, headers=headers, timeout=timeout)
    response.raise_for_status()

    if response.request:
        log.debug("request headers: %s", pprint.pformat(response.request.headers))
    else:
        log.debug("response without request.")
    log.debug(
        "response headers: %s",
        pprint.pformat(
            {k: v for k, v in response.headers.items() if k.lower() in STORE_HEADERS}
        ),
    )
    log.debug("status: %d", response.status_code)
    if "range" in headers:
        # 200 is also a possibility that we'd rather not deal with; if the
        # server can't do range requests, also mark jlap as unavailable. Which
        # status codes mean 'try again' instead of 'it will never work'?
        if response.status_code not in (206, 304, 404, 416):
            raise HTTPError(
                f"Unexpected response code for range request {response.status_code}",
                response=response,
            )

    log.info("%s", response)

    return response


def format_hash(hash):
    """Abbreviate hash for formatting."""
    return hash[:16] + "\N{HORIZONTAL ELLIPSIS}"


def find_patches(patches, have, want):
    apply = []
    for patch in reversed(patches):
        if have == want:
            break
        if patch["to"] == want:
            apply.append(patch)
            want = patch["from"]

    if have != want:
        log.debug(f"No patch from local revision {format_hash(have)}")
        raise JlapPatchNotFound(f"No patch from local revision {format_hash(have)}")

    return apply


def apply_patches(data, apply):
    while apply:
        patch = apply.pop()
        log.debug(
            f"{format_hash(patch['from'])} \N{RIGHTWARDS ARROW} {format_hash(patch['to'])}, "
            f"{len(patch['patch'])} steps"
        )
        data = jsonpatch.JsonPatch(patch["patch"]).apply(data, in_place=True)


def withext(url, ext):
    return re.sub(r"(\.\w+)$", ext, url)


@contextmanager
def timeme(message):
    begin = time.monotonic()
    yield
    end = time.monotonic()
    log.debug("%sTook %0.02fs", message, end - begin)


def build_headers(json_path: pathlib.Path, state: RepodataState):
    """Caching headers for a path and state."""
    headers = {}
    # simplify if we require state to be empty when json_path is missing.
    if json_path.exists():
        etag = state.get("_etag")
        if etag:
            headers["if-none-match"] = etag
    return headers


class HashWriter(io.RawIOBase):
    def __init__(self, backing, hasher):
        self.backing = backing
        self.hasher = hasher

    def write(self, b: bytes):
        self.hasher.update(b)
        return self.backing.write(b)

    def close(self):
        self.backing.close()


def download_and_hash(
    hasher,
    url,
    json_path: pathlib.Path,
    session: Session,
    state: RepodataState | None,
    is_zst=False,
    dest_path: pathlib.Path | None = None,
):
    """Download url if it doesn't exist, passing bytes through hasher.update().

    json_path: Path of old cached data (ignore etag if not exists).
    dest_path: Path to write new data.
    """
    if dest_path is None:
        dest_path = json_path
    state = state or RepodataState()
    headers = build_headers(json_path, state)
    timeout = context.remote_connect_timeout_secs, context.remote_read_timeout_secs
    response = session.get(url, stream=True, timeout=timeout, headers=headers)
    log.debug("%s %s", url, response.headers)
    response.raise_for_status()
    length = 0
    # is there a status code for which we must clear the file?
    if response.status_code == 200:
        if is_zst:
            decompressor = zstandard.ZstdDecompressor()
            writer = decompressor.stream_writer(
                HashWriter(dest_path.open("wb"), hasher),  # type: ignore
                closefd=True,
            )
        else:
            writer = HashWriter(dest_path.open("wb"), hasher)
        with writer as repodata:
            for block in response.iter_content(chunk_size=1 << 14):
                repodata.write(block)
    if response.request:
        try:
            length = int(response.headers["Content-Length"])
        except (KeyError, ValueError, AttributeError):
            pass
        log.info("Download %d bytes %r", length, response.request.headers)
    return response  # can be 304 not modified


def _is_http_error_most_400_codes(e: HTTPError) -> bool:
    """
    Determine whether the `HTTPError` is an HTTP 400 error code (except for 416).
    """
    if e.response is None:  # 404 e.response is falsey
        return False
    status_code = e.response.status_code
    return 400 <= status_code < 500 and status_code != 416


def request_url_jlap_state(
    url,
    state: RepodataState,
    full_download=False,
    *,
    session: Session,
    cache: RepodataCache,
    temp_path: pathlib.Path,
) -> dict | None:
    jlap_state = state.get(JLAP_KEY, {})
    headers = jlap_state.get(HEADERS, {})
    json_path = cache.cache_path_json

    buffer = JLAP()  # type checks

    if (
        full_download
        or not (NOMINAL_HASH in state and json_path.exists())
        or not state.should_check_format("jlap")
    ):
        hasher = hash()
        with timeme(f"Download complete {url} "):
            # Don't deal with 304 Not Modified if hash unavailable e.g. if
            # cached without jlap
            if NOMINAL_HASH not in state:
                state.pop(ETAG_KEY, None)
                state.pop(LAST_MODIFIED_KEY, None)

            try:
                if state.should_check_format("zst"):
                    response = download_and_hash(
                        hasher,
                        withext(url, ".json.zst"),
                        json_path,  # makes conditional request if exists
                        dest_path=temp_path,  # writes to
                        session=session,
                        state=state,
                        is_zst=True,
                    )
                else:
                    raise JlapSkipZst()
            except (JlapSkipZst, HTTPError, zstandard.ZstdError) as e:
                if isinstance(e, zstandard.ZstdError):
                    log.warning(
                        "Could not decompress %s as zstd. Fall back to .json. (%s)",
                        mask_anaconda_token(withext(url, ".json.zst")),
                        e,
                    )
                if isinstance(e, HTTPError) and not _is_http_error_most_400_codes(e):
                    raise
                if not isinstance(e, JlapSkipZst):
                    # don't update last-checked timestamp on skip
                    state.set_has_format("zst", False)
                response = download_and_hash(
                    hasher,
                    withext(url, ".json"),
                    json_path,
                    dest_path=temp_path,
                    session=session,
                    state=state,
                )

            # will we use state['headers'] for caching against
            state["_mod"] = response.headers.get("last-modified")
            state["_etag"] = response.headers.get("etag")
            state["_cache_control"] = response.headers.get("cache-control")

        # was not re-hashed if 304 not modified
        if response.status_code == 200:
            state[NOMINAL_HASH] = state[ON_DISK_HASH] = hasher.hexdigest()

        have = state[NOMINAL_HASH]

        # a jlap buffer with zero patches. the buffer format is (position,
        # payload, checksum) where position is the offset from the beginning of
        # the file; payload is the leading or trailing checksum or other data;
        # and checksum is the running checksum for the file up to that point.
        buffer = JLAP([[-1, "", ""], [0, json.dumps({LATEST: have}), ""], [1, "", ""]])

    else:
        have = state[NOMINAL_HASH]
        # have_hash = state.get(ON_DISK_HASH)

        need_jlap = True
        try:
            iv_hex = jlap_state.get("iv", "")
            pos = jlap_state.get("pos", 0)
            etag = headers.get(ETAG_KEY, None)
            jlap_url = withext(url, ".jlap")
            log.debug(
                "Fetch %s from iv=%s, pos=%s",
                mask_anaconda_token(jlap_url),
                iv_hex,
                pos,
            )
            # wrong to read state outside of function, and totally rebuild inside
            buffer, jlap_state = fetch_jlap(
                jlap_url,
                pos=pos,
                etag=etag,
                iv=bytes.fromhex(iv_hex),
                session=session,
                ignore_etag=False,
            )
            state.set_has_format("jlap", True)
            need_jlap = False
        except ValueError:
            log.info("Checksum not OK on JLAP range request. Retry with complete JLAP.")
        except IndexError:
            log.exception("IndexError reading JLAP. Invalid file?")
        except HTTPError as e:
            # If we get a 416 Requested range not satisfiable, the server-side
            # file may have been truncated and we need to fetch from 0
            if _is_http_error_most_400_codes(e):
                state.set_has_format("jlap", False)
                return request_url_jlap_state(
                    url,
                    state,
                    full_download=True,
                    session=session,
                    cache=cache,
                    temp_path=temp_path,
                )
            log.info(
                "Response code %d on JLAP range request. Retry with complete JLAP.",
                e.response.status_code,
            )

        if need_jlap:  # retry whole file, if range failed
            try:
                buffer, jlap_state = fetch_jlap(withext(url, ".jlap"), session=session)
            except (ValueError, IndexError) as e:
                log.exception("Error parsing jlap", exc_info=e)
                # a 'latest' hash that we can't achieve, triggering later error handling
                buffer = JLAP(
                    [[-1, "", ""], [0, json.dumps({LATEST: "0" * 32}), ""], [1, "", ""]]
                )
                state.set_has_format("jlap", False)

        state[JLAP_KEY] = jlap_state

    with timeme("Apply Patches "):
        # buffer[0] == previous iv
        # buffer[1:-2] == patches
        # buffer[-2] == footer = new_state["footer"]
        # buffer[-1] == trailing checksum

        patches = list(json.loads(patch) for _, patch, _ in buffer.body)
        _, footer, _ = buffer.penultimate
        want = json.loads(footer)["latest"]

        try:
            apply = find_patches(patches, have, want)
            log.info(
                f"Apply {len(apply)} patches "
                f"{format_hash(have)} \N{RIGHTWARDS ARROW} {format_hash(want)}"
            )

            if apply:
                with timeme("Load "):
                    # we haven't loaded repodata yet; it could fail to parse, or
                    # have the wrong hash.
                    # if this fails, then we also need to fetch again from 0
                    repodata_json = json.loads(cache.load())
                    # XXX cache.state must equal what we started with, otherwise
                    # bail with 'repodata on disk' (indicating another process
                    # downloaded repodata.json in parallel with us)
                    if have != cache.state.get(NOMINAL_HASH):  # or check mtime_ns?
                        log.warning("repodata cache changed during jlap fetch.")
                        return None

                apply_patches(repodata_json, apply)

                with timeme("Write changed "), temp_path.open("wb") as repodata:
                    hasher = hash()
                    HashWriter(repodata, hasher).write(
                        json.dumps(repodata_json, separators=(",", ":")).encode("utf-8")
                    )

                    # actual hash of serialized json
                    state[ON_DISK_HASH] = hasher.hexdigest()

                    # hash of equivalent upstream json
                    state[NOMINAL_HASH] = want

                    # avoid duplicate parsing
                    return repodata_json
            else:
                assert state[NOMINAL_HASH] == want

        except (JlapPatchNotFound, json.JSONDecodeError) as e:
            if isinstance(e, JlapPatchNotFound):
                # 'have' hash not mentioned in patchset
                #
                # XXX or skip jlap at top of fn; make sure it is not
                # possible to download the complete json twice
                log.info(
                    "Current repodata.json %s not found in patchset. Re-download repodata.json"
                )

            assert not full_download, "Recursion error"  # pragma: no cover

            return request_url_jlap_state(
                url,
                state,
                full_download=True,
                session=session,
                cache=cache,
                temp_path=temp_path,
            )
