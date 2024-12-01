# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Conda exceptions."""

from __future__ import annotations

import json
import os
import sys
from datetime import timedelta
from logging import getLogger
from os.path import join
from textwrap import dedent
from traceback import format_exception, format_exception_only
from typing import TYPE_CHECKING

from requests.exceptions import JSONDecodeError

from . import CondaError, CondaExitZero, CondaMultiError
from .auxlib.entity import EntityEncoder
from .auxlib.ish import dals
from .auxlib.logz import stringify
from .base.constants import COMPATIBLE_SHELLS, PathConflict, SafetyChecks
from .common.compat import on_win
from .common.io import dashlist
from .common.iterators import groupby_to_dict as groupby
from .common.signals import get_signal_name
from .common.url import join_url, maybe_unquote
from .deprecations import DeprecatedError  # noqa: F401
from .exception_handler import ExceptionHandler, conda_exception_handler  # noqa: F401
from .models.channel import Channel

if TYPE_CHECKING:
    import requests

log = getLogger(__name__)


# TODO: for conda-build compatibility only
# remove in conda 4.4
class ResolvePackageNotFound(CondaError):
    def __init__(self, bad_deps):
        # bad_deps is a list of lists
        # bad_deps should really be named 'invalid_chains'
        self.bad_deps = tuple(dep for deps in bad_deps for dep in deps if dep)
        formatted_chains = tuple(
            " -> ".join(map(str, bad_chain)) for bad_chain in bad_deps
        )
        self._formatted_chains = formatted_chains
        message = "\n" + "\n".join(
            (f"  - {bad_chain}") for bad_chain in formatted_chains
        )
        super().__init__(message)


NoPackagesFound = NoPackagesFoundError = ResolvePackageNotFound  # NOQA


class LockError(CondaError):
    def __init__(self, message):
        msg = f"{message}"
        super().__init__(msg)


class ArgumentError(CondaError):
    return_code = 2

    def __init__(self, message, **kwargs):
        super().__init__(message, **kwargs)


class Help(CondaError):
    pass


class ActivateHelp(Help):
    def __init__(self):
        message = dals(
            """
        usage: conda activate [-h] [--[no-]stack] [env_name_or_prefix]

        Activate a conda environment.

        Options:

        positional arguments:
          env_name_or_prefix    The environment name or prefix to activate. If the
                                prefix is a relative path, it must start with './'
                                (or '.\\' on Windows).

        optional arguments:
          -h, --help            Show this help message and exit.
          --stack               Stack the environment being activated on top of the
                                previous active environment, rather replacing the
                                current active environment with a new one. Currently,
                                only the PATH environment variable is stacked. This
                                may be enabled implicitly by the 'auto_stack'
                                configuration variable.
          --no-stack            Do not stack the environment. Overrides 'auto_stack'
                                setting.
        """
        )
        super().__init__(message)


class DeactivateHelp(Help):
    def __init__(self):
        message = dals(
            """
        usage: conda deactivate [-h]

        Deactivate the current active conda environment.

        Options:

        optional arguments:
          -h, --help            Show this help message and exit.
        """
        )
        super().__init__(message)


class GenericHelp(Help):
    def __init__(self, command):
        message = f"help requested for {command}"
        super().__init__(message)


class CondaSignalInterrupt(CondaError):
    def __init__(self, signum):
        signal_name = get_signal_name(signum)
        super().__init__(
            "Signal interrupt %(signal_name)s", signal_name=signal_name, signum=signum
        )


class TooManyArgumentsError(ArgumentError):
    def __init__(
        self, expected, received, offending_arguments, optional_message="", *args
    ):
        self.expected = expected
        self.received = received
        self.offending_arguments = offending_arguments
        self.optional_message = optional_message

        suffix = "s" if received - expected > 1 else ""
        msg = "{} Got {} argument{} ({}) but expected {}.".format(
            optional_message,
            received,
            suffix,
            ", ".join(offending_arguments),
            expected,
        )
        super().__init__(msg, *args)


class ClobberError(CondaError):
    def __init__(self, message, path_conflict, **kwargs):
        self.path_conflict = path_conflict
        super().__init__(message, **kwargs)

    def __repr__(self):
        clz_name = (
            "ClobberWarning"
            if self.path_conflict == PathConflict.warn
            else "ClobberError"
        )
        return f"{clz_name}: {self}\n"


