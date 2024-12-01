# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""
Collection of helper functions to standardize reused CLI arguments.
"""

from __future__ import annotations

from argparse import SUPPRESS, _HelpAction
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from argparse import ArgumentParser, _ArgumentGroup, _MutuallyExclusiveGroup

try:
    from argparse import BooleanOptionalAction
except ImportError:
    # Python < 3.9
    from argparse import Action

    class BooleanOptionalAction(Action):
        # from Python 3.9+ argparse.py
        def __init__(
            self,
            option_strings,
            dest,
            default=None,
            type=None,
            choices=None,
            required=False,
            help=None,
            metavar=None,
        ):
            _option_strings = []
            for option_string in option_strings:
                _option_strings.append(option_string)

                if option_string.startswith("--"):
                    option_string = "--no-" + option_string[2:]
                    _option_strings.append(option_string)

            super().__init__(
                option_strings=_option_strings,
                dest=dest,
                nargs=0,
                default=default,
                type=type,
                choices=choices,
                required=required,
                help=help,
                metavar=metavar,
            )

        def __call__(self, parser, namespace, values, option_string=None):
            if option_string in self.option_strings:
                setattr(namespace, self.dest, not option_string.startswith("--no-"))

        def format_usage(self):
            return " | ".join(self.option_strings)


def add_parser_create_install_update(p, prefix_required=False):
    from ..common.constants import NULL

    add_parser_prefix(p, prefix_required)
    channel_options = add_parser_channels(p)
    solver_mode_options = add_parser_solver_mode(p)
    package_install_options = add_parser_package_install_options(p)
    add_parser_networking(p)

    output_and_prompt_options = add_output_and_prompt_options(p)
    output_and_prompt_options.add_argument(
        "--download-only",
        action="store_true",
        default=NULL,
        help="Solve an environment and ensure package caches are populated, but exit "
        "prior to unlinking and linking packages into the prefix.",
    )
    add_parser_show_channel_urls(output_and_prompt_options)

    add_parser_pscheck(p)
    add_parser_known(p)

    # Add the file kwarg. We don't use {action="store", nargs='*'} as we don't
    # want to gobble up all arguments after --file.
    p.add_argument(
        "--file",
        default=[],
        action="append",
        help="Read package versions from the given file. Repeated file "
        "specifications can be passed (e.g. --file=file1 --file=file2).",
    )
    p.add_argument(
        "packages",
        metavar="package_spec",
        action="store",
        nargs="*",
        help="List of packages to install or update in the conda environment.",
    )

    return solver_mode_options, package_install_options, channel_options


def add_parser_pscheck(p: ArgumentParser) -> None:
    p.add_argument("--force-pscheck", action="store_true", help=SUPPRESS)


def add_parser_show_channel_urls(p: ArgumentParser | _ArgumentGroup) -> None:
    from ..common.constants import NULL

    p.add_argument(
        "--show-channel-urls",
        action="store_true",
        dest="show_channel_urls",
        default=NULL,
        help="Show channel urls. "
        "Overrides the value given by `conda config --show show_channel_urls`.",
    )
    p.add_argument(
        "--no-show-channel-urls",
        action="store_false",
        dest="show_channel_urls",
        help=SUPPRESS,
    )


def add_parser_help(p: ArgumentParser) -> None:
    """
    So we can use consistent capitalization and periods in the help. You must
    use the add_help=False argument to ArgumentParser or add_parser to use
    this. Add this first to be consistent with the default argparse output.

    """
    p.add_argument(
        "-h",
        "--help",
        action=_HelpAction,
        help="Show this help message and exit.",
    )


def add_parser_prefix(
    p: ArgumentParser,
    prefix_required: bool = False,
) -> _MutuallyExclusiveGroup:
    target_environment_group = p.add_argument_group("Target Environment Specification")
    npgroup = target_environment_group.add_mutually_exclusive_group(
        required=prefix_required
    )
    npgroup.add_argument(
        "-n",
        "--name",
        action="store",
        help="Name of environment.",
        metavar="ENVIRONMENT",
    )
    npgroup.add_argument(
        "-p",
        "--prefix",
        action="store",
        help="Full path to environment location (i.e. prefix).",
        metavar="PATH",
    )
    return npgroup


def add_parser_json(p: ArgumentParser) -> _ArgumentGroup:
    from ..common.constants import NULL

    output_and_prompt_options = p.add_argument_group(
        "Output, Prompt, and Flow Control Options"
    )
    output_and_prompt_options.add_argument(
        "--json",
        action="store_true",
        default=NULL,
        help="Report all output as json. Suitable for using conda programmatically.",
    )
    add_parser_verbose(output_and_prompt_options)
    output_and_prompt_options.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        default=NULL,
        help="Do not display progress bar.",
    )
    return output_and_prompt_options


def add_output_and_prompt_options(p: ArgumentParser) -> _ArgumentGroup:
    from ..common.constants import NULL

    output_and_prompt_options = add_parser_json(p)
    output_and_prompt_options.add_argument(
        "-d",
        "--dry-run",
        action="store_true",
        help="Only display what would have been done.",
    )
    output_and_prompt_options.add_argument(
        "-y",
        "--yes",
        action="store_true",
        default=NULL,
        help="Sets any confirmation values to 'yes' automatically. "
        "Users will not be asked to confirm any adding, deleting, backups, etc.",
    )
    return output_and_prompt_options


def add_parser_channels(p: ArgumentParser) -> _ArgumentGroup:
    from ..common.constants import NULL

    channel_customization_options = p.add_argument_group("Channel Customization")
    channel_customization_options.add_argument(
        "-c",
        "--channel",
        # beware conda-build uses this (currently or in the past?)
        # if ever renaming to "channels" consider removing context.channels alias to channel
        dest="channel",
        action="append",
        help=(
            "Additional channel to search for packages. These are URLs searched in the order "
            "they are given (including local directories using the 'file://' syntax or "
            "simply a path like '/home/conda/mychan' or '../mychan'). Then, the defaults "
            "or channels from .condarc are searched (unless --override-channels is given). "
            "You can use 'defaults' to get the default packages for conda. You can also "
            "use any name and the .condarc channel_alias value will be prepended. The "
            "default channel_alias is https://conda.anaconda.org/."
        ),
    )
    channel_customization_options.add_argument(
        "--use-local",
        action="store_true",
        default=NULL,
        help="Use locally built packages. Identical to '-c local'.",
    )
    channel_customization_options.add_argument(
        "--override-channels",
        action="store_true",
        help="""Do not search default or .condarc channels.  Requires --channel.""",
    )
    channel_customization_options.add_argument(
        "--repodata-fn",
        action="append",
        dest="repodata_fns",
        help=(
            "Specify file name of repodata on the remote server where your channels "
            "are configured or within local backups. Conda will try whatever you "
            "specify, but will ultimately fall back to repodata.json if your specs are "
            "not satisfiable with what you specify here. This is used to employ repodata "
            "that is smaller and reduced in time scope. You may pass this flag more than "
            "once. Leftmost entries are tried first, and the fallback to repodata.json "
            "is added for you automatically. For more information, see "
            "conda config --describe repodata_fns."
        ),
    )
    channel_customization_options.add_argument(
        "--experimental",
        action="append",
        choices=["jlap", "lock"],
        help="jlap: Download incremental package index data from repodata.jlap; implies 'lock'. "
        "lock: use locking when reading, updating index (repodata.json) cache. Now enabled.",
    )
    channel_customization_options.add_argument(
        "--no-lock",
        action="store_true",
        help="Disable locking when reading, updating index (repodata.json) cache. ",
    )

    channel_customization_options.add_argument(
        "--repodata-use-zst",
        action=BooleanOptionalAction,
        dest="repodata_use_zst",
        default=NULL,
        help="Check for/do not check for repodata.json.zst. Enabled by default.",
    )
    return channel_customization_options


def add_parser_solver_mode(p: ArgumentParser) -> _ArgumentGroup:
    from ..base.constants import DepsModifier
    from ..common.constants import NULL

    solver_mode_options = p.add_argument_group("Solver Mode Modifiers")
    deps_modifiers = solver_mode_options.add_mutually_exclusive_group()
    solver_mode_options.add_argument(
        "--strict-channel-priority",
        action="store_const",
        dest="channel_priority",
        default=NULL,
        const="strict",
        help="Packages in lower priority channels are not considered if a package "
        "with the same name appears in a higher priority channel.",
    )
    solver_mode_options.add_argument(
        "--channel-priority",
        action="store_true",
        dest="channel_priority",
        default=NULL,
        help=SUPPRESS,
    )
    solver_mode_options.add_argument(
        "--no-channel-priority",
        action="store_const",
        dest="channel_priority",
        default=NULL,
        const="disabled",
        help="Package version takes precedence over channel priority. "
        "Overrides the value given by `conda config --show channel_priority`.",
    )
    deps_modifiers.add_argument(
        "--no-deps",
        action="store_const",
        const=DepsModifier.NO_DEPS,
        dest="deps_modifier",
        help="Do not install, update, remove, or change dependencies. This WILL lead "
        "to broken environments and inconsistent behavior. Use at your own risk.",
        default=NULL,
    )
    deps_modifiers.add_argument(
        "--only-deps",
        action="store_const",
        const=DepsModifier.ONLY_DEPS,
        dest="deps_modifier",
        help="Only install dependencies.",
        default=NULL,
    )
    solver_mode_options.add_argument(
        "--no-pin",
        action="store_true",
        dest="ignore_pinned",
        default=NULL,
        help="Ignore pinned file.",
    )
    return solver_mode_options


def add_parser_update_modifiers(solver_mode_options: ArgumentParser):
    from ..base.constants import UpdateModifier
    from ..common.constants import NULL

    update_modifiers = solver_mode_options.add_mutually_exclusive_group()
    update_modifiers.add_argument(
        "--freeze-installed",
        "--no-update-deps",
        action="store_const",
        const=UpdateModifier.FREEZE_INSTALLED,
        dest="update_modifier",
        default=NULL,
        help="Do not update or change already-installed dependencies.",
    )
    update_modifiers.add_argument(
        "--update-deps",
        action="store_const",
        const=UpdateModifier.UPDATE_DEPS,
        dest="update_modifier",
        default=NULL,
        help="Update dependencies that have available updates.",
    )
    update_modifiers.add_argument(
        "-S",
        "--satisfied-skip-solve",
        action="store_const",
        const=UpdateModifier.SPECS_SATISFIED_SKIP_SOLVE,
        dest="update_modifier",
        default=NULL,
        help="Exit early and do not run the solver if the requested specs are satisfied. "
        "Also skips aggressive updates as configured by the "
        "'aggressive_update_packages' config setting. Use "
        "'conda config --describe aggressive_update_packages' to view your setting. "
        "--satisfied-skip-solve is similar to the default behavior of 'pip install'.",
    )
    update_modifiers.add_argument(
        "--update-all",
        "--all",
        action="store_const",
        const=UpdateModifier.UPDATE_ALL,
        dest="update_modifier",
        help="Update all installed packages in the environment.",
        default=NULL,
    )
    update_modifiers.add_argument(
        "--update-specs",
        action="store_const",
        const=UpdateModifier.UPDATE_SPECS,
        dest="update_modifier",
        help="Update based on provided specifications.",
        default=NULL,
    )


def add_parser_prune(p: ArgumentParser) -> None:
    from ..common.constants import NULL

    p.add_argument(
        "--prune",
        action="store_true",
        default=NULL,
        help=SUPPRESS,
    )


def add_parser_solver(p: ArgumentParser) -> None:
    """
    Add a command-line flag for alternative solver backends.

    See ``context.solver`` for more info.
    """
    from ..base.context import context
    from ..common.constants import NULL

    group = p.add_mutually_exclusive_group()
    group.add_argument(
        "--solver",
        dest="solver",
        choices=context.plugin_manager.get_solvers(),
        help="Choose which solver backend to use.",
        default=NULL,
    )


def add_parser_networking(p: ArgumentParser) -> _ArgumentGroup:
    from ..common.constants import NULL

    networking_options = p.add_argument_group("Networking Options")
    networking_options.add_argument(
        "-C",
        "--use-index-cache",
        action="store_true",
        default=False,
        help="Use cache of channel index files, even if it has expired. This is useful "
        "if you don't want conda to check whether a new version of the repodata "
        "file exists, which will save bandwidth.",
    )
    networking_options.add_argument(
        "-k",
        "--insecure",
        action="store_false",
        dest="ssl_verify",
        default=NULL,
        help='Allow conda to perform "insecure" SSL connections and transfers. '
        "Equivalent to setting 'ssl_verify' to 'false'.",
    )
    networking_options.add_argument(
        "--offline",
        action="store_true",
        default=NULL,
        help="Offline mode. Don't connect to the Internet.",
    )
    return networking_options


def add_parser_package_install_options(p: ArgumentParser) -> _ArgumentGroup:
    from ..common.constants import NULL

    package_install_options = p.add_argument_group(
        "Package Linking and Install-time Options"
    )
    package_install_options.add_argument(
        "-f",
        "--force",
        action="store_true",
        default=NULL,
        help=SUPPRESS,
    )
    package_install_options.add_argument(
        "--copy",
        action="store_true",
        default=NULL,
        help="Install all packages using copies instead of hard- or soft-linking.",
    )
    package_install_options.add_argument(
        "--shortcuts",
        action="store_true",
        help=SUPPRESS,
        dest="shortcuts",
        default=NULL,
    )
    package_install_options.add_argument(
        "--no-shortcuts",
        action="store_false",
        help="Don't install start menu shortcuts",
        dest="shortcuts",
        default=NULL,
    )
    package_install_options.add_argument(
        "--shortcuts-only",
        action="append",
        help="Install shortcuts only for this package name. Can be used several times.",
        dest="shortcuts_only",
    )
    return package_install_options


def add_parser_known(p: ArgumentParser) -> None:
    p.add_argument(
        "--unknown",
        action="store_true",
        default=False,
        dest="unknown",
        help=SUPPRESS,
    )


def add_parser_default_packages(p: ArgumentParser) -> None:
    p.add_argument(
        "--no-default-packages",
        action="store_true",
        help="Ignore create_default_packages in the .condarc file.",
    )


def add_parser_platform(parser):
    from ..base.constants import KNOWN_SUBDIRS
    from ..common.constants import NULL

    parser.add_argument(
        "--subdir",
        "--platform",
        default=NULL,
        dest="subdir",
        choices=[s for s in KNOWN_SUBDIRS if s != "noarch"],
        metavar="SUBDIR",
        help="Use packages built for this platform. "
        "The new environment will be configured to remember this choice. "
        "Should be formatted like 'osx-64', 'linux-32', 'win-64', and so on. "
        "Defaults to the current (native) platform.",
    )


def add_parser_verbose(parser: ArgumentParser | _ArgumentGroup) -> None:
    from ..common.constants import NULL
    from .actions import NullCountAction

    parser.add_argument(
        "-v",
        "--verbose",
        action=NullCountAction,
        help=(
            "Can be used multiple times. Once for detailed output, twice for INFO logging, "
            "thrice for DEBUG logging, four times for TRACE logging."
        ),
        dest="verbosity",
        default=NULL,
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help=SUPPRESS,
        default=NULL,
    )
    parser.add_argument(
        "--trace",
        action="store_true",
        help=SUPPRESS,
        default=NULL,
    )
