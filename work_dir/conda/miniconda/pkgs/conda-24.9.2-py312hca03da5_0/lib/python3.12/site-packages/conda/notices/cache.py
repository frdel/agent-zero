# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""
Handles all caching logic including:
  - Retrieving from cache
  - Saving to cache
  - Determining whether not certain items have expired and need to be refreshed
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING

from platformdirs import user_cache_dir

from ..base.constants import APP_NAME, NOTICES_CACHE_FN, NOTICES_CACHE_SUBDIR
from ..utils import ensure_dir_exists
from .types import ChannelNoticeResponse

if TYPE_CHECKING:
    from typing import Sequence

    from .types import ChannelNotice

logger = logging.getLogger(__name__)


def cached_response(func):
    @wraps(func)
    def wrapper(url: str, name: str):
        cache_dir = get_notices_cache_dir()
        cache_val = get_notice_response_from_cache(url, name, cache_dir)

        if cache_val:
            return cache_val

        return_value = func(url, name)
        if return_value is not None:
            write_notice_response_to_cache(return_value, cache_dir)

        return return_value

    return wrapper


def is_notice_response_cache_expired(
    channel_notice_response: ChannelNoticeResponse,
) -> bool:
    """
    This checks the contents of the cache response to see if it is expired.

    If for whatever reason we encounter an exception while parsing the individual
    messages, we assume an invalid cache and return true.
    """
    now = datetime.now(timezone.utc)

    def is_channel_notice_expired(expired_at: datetime | None) -> bool:
        """If there is no "expired_at" field present assume it is expired."""
        if expired_at is None:
            return True
        return expired_at < now

    return any(
        is_channel_notice_expired(chn.expired_at)
        for chn in channel_notice_response.notices
    )


@ensure_dir_exists
def get_notices_cache_dir() -> Path:
    """Returns the location of the notices cache directory as a Path object"""
    cache_dir = user_cache_dir(APP_NAME, appauthor=APP_NAME)

    return Path(cache_dir).joinpath(NOTICES_CACHE_SUBDIR)


def get_notices_cache_file() -> Path:
    """Returns the location of the notices cache file as a Path object"""
    cache_dir = get_notices_cache_dir()
    cache_file = cache_dir.joinpath(NOTICES_CACHE_FN)

    if not cache_file.is_file():
        with open(cache_file, "w") as fp:
            fp.write("")

    return cache_file


def get_notice_response_from_cache(
    url: str, name: str, cache_dir: Path
) -> ChannelNoticeResponse | None:
    """Retrieves a notice response object from cache if it exists."""
    cache_key = ChannelNoticeResponse.get_cache_key(url, cache_dir)

    if os.path.isfile(cache_key):
        with open(cache_key) as fp:
            data = json.load(fp)
        chn_ntc_resp = ChannelNoticeResponse(url, name, data)

        if not is_notice_response_cache_expired(chn_ntc_resp):
            return chn_ntc_resp


def write_notice_response_to_cache(
    channel_notice_response: ChannelNoticeResponse, cache_dir: Path
) -> None:
    """Writes our notice data to our local cache location."""
    cache_key = ChannelNoticeResponse.get_cache_key(
        channel_notice_response.url, cache_dir
    )

    with open(cache_key, "w") as fp:
        json.dump(channel_notice_response.json_data, fp)


def mark_channel_notices_as_viewed(
    cache_file: Path, channel_notices: Sequence[ChannelNotice]
) -> None:
    """Insert channel notice into our database marking it as read."""
    notice_ids = {chn.id for chn in channel_notices}

    with open(cache_file) as fp:
        contents: str = fp.read()

    contents_unique = set(filter(None, set(contents.splitlines())))
    contents_new = contents_unique.union(notice_ids)

    # Save new version of cache file
    with open(cache_file, "w") as fp:
        fp.write("\n".join(contents_new))


def get_viewed_channel_notice_ids(
    cache_file: Path, channel_notices: Sequence[ChannelNotice]
) -> set[str]:
    """Return the ids of the channel notices which have already been seen."""
    notice_ids = {chn.id for chn in channel_notices}

    with open(cache_file) as fp:
        contents: str = fp.read()

    contents_unique = set(filter(None, set(contents.splitlines())))

    return notice_ids.intersection(contents_unique)