class BasicClobberError(ClobberError):
    def __init__(self, source_path, target_path, context):
        message = dals(
            """
        Conda was asked to clobber an existing path.
          source path: %(source_path)s
          target path: %(target_path)s
        """
        )
        if context.path_conflict == PathConflict.prevent:
            message += (
                "Conda no longer clobbers existing paths without the use of the "
                "--clobber option\n."
            )
        super().__init__(
            message,
            context.path_conflict,
            target_path=target_path,
            source_path=source_path,
        )


class KnownPackageClobberError(ClobberError):
    def __init__(
        self, target_path, colliding_dist_being_linked, colliding_linked_dist, context
    ):
        message = dals(
            """
        The package '%(colliding_dist_being_linked)s' cannot be installed due to a
        path collision for '%(target_path)s'.
        This path already exists in the target prefix, and it won't be removed by
        an uninstall action in this transaction. The path appears to be coming from
        the package '%(colliding_linked_dist)s', which is already installed in the prefix.
        """
        )
        if context.path_conflict == PathConflict.prevent:
            message += (
                "If you'd like to proceed anyway, re-run the command with "
                "the `--clobber` flag.\n."
            )
        super().__init__(
            message,
            context.path_conflict,
            target_path=target_path,
            colliding_dist_being_linked=colliding_dist_being_linked,
            colliding_linked_dist=colliding_linked_dist,
        )


class UnknownPackageClobberError(ClobberError):
    def __init__(self, target_path, colliding_dist_being_linked, context):
        message = dals(
            """
        The package '%(colliding_dist_being_linked)s' cannot be installed due to a
        path collision for '%(target_path)s'.
        This path already exists in the target prefix, and it won't be removed
        by an uninstall action in this transaction. The path is one that conda
        doesn't recognize. It may have been created by another package manager.
        """
        )
        if context.path_conflict == PathConflict.prevent:
            message += (
                "If you'd like to proceed anyway, re-run the command with "
                "the `--clobber` flag.\n."
            )
        super().__init__(
            message,
            context.path_conflict,
            target_path=target_path,
            colliding_dist_being_linked=colliding_dist_being_linked,
        )


class SharedLinkPathClobberError(ClobberError):
    def __init__(self, target_path, incompatible_package_dists, context):
        message = dals(
            """
        This transaction has incompatible packages due to a shared path.
          packages: %(incompatible_packages)s
          path: '%(target_path)s'
        """
        )
        if context.path_conflict == PathConflict.prevent:
            message += (
                "If you'd like to proceed anyway, re-run the command with "
                "the `--clobber` flag.\n."
            )
        super().__init__(
            message,
            context.path_conflict,
            target_path=target_path,
            incompatible_packages=", ".join(str(d) for d in incompatible_package_dists),
        )


class CommandNotFoundError(CondaError):
    def __init__(self, command):
        activate_commands = {
            "activate",
            "deactivate",
            "run",
        }
        conda_commands = {
            "clean",
            "config",
            "create",
            "--help",  # https://github.com/conda/conda/issues/11585
            "info",
            "install",
            "list",
            "package",
            "remove",
            "search",
            "uninstall",
            "update",
            "upgrade",
        }
        build_commands = {
            "build",
            "convert",
            "develop",
            "index",
            "inspect",
            "metapackage",
            "render",
            "skeleton",
        }
        from .cli.main import init_loggers

        init_loggers()
        if command in activate_commands:
            # TODO: Point users to a page at conda-docs, which explains this context in more detail
            builder = [
                "Your shell has not been properly configured to use 'conda %(command)s'."
            ]
            if on_win:
                builder.append(
                    dals(
                        """
                If using 'conda %(command)s' from a batch script, change your
                invocation to 'CALL conda.bat %(command)s'.
                """
                    )
                )
            builder.append(
                dals(
                    """
            To initialize your shell, run

                $ conda init <SHELL_NAME>

            Currently supported shells are:%(supported_shells)s

            See 'conda init --help' for more information and options.

            IMPORTANT: You may need to close and restart your shell after running 'conda init'.
            """
                )
                % {
                    "supported_shells": dashlist(COMPATIBLE_SHELLS),
                }
            )
            message = "\n".join(builder)
        elif command in build_commands:
            message = "To use 'conda %(command)s', install conda-build."
        else:
            from difflib import get_close_matches

            from .cli.find_commands import find_commands

            message = "No command 'conda %(command)s'."
            choices = (
                activate_commands
                | conda_commands
                | build_commands
                | set(find_commands())
            )
            close = get_close_matches(command, choices)
            if close:
                message += f"\nDid you mean 'conda {close[0]}'?"
        super().__init__(message, command=command)


