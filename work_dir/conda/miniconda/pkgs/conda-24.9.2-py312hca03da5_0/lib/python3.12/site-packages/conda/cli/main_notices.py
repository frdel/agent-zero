# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""CLI implementation for `conda notices`.

Manually retrieves channel notifications, caches them and displays them.
"""

from argparse import ArgumentParser, Namespace, _SubParsersAction


def configure_parser(sub_parsers: _SubParsersAction, **kwargs) -> ArgumentParser:
    from ..auxlib.ish import dals
    from .helpers import add_parser_channels, add_parser_json

    summary = "Retrieve latest channel notifications."
    description = dals(
        f"""
        {summary}

        Conda channel maintainers have the option of setting messages that
        users will see intermittently. Some of these notices are informational
        while others are messages concerning the stability of the channel.

        """
    )
    epilog = dals(
        """
        Examples::

            conda notices

            conda notices -c defaults

        """
    )

    p = sub_parsers.add_parser(
        "notices",
        help=summary,
        description=description,
        epilog=epilog,
        **kwargs,
    )
    add_parser_channels(p)
    add_parser_json(p)

    p.set_defaults(func="conda.cli.main_notices.execute")

    return p


def execute(args: Namespace, parser: ArgumentParser) -> int:
    """Command that retrieves channel notifications, caches them and displays them."""
    from ..exceptions import CondaError
    from ..notices import core as notices

    try:
        channel_notice_set = notices.retrieve_notices()
    except OSError as exc:
        raise CondaError(f"Unable to retrieve notices: {exc}")

    notices.display_notices(channel_notice_set)

    return 0
