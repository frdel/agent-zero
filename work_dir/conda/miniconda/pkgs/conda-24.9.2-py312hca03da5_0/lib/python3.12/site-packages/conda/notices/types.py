# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Implements all conda.notices types."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import TYPE_CHECKING, NamedTuple

from ..base.constants import NoticeLevel

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Sequence

#: Value to use for message ID when it is not provided
UNDEFINED_MESSAGE_ID = "undefined"


class ChannelNotice(NamedTuple):
    """Represents an individual channel notice."""

    id: str
    channel_name: str | None
    message: str | None
    level: NoticeLevel
    created_at: datetime | None
    expired_at: datetime | None
    interval: int | None

    def to_dict(self):
        return {
            "id": self.id,
            "channel_name": self.channel_name,
            "message": self.message,
            "level": self.level.name.lower(),
            "created_at": self.created_at.isoformat(),
            "expired_at": self.expired_at.isoformat(),
            "interval": self.interval,
        }


class ChannelNoticeResultSet(NamedTuple):
    """
    Represents a list of a channel notices, plus some accompanying
    metadata such as `viewed_channel_notices`.
    """

    #: Channel notices that are included in this particular set
    channel_notices: Sequence[ChannelNotice]

    #: Total number of channel notices; not just the ones that will be displayed
    total_number_channel_notices: int

    #: The number of channel notices that have already been viewed
    viewed_channel_notices: int


class ChannelNoticeResponse(NamedTuple):
    url: str
    name: str
    json_data: dict | None

    @property
    def notices(self) -> Sequence[ChannelNotice]:
        if self.json_data:
            notices = self.json_data.get("notices", ())

            return tuple(
                ChannelNotice(
                    id=str(notice.get("id", UNDEFINED_MESSAGE_ID)),
                    channel_name=self.name,
                    message=notice.get("message"),
                    level=self._parse_notice_level(notice.get("level")),
                    created_at=self._parse_iso_timestamp(notice.get("created_at")),
                    expired_at=self._parse_iso_timestamp(notice.get("expired_at")),
                    interval=notice.get("interval"),
                )
                for notice in notices
            )

        # Default value
        return ()

    @staticmethod
    def _parse_notice_level(level: str | None) -> NoticeLevel:
        """
        We use this to validate notice levels and provide reasonable defaults
        if any are invalid.
        """
        try:
            return NoticeLevel(level)
        except ValueError:
            # If we get an invalid value, rather than fail, we simply use a reasonable default
            return NoticeLevel(NoticeLevel.INFO)

    @staticmethod
    def _parse_iso_timestamp(iso_timestamp: str | None) -> datetime | None:
        """Parse ISO timestamp and fail over to a default value of none."""
        if iso_timestamp is None:
            return None
        try:
            return datetime.fromisoformat(iso_timestamp)
        except ValueError:
            return None

    @classmethod
    def get_cache_key(cls, url: str, cache_dir: Path) -> Path:
        """Returns where this channel response will be cached by hashing the URL."""
        bytes_filename = url.encode()
        sha256_hash = hashlib.sha256(bytes_filename)
        cache_filename = f"{sha256_hash.hexdigest()}.json"

        return cache_dir.joinpath(cache_filename)