class PathNotFoundError(CondaError, OSError):
    def __init__(self, path):
        message = "%(path)s"
        super().__init__(message, path=path)


class DirectoryNotFoundError(CondaError):
    def __init__(self, path):
        message = "%(path)s"
        super().__init__(message, path=path)


class EnvironmentLocationNotFound(CondaError):
    def __init__(self, location):
        message = "Not a conda environment: %(location)s"
        super().__init__(message, location=location)


class EnvironmentNameNotFound(CondaError):
    def __init__(self, environment_name):
        message = dals(
            """
        Could not find conda environment: %(environment_name)s
        You can list all discoverable environments with `conda info --envs`.
        """
        )
        super().__init__(message, environment_name=environment_name)


class NoBaseEnvironmentError(CondaError):
    def __init__(self):
        message = dals(
            """
        This conda installation has no default base environment. Use
        'conda create' to create new environments and 'conda activate' to
        activate environments.
        """
        )
        super().__init__(message)


class DirectoryNotACondaEnvironmentError(CondaError):
    def __init__(self, target_directory):
        message = dals(
            """
        The target directory exists, but it is not a conda environment.
        Use 'conda create' to convert the directory to a conda environment.
          target directory: %(target_directory)s
        """
        )
        super().__init__(message, target_directory=target_directory)


class CondaEnvironmentError(CondaError, EnvironmentError):
    def __init__(self, message, *args):
        msg = f"{message}"
        super().__init__(msg, *args)


class DryRunExit(CondaExitZero):
    def __init__(self):
        msg = "Dry run. Exiting."
        super().__init__(msg)


class CondaSystemExit(CondaExitZero, SystemExit):
    def __init__(self, *args):
        msg = " ".join(str(arg) for arg in self.args)
        super().__init__(msg)


class PaddingError(CondaError):
    def __init__(self, dist, placeholder, placeholder_length):
        msg = (
            "Placeholder of length '%d' too short in package %s.\n"
            "The package must be rebuilt with conda-build > 2.0."
            % (placeholder_length, dist)
        )
        super().__init__(msg)


class LinkError(CondaError):
    def __init__(self, message):
        super().__init__(message)


class CondaOSError(CondaError, OSError):
    def __init__(self, message, **kwargs):
        msg = f"{message}"
        super().__init__(msg, **kwargs)


class ProxyError(CondaError):
    def __init__(self):
        message = dals(
            """
        Conda cannot proceed due to an error in your proxy configuration.
        Check for typos and other configuration errors in any '.netrc' file in your home directory,
        any environment variables ending in '_PROXY', and any other system-wide proxy
        configuration settings.
        """
        )
        super().__init__(message)


class CondaIOError(CondaError, IOError):
    def __init__(self, message, *args):
        msg = f"{message}"
        super().__init__(msg)


class CondaFileIOError(CondaIOError):
    def __init__(self, filepath, message, *args):
        self.filepath = filepath

        msg = f"'{filepath}'. {message}"
        super().__init__(msg, *args)


class CondaKeyError(CondaError, KeyError):
    def __init__(self, key, message, *args):
        self.key = key
        self.msg = f"{key!r}: {message}"
        super().__init__(self.msg, *args)


class ChannelError(CondaError):
    pass


class ChannelNotAllowed(ChannelError):
    warning = "Channel not included in allowlist"

    def __init__(self, channel):
        channel_name = channel.name
        channel_url = maybe_unquote(channel.base_url)
        message = dals(
            """
        %(warning)s:
          channel name: %(channel_name)s
          channel url: %(channel_url)s
        """
        )
        super().__init__(
            message,
            channel_url=channel_url,
            channel_name=channel_name,
            warning=self.warning,
        )


class ChannelDenied(ChannelNotAllowed):
    warning = "Channel included in denylist"


