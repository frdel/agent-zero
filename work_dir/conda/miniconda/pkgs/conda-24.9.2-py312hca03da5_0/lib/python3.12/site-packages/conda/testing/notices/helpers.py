# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Collection of helper functions used in conda.notices tests."""

from __future__ import annotations

import datetime
import json
import os
import uuid
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING

from ...models.channel import get_channel_objs
from ...notices.cache import get_notices_cache_file
from ...notices.core import get_channel_name_and_urls
from ...notices.types import ChannelNoticeResponse

if TYPE_CHECKING:
    from typing import Sequence
    from unittest import mock

    from ...base.context import Context

DEFAULT_NOTICE_MESG = "Here is an example message that will be displayed to users"


def get_test_notices(
    messages: Sequence[str],
    level: str | None = "info",
    created_at: datetime.datetime | None = None,
    expired_at: datetime.datetime | None = None,
) -> dict:
    created_at = created_at or datetime.datetime.now(datetime.timezone.utc)
    expired_at = expired_at or created_at + datetime.timedelta(days=7)

    return {
        "notices": [
            {
                "id": str(uuid.uuid4()),
                "message": message,
                "level": level,
                "created_at": created_at.isoformat(),
                "expired_at": expired_at.isoformat(),
            }
            for message in messages
        ]
    }


def add_resp_to_mock(
    mock_session: mock.MagicMock,
    status_code: int,
    messages_json: dict,
    raise_exc: bool = False,
) -> None:
    """Adds any number of MockResponse to MagicMock object as side_effects"""

    def forever_404():
        while True:
            yield MockResponse(404, {})

    def one_200():
        yield MockResponse(status_code, messages_json, raise_exc=raise_exc)

    chn = chain(one_200(), forever_404())
    mock_session().get.side_effect = tuple(next(chn) for _ in range(100))


def create_notice_cache_files(
    cache_dir: Path,
    cache_files: Sequence[str],
    messages_json_seq: Sequence[dict],
) -> None:
    """Creates the cache files that we use in tests"""
    for message_json, file in zip(messages_json_seq, cache_files):
        with cache_dir.joinpath(file).open("w") as fp:
            json.dump(message_json, fp)


def offset_cache_file_mtime(mtime_offset) -> None:
    """
    Allows for offsetting the mtime of the notices cache file. This is often
    used to mock an older creation time the cache file.
    """
    cache_file = get_notices_cache_file()
    os.utime(
        cache_file,
        times=(cache_file.stat().st_atime, cache_file.stat().st_mtime - mtime_offset),
    )


class DummyArgs:
    """Dummy object that sets all kwargs as object properties."""

    def __init__(self, **kwargs):
        self.no_ansi_colors = True

        for key, val in kwargs.items():
            setattr(self, key, val)


def notices_decorator_assert_message_in_stdout(
    captured,
    messages: Sequence[str],
    dummy_mesg: str | None = None,
    not_in: bool = False,
):
    """
    Tests a run of notices decorator where we expect to see the messages
    print to stdout.
    """
    assert captured.err == ""
    assert dummy_mesg in captured.out

    for mesg in messages:
        if not_in:
            assert mesg not in captured.out
        else:
            assert mesg in captured.out


class MockResponse:
    def __init__(self, status_code, json_data, raise_exc=False):
        self.status_code = status_code
        self.json_data = json_data
        self.raise_exc = raise_exc

    def json(self):
        if self.raise_exc:
            raise ValueError("Error")
        return self.json_data


def get_notice_cache_filenames(ctx: Context) -> tuple[str]:
    """Returns the filenames of the cache files that will be searched for"""
    channel_urls_and_names = get_channel_name_and_urls(get_channel_objs(ctx))

    return tuple(
        ChannelNoticeResponse.get_cache_key(url, Path("")).name
        for url, name in channel_urls_and_names
    )
