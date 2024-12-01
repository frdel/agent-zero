# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Conda activate and deactivate logic.

Implementation for all shell interface logic exposed via
`conda shell.* [activate|deactivate|reactivate|hook|commands]`. This includes a custom argument
parser, an abstract shell class, and special path handling for Windows.

See conda.cli.main.main_sourced for the entry point into this module.
"""

from __future__ import annotations

import abc
import json
import os
import re
import sys
from logging import getLogger
from os.path import (
    abspath,
    basename,
    dirname,
    exists,
    expanduser,
    expandvars,
    isdir,
    join,
)
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING

# Since we have to have configuration context here, anything imported by
#   conda.base.context is fair game, but nothing more.
from . import CONDA_PACKAGE_ROOT, CONDA_SOURCE_ROOT
from .auxlib.compat import Utf8NamedTemporaryFile
from .base.constants import (
    CONDA_ENV_VARS_UNSET_VAR,
    PACKAGE_ENV_VARS_DIR,
    PREFIX_STATE_FILE,
)
from .base.context import ROOT_ENV_NAME, context, locate_prefix_by_name
from .common.compat import on_win
from .common.path import _cygpath, paths_equal, unix_path_to_win, win_path_to_unix
from .common.path import path_identity as _path_identity
from .deprecations import deprecated

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

log = getLogger(__name__)


class _Activator(metaclass=abc.ABCMeta):
    # Activate and deactivate have three tasks
    #   1. Set and unset environment variables
    #   2. Execute/source activate.d/deactivate.d scripts
    #   3. Update the command prompt
    #
    # Shells should also use 'reactivate' following conda's install, update, and
    #   remove/uninstall commands.
    #
    # All core logic is in build_activate() or build_deactivate(), and is independent of
    # shell type.  Each returns a map containing the keys:
    #   export_vars
    #   unset_var
    #   activate_scripts
    #   deactivate_scripts
    #
    # The value of the CONDA_PROMPT_MODIFIER environment variable holds conda's contribution
    #   to the command prompt.
    #
    # To implement support for a new shell, ideally one would only need to add shell-specific
    # information to the __init__ method of this class.

    # The following instance variables must be defined by each implementation.
    pathsep_join: str
    sep: str
    path_conversion: Callable[
        [str | Iterable[str] | None], str | tuple[str, ...] | None
    ]
    script_extension: str
    #: temporary file's extension, None writes to stdout instead
    tempfile_extension: str | None
    command_join: str

    unset_var_tmpl: str
    export_var_tmpl: str
    set_var_tmpl: str
    run_script_tmpl: str

    hook_source_path: Path | None

    def __init__(self, arguments=None):
        self._raw_arguments = arguments

    def get_export_unset_vars(self, export_metavars=True, **kwargs):
        """
        :param export_metavars: whether to export `conda_exe_vars` meta variables.
        :param kwargs: environment variables to export.
            .. if you pass and set any other variable to None, then it
            emits it to the dict with a value of None.

        :return: A dict of env vars to export ordered the same way as kwargs.
            And a list of env vars to unset.
        """
        unset_vars = []
        export_vars = {}

        # split provided environment variables into exports vs unsets
        for name, value in kwargs.items():
            if value is None:
                if context.envvars_force_uppercase:
                    unset_vars.append(name.upper())
                else:
                    unset_vars.append(name)

            else:
                if context.envvars_force_uppercase:
                    export_vars[name.upper()] = value
                else:
                    export_vars[name] = value

        if export_metavars:
            # split meta variables into exports vs unsets
            for name, value in context.conda_exe_vars_dict.items():
                if value is None:
                    if context.envvars_force_uppercase:
                        unset_vars.append(name.upper())
                    else:
                        unset_vars.append(name)
                elif "/" in value or "\\" in value:
                    if context.envvars_force_uppercase:
                        export_vars[name.upper()] = self.path_conversion(value)
                    else:
                        export_vars[name] = self.path_conversion(value)
                else:
                    if context.envvars_force_uppercase:
                        export_vars[name.upper()] = value
                    else:
                        export_vars[name] = value
        else:
            # unset all meta variables
            unset_vars.extend(context.conda_exe_vars_dict)

        return export_vars, unset_vars

    @deprecated(
        "24.9",
        "25.3",
        addendum="Use `conda.activate._Activator.get_export_unset_vars` instead.",
    )
    def add_export_unset_vars(self, export_vars, unset_vars, **kwargs):
        new_export_vars, new_unset_vars = self.get_export_unset_vars(**kwargs)
        return {
            {**(export_vars or {}), **new_export_vars},
            [*(unset_vars or []), *new_unset_vars],
        }

    @deprecated("24.9", "25.3", addendum="For testing only. Moved to test suite.")
    def get_scripts_export_unset_vars(self, **kwargs) -> tuple[str, str]:
        export_vars, unset_vars = self.get_export_unset_vars(**kwargs)
        return (
            self.command_join.join(
                self.export_var_tmpl % (k, v) for k, v in (export_vars or {}).items()
            ),
            self.command_join.join(
                self.unset_var_tmpl % (k) for k in (unset_vars or [])
            ),
        )

    def _finalize(self, commands, ext):
        commands = (*commands, "")  # add terminating newline
        if ext is None:
            return self.command_join.join(commands)
        elif ext:
            with Utf8NamedTemporaryFile("w+", suffix=ext, delete=False) as tf:
                # the default mode is 'w+b', and universal new lines don't work in that mode
                # command_join should account for that
                tf.write(self.command_join.join(commands))
            return tf.name
        else:
            raise NotImplementedError()

    def activate(self):
        if self.stack:
            builder_result = self.build_stack(self.env_name_or_prefix)
        else:
            builder_result = self.build_activate(self.env_name_or_prefix)
        return self._finalize(
            self._yield_commands(builder_result), self.tempfile_extension
        )

    def deactivate(self):
        return self._finalize(
            self._yield_commands(self.build_deactivate()), self.tempfile_extension
        )

    def reactivate(self):
        return self._finalize(
            self._yield_commands(self.build_reactivate()), self.tempfile_extension
        )

    def hook(self, auto_activate_base: bool | None = None) -> str:
        builder: list[str] = []
        if preamble := self._hook_preamble():
            builder.append(preamble)
        if self.hook_source_path:
            builder.append(self.hook_source_path.read_text())
        if (
            auto_activate_base is None
            and context.auto_activate_base
            or auto_activate_base
        ):
            builder.append("conda activate base\n")
        postamble = self._hook_postamble()
        if postamble is not None:
            builder.append(postamble)
        return "\n".join(builder)

    def execute(self):
        # return value meant to be written to stdout
        self._parse_and_set_args(self._raw_arguments)

        # invoke pre/post commands, see conda.cli.conda_argparse.do_call
        context.plugin_manager.invoke_pre_commands(self.command)
        response = getattr(self, self.command)()
        context.plugin_manager.invoke_post_commands(self.command)
        return response

    @deprecated(
        "25.3",
        "25.9",
        addendum="Use `conda commands` instead.",
        # these commands are already pretty hidden in their implementation and access (`conda shell.posix commands`)
        # so we opt to not warn end users that this is going away, we only need to notify tab-completion devs
        # deprecation_type=FutureWarning,
    )
    def commands(self):
        """
        Returns a list of possible subcommands that are valid
        immediately following `conda` at the command line.
        This method is generally only used by tab-completion.
        """
        # Import locally to reduce impact on initialization time.
        from .cli.conda_argparse import find_builtin_commands, generate_parser
        from .cli.find_commands import find_commands

        # return value meant to be written to stdout
        # Hidden commands to provide metadata to shells.
        return "\n".join(
            sorted(
                {
                    *find_builtin_commands(generate_parser()),
                    *find_commands(True),
                }
            )
        )

    @abc.abstractmethod
    def _hook_preamble(self) -> str | None:
        # must be implemented in subclass
        raise NotImplementedError

    def _hook_postamble(self) -> str | None:
        return None

    def _parse_and_set_args(self, arguments):
        def raise_invalid_command_error(actual_command=None):
            from .exceptions import ArgumentError

            message = (
                "'activate', 'deactivate', 'hook', 'commands', or 'reactivate' "
                "command must be given"
            )
            if actual_command:
                message += f". Instead got '{actual_command}'."
            raise ArgumentError(message)

        if arguments is None or len(arguments) < 1:
            raise_invalid_command_error()

        command, *arguments = arguments
        help_flags = ("-h", "--help", "/?")
        non_help_args = tuple(arg for arg in arguments if arg not in help_flags)
        help_requested = len(arguments) != len(non_help_args)
        remainder_args = list(arg for arg in non_help_args if arg and arg != command)

        if not command:
            raise_invalid_command_error()
        elif help_requested:
            from .exceptions import ActivateHelp, DeactivateHelp, GenericHelp

            help_classes = {
                "activate": ActivateHelp(),
                "deactivate": DeactivateHelp(),
                "hook": GenericHelp("hook"),
                "commands": GenericHelp("commands"),
                "reactivate": GenericHelp("reactivate"),
            }
            raise help_classes[command]
        elif command not in (
            "activate",
            "deactivate",
            "reactivate",
            "hook",
            "commands",
        ):
            raise_invalid_command_error(actual_command=command)

        if command.endswith("activate") or command == "hook":
            try:
                dev_idx = remainder_args.index("--dev")
            except ValueError:
                context.dev = False
            else:
                del remainder_args[dev_idx]
                context.dev = True

        if command == "activate":
            self.stack = context.auto_stack and context.shlvl <= context.auto_stack
            try:
                stack_idx = remainder_args.index("--stack")
            except ValueError:
                stack_idx = -1
            try:
                no_stack_idx = remainder_args.index("--no-stack")
            except ValueError:
                no_stack_idx = -1
            if stack_idx >= 0 and no_stack_idx >= 0:
                from .exceptions import ArgumentError

                raise ArgumentError(
                    "cannot specify both --stack and --no-stack to " + command
                )
            if stack_idx >= 0:
                self.stack = True
                del remainder_args[stack_idx]
            if no_stack_idx >= 0:
                self.stack = False
                del remainder_args[no_stack_idx]
            if len(remainder_args) > 1:
                from .exceptions import ArgumentError

                raise ArgumentError(
                    command
                    + " does not accept more than one argument:\n"
                    + str(remainder_args)
                    + "\n"
                )
            self.env_name_or_prefix = remainder_args and remainder_args[0] or "base"

        else:
            if remainder_args:
                from .exceptions import ArgumentError

                raise ArgumentError(
                    f"{command} does not accept arguments\nremainder_args: {remainder_args}\n"
                )

        self.command = command

    def _yield_commands(self, cmds_dict):
        for key, value in sorted(cmds_dict.get("export_path", {}).items()):
            yield self.export_var_tmpl % (key, value)

        for script in cmds_dict.get("deactivate_scripts", ()):
            yield self.run_script_tmpl % script

        for key in cmds_dict.get("unset_vars", ()):
            yield self.unset_var_tmpl % key

        for key, value in cmds_dict.get("set_vars", {}).items():
            yield self.set_var_tmpl % (key, value)

        for key, value in cmds_dict.get("export_vars", {}).items():
            yield self.export_var_tmpl % (key, value)

        for script in cmds_dict.get("activate_scripts", ()):
            yield self.run_script_tmpl % script

    def build_activate(self, env_name_or_prefix):
        return self._build_activate_stack(env_name_or_prefix, False)

    def build_stack(self, env_name_or_prefix):
        return self._build_activate_stack(env_name_or_prefix, True)

    def _build_activate_stack(self, env_name_or_prefix, stack):
        # get environment prefix
        if re.search(r"\\|/", env_name_or_prefix):
            prefix = expand(env_name_or_prefix)
            if not isdir(join(prefix, "conda-meta")):
                from .exceptions import EnvironmentLocationNotFound

                raise EnvironmentLocationNotFound(prefix)
        elif env_name_or_prefix in (ROOT_ENV_NAME, "root"):
            prefix = context.root_prefix
        else:
            prefix = locate_prefix_by_name(env_name_or_prefix)

        # get prior shlvl and prefix
        old_conda_shlvl = int(os.getenv("CONDA_SHLVL", "").strip() or 0)
        old_conda_prefix = os.getenv("CONDA_PREFIX")

        # if the prior active prefix is this prefix we are actually doing a reactivate
        if old_conda_prefix == prefix and old_conda_shlvl > 0:
            return self.build_reactivate()

        activate_scripts = self._get_activate_scripts(prefix)
        conda_shlvl = old_conda_shlvl + 1
        conda_default_env = self._default_env(prefix)
        conda_prompt_modifier = self._prompt_modifier(prefix, conda_default_env)
        env_vars = {
            name: value
            for name, value in self._get_environment_env_vars(prefix).items()
            if value != CONDA_ENV_VARS_UNSET_VAR
        }

        # get clobbered environment variables
        clobber_vars = set(env_vars).intersection(os.environ)
        overwritten_clobber_vars = [
            clobber_var
            for clobber_var in clobber_vars
            if os.getenv(clobber_var) != env_vars[clobber_var]
        ]
        if overwritten_clobber_vars:
            print(
                "WARNING: overwriting environment variables set in the machine",
                file=sys.stderr,
            )
            print(f"overwriting variable {overwritten_clobber_vars}", file=sys.stderr)
        for name in clobber_vars:
            env_vars[f"__CONDA_SHLVL_{old_conda_shlvl}_{name}"] = os.getenv(name)

        if old_conda_shlvl == 0:
            export_vars, unset_vars = self.get_export_unset_vars(
                path=self.pathsep_join(self._add_prefix_to_path(prefix)),
                conda_prefix=prefix,
                conda_shlvl=conda_shlvl,
                conda_default_env=conda_default_env,
                conda_prompt_modifier=conda_prompt_modifier,
                **env_vars,
            )
            deactivate_scripts = ()
        elif stack:
            export_vars, unset_vars = self.get_export_unset_vars(
                path=self.pathsep_join(self._add_prefix_to_path(prefix)),
                conda_prefix=prefix,
                conda_shlvl=conda_shlvl,
                conda_default_env=conda_default_env,
                conda_prompt_modifier=conda_prompt_modifier,
                **env_vars,
                **{
                    f"CONDA_PREFIX_{old_conda_shlvl}": old_conda_prefix,
                    f"CONDA_STACKED_{conda_shlvl}": "true",
                },
            )
            deactivate_scripts = ()
        else:
            export_vars, unset_vars = self.get_export_unset_vars(
                path=self.pathsep_join(
                    self._replace_prefix_in_path(old_conda_prefix, prefix)
                ),
                conda_prefix=prefix,
                conda_shlvl=conda_shlvl,
                conda_default_env=conda_default_env,
                conda_prompt_modifier=conda_prompt_modifier,
                **env_vars,
                **{
                    f"CONDA_PREFIX_{old_conda_shlvl}": old_conda_prefix,
                },
            )
            deactivate_scripts = self._get_deactivate_scripts(old_conda_prefix)

        set_vars = {}
        if context.changeps1:
            self._update_prompt(set_vars, conda_prompt_modifier)

        return {
            "unset_vars": unset_vars,
            "set_vars": set_vars,
            "export_vars": export_vars,
            "deactivate_scripts": deactivate_scripts,
            "activate_scripts": activate_scripts,
        }

    def build_deactivate(self):
        self._deactivate = True
        # query environment
        old_conda_prefix = os.getenv("CONDA_PREFIX")
        old_conda_shlvl = int(os.getenv("CONDA_SHLVL", "").strip() or 0)
        if not old_conda_prefix or old_conda_shlvl < 1:
            # no active environment, so cannot deactivate; do nothing
            return {
                "unset_vars": (),
                "set_vars": {},
                "export_vars": {},
                "deactivate_scripts": (),
                "activate_scripts": (),
            }
        deactivate_scripts = self._get_deactivate_scripts(old_conda_prefix)
        old_conda_environment_env_vars = self._get_environment_env_vars(
            old_conda_prefix
        )

        new_conda_shlvl = old_conda_shlvl - 1
        set_vars = {}
        if old_conda_shlvl == 1:
            new_path = self.pathsep_join(
                self._remove_prefix_from_path(old_conda_prefix)
            )
            # You might think that you can remove the CONDA_EXE vars with export_metavars=False
            # here so that "deactivate means deactivate" but you cannot since the conda shell
            # scripts still refer to them and they only set them once at the top. We could change
            # that though, the conda() shell function could set them instead of doing it at the
            # top.  This would be *much* cleaner. I personally cannot abide that I have
            # deactivated conda and anything at all in my env still references it (apart from the
            # shell script, we need something I suppose!)
            export_vars, unset_vars = self.get_export_unset_vars(
                conda_prefix=None,
                conda_shlvl=new_conda_shlvl,
                conda_default_env=None,
                conda_prompt_modifier=None,
            )
            conda_prompt_modifier = ""
            activate_scripts = ()
            export_path = {"PATH": new_path}
        else:
            assert old_conda_shlvl > 1
            new_prefix = os.getenv("CONDA_PREFIX_%d" % new_conda_shlvl)
            conda_default_env = self._default_env(new_prefix)
            conda_prompt_modifier = self._prompt_modifier(new_prefix, conda_default_env)
            new_conda_environment_env_vars = self._get_environment_env_vars(new_prefix)

            old_prefix_stacked = "CONDA_STACKED_%d" % old_conda_shlvl in os.environ
            new_path = ""

            unset_vars = ["CONDA_PREFIX_%d" % new_conda_shlvl]
            if old_prefix_stacked:
                new_path = self.pathsep_join(
                    self._remove_prefix_from_path(old_conda_prefix)
                )
                unset_vars.append("CONDA_STACKED_%d" % old_conda_shlvl)
            else:
                new_path = self.pathsep_join(
                    self._replace_prefix_in_path(old_conda_prefix, new_prefix)
                )

            export_vars, unset_vars2 = self.get_export_unset_vars(
                conda_prefix=new_prefix,
                conda_shlvl=new_conda_shlvl,
                conda_default_env=conda_default_env,
                conda_prompt_modifier=conda_prompt_modifier,
                **new_conda_environment_env_vars,
            )
            unset_vars += unset_vars2
            export_path = {"PATH": new_path}
            activate_scripts = self._get_activate_scripts(new_prefix)

        if context.changeps1:
            self._update_prompt(set_vars, conda_prompt_modifier)

        for env_var in old_conda_environment_env_vars.keys():
            if save_value := os.getenv(f"__CONDA_SHLVL_{new_conda_shlvl}_{env_var}"):
                export_vars[env_var] = save_value
            else:
                unset_vars.append(env_var)
        return {
            "unset_vars": unset_vars,
            "set_vars": set_vars,
            "export_vars": export_vars,
            "export_path": export_path,
            "deactivate_scripts": deactivate_scripts,
            "activate_scripts": activate_scripts,
        }

    def build_reactivate(self):
        self._reactivate = True
        conda_prefix = os.getenv("CONDA_PREFIX")
        conda_shlvl = int(os.getenv("CONDA_SHLVL", "").strip() or 0)
        if not conda_prefix or conda_shlvl < 1:
            # no active environment, so cannot reactivate; do nothing
            return {
                "unset_vars": [],
                "set_vars": {},
                "export_vars": {},
                "deactivate_scripts": (),
                "activate_scripts": (),
            }
        conda_default_env = os.getenv(
            "CONDA_DEFAULT_ENV", self._default_env(conda_prefix)
        )
        new_path = self.pathsep_join(
            self._replace_prefix_in_path(conda_prefix, conda_prefix)
        )
        set_vars = {}
        conda_prompt_modifier = self._prompt_modifier(conda_prefix, conda_default_env)
        if context.changeps1:
            self._update_prompt(set_vars, conda_prompt_modifier)

        export_vars, unset_vars = self.get_export_unset_vars(
            PATH=new_path,
            CONDA_SHLVL=conda_shlvl,
            CONDA_PROMPT_MODIFIER=self._prompt_modifier(
                conda_prefix, conda_default_env
            ),
        )

        # environment variables are set only to aid transition from conda 4.3 to conda 4.4
        return {
            "unset_vars": unset_vars,
            "set_vars": set_vars,
            "export_vars": export_vars,
            "deactivate_scripts": self._get_deactivate_scripts(conda_prefix),
            "activate_scripts": self._get_activate_scripts(conda_prefix),
        }

    def _get_starting_path_list(self):
        # For isolation, running the conda test suite *without* env. var. inheritance
        # every so often is a good idea. We should probably make this a pytest fixture
        # along with one that tests both hardlink-only and copy-only, but before that
        # conda's testsuite needs to be a lot faster!
        clean_paths = {
            "darwin": "/usr/bin:/bin:/usr/sbin:/sbin",
            # You may think 'let us do something more clever here and interpolate
            # `%windir%`' but the point here is the the whole env. is cleaned out
            "win32": "C:\\Windows\\system32;"
            "C:\\Windows;"
            "C:\\Windows\\System32\\Wbem;"
            "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\",
        }
        path = os.getenv(
            "PATH",
            clean_paths[sys.platform] if sys.platform in clean_paths else "/usr/bin",
        )
        path_split = path.split(os.pathsep)
        return path_split

    @deprecated.argument("24.9", "25.3", "extra_library_bin")
    def _get_path_dirs(self, prefix):
        if on_win:  # pragma: unix no cover
            yield prefix.rstrip(self.sep)

            # We need to stat(2) for possible environments because
            # tests can't be told where to look!
            #
            # mingw-w64 is a legacy variant used by m2w64-* packages
            #
            # We could include clang32 and mingw32 variants
            variants = []
            for variant in ["ucrt64", "clang64", "mingw64", "clangarm64"]:
                path = self.sep.join((prefix, "Library", variant))

                # MSYS2 /c/
                # cygwin /cygdrive/c/
                if re.match("^(/[A-Za-z]/|/cygdrive/[A-Za-z]/).*", prefix):
                    path = unix_path_to_win(path, prefix)

                if isdir(path):
                    variants.append(variant)

            if len(variants) > 1:
                print(
                    f"WARNING: {prefix}: {variants} MSYS2 envs exist: please check your dependencies",
                    file=sys.stderr,
                )
                print(
                    f"WARNING: conda list -n {self._default_env(prefix)}",
                    file=sys.stderr,
                )

            if variants:
                yield self.sep.join((prefix, "Library", variants[0], "bin"))

            yield self.sep.join((prefix, "Library", "mingw-w64", "bin"))
            yield self.sep.join((prefix, "Library", "usr", "bin"))
            yield self.sep.join((prefix, "Library", "bin"))
            yield self.sep.join((prefix, "Scripts"))
            yield self.sep.join((prefix, "bin"))
        else:
            yield self.sep.join((prefix, "bin"))

    def _add_prefix_to_path(self, prefix, starting_path_dirs=None):
        prefix = self.path_conversion(prefix)
        if starting_path_dirs is None:
            path_list = list(self.path_conversion(self._get_starting_path_list()))
        else:
            path_list = list(self.path_conversion(starting_path_dirs))

        # If this is the first time we're activating an environment, we need to ensure that
        # the condabin directory is included in the path list.
        # Under normal conditions, if the shell hook is working correctly, this should
        # never trigger.
        old_conda_shlvl = int(os.getenv("CONDA_SHLVL", "").strip() or 0)
        if not old_conda_shlvl and not any(p.endswith("condabin") for p in path_list):
            condabin_dir = self.path_conversion(join(context.conda_prefix, "condabin"))
            path_list.insert(0, condabin_dir)

        path_list[0:0] = list(self.path_conversion(self._get_path_dirs(prefix)))
        return tuple(path_list)

    def _remove_prefix_from_path(self, prefix, starting_path_dirs=None):
        return self._replace_prefix_in_path(prefix, None, starting_path_dirs)

    def _replace_prefix_in_path(self, old_prefix, new_prefix, starting_path_dirs=None):
        old_prefix = self.path_conversion(old_prefix)
        new_prefix = self.path_conversion(new_prefix)
        if starting_path_dirs is None:
            path_list = list(self.path_conversion(self._get_starting_path_list()))
        else:
            path_list = list(self.path_conversion(starting_path_dirs))

        def index_of_path(paths, test_path):
            for q, path in enumerate(paths):
                if paths_equal(path, test_path):
                    return q
            return None

        if old_prefix is not None:
            prefix_dirs = tuple(self._get_path_dirs(old_prefix))
            first_idx = index_of_path(path_list, prefix_dirs[0])
            if first_idx is None:
                first_idx = 0
            else:
                prefix_dirs_idx = len(prefix_dirs) - 1
                last_idx = None
                while last_idx is None and prefix_dirs_idx > -1:
                    last_idx = index_of_path(path_list, prefix_dirs[prefix_dirs_idx])
                    if last_idx is None:
                        print(
                            f"Did not find path entry {prefix_dirs[prefix_dirs_idx]}",
                            file=sys.stderr,
                        )
                    prefix_dirs_idx = prefix_dirs_idx - 1
                # this compensates for an extra Library/bin dir entry from the interpreter on
                #     windows.  If that entry isn't being added, it should have no effect.
                library_bin_dir = self.path_conversion(
                    self.sep.join((sys.prefix, "Library", "bin"))
                )
                if path_list[last_idx + 1] == library_bin_dir:
                    last_idx += 1
                del path_list[first_idx : last_idx + 1]
        else:
            first_idx = 0

        if new_prefix is not None:
            path_list[first_idx:first_idx] = list(self._get_path_dirs(new_prefix))

        return tuple(path_list)

    def _update_prompt(self, set_vars, conda_prompt_modifier):
        pass

    def _default_env(self, prefix):
        if paths_equal(prefix, context.root_prefix):
            return "base"
        return basename(prefix) if basename(dirname(prefix)) == "envs" else prefix

    def _prompt_modifier(self, prefix, conda_default_env):
        if context.changeps1:
            # Get current environment and prompt stack
            env_stack = []
            prompt_stack = []
            old_shlvl = int(os.getenv("CONDA_SHLVL", "0").rstrip())
            for i in range(1, old_shlvl + 1):
                if i == old_shlvl:
                    env_i = self._default_env(os.getenv("CONDA_PREFIX", ""))
                else:
                    env_i = self._default_env(
                        os.getenv(f"CONDA_PREFIX_{i}", "").rstrip()
                    )
                stacked_i = bool(os.getenv(f"CONDA_STACKED_{i}", "").rstrip())
                env_stack.append(env_i)
                if not stacked_i:
                    prompt_stack = prompt_stack[0:-1]
                prompt_stack.append(env_i)

            # Modify prompt stack according to pending operation
            deactivate = getattr(self, "_deactivate", False)
            reactivate = getattr(self, "_reactivate", False)
            if deactivate:
                prompt_stack = prompt_stack[0:-1]
                env_stack = env_stack[0:-1]
                stacked = bool(os.getenv(f"CONDA_STACKED_{old_shlvl}", "").rstrip())
                if not stacked and env_stack:
                    prompt_stack.append(env_stack[-1])
            elif reactivate:
                pass
            else:
                stack = getattr(self, "stack", False)
                if not stack:
                    prompt_stack = prompt_stack[0:-1]
                prompt_stack.append(conda_default_env)

            conda_stacked_env = ",".join(prompt_stack[::-1])

            return context.env_prompt.format(
                default_env=conda_default_env,
                stacked_env=conda_stacked_env,
                prefix=prefix,
                name=basename(prefix),
            )
        else:
            return ""

    def _get_activate_scripts(self, prefix):
        _script_extension = self.script_extension
        se_len = -len(_script_extension)
        try:
            paths = (
                entry.path
                for entry in os.scandir(join(prefix, "etc", "conda", "activate.d"))
            )
        except OSError:
            return ()
        return self.path_conversion(
            sorted(p for p in paths if p[se_len:] == _script_extension)
        )

    def _get_deactivate_scripts(self, prefix):
        _script_extension = self.script_extension
        se_len = -len(_script_extension)
        try:
            paths = (
                entry.path
                for entry in os.scandir(join(prefix, "etc", "conda", "deactivate.d"))
            )
        except OSError:
            return ()
        return self.path_conversion(
            sorted((p for p in paths if p[se_len:] == _script_extension), reverse=True)
        )

    def _get_environment_env_vars(self, prefix):
        env_vars_file = join(prefix, PREFIX_STATE_FILE)
        pkg_env_var_dir = join(prefix, PACKAGE_ENV_VARS_DIR)
        env_vars = {}

        # First get env vars from packages
        if exists(pkg_env_var_dir):
            for pkg_env_var_path in sorted(
                entry.path for entry in os.scandir(pkg_env_var_dir)
            ):
                with open(pkg_env_var_path) as f:
                    env_vars.update(json.loads(f.read()))

        # Then get env vars from environment specification
        if exists(env_vars_file):
            with open(env_vars_file) as f:
                prefix_state = json.loads(f.read())
                prefix_state_env_vars = prefix_state.get("env_vars", {})
                dup_vars = [
                    ev for ev in env_vars.keys() if ev in prefix_state_env_vars.keys()
                ]
                for dup in dup_vars:
                    print(
                        "WARNING: duplicate env vars detected. Vars from the environment "
                        "will overwrite those from packages",
                        file=sys.stderr,
                    )
                    print(f"variable {dup} duplicated", file=sys.stderr)
                env_vars.update(prefix_state_env_vars)

        return env_vars


def expand(path):
    return abspath(expanduser(expandvars(path)))


@deprecated("25.3", "25.9", addendum="Use `conda.common.compat.ensure_binary` instead.")
def ensure_binary(value):
    try:
        return value.encode("utf-8")
    except AttributeError:  # pragma: no cover
        # AttributeError: '<>' object has no attribute 'encode'
        # In this case assume already binary type and do nothing
        return value


@deprecated("25.3", "25.9")
def ensure_fs_path_encoding(value):
    from .common.compat import FILESYSTEM_ENCODING

    try:
        return value.decode(FILESYSTEM_ENCODING)
    except AttributeError:
        return value


deprecated.constant(
    "25.3",
    "25.9",
    "_Cygpath",
    _cygpath,
    addendum="Use `conda.common.path._cygpath` instead.",
)
del _cygpath

deprecated.constant(
    "25.3",
    "25.9",
    "native_path_to_unix",
    win_path_to_unix,
    addendum="Use `conda.common.path.win_path_to_unix` instead.",
)
deprecated.constant(
    "25.3",
    "25.9",
    "unix_path_to_native",
    unix_path_to_win,
    addendum="Use `conda.common.path.unix_path_to_win` instead.",
)
deprecated.constant(
    "25.3",
    "25.9",
    "path_identity",
    _path_identity,
    addendum="Use `conda.common.path.path_identity` instead.",
)


def backslash_to_forwardslash(
    paths: str | Iterable[str] | None,
) -> str | tuple[str, ...] | None:
    if paths is None:
        return None
    elif isinstance(paths, str):
        return paths.replace("\\", "/")
    else:
        return tuple([path.replace("\\", "/") for path in paths])


class PosixActivator(_Activator):
    pathsep_join = ":".join
    sep = "/"
    path_conversion = staticmethod(win_path_to_unix if on_win else _path_identity)
    script_extension = ".sh"
    tempfile_extension = None  # output to stdout
    command_join = "\n"

    unset_var_tmpl = "unset %s"
    export_var_tmpl = "export %s='%s'"
    set_var_tmpl = "%s='%s'"
    run_script_tmpl = '. "%s"'

    hook_source_path = Path(
        CONDA_PACKAGE_ROOT,
        "shell",
        "etc",
        "profile.d",
        "conda.sh",
    )

    def _update_prompt(self, set_vars, conda_prompt_modifier):
        ps1 = os.getenv("PS1", "")
        if "POWERLINE_COMMAND" in ps1:
            # Defer to powerline (https://github.com/powerline/powerline) if it's in use.
            return
        current_prompt_modifier = os.getenv("CONDA_PROMPT_MODIFIER")
        if current_prompt_modifier:
            ps1 = re.sub(re.escape(current_prompt_modifier), r"", ps1)
        # Because we're using single-quotes to set shell variables, we need to handle the
        # proper escaping of single quotes that are already part of the string.
        # Best solution appears to be https://stackoverflow.com/a/1250279
        ps1 = ps1.replace("'", "'\"'\"'")
        set_vars.update(
            {
                "PS1": conda_prompt_modifier + ps1,
            }
        )

    def _hook_preamble(self) -> str:
        result = []
        for key, value in context.conda_exe_vars_dict.items():
            if value is None:
                # Using `unset_var_tmpl` would cause issues for people running
                # with shell flag -u set (error on unset).
                result.append(self.export_var_tmpl % (key, ""))
            elif on_win and ("/" in value or "\\" in value):
                result.append(f'''export {key}="$(cygpath '{value}')"''')
            else:
                result.append(self.export_var_tmpl % (key, value))
        return "\n".join(result) + "\n"


class CshActivator(_Activator):
    pathsep_join = ":".join
    sep = "/"
    path_conversion = staticmethod(win_path_to_unix if on_win else _path_identity)
    script_extension = ".csh"
    tempfile_extension = None  # output to stdout
    command_join = ";\n"

    unset_var_tmpl = "unsetenv %s"
    export_var_tmpl = 'setenv %s "%s"'
    set_var_tmpl = "set %s='%s'"
    run_script_tmpl = 'source "%s"'

    hook_source_path = Path(
        CONDA_PACKAGE_ROOT,
        "shell",
        "etc",
        "profile.d",
        "conda.csh",
    )

    def _update_prompt(self, set_vars, conda_prompt_modifier):
        prompt = os.getenv("prompt", "")
        current_prompt_modifier = os.getenv("CONDA_PROMPT_MODIFIER")
        if current_prompt_modifier:
            prompt = re.sub(re.escape(current_prompt_modifier), r"", prompt)
        set_vars.update(
            {
                "prompt": conda_prompt_modifier + prompt,
            }
        )

    def _hook_preamble(self) -> str:
        if on_win:
            return dedent(
                f"""
                setenv CONDA_EXE `cygpath {context.conda_exe}`
                setenv _CONDA_ROOT `cygpath {context.conda_prefix}`
                setenv _CONDA_EXE `cygpath {context.conda_exe}`
                setenv CONDA_PYTHON_EXE `cygpath {sys.executable}`
                """
            ).strip()
        else:
            return dedent(
                f"""
                setenv CONDA_EXE "{context.conda_exe}"
                setenv _CONDA_ROOT "{context.conda_prefix}"
                setenv _CONDA_EXE "{context.conda_exe}"
                setenv CONDA_PYTHON_EXE "{sys.executable}"
                """
            ).strip()


class XonshActivator(_Activator):
    pathsep_join = ";".join if on_win else ":".join
    sep = "/"
    path_conversion = staticmethod(
        backslash_to_forwardslash if on_win else _path_identity
    )
    # 'scripts' really refer to de/activation scripts, not scripts in the language per se
    # xonsh can piggy-back activation scripts from other languages depending on the platform
    script_extension = ".bat" if on_win else ".sh"
    tempfile_extension = None  # output to stdout
    command_join = "\n"

    unset_var_tmpl = "del $%s"
    export_var_tmpl = "$%s = '%s'"
    # TODO: determine if different than export_var_tmpl
    set_var_tmpl = "$%s = '%s'"
    run_script_tmpl = (
        'source-cmd --suppress-skip-message "%s"'
        if on_win
        else 'source-bash --suppress-skip-message -n "%s"'
    )

    hook_source_path = Path(CONDA_PACKAGE_ROOT, "shell", "conda.xsh")

    def _hook_preamble(self) -> str:
        return f'$CONDA_EXE = "{self.path_conversion(context.conda_exe)}"'


class CmdExeActivator(_Activator):
    pathsep_join = ";".join
    sep = "\\"
    path_conversion = staticmethod(_path_identity)
    script_extension = ".bat"
    tempfile_extension = ".bat"
    command_join = "\n"

    unset_var_tmpl = "@SET %s="
    export_var_tmpl = '@SET "%s=%s"'
    # TODO: determine if different than export_var_tmpl
    set_var_tmpl = '@SET "%s=%s"'
    run_script_tmpl = '@CALL "%s"'

    hook_source_path = None

    def _hook_preamble(self) -> None:
        # TODO: cmd.exe doesn't get a hook function? Or do we need to do something different?
        #       Like, for cmd.exe only, put a special directory containing only conda.bat on PATH?
        pass


class FishActivator(_Activator):
    pathsep_join = '" "'.join
    sep = "/"
    path_conversion = staticmethod(win_path_to_unix if on_win else _path_identity)
    script_extension = ".fish"
    tempfile_extension = None  # output to stdout
    command_join = ";\n"

    unset_var_tmpl = "set -e %s"
    export_var_tmpl = 'set -gx %s "%s"'
    set_var_tmpl = 'set -g %s "%s"'
    run_script_tmpl = 'source "%s"'

    hook_source_path = Path(
        CONDA_PACKAGE_ROOT,
        "shell",
        "etc",
        "fish",
        "conf.d",
        "conda.fish",
    )

    def _hook_preamble(self) -> str:
        if on_win:
            return dedent(
                f"""
                set -gx CONDA_EXE (cygpath "{context.conda_exe}")
                set _CONDA_ROOT (cygpath "{context.conda_prefix}")
                set _CONDA_EXE (cygpath "{context.conda_exe}")
                set -gx CONDA_PYTHON_EXE (cygpath "{sys.executable}")
                """
            ).strip()
        else:
            return dedent(
                f"""
                set -gx CONDA_EXE "{context.conda_exe}"
                set _CONDA_ROOT "{context.conda_prefix}"
                set _CONDA_EXE "{context.conda_exe}"
                set -gx CONDA_PYTHON_EXE "{sys.executable}"
                """
            ).strip()


class PowerShellActivator(_Activator):
    pathsep_join = ";".join if on_win else ":".join
    sep = "\\" if on_win else "/"
    path_conversion = staticmethod(_path_identity)
    script_extension = ".ps1"
    tempfile_extension = None  # output to stdout
    command_join = "\n"

    unset_var_tmpl = "$Env:%s = $null"
    export_var_tmpl = '$Env:%s = "%s"'
    set_var_tmpl = '$Env:%s = "%s"'
    run_script_tmpl = '. "%s"'

    hook_source_path = Path(
        CONDA_PACKAGE_ROOT,
        "shell",
        "condabin",
        "conda-hook.ps1",
    )

    def _hook_preamble(self) -> str:
        if context.dev:
            return dedent(
                f"""
                $Env:PYTHONPATH = "{CONDA_SOURCE_ROOT}"
                $Env:CONDA_EXE = "{sys.executable}"
                $Env:_CE_M = "-m"
                $Env:_CE_CONDA = "conda"
                $Env:_CONDA_ROOT = "{CONDA_PACKAGE_ROOT}"
                $Env:_CONDA_EXE = "{context.conda_exe}"
                $CondaModuleArgs = @{{ChangePs1 = ${context.changeps1}}}
                """
            ).strip()
        else:
            return dedent(
                f"""
                $Env:CONDA_EXE = "{context.conda_exe}"
                $Env:_CE_M = $null
                $Env:_CE_CONDA = $null
                $Env:_CONDA_ROOT = "{context.conda_prefix}"
                $Env:_CONDA_EXE = "{context.conda_exe}"
                $CondaModuleArgs = @{{ChangePs1 = ${context.changeps1}}}
                """
            ).strip()

    def _hook_postamble(self) -> str:
        return "Remove-Variable CondaModuleArgs"


class JSONFormatMixin(_Activator):
    """Returns the necessary values for activation as JSON, so that tools can use them."""

    pathsep_join = list
    tempfile_extension = None  # output to stdout
    command_join = list

    def _hook_preamble(self):
        if context.dev:
            return {
                "PYTHONPATH": CONDA_SOURCE_ROOT,
                "CONDA_EXE": sys.executable,
                "_CE_M": "-m",
                "_CE_CONDA": "conda",
                "_CONDA_ROOT": CONDA_PACKAGE_ROOT,
                "_CONDA_EXE": context.conda_exe,
            }
        else:
            return {
                "CONDA_EXE": context.conda_exe,
                "_CE_M": "",
                "_CE_CONDA": "",
                "_CONDA_ROOT": context.conda_prefix,
                "_CONDA_EXE": context.conda_exe,
            }

    @deprecated(
        "24.9",
        "25.3",
        addendum="Use `conda.activate._Activator.get_export_unset_vars` instead.",
    )
    def get_scripts_export_unset_vars(self, **kwargs):
        export_vars, unset_vars = self.get_export_unset_vars(**kwargs)
        return export_vars or {}, unset_vars or []

    def _finalize(self, commands, ext):
        merged = {}
        for _cmds in commands:
            merged.update(_cmds)

        commands = merged
        if ext is None:
            return json.dumps(commands, indent=2)
        elif ext:
            with Utf8NamedTemporaryFile("w+", suffix=ext, delete=False) as tf:
                # the default mode is 'w+b', and universal new lines don't work in that mode
                # command_join should account for that
                json.dump(commands, tf, indent=2)
            return tf.name
        else:
            raise NotImplementedError()

    def _yield_commands(self, cmds_dict):
        # TODO: _Is_ defining our own object shape here any better than
        # just dumping the `cmds_dict`?
        path = cmds_dict.get("export_path", {})
        export_vars = cmds_dict.get("export_vars", {})
        # treat PATH specially
        if "PATH" in export_vars:
            new_path = path.get("PATH", [])
            new_path.extend(export_vars.pop("PATH"))
            path["PATH"] = new_path

        yield {
            "path": path,
            "vars": {
                "export": export_vars,
                "unset": cmds_dict.get("unset_vars", ()),
                "set": cmds_dict.get("set_vars", {}),
            },
            "scripts": {
                "activate": cmds_dict.get("activate_scripts", ()),
                "deactivate": cmds_dict.get("deactivate_scripts", ()),
            },
        }


activator_map: dict[str, type[_Activator]] = {
    "posix": PosixActivator,
    "ash": PosixActivator,
    "bash": PosixActivator,
    "dash": PosixActivator,
    "zsh": PosixActivator,
    "csh": CshActivator,
    "tcsh": CshActivator,
    "xonsh": XonshActivator,
    "cmd.exe": CmdExeActivator,
    "fish": FishActivator,
    "powershell": PowerShellActivator,
}

formatter_map = {
    "json": JSONFormatMixin,
}


def _build_activator_cls(shell):
    """Dynamically construct the activator class.

    Detect the base activator and any number of formatters (appended using '+' to the base name).
    For example, `posix+json` (as in `conda shell.posix+json activate`) would use the
    `PosixActivator` base class and add the `JSONFormatMixin`.
    """
    shell_etc = shell.split("+")
    activator, formatters = shell_etc[0], shell_etc[1:]

    bases = [activator_map[activator]]
    for f in formatters:
        bases.append(formatter_map[f])

    cls = type("Activator", tuple(reversed(bases)), {})
    return cls