class UnavailableInvalidChannel(ChannelError):
    status_code: str | int

    def __init__(
        self, channel, status_code, response: requests.models.Response | None = None
    ):
        # parse channel
        channel = Channel(channel)
        channel_name = channel.name
        channel_url = maybe_unquote(channel.base_url)

        # define hardcoded/default reason/message
        reason = getattr(response, "reason", None)
        message = dals(
            """
            The channel is not accessible or is invalid.

            You will need to adjust your conda configuration to proceed.
            Use `conda config --show channels` to view your configuration's current state,
            and use `conda config --show-sources` to view config file locations.
            """
        )
        if channel.scheme == "file":
            url = join_url(channel.location, channel.name)
            message += dedent(
                f"""
                As of conda 4.3, a valid channel must contain a `noarch/repodata.json` and
                associated `noarch/repodata.json.bz2` file, even if `noarch/repodata.json` is
                empty. Use `conda index {url}`, or create `noarch/repodata.json`
                and associated `noarch/repodata.json.bz2`.
                """
            )

        # if response includes a valid json body we prefer the reason/message defined there
        try:
            body = response.json()
        except (AttributeError, JSONDecodeError):
            body = {}
        else:
            reason = body.get("reason", None) or reason
            message = body.get("message", None) or message

        # standardize arguments
        status_code = status_code or "000"
        reason = reason or "UNAVAILABLE OR INVALID"
        if isinstance(reason, str):
            reason = reason.upper()

        self.status_code = status_code

        super().__init__(
            f"HTTP {status_code} {reason} for channel {channel_name} <{channel_url}>\n\n{message}",
            channel_name=channel_name,
            channel_url=channel_url,
            status_code=status_code,
            reason=reason,
            response_details=stringify(response, content_max_len=1024) or "",
            json=body,
        )


class OperationNotAllowed(CondaError):
    def __init__(self, message):
        super().__init__(message)


class CondaImportError(CondaError, ImportError):
    def __init__(self, message):
        msg = f"{message}"
        super().__init__(msg)


class ParseError(CondaError):
    def __init__(self, message):
        msg = f"{message}"
        super().__init__(msg)


class CouldntParseError(ParseError):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(self.args[0])


class ChecksumMismatchError(CondaError):
    def __init__(
        self, url, target_full_path, checksum_type, expected_checksum, actual_checksum
    ):
        message = dals(
            """
        Conda detected a mismatch between the expected content and downloaded content
        for url '%(url)s'.
          download saved to: %(target_full_path)s
          expected %(checksum_type)s: %(expected_checksum)s
          actual %(checksum_type)s: %(actual_checksum)s
        """
        )
        url = maybe_unquote(url)
        super().__init__(
            message,
            url=url,
            target_full_path=target_full_path,
            checksum_type=checksum_type,
            expected_checksum=expected_checksum,
            actual_checksum=actual_checksum,
        )


class PackageNotInstalledError(CondaError):
    def __init__(self, prefix, package_name):
        message = dals(
            """
        Package is not installed in prefix.
          prefix: %(prefix)s
          package name: %(package_name)s
        """
        )
        super().__init__(message, prefix=prefix, package_name=package_name)


class CondaHTTPError(CondaError):
    def __init__(
        self,
        message,
        url,
        status_code,
        reason,
        elapsed_time,
        response=None,
        caused_by=None,
    ):
        # if response includes a valid json body we prefer the reason/message defined there
        try:
            body = response.json()
        except (AttributeError, JSONDecodeError):
            body = {}
        else:
            reason = body.get("reason", None) or reason
            message = body.get("message", None) or message

        # standardize arguments
        url = maybe_unquote(url)
        status_code = status_code or "000"
        reason = reason or "CONNECTION FAILED"
        if isinstance(reason, str):
            reason = reason.upper()
        elapsed_time = elapsed_time or "-"
        if isinstance(elapsed_time, timedelta):
            elapsed_time = str(elapsed_time).split(":", 1)[-1]

        # extract CF-RAY
        try:
            cf_ray = response.headers["CF-RAY"]
        except (AttributeError, KeyError):
            cf_ray = ""
        else:
            cf_ray = f"CF-RAY: {cf_ray}\n"

        super().__init__(
            dals(
                f"""
                HTTP {status_code} {reason} for url <{url}>
                Elapsed: {elapsed_time}
                {cf_ray}
                """
            )
            # since message may include newlines don't include in f-string/dals above
            + message,
            url=url,
            status_code=status_code,
            reason=reason,
            elapsed_time=elapsed_time,
            response_details=stringify(response, content_max_len=1024) or "",
            json=body,
            caused_by=caused_by,
        )


