# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Handles all display/view logic."""

import json
from typing import Sequence

from ..base.context import context
from .types import ChannelNotice


def print_notices(channel_notices: Sequence[ChannelNotice]):
    """
    Accepts a list of channel notice responses and prints a display.

    Args:
        channel_notices: A sequence of ChannelNotice objects.
    """
    current_channel = None

    if context.json:
        json_output = json.dumps(
            [channel_notice.to_dict() for channel_notice in channel_notices]
        )
        print(json_output)

    else:
        for channel_notice in channel_notices:
            if current_channel != channel_notice.channel_name:
                print()
                channel_header = "Channel"
                channel_header += (
                    f' "{channel_notice.channel_name}" has the following notices:'
                )
                print(channel_header)
                current_channel = channel_notice.channel_name
            print_notice_message(channel_notice)
            print()


def print_notice_message(notice: ChannelNotice, indent: str = "  ") -> None:
    """Prints a single channel notice."""
    timestamp = f"{notice.created_at:%c}" if notice.created_at else ""

    level = f"[{notice.level}] -- {timestamp}"

    print(f"{indent}{level}\n{indent}{notice.message}")


def print_more_notices_message(
    total_notices: int, displayed_notices: int, viewed_notices: int
) -> None:
    """Conditionally shows a message informing users how many more message there are."""
    notices_not_shown = total_notices - viewed_notices - displayed_notices

    if notices_not_shown > 0:
        if notices_not_shown > 1:
            msg = f"There are {notices_not_shown} more messages. To retrieve them run:\n\n"
        else:
            msg = f"There is {notices_not_shown} more message. To retrieve it run:\n\n"
        print(f"{msg}conda notices\n")
