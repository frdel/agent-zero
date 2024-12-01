# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Entry point for all conda subcommands."""

import sys


def init_loggers():
    import logging

    from ..base.context import context
    from ..gateways.logging import initialize_logging, set_log_level

    initialize_logging()

    # silence logging info to avoid interfering with JSON output
    if context.json:
        for logger in ("conda.stdout.verbose", "conda.stdoutlog", "conda.stderrlog"):
            logging.getLogger(logger).setLevel(logging.CRITICAL + 10)

    # set log_level
    set_log_level(context.log_level)


def main_subshell(*args, post_parse_hook=None, **kwargs):
    """Entrypoint for the "subshell" invocation of CLI interface. E.g. `conda create`."""
    # defer import here so it doesn't hit the 'conda shell.*' subcommands paths
    from ..base.context import context
    from .conda_argparse import do_call, generate_parser, generate_pre_parser

    args = args or ["--help"]

    pre_parser = generate_pre_parser(add_help=False)
    pre_args, _ = pre_parser.parse_known_args(args)

    # the arguments that we want to pass to the main parser later on
    override_args = {
        "json": pre_args.json,
        "debug": pre_args.debug,
        "trace": pre_args.trace,
        "verbosity": pre_args.verbosity,
    }

    context.__init__(argparse_args=pre_args)
    if context.no_plugins:
        context.plugin_manager.disable_external_plugins()

    # reinitialize in case any of the entrypoints modified the context
    context.__init__(argparse_args=pre_args)

    parser = generate_parser(add_help=True)
    args = parser.parse_args(args, override_args=override_args, namespace=pre_args)

    context.__init__(argparse_args=args)
    init_loggers()

    # used with main_pip.py
    if post_parse_hook:
        post_parse_hook(args, parser)

    exit_code = do_call(args, parser)
    if isinstance(exit_code, int):
        return exit_code
    elif hasattr(exit_code, "rc"):
        return exit_code.rc


def main_sourced(shell, *args, **kwargs):
    """Entrypoint for the "sourced" invocation of CLI interface. E.g. `conda activate`."""
    shell = shell.replace("shell.", "", 1)

    # This is called any way later in conda.activate, so no point in removing it
    from ..base.context import context

    context.__init__()

    from ..activate import _build_activator_cls

    try:
        activator_cls = _build_activator_cls(shell)
    except KeyError:
        from ..exceptions import CondaError

        raise CondaError(f"{shell} is not a supported shell.")

    activator = activator_cls(args)
    print(activator.execute(), end="")
    return 0


def main(*args, **kwargs):
    # conda.common.compat contains only stdlib imports
    from ..common.compat import ensure_text_type
    from ..exception_handler import conda_exception_handler

    # cleanup argv
    args = args or sys.argv[1:]  # drop executable/script
    args = tuple(ensure_text_type(s) for s in args)

    if args and args[0].strip().startswith("shell."):
        main = main_sourced
    else:
        main = main_subshell

    return conda_exception_handler(main, *args, **kwargs)