class CondaSSLError(CondaError):
    pass


class AuthenticationError(CondaError):
    pass


class PackagesNotFoundError(CondaError):
    def __init__(self, packages, channel_urls=()):
        format_list = lambda iterable: "  - " + "\n  - ".join(str(x) for x in iterable)

        if channel_urls:
            message = dals(
                """
            The following packages are not available from current channels:

            %(packages_formatted)s

            Current channels:

            %(channels_formatted)s

            To search for alternate channels that may provide the conda package you're
            looking for, navigate to

                https://anaconda.org

            and use the search bar at the top of the page.
            """
            )
            from .base.context import context

            if context.use_only_tar_bz2:
                message += dals(
                    """
                Note: 'use_only_tar_bz2' is enabled. This might be omitting some
                packages from the index. Set this option to 'false' and retry.
                """
                )
            packages_formatted = format_list(packages)
            channels_formatted = format_list(channel_urls)
        else:
            message = dals(
                """
            The following packages are missing from the target environment:
            %(packages_formatted)s
            """
            )
            packages_formatted = format_list(packages)
            channels_formatted = ()

        super().__init__(
            message,
            packages=packages,
            packages_formatted=packages_formatted,
            channel_urls=channel_urls,
            channels_formatted=channels_formatted,
        )


class UnsatisfiableError(CondaError):
    """An exception to report unsatisfiable dependencies.

    Args:
        bad_deps: a list of tuples of objects (likely MatchSpecs).
        chains: (optional) if True, the tuples are interpreted as chains
            of dependencies, from top level to bottom. If False, the tuples
            are interpreted as simple lists of conflicting specs.

    Returns:
        Raises an exception with a formatted message detailing the
        unsatisfiable specifications.
    """

    def _format_chain_str(self, bad_deps):
        chains = {}
        for dep in sorted(bad_deps, key=len, reverse=True):
            dep1 = [s.partition(" ") for s in dep[1:]]
            key = (dep[0],) + tuple(v[0] for v in dep1)
            vals = ("",) + tuple(v[2] for v in dep1)
            found = False
            for key2, csets in chains.items():
                if key2[: len(key)] == key:
                    for cset, val in zip(csets, vals):
                        cset.add(val)
                    found = True
            if not found:
                chains[key] = [{val} for val in vals]
        for key, csets in chains.items():
            deps = []
            for name, cset in zip(key, csets):
                if "" not in cset:
                    pass
                elif len(cset) == 1:
                    cset.clear()
                else:
                    cset.remove("")
                    cset.add("*")
                if name[0] == "@":
                    name = "feature:" + name[1:]
                deps.append(
                    "{} {}".format(name, "|".join(sorted(cset))) if cset else name
                )
            chains[key] = " -> ".join(deps)
        return [chains[key] for key in sorted(chains.keys())]

    def __init__(self, bad_deps, chains=True, strict=False):
        from .models.match_spec import MatchSpec

        messages = {
            "python": dals(
                """

The following specifications were found
to be incompatible with the existing python installation in your environment:

Specifications:\n{specs}

Your python: {ref}

If python is on the left-most side of the chain, that's the version you've asked for.
When python appears to the right, that indicates that the thing on the left is somehow
not available for the python version you are constrained to. Note that conda will not
change your python version to a different minor version unless you explicitly specify
that.

        """
            ),
            "request_conflict_with_history": dals(
                """

The following specifications were found to be incompatible with a past
explicit spec that is not an explicit spec in this operation ({ref}):\n{specs}

                    """
            ),
            "direct": dals(
                """

The following specifications were found to be incompatible with each other:
                    """
            ),
            "virtual_package": dals(
                """

The following specifications were found to be incompatible with your system:\n{specs}

Your installed version is: {ref}
"""
            ),
        }

        msg = ""
        self.unsatisfiable = []
        if len(bad_deps) == 0:
            msg += """
Did not find conflicting dependencies. If you would like to know which
packages conflict ensure that you have enabled unsatisfiable hints.

conda config --set unsatisfiable_hints True
            """
        else:
            for class_name, dep_class in bad_deps.items():
                if dep_class:
                    _chains = []
                    if class_name == "direct":
                        msg += messages["direct"]
                        last_dep_entry = {d[0][-1].name for d in dep_class}
                        dep_constraint_map = {}
                        for dep in dep_class:
                            if dep[0][-1].name in last_dep_entry:
                                if not dep_constraint_map.get(dep[0][-1].name):
                                    dep_constraint_map[dep[0][-1].name] = []
                                dep_constraint_map[dep[0][-1].name].append(dep[0])
                        msg += "\nOutput in format: Requested package -> Available versions"
                        for dep, chain in dep_constraint_map.items():
                            if len(chain) > 1:
                                msg += f"\n\nPackage {dep} conflicts for:\n"
                                msg += "\n".join(
                                    [" -> ".join([str(i) for i in c]) for c in chain]
                                )
                                self.unsatisfiable += [
                                    tuple(entries) for entries in chain
                                ]
                    else:
                        for dep_chain, installed_blocker in dep_class:
                            # Remove any target values from the MatchSpecs, convert to strings
                            dep_chain = [
                                str(MatchSpec(dep, target=None)) for dep in dep_chain
                            ]
                            _chains.append(dep_chain)

                        if _chains:
                            _chains = self._format_chain_str(_chains)
                        else:
                            _chains = [", ".join(c) for c in _chains]
                        msg += messages[class_name].format(
                            specs=dashlist(_chains), ref=installed_blocker
                        )
        if strict:
            msg += (
                "\nNote that strict channel priority may have removed "
                "packages required for satisfiability."
            )

        super().__init__(msg)


class RemoveError(CondaError):
    def __init__(self, message):
        msg = f"{message}"
        super().__init__(msg)


class DisallowedPackageError(CondaError):
    def __init__(self, package_ref, **kwargs):
        from .models.records import PackageRecord

        package_ref = PackageRecord.from_objects(package_ref)
        message = (
            "The package '%(dist_str)s' is disallowed by configuration.\n"
            "See 'conda config --show disallowed_packages'."
        )
        super().__init__(
            message, package_ref=package_ref, dist_str=package_ref.dist_str(), **kwargs
        )


class SpecsConfigurationConflictError(CondaError):
    def __init__(self, requested_specs, pinned_specs, prefix):
        message = dals(
            """
        Requested specs conflict with configured specs.
          requested specs: {requested_specs_formatted}
          pinned specs: {pinned_specs_formatted}
        Use 'conda config --show-sources' to look for 'pinned_specs' and 'track_features'
        configuration parameters.  Pinned specs may also be defined in the file
        {pinned_specs_path}.
        """
        ).format(
            requested_specs_formatted=dashlist(requested_specs, 4),
            pinned_specs_formatted=dashlist(pinned_specs, 4),
            pinned_specs_path=join(prefix, "conda-meta", "pinned"),
        )
        super().__init__(
            message,
            requested_specs=requested_specs,
            pinned_specs=pinned_specs,
            prefix=prefix,
        )


class CondaIndexError(CondaError, IndexError):
    def __init__(self, message):
        msg = f"{message}"
        super().__init__(msg)


class CondaValueError(CondaError, ValueError):
    def __init__(self, message, *args, **kwargs):
        super().__init__(message, *args, **kwargs)


class CyclicalDependencyError(CondaError, ValueError):
    def __init__(self, packages_with_cycles, **kwargs):
        from .models.records import PackageRecord

        packages_with_cycles = tuple(
            PackageRecord.from_objects(p) for p in packages_with_cycles
        )
        message = f"Cyclic dependencies exist among these items: {dashlist(p.dist_str() for p in packages_with_cycles)}"
        super().__init__(message, packages_with_cycles=packages_with_cycles, **kwargs)


class CorruptedEnvironmentError(CondaError):
    def __init__(self, environment_location, corrupted_file, **kwargs):
        message = dals(
            """
        The target environment has been corrupted. Corrupted environments most commonly
        occur when the conda process is force-terminated while in an unlink-link
        transaction.
          environment location: %(environment_location)s
          corrupted file: %(corrupted_file)s
        """
        )
        super().__init__(
            message,
            environment_location=environment_location,
            corrupted_file=corrupted_file,
            **kwargs,
        )


class CondaHistoryError(CondaError):
    def __init__(self, message):
        msg = f"{message}"
        super().__init__(msg)


class CondaUpgradeError(CondaError):
    def __init__(self, message):
        msg = f"{message}"
        super().__init__(msg)


class CondaVerificationError(CondaError):
    def __init__(self, message):
        super().__init__(message)


class SafetyError(CondaError):
    def __init__(self, message):
        super().__init__(message)


class CondaMemoryError(CondaError, MemoryError):
    def __init__(self, caused_by, **kwargs):
        message = "The conda process ran out of memory. Increase system memory and/or try again."
        super().__init__(message, caused_by=caused_by, **kwargs)


class NotWritableError(CondaError, OSError):
    def __init__(self, path, errno, **kwargs):
        kwargs.update(
            {
                "path": path,
                "errno": errno,
            }
        )
        if on_win:
            message = dals(
                """
            The current user does not have write permissions to a required path.
              path: %(path)s
            """
            )
        else:
            message = dals(
                """
            The current user does not have write permissions to a required path.
              path: %(path)s
              uid: %(uid)s
              gid: %(gid)s

            If you feel that permissions on this path are set incorrectly, you can manually
            change them by executing

              $ sudo chown %(uid)s:%(gid)s %(path)s

            In general, it's not advisable to use 'sudo conda'.
            """
            )
            kwargs.update(
                {
                    "uid": os.geteuid(),
                    "gid": os.getegid(),
                }
            )
        super().__init__(message, **kwargs)
        self.errno = errno


class NoWritableEnvsDirError(CondaError):
    def __init__(self, envs_dirs, **kwargs):
        message = f"No writeable envs directories configured.{dashlist(envs_dirs)}"
        super().__init__(message, envs_dirs=envs_dirs, **kwargs)


class NoWritablePkgsDirError(CondaError):
    def __init__(self, pkgs_dirs, **kwargs):
        message = f"No writeable pkgs directories configured.{dashlist(pkgs_dirs)}"
        super().__init__(message, pkgs_dirs=pkgs_dirs, **kwargs)


class EnvironmentNotWritableError(CondaError):
    def __init__(self, environment_location, **kwargs):
        kwargs.update(
            {
                "environment_location": environment_location,
            }
        )
        if on_win:
            message = dals(
                """
            The current user does not have write permissions to the target environment.
              environment location: %(environment_location)s
            """
            )
        else:
            message = dals(
                """
            The current user does not have write permissions to the target environment.
              environment location: %(environment_location)s
              uid: %(uid)s
              gid: %(gid)s
            """
            )
            kwargs.update(
                {
                    "uid": os.geteuid(),
                    "gid": os.getegid(),
                }
            )
        super().__init__(message, **kwargs)


class CondaDependencyError(CondaError):
    def __init__(self, message):
        super().__init__(message)


class BinaryPrefixReplacementError(CondaError):
    def __init__(
        self, path, placeholder, new_prefix, original_data_length, new_data_length
    ):
        message = dals(
            """
        Refusing to replace mismatched data length in binary file.
          path: %(path)s
          placeholder: %(placeholder)s
          new prefix: %(new_prefix)s
          original data Length: %(original_data_length)d
          new data length: %(new_data_length)d
        """
        )
        kwargs = {
            "path": path,
            "placeholder": placeholder,
            "new_prefix": new_prefix,
            "original_data_length": original_data_length,
            "new_data_length": new_data_length,
        }
        super().__init__(message, **kwargs)


class InvalidSpec(CondaError, ValueError):
    def __init__(self, message: str, **kwargs):
        super().__init__(message, **kwargs)


class InvalidVersionSpec(InvalidSpec):
    def __init__(self, invalid_spec: str, details: str):
        message = "Invalid version '%(invalid_spec)s': %(details)s"
        super().__init__(message, invalid_spec=invalid_spec, details=details)


class InvalidMatchSpec(InvalidSpec):
    def __init__(self, invalid_spec: str, details: str):
        message = "Invalid spec '%(invalid_spec)s': %(details)s"
        super().__init__(message, invalid_spec=invalid_spec, details=details)


class EncodingError(CondaError):
    def __init__(self, caused_by, **kwargs):
        message = (
            dals(
                """
        A unicode encoding or decoding error has occurred.
        Python 2 is the interpreter under which conda is running in your base environment.
        Replacing your base environment with one having Python 3 may help resolve this issue.
        If you still have a need for Python 2 environments, consider using 'conda create'
        and 'conda activate'.  For example:

            $ conda create -n py2 python=2
            $ conda activate py2

        Error details: %r

        """
            )
            % caused_by
        )
        super().__init__(message, caused_by=caused_by, **kwargs)


class NoSpaceLeftError(CondaError):
    def __init__(self, caused_by, **kwargs):
        message = "No space left on devices."
        super().__init__(message, caused_by=caused_by, **kwargs)


class CondaEnvException(CondaError):
    def __init__(self, message, *args, **kwargs):
        msg = f"{message}"
        super().__init__(msg, *args, **kwargs)


class EnvironmentFileNotFound(CondaEnvException):
    def __init__(self, filename, *args, **kwargs):
        msg = f"'{filename}' file not found"
        self.filename = filename
        super().__init__(msg, *args, **kwargs)


class EnvironmentFileExtensionNotValid(CondaEnvException):
    def __init__(self, filename, *args, **kwargs):
        msg = f"'{filename}' file extension must be one of '.txt', '.yaml' or '.yml'"
        self.filename = filename
        super().__init__(msg, *args, **kwargs)


class EnvironmentFileEmpty(CondaEnvException):
    def __init__(self, filename, *args, **kwargs):
        self.filename = filename
        msg = f"'{filename}' is empty"
        super().__init__(msg, *args, **kwargs)


class EnvironmentFileNotDownloaded(CondaError):
    def __init__(self, username, packagename, *args, **kwargs):
        msg = f"{username}/{packagename} file not downloaded"
        self.username = username
        self.packagename = packagename
        super().__init__(msg, *args, **kwargs)


class SpecNotFound(CondaError):
    def __init__(self, msg, *args, **kwargs):
        super().__init__(msg, *args, **kwargs)


class PluginError(CondaError):
    pass


def maybe_raise(error, context):
    if isinstance(error, CondaMultiError):
        groups = groupby(lambda e: isinstance(e, ClobberError), error.errors)
        clobber_errors = groups.get(True, ())
        groups = groupby(lambda e: isinstance(e, SafetyError), groups.get(False, ()))
        safety_errors = groups.get(True, ())
        other_errors = groups.get(False, ())

        if (
            (safety_errors and context.safety_checks == SafetyChecks.enabled)
            or (
                clobber_errors
                and context.path_conflict == PathConflict.prevent
                and not context.clobber
            )
            or other_errors
        ):
            raise error
        elif (safety_errors and context.safety_checks == SafetyChecks.warn) or (
            clobber_errors
            and context.path_conflict == PathConflict.warn
            and not context.clobber
        ):
            print_conda_exception(error)

    elif isinstance(error, ClobberError):
        if context.path_conflict == PathConflict.prevent and not context.clobber:
            raise error
        elif context.path_conflict == PathConflict.warn and not context.clobber:
            print_conda_exception(error)

    elif isinstance(error, SafetyError):
        if context.safety_checks == SafetyChecks.enabled:
            raise error
        elif context.safety_checks == SafetyChecks.warn:
            print_conda_exception(error)

    else:
        raise error


def print_conda_exception(exc_val, exc_tb=None):
    from .base.context import context

    rc = getattr(exc_val, "return_code", None)
    if context.debug or (not isinstance(exc_val, DryRunExit) and context.info):
        print(_format_exc(exc_val, exc_tb), file=sys.stderr)
    elif context.json:
        if isinstance(exc_val, DryRunExit):
            return
        logger = getLogger("conda.stdout" if rc else "conda.stderr")
        exc_json = json.dumps(
            exc_val.dump_map(), indent=2, sort_keys=True, cls=EntityEncoder
        )
        logger.info(f"{exc_json}\n")
    else:
        stderrlog = getLogger("conda.stderr")
        stderrlog.error("\n%r\n", exc_val)
        # An alternative which would allow us not to reload sys with newly setdefaultencoding()
        # is to not use `%r`, e.g.:
        # Still, not being able to use `%r` seems too great a price to pay.
        # stderrlog.error("\n" + exc_val.__repr__() + \n")


def _format_exc(exc_val=None, exc_tb=None):
    if exc_val is None:
        exc_type, exc_val, exc_tb = sys.exc_info()
    else:
        exc_type = type(exc_val)
    if exc_tb:
        formatted_exception = format_exception(exc_type, exc_val, exc_tb)
    else:
        formatted_exception = format_exception_only(exc_type, exc_val)
    return "".join(formatted_exception)


class InvalidInstaller(Exception):
    def __init__(self, name):
        msg = f"Unable to load installer for {name}"
        super().__init__(msg)
