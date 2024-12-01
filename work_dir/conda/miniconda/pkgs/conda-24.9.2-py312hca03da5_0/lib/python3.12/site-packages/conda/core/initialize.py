# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Backend logic for `conda init`.

Sections in this module are

  1. top-level functions
  2. plan creators
  3. plan runners
  4. individual operations
  5. helper functions

The top-level functions compose and execute full plans.

A plan is created by composing various individual operations.  The plan data structure is a
list of dicts, where each dict represents an individual operation.  The dict contains two
keys--`function` and `kwargs`--where function is the name of the individual operation function
within this module.

Each individual operation must

  a) return a `Result` (i.e. NEEDS_SUDO, MODIFIED, or NO_CHANGE)
  b) have no side effects if context.dry_run is True
  c) be verbose and descriptive about the changes being made or proposed is context.verbose

The plan runner functions take the plan (list of dicts) as an argument, and then coordinate the
execution of each individual operation.  The docstring for `run_plan_elevated()` has details on
how that strategy is implemented.

"""

import json
import os
import re
import struct
import sys
from difflib import unified_diff
from errno import ENOENT
from glob import glob
from itertools import chain
from logging import getLogger
from os.path import abspath, basename, dirname, exists, expanduser, isdir, isfile, join
from pathlib import Path
from random import randint

from .. import CONDA_PACKAGE_ROOT, CondaError
from .. import __version__ as CONDA_VERSION
from ..activate import (
    CshActivator,
    FishActivator,
    PosixActivator,
    PowerShellActivator,
    XonshActivator,
)
from ..auxlib.compat import Utf8NamedTemporaryFile
from ..auxlib.ish import dals
from ..base.context import context
from ..common.compat import (
    ensure_binary,
    ensure_text_type,
    ensure_utf8_encoding,
    on_mac,
    on_win,
    open_utf8,
)
from ..common.path import (
    BIN_DIRECTORY,
    expand,
    get_python_short_path,
    get_python_site_packages_short_path,
    win_path_ok,
)
from ..exceptions import CondaValueError
from ..gateways.disk.create import copy, mkdir_p
from ..gateways.disk.delete import rm_rf
from ..gateways.disk.link import lexists
from ..gateways.disk.permissions import make_executable
from ..gateways.disk.read import compute_sum
from ..gateways.subprocess import subprocess_call
from .portability import generate_shebang_for_entry_point

if on_win:  # pragma: no cover
    import winreg

    # Use v1 import paths to avoid bootstrapping issues
    # TODO: Remove once fully deployed (one release after merge)
    from menuinst.knownfolders import FOLDERID, get_folder_path
    from menuinst.winshortcut import create_shortcut


log = getLogger(__name__)

CONDA_INITIALIZE_RE_BLOCK = (
    r"^# >>> conda initialize >>>(?:\n|\r\n)"
    r"([\s\S]*?)"
    r"# <<< conda initialize <<<(?:\n|\r\n)?"
)

CONDA_INITIALIZE_PS_RE_BLOCK = (
    r"^#region conda initialize(?:\n|\r\n)([\s\S]*?)#endregion(?:\n|\r\n)?"
)


class Result:
    NEEDS_SUDO = "needs sudo"
    MODIFIED = "modified"
    NO_CHANGE = "no change"


# #####################################################
# top-level functions
# #####################################################


def install(conda_prefix):
    plan = make_install_plan(conda_prefix)
    run_plan(plan)
    if not context.dry_run:
        assert not any(step["result"] == Result.NEEDS_SUDO for step in plan)
    print_plan_results(plan)
    return 0


def initialize(
    conda_prefix, shells, for_user, for_system, anaconda_prompt, reverse=False
):
    plan1 = []
    if os.getenv("CONDA_PIP_UNINITIALIZED") == "true":
        plan1 = make_install_plan(conda_prefix)
        run_plan(plan1)
        if not context.dry_run:
            run_plan_elevated(plan1)

    plan2 = make_initialize_plan(
        conda_prefix, shells, for_user, for_system, anaconda_prompt, reverse=reverse
    )
    run_plan(plan2)
    if not context.dry_run:
        run_plan_elevated(plan2)

    plan = plan1 + plan2
    print_plan_results(plan)

    if any(step["result"] == Result.NEEDS_SUDO for step in plan):
        print("Operation failed.", file=sys.stderr)
        return 1


def initialize_dev(shell, dev_env_prefix=None, conda_source_root=None):
    # > alias conda-dev='eval "$(python -m conda init --dev)"'
    # > eval "$(python -m conda init --dev)"

    prefix = expand(dev_env_prefix or sys.prefix)
    conda_source_root = expand(conda_source_root or os.getcwd())

    python_exe, python_version, site_packages_dir = _get_python_info(prefix)

    if not isfile(join(conda_source_root, "conda", "__main__.py")):
        raise CondaValueError(
            f"Directory is not a conda source root: {conda_source_root}"
        )

    plan = make_install_plan(prefix)
    plan.append(
        {
            "function": remove_conda_in_sp_dir.__name__,
            "kwargs": {
                "target_path": site_packages_dir,
            },
        }
    )
    plan.append(
        {
            "function": make_conda_egg_link.__name__,
            "kwargs": {
                "target_path": join(site_packages_dir, "conda.egg-link"),
                "conda_source_root": conda_source_root,
            },
        }
    )
    plan.append(
        {
            "function": modify_easy_install_pth.__name__,
            "kwargs": {
                "target_path": join(site_packages_dir, "easy-install.pth"),
                "conda_source_root": conda_source_root,
            },
        }
    )
    plan.append(
        {
            "function": make_dev_egg_info_file.__name__,
            "kwargs": {
                "target_path": join(conda_source_root, "conda.egg-info"),
            },
        }
    )

    run_plan(plan)

    if context.dry_run or context.verbose:
        print_plan_results(plan, sys.stderr)

    if any(step["result"] == Result.NEEDS_SUDO for step in plan):  # pragma: no cover
        raise CondaError(
            "Operation failed. Privileged install disallowed for 'conda init --dev'."
        )

    env_vars = {
        "PYTHONHASHSEED": randint(0, 4294967296),
        "PYTHON_MAJOR_VERSION": python_version[0],
        "TEST_PLATFORM": "win" if on_win else "unix",
    }
    unset_env_vars = (
        "CONDA_DEFAULT_ENV",
        "CONDA_EXE",
        "_CE_M",
        "_CE_CONDA",
        "CONDA_PREFIX",
        "CONDA_PREFIX_1",
        "CONDA_PREFIX_2",
        "CONDA_PYTHON_EXE",
        "CONDA_PROMPT_MODIFIER",
        "CONDA_SHLVL",
    )

    if shell == "bash":
        print("\n".join(_initialize_dev_bash(prefix, env_vars, unset_env_vars)))
    elif shell == "cmd.exe":
        script = _initialize_dev_cmdexe(prefix, env_vars, unset_env_vars)
        if not context.dry_run:
            with open_utf8("dev-init.bat", "w") as fh:
                fh.write("\n".join(script))
        if context.verbose:
            print("\n".join(script))
        print("now run  > .\\dev-init.bat")
    else:
        raise NotImplementedError()
    return 0


def _initialize_dev_bash(prefix, env_vars, unset_env_vars):
    sys_executable = abspath(sys.executable)
    if on_win:
        sys_executable = f"$(cygpath '{sys_executable}')"

    # unset/set environment variables
    yield from (f"unset {envvar}" for envvar in unset_env_vars)
    yield from (
        f"export {envvar}='{value}'" for envvar, value in sorted(env_vars.items())
    )

    # initialize shell interface
    yield f'eval "$("{sys_executable}" -m conda shell.bash hook)"'

    # optionally activate environment
    if context.auto_activate_base:
        yield f"conda activate '{prefix}'"


def _initialize_dev_cmdexe(prefix, env_vars, unset_env_vars):
    dev_arg = ""
    if context.dev:
        dev_arg = "--dev"
    condabin = Path(prefix, "condabin")

    yield (
        '@IF NOT "%CONDA_PROMPT_MODIFIER%" == "" '
        '@CALL SET "PROMPT=%%PROMPT:%CONDA_PROMPT_MODIFIER%=%_empty_not_set_%%%"'
    )

    # unset/set environment variables
    yield from (f"@SET {envvar}=" for envvar in unset_env_vars)
    yield from (
        f'@SET "{envvar}={value}"' for envvar, value in sorted(env_vars.items())
    )

    # initialize shell interface
    yield f'@CALL "{condabin / "conda_hook.bat"}" {dev_arg}'
    yield "@IF %ERRORLEVEL% NEQ 0 @EXIT /B %ERRORLEVEL%"

    # optionally activate environment
    if context.auto_activate_base:
        yield f'@CALL "{condabin / "conda.bat"}" activate {dev_arg} "{prefix}"'
        yield "@IF %ERRORLEVEL% NEQ 0 @EXIT /B %ERRORLEVEL%"


# #####################################################
# plan creators
# #####################################################


def make_install_plan(conda_prefix):
    try:
        python_exe, python_version, site_packages_dir = _get_python_info(conda_prefix)
    except OSError:
        python_exe, python_version, site_packages_dir = None, None, None  # NOQA

    plan = []

    # ######################################
    # executables
    # ######################################
    if on_win:
        conda_exe_path = join(conda_prefix, "Scripts", "conda-script.py")
        conda_env_exe_path = join(conda_prefix, "Scripts", "conda-env-script.py")
        plan.append(
            {
                "function": make_entry_point_exe.__name__,
                "kwargs": {
                    "target_path": join(conda_prefix, "Scripts", "conda.exe"),
                    "conda_prefix": conda_prefix,
                },
            }
        )
        plan.append(
            {
                "function": make_entry_point_exe.__name__,
                "kwargs": {
                    "target_path": join(conda_prefix, "Scripts", "conda-env.exe"),
                    "conda_prefix": conda_prefix,
                },
            }
        )
    else:
        # We can't put a conda.exe in condabin on Windows. It'll conflict with conda.bat.
        plan.append(
            {
                "function": make_entry_point.__name__,
                "kwargs": {
                    "target_path": join(conda_prefix, "condabin", "conda"),
                    "conda_prefix": conda_prefix,
                    "module": "conda.cli",
                    "func": "main",
                },
            }
        )
        conda_exe_path = join(conda_prefix, "bin", "conda")
        conda_env_exe_path = join(conda_prefix, "bin", "conda-env")

    plan.append(
        {
            "function": make_entry_point.__name__,
            "kwargs": {
                "target_path": conda_exe_path,
                "conda_prefix": conda_prefix,
                "module": "conda.cli",
                "func": "main",
            },
        }
    )
    plan.append(
        {
            "function": make_entry_point.__name__,
            "kwargs": {
                "target_path": conda_env_exe_path,
                "conda_prefix": conda_prefix,
                # TODO: Remove upon full deprecation in 25.3
                "module": "conda_env.cli.main",
                "func": "main",
            },
        }
    )

    # ######################################
    # shell wrappers
    # ######################################
    if on_win:
        plan.append(
            {
                "function": install_condabin_conda_bat.__name__,
                "kwargs": {
                    "target_path": join(conda_prefix, "condabin", "conda.bat"),
                    "conda_prefix": conda_prefix,
                },
            }
        )
        plan.append(
            {
                "function": install_library_bin_conda_bat.__name__,
                "kwargs": {
                    "target_path": join(conda_prefix, "Library", "bin", "conda.bat"),
                    "conda_prefix": conda_prefix,
                },
            }
        )
        plan.append(
            {
                "function": install_condabin_conda_activate_bat.__name__,
                "kwargs": {
                    "target_path": join(
                        conda_prefix, "condabin", "_conda_activate.bat"
                    ),
                    "conda_prefix": conda_prefix,
                },
            }
        )
        plan.append(
            {
                "function": install_condabin_rename_tmp_bat.__name__,
                "kwargs": {
                    "target_path": join(conda_prefix, "condabin", "rename_tmp.bat"),
                    "conda_prefix": conda_prefix,
                },
            }
        )
        plan.append(
            {
                "function": install_condabin_conda_auto_activate_bat.__name__,
                "kwargs": {
                    "target_path": join(
                        conda_prefix, "condabin", "conda_auto_activate.bat"
                    ),
                    "conda_prefix": conda_prefix,
                },
            }
        )
        plan.append(
            {
                "function": install_condabin_hook_bat.__name__,
                "kwargs": {
                    "target_path": join(conda_prefix, "condabin", "conda_hook.bat"),
                    "conda_prefix": conda_prefix,
                },
            }
        )
        plan.append(
            {
                "function": install_Scripts_activate_bat.__name__,
                "kwargs": {
                    "target_path": join(conda_prefix, "Scripts", "activate.bat"),
                    "conda_prefix": conda_prefix,
                },
            }
        )
        plan.append(
            {
                "function": install_activate_bat.__name__,
                "kwargs": {
                    "target_path": join(conda_prefix, "condabin", "activate.bat"),
                    "conda_prefix": conda_prefix,
                },
            }
        )
        plan.append(
            {
                "function": install_deactivate_bat.__name__,
                "kwargs": {
                    "target_path": join(conda_prefix, "condabin", "deactivate.bat"),
                    "conda_prefix": conda_prefix,
                },
            }
        )

    plan.append(
        {
            "function": install_activate.__name__,
            "kwargs": {
                "target_path": join(conda_prefix, BIN_DIRECTORY, "activate"),
                "conda_prefix": conda_prefix,
            },
        }
    )
    plan.append(
        {
            "function": install_deactivate.__name__,
            "kwargs": {
                "target_path": join(conda_prefix, BIN_DIRECTORY, "deactivate"),
                "conda_prefix": conda_prefix,
            },
        }
    )

    plan.append(
        {
            "function": install_conda_sh.__name__,
            "kwargs": {
                "target_path": join(conda_prefix, "etc", "profile.d", "conda.sh"),
                "conda_prefix": conda_prefix,
            },
        }
    )
    plan.append(
        {
            "function": install_conda_fish.__name__,
            "kwargs": {
                "target_path": join(
                    conda_prefix, "etc", "fish", "conf.d", "conda.fish"
                ),
                "conda_prefix": conda_prefix,
            },
        }
    )
    plan.append(
        {
            "function": install_conda_psm1.__name__,
            "kwargs": {
                "target_path": join(conda_prefix, "shell", "condabin", "Conda.psm1"),
                "conda_prefix": conda_prefix,
            },
        }
    )
    plan.append(
        {
            "function": install_conda_hook_ps1.__name__,
            "kwargs": {
                "target_path": join(
                    conda_prefix, "shell", "condabin", "conda-hook.ps1"
                ),
                "conda_prefix": conda_prefix,
            },
        }
    )
    if site_packages_dir:
        plan.append(
            {
                "function": install_conda_xsh.__name__,
                "kwargs": {
                    "target_path": join(site_packages_dir, "xontrib", "conda.xsh"),
                    "conda_prefix": conda_prefix,
                },
            }
        )
    else:
        print(
            "WARNING: Cannot install xonsh wrapper without a python interpreter in prefix: "
            f"{conda_prefix}",
            file=sys.stderr,
        )
    plan.append(
        {
            "function": install_conda_csh.__name__,
            "kwargs": {
                "target_path": join(conda_prefix, "etc", "profile.d", "conda.csh"),
                "conda_prefix": conda_prefix,
            },
        }
    )
    return plan


def make_initialize_plan(
    conda_prefix, shells, for_user, for_system, anaconda_prompt, reverse=False
):
    """
    Creates a plan for initializing conda in shells.

    Bash:
    On Linux, when opening the terminal, .bashrc is sourced (because it is an interactive shell).
    On macOS on the other hand, the .bash_profile gets sourced by default when executing it in
    Terminal.app. Some other programs do the same on macOS so that's why we're initializing conda
    in .bash_profile.
    On Windows, there are multiple ways to open bash depending on how it was installed. Git Bash,
    Cygwin, and MSYS2 all use .bash_profile by default.

    PowerShell:
    There's several places PowerShell can store its path, depending on if it's Windows PowerShell,
    PowerShell Core on Windows, or PowerShell Core on macOS/Linux. The easiest way to resolve it
    is to just ask different possible installations of PowerShell where their profiles are.
    """
    plan = make_install_plan(conda_prefix)
    shells = set(shells)
    if shells & {"bash", "zsh"}:
        if "bash" in shells and for_user:
            bashrc_path = expand(
                join("~", ".bash_profile" if (on_mac or on_win) else ".bashrc")
            )
            plan.append(
                {
                    "function": init_sh_user.__name__,
                    "kwargs": {
                        "target_path": bashrc_path,
                        "conda_prefix": conda_prefix,
                        "shell": "bash",
                        "reverse": reverse,
                    },
                }
            )

        if "zsh" in shells and for_user:
            if "ZDOTDIR" in os.environ:
                zshrc_path = expand(join("$ZDOTDIR", ".zshrc"))
            else:
                zshrc_path = expand(join("~", ".zshrc"))
            plan.append(
                {
                    "function": init_sh_user.__name__,
                    "kwargs": {
                        "target_path": zshrc_path,
                        "conda_prefix": conda_prefix,
                        "shell": "zsh",
                        "reverse": reverse,
                    },
                }
            )

        if for_system:
            plan.append(
                {
                    "function": init_sh_system.__name__,
                    "kwargs": {
                        "target_path": "/etc/profile.d/conda.sh",
                        "conda_prefix": conda_prefix,
                        "reverse": reverse,
                    },
                }
            )

    if "fish" in shells:
        if for_user:
            config_fish_path = expand(join("~", ".config", "fish", "config.fish"))
            plan.append(
                {
                    "function": init_fish_user.__name__,
                    "kwargs": {
                        "target_path": config_fish_path,
                        "conda_prefix": conda_prefix,
                        "reverse": reverse,
                    },
                }
            )

        if for_system:
            config_fish_path = expand(join("~", ".config", "fish", "config.fish"))
            plan.append(
                {
                    "function": init_fish_user.__name__,
                    "kwargs": {
                        "target_path": config_fish_path,
                        "conda_prefix": conda_prefix,
                        "reverse": reverse,
                    },
                }
            )

    if "xonsh" in shells:
        if for_user:
            config_xonsh_path = expand(join("~", ".xonshrc"))
            plan.append(
                {
                    "function": init_xonsh_user.__name__,
                    "kwargs": {
                        "target_path": config_xonsh_path,
                        "conda_prefix": conda_prefix,
                        "reverse": reverse,
                    },
                }
            )

        if for_system:
            if on_win:
                config_xonsh_path = expand(
                    join("%ALLUSERSPROFILE%", "xonsh", "xonshrc")
                )
            else:
                config_xonsh_path = "/etc/xonshrc"
            plan.append(
                {
                    "function": init_xonsh_user.__name__,
                    "kwargs": {
                        "target_path": config_xonsh_path,
                        "conda_prefix": conda_prefix,
                        "reverse": reverse,
                    },
                }
            )

    if "tcsh" in shells and for_user:
        tcshrc_path = expand(join("~", ".tcshrc"))
        plan.append(
            {
                "function": init_sh_user.__name__,
                "kwargs": {
                    "target_path": tcshrc_path,
                    "conda_prefix": conda_prefix,
                    "shell": "tcsh",
                    "reverse": reverse,
                },
            }
        )

    if "powershell" in shells:
        if for_user:
            profile = "$PROFILE.CurrentUserAllHosts"

        if for_system:
            profile = "$PROFILE.AllUsersAllHosts"

        def find_powershell_paths(*exe_names):
            for exe_name in exe_names:
                try:
                    yield subprocess_call(
                        (exe_name, "-NoProfile", "-Command", profile)
                    ).stdout.strip()
                except Exception:
                    pass

        config_powershell_paths = set(
            find_powershell_paths("powershell", "pwsh", "pwsh-preview")
        )

        for config_path in config_powershell_paths:
            if config_path is not None:
                plan.append(
                    {
                        "function": init_powershell_user.__name__,
                        "kwargs": {
                            "target_path": config_path,
                            "conda_prefix": conda_prefix,
                            "reverse": reverse,
                        },
                    }
                )

    if "cmd.exe" in shells:
        if for_user:
            plan.append(
                {
                    "function": init_cmd_exe_registry.__name__,
                    "kwargs": {
                        "target_path": "HKEY_CURRENT_USER\\Software\\Microsoft\\"
                        "Command Processor\\AutoRun",
                        "conda_prefix": conda_prefix,
                        "reverse": reverse,
                    },
                }
            )
        if for_system:
            plan.append(
                {
                    "function": init_cmd_exe_registry.__name__,
                    "kwargs": {
                        "target_path": "HKEY_LOCAL_MACHINE\\Software\\Microsoft\\"
                        "Command Processor\\AutoRun",
                        "conda_prefix": conda_prefix,
                        "reverse": reverse,
                    },
                }
            )
            # it would be nice to enable this on a user-level basis, but unfortunately, it is
            #    a system-level key only.
            plan.append(
                {
                    "function": init_long_path.__name__,
                    "kwargs": {
                        "target_path": "HKEY_LOCAL_MACHINE\\SYSTEM\\CurrentControlSet\\Control\\"
                        "FileSystem\\LongPathsEnabled"
                    },
                }
            )
        if anaconda_prompt:
            plan.append(
                {
                    "function": install_anaconda_prompt.__name__,
                    "kwargs": {
                        "target_path": join(
                            conda_prefix, "condabin", "Anaconda Prompt.lnk"
                        ),
                        "conda_prefix": conda_prefix,
                        "reverse": reverse,
                    },
                }
            )
            if on_win:
                desktop_dir, exception = get_folder_path(FOLDERID.Desktop)
                assert not exception
            else:
                desktop_dir = join(expanduser("~"), "Desktop")
            plan.append(
                {
                    "function": install_anaconda_prompt.__name__,
                    "kwargs": {
                        "target_path": join(desktop_dir, "Anaconda Prompt.lnk"),
                        "conda_prefix": conda_prefix,
                        "reverse": reverse,
                    },
                }
            )

    return plan


# #####################################################
# plan runners
# #####################################################


def run_plan(plan):
    for step in plan:
        previous_result = step.get("result", None)
        if previous_result in (Result.MODIFIED, Result.NO_CHANGE):
            continue
        try:
            result = globals()[step["function"]](
                *step.get("args", ()), **step.get("kwargs", {})
            )
        except OSError as e:
            log.info("%s: %r", step["function"], e, exc_info=True)
            result = Result.NEEDS_SUDO
        step["result"] = result


def run_plan_elevated(plan):
    """
    The strategy of this function differs between unix and Windows.  Both strategies use a
    subprocess call, where the subprocess is run with elevated privileges.  The executable
    invoked with the subprocess is `python -m conda.core.initialize`, so see the
    `if __name__ == "__main__"` at the bottom of this module.

    For unix platforms, we convert the plan list to json, and then call this module with
    `sudo python -m conda.core.initialize` while piping the plan json to stdin.  We collect json
    from stdout for the results of the plan execution with elevated privileges.

    For Windows, we create a temporary file that holds the json content of the plan.  The
    subprocess reads the content of the file, modifies the content of the file with updated
    execution status, and then closes the file.  This process then reads the content of that file
    for the individual operation execution results, and then deletes the file.
    """
    if any(step["result"] == Result.NEEDS_SUDO for step in plan):
        if on_win:
            from ..common._os.windows import run_as_admin

            temp_path = None
            try:
                with Utf8NamedTemporaryFile("w+", suffix=".json", delete=False) as tf:
                    # the default mode is 'w+b', and universal new lines don't work in that mode
                    tf.write(
                        json.dumps(
                            plan, ensure_ascii=False, default=lambda x: x.__dict__
                        )
                    )
                    temp_path = tf.name
                python_exe = f'"{abspath(sys.executable)}"'
                hinstance, error_code = run_as_admin(
                    (python_exe, "-m", "conda.core.initialize", f'"{temp_path}"')
                )
                if error_code is not None:
                    print(
                        f"ERROR during elevated execution.\n  rc: {error_code}",
                        file=sys.stderr,
                    )

                with open_utf8(temp_path) as fh:
                    _plan = json.loads(ensure_text_type(fh.read()))

            finally:
                if temp_path and lexists(temp_path):
                    rm_rf(temp_path)

        else:
            stdin = json.dumps(plan, ensure_ascii=False, default=lambda x: x.__dict__)
            result = subprocess_call(
                f"sudo {sys.executable} -m conda.core.initialize",
                env={},
                path=os.getcwd(),
                stdin=stdin,
            )
            stderr = result.stderr.strip()
            if stderr:
                print(stderr, file=sys.stderr)
            _plan = json.loads(result.stdout.strip())

        del plan[:]
        plan.extend(_plan)


def run_plan_from_stdin():
    stdin = sys.stdin.read().strip()
    plan = json.loads(stdin)
    run_plan(plan)
    sys.stdout.write(json.dumps(plan))


def run_plan_from_temp_file(temp_path):
    with open_utf8(temp_path) as fh:
        plan = json.loads(ensure_text_type(fh.read()))
    run_plan(plan)
    with open_utf8(temp_path, "w+b") as fh:
        fh.write(ensure_binary(json.dumps(plan, ensure_ascii=False)))


def print_plan_results(plan, stream=None):
    if not stream:
        stream = sys.stdout
    for step in plan:
        print(
            "%-14s%s" % (step.get("result"), step["kwargs"]["target_path"]), file=stream
        )

    changed = any(step.get("result") == Result.MODIFIED for step in plan)
    if changed:
        print(
            "\n==> For changes to take effect, close and re-open your current shell. <==\n",
            file=stream,
        )
    else:
        print("No action taken.", file=stream)


# #####################################################
# individual operations
# #####################################################


def make_entry_point(target_path, conda_prefix, module, func):
    # 'ep' in this function refers to 'entry point'
    # target_path: join(conda_prefix, 'bin', 'conda')
    conda_ep_path = target_path

    if isfile(conda_ep_path):
        with open_utf8(conda_ep_path) as fh:
            original_ep_content = fh.read()
    else:
        original_ep_content = ""

    if on_win:
        # no shebang needed on windows
        new_ep_content = ""
    else:
        python_path = join(conda_prefix, get_python_short_path())
        new_ep_content = generate_shebang_for_entry_point(
            python_path, with_usr_bin_env=True
        )

    conda_extra = dals(
        """
    # Before any more imports, leave cwd out of sys.path for internal 'conda shell.*' commands.
    # see https://github.com/conda/conda/issues/6549
    if len(sys.argv) > 1 and sys.argv[1].startswith('shell.') and sys.path and sys.path[0] == '':
        # The standard first entry in sys.path is an empty string,
        # and os.path.abspath('') expands to os.getcwd().
        del sys.path[0]
    """
    )

    new_ep_content += dals(
        """
    # -*- coding: utf-8 -*-
    import sys
    %(extra)s
    if __name__ == '__main__':
        from %(module)s import %(func)s
        sys.exit(%(func)s())
    """
    ) % {
        "extra": conda_extra if module == "conda.cli" else "",
        "module": module,
        "func": func,
    }

    if new_ep_content != original_ep_content:
        if context.verbose:
            print("\n")
            print(target_path)
            print(make_diff(original_ep_content, new_ep_content))
        if not context.dry_run:
            mkdir_p(dirname(conda_ep_path))
            with open_utf8(conda_ep_path, "w") as fdst:
                fdst.write(new_ep_content)
            if not on_win:
                make_executable(conda_ep_path)
        return Result.MODIFIED
    else:
        return Result.NO_CHANGE


def make_entry_point_exe(target_path, conda_prefix):
    # target_path: join(conda_prefix, 'Scripts', 'conda.exe')
    exe_path = target_path
    bits = 8 * struct.calcsize("P")
    source_exe_path = join(CONDA_PACKAGE_ROOT, "shell", "cli-%d.exe" % bits)
    if isfile(exe_path):
        if compute_sum(exe_path, "md5") == compute_sum(source_exe_path, "md5"):
            return Result.NO_CHANGE

    if not context.dry_run:
        if not isdir(dirname(exe_path)):
            mkdir_p(dirname(exe_path))
        # prefer copy() over create_hard_link_or_copy() because of windows file deletion issues
        # with open processes
        copy(source_exe_path, exe_path)
    return Result.MODIFIED


def install_anaconda_prompt(target_path, conda_prefix, reverse):
    # target_path: join(conda_prefix, 'condabin', 'Anaconda Prompt.lnk')
    # target: join(os.environ["HOMEPATH"], "Desktop", "Anaconda Prompt.lnk")
    icon_path = join(CONDA_PACKAGE_ROOT, "shell", "conda_icon.ico")
    target = join(os.environ["HOMEPATH"], "Desktop", "Anaconda Prompt.lnk")

    args = (
        "/K",
        '""{}" && "{}""'.format(
            join(conda_prefix, "condabin", "conda_hook.bat"),
            join(conda_prefix, "condabin", "conda_auto_activate.bat"),
        ),
    )
    # The API for the call to 'create_shortcut' has 3
    # required arguments (path, description, filename)
    # and 4 optional ones (args, working_dir, icon_path, icon_index).
    result = Result.NO_CHANGE
    if not context.dry_run:
        create_shortcut(
            "%windir%\\System32\\cmd.exe",
            "Anconda Prompt",
            "" + target_path,
            " ".join(args),
            "" + expanduser("~"),
            "" + icon_path,
        )
        result = Result.MODIFIED
    if reverse:
        if os.path.isfile(target):
            os.remove(target)
            result = Result.MODIFIED
    return result


def _install_file(target_path, file_content):
    if isfile(target_path):
        with open_utf8(target_path) as fh:
            original_content = fh.read()
    else:
        original_content = ""

    new_content = file_content

    if new_content != original_content:
        if context.verbose:
            print("\n")
            print(target_path)
            print(make_diff(original_content, new_content))
        if not context.dry_run:
            mkdir_p(dirname(target_path))
            with open_utf8(target_path, "w") as fdst:
                fdst.write(new_content)
        return Result.MODIFIED
    else:
        return Result.NO_CHANGE


def install_conda_sh(target_path, conda_prefix):
    # target_path: join(conda_prefix, 'etc', 'profile.d', 'conda.sh')
    file_content = PosixActivator().hook(auto_activate_base=False)
    return _install_file(target_path, file_content)


def install_Scripts_activate_bat(target_path, conda_prefix):
    # target_path: join(conda_prefix, 'Scripts', 'activate.bat')
    src_path = join(CONDA_PACKAGE_ROOT, "shell", "Scripts", "activate.bat")
    with open_utf8(src_path) as fsrc:
        file_content = fsrc.read()
    return _install_file(target_path, file_content)


def install_activate_bat(target_path, conda_prefix):
    # target_path: join(conda_prefix, 'condabin', 'activate.bat')
    src_path = join(CONDA_PACKAGE_ROOT, "shell", "condabin", "activate.bat")
    with open_utf8(src_path) as fsrc:
        file_content = fsrc.read()
    return _install_file(target_path, file_content)


def install_deactivate_bat(target_path, conda_prefix):
    # target_path: join(conda_prefix, 'condabin', 'deactivate.bat')
    src_path = join(CONDA_PACKAGE_ROOT, "shell", "condabin", "deactivate.bat")
    with open_utf8(src_path) as fsrc:
        file_content = fsrc.read()
    return _install_file(target_path, file_content)


def install_activate(target_path, conda_prefix):
    # target_path: join(conda_prefix, BIN_DIRECTORY, 'activate')
    src_path = join(CONDA_PACKAGE_ROOT, "shell", "bin", "activate")
    file_content = f'#!/bin/sh\n_CONDA_ROOT="{conda_prefix}"\n'
    with open_utf8(src_path) as fsrc:
        file_content += fsrc.read()
    return _install_file(target_path, file_content)


def install_deactivate(target_path, conda_prefix):
    # target_path: join(conda_prefix, BIN_DIRECTORY, 'deactivate')
    src_path = join(CONDA_PACKAGE_ROOT, "shell", "bin", "deactivate")
    file_content = f'#!/bin/sh\n_CONDA_ROOT="{conda_prefix}"\n'
    with open_utf8(src_path) as fsrc:
        file_content += fsrc.read()
    return _install_file(target_path, file_content)


def install_condabin_conda_bat(target_path, conda_prefix):
    # target_path: join(conda_prefix, 'condabin', 'conda.bat')
    conda_bat_src_path = join(CONDA_PACKAGE_ROOT, "shell", "condabin", "conda.bat")
    with open_utf8(conda_bat_src_path) as fsrc:
        file_content = fsrc.read()
    return _install_file(target_path, file_content)


def install_library_bin_conda_bat(target_path, conda_prefix):
    # target_path: join(conda_prefix, 'Library', 'bin', 'conda.bat')
    conda_bat_src_path = join(
        CONDA_PACKAGE_ROOT, "shell", "Library", "bin", "conda.bat"
    )
    with open_utf8(conda_bat_src_path) as fsrc:
        file_content = fsrc.read()
    return _install_file(target_path, file_content)


def install_condabin_conda_activate_bat(target_path, conda_prefix):
    # target_path: join(conda_prefix, 'condabin', '_conda_activate.bat')
    conda_bat_src_path = join(
        CONDA_PACKAGE_ROOT, "shell", "condabin", "_conda_activate.bat"
    )
    with open_utf8(conda_bat_src_path) as fsrc:
        file_content = fsrc.read()
    return _install_file(target_path, file_content)


def install_condabin_rename_tmp_bat(target_path, conda_prefix):
    # target_path: join(conda_prefix, 'condabin', 'rename_tmp.bat')
    conda_bat_src_path = join(CONDA_PACKAGE_ROOT, "shell", "condabin", "rename_tmp.bat")
    with open_utf8(conda_bat_src_path) as fsrc:
        file_content = fsrc.read()
    return _install_file(target_path, file_content)


def install_condabin_conda_auto_activate_bat(target_path, conda_prefix):
    # target_path: join(conda_prefix, 'condabin', 'conda_auto_activate.bat')
    conda_bat_src_path = join(
        CONDA_PACKAGE_ROOT, "shell", "condabin", "conda_auto_activate.bat"
    )
    with open_utf8(conda_bat_src_path) as fsrc:
        file_content = fsrc.read()
    return _install_file(target_path, file_content)


def install_condabin_hook_bat(target_path, conda_prefix):
    # target_path: join(conda_prefix, 'condabin', 'conda_hook.bat')
    conda_bat_src_path = join(CONDA_PACKAGE_ROOT, "shell", "condabin", "conda_hook.bat")
    with open_utf8(conda_bat_src_path) as fsrc:
        file_content = fsrc.read()
    return _install_file(target_path, file_content)


def install_conda_fish(target_path, conda_prefix):
    # target_path: join(conda_prefix, 'etc', 'fish', 'conf.d', 'conda.fish')
    file_content = FishActivator().hook(auto_activate_base=False)
    return _install_file(target_path, file_content)


def install_conda_psm1(target_path, conda_prefix):
    # target_path: join(conda_prefix, 'shell', 'condabin', 'Conda.psm1')
    conda_psm1_path = join(CONDA_PACKAGE_ROOT, "shell", "condabin", "Conda.psm1")
    with open_utf8(conda_psm1_path) as fsrc:
        file_content = fsrc.read()
    return _install_file(target_path, file_content)


def install_conda_hook_ps1(target_path, conda_prefix):
    # target_path: join(conda_prefix, 'shell', 'condabin', 'conda-hook.ps1')
    file_content = PowerShellActivator().hook(auto_activate_base=False)
    return _install_file(target_path, file_content)


def install_conda_xsh(target_path, conda_prefix):
    # target_path: join(site_packages_dir, 'xonsh', 'conda.xsh')
    file_content = XonshActivator().hook(auto_activate_base=False)
    return _install_file(target_path, file_content)


def install_conda_csh(target_path, conda_prefix):
    # target_path: join(conda_prefix, 'etc', 'profile.d', 'conda.csh')
    file_content = CshActivator().hook(auto_activate_base=False)
    return _install_file(target_path, file_content)


def _config_fish_content(conda_prefix):
    conda_exe = join(conda_prefix, BIN_DIRECTORY, "conda.exe" if on_win else "conda")
    if on_win:
        from ..activate import native_path_to_unix

        conda_exe = native_path_to_unix(conda_exe)
    conda_initialize_content = dals(
        """
        # >>> conda initialize >>>
        # !! Contents within this block are managed by 'conda init' !!
        if test -f %(conda_exe)s
            eval %(conda_exe)s "shell.fish" "hook" $argv | source
        else
            if test -f "%(conda_prefix)s/etc/fish/conf.d/conda.fish"
                . "%(conda_prefix)s/etc/fish/conf.d/conda.fish"
            else
                set -x PATH "%(conda_prefix)s/bin" $PATH
            end
        end
        # <<< conda initialize <<<
        """
    ) % {
        "conda_exe": conda_exe,
        "conda_prefix": conda_prefix,
    }
    return conda_initialize_content


def init_fish_user(target_path, conda_prefix, reverse):
    # target_path: ~/.config/config.fish
    user_rc_path = target_path

    try:
        with open_utf8(user_rc_path) as fh:
            rc_content = fh.read()
    except FileNotFoundError:
        rc_content = ""
    except:
        raise

    rc_original_content = rc_content

    conda_init_comment = "# commented out by conda initialize"
    conda_initialize_content = _config_fish_content(conda_prefix)
    if reverse:
        # uncomment any lines that were commented by prior conda init run
        rc_content = re.sub(
            rf"#\s(.*?)\s*{conda_init_comment}",
            r"\1",
            rc_content,
            flags=re.MULTILINE,
        )

        # remove any conda init sections added
        rc_content = re.sub(
            r"^\s*" + CONDA_INITIALIZE_RE_BLOCK,
            "",
            rc_content,
            flags=re.DOTALL | re.MULTILINE,
        )
    else:
        if not on_win:
            rc_content = re.sub(
                rf"^[ \t]*?(set -gx PATH ([\'\"]?).*?{basename(conda_prefix)}\/bin\2 [^\n]*?\$PATH)"
                r"",
                rf"# \1  {conda_init_comment}",
                rc_content,
                flags=re.MULTILINE,
            )

        rc_content = re.sub(
            r"^[ \t]*[^#\n]?[ \t]*((?:source|\.) .*etc\/fish\/conf\.d\/conda\.fish.*?)\n"
            r"(conda activate.*?)$",
            rf"# \1  {conda_init_comment}\n# \2  {conda_init_comment}",
            rc_content,
            flags=re.MULTILINE,
        )
        rc_content = re.sub(
            r"^[ \t]*[^#\n]?[ \t]*((?:source|\.) .*etc\/fish\/conda\.d\/conda\.fish.*?)$",
            rf"# \1  {conda_init_comment}",
            rc_content,
            flags=re.MULTILINE,
        )

        replace_str = "__CONDA_REPLACE_ME_123__"
        rc_content = re.sub(
            CONDA_INITIALIZE_RE_BLOCK,
            replace_str,
            rc_content,
            flags=re.MULTILINE,
        )
        # TODO: maybe remove all but last of replace_str, if there's more than one occurrence
        rc_content = rc_content.replace(replace_str, conda_initialize_content)

        if "# >>> conda initialize >>>" not in rc_content:
            rc_content += f"\n{conda_initialize_content}\n"

    if rc_content != rc_original_content:
        if context.verbose:
            print("\n")
            print(target_path)
            print(make_diff(rc_original_content, rc_content))
        if not context.dry_run:
            # Make the directory if needed.
            if not exists(dirname(user_rc_path)):
                mkdir_p(dirname(user_rc_path))
            with open_utf8(user_rc_path, "w") as fh:
                fh.write(rc_content)
        return Result.MODIFIED
    else:
        return Result.NO_CHANGE


def _config_xonsh_content(conda_prefix):
    conda_exe = join(conda_prefix, BIN_DIRECTORY, "conda.exe" if on_win else "conda")
    if on_win:
        from ..activate import native_path_to_unix

        conda_exe = native_path_to_unix(conda_exe)
    conda_initialize_content = dals(
        """
    # >>> conda initialize >>>
    # !! Contents within this block are managed by 'conda init' !!
    if !(test -f "{conda_exe}"):
        import sys as _sys
        from types import ModuleType as _ModuleType
        _mod = _ModuleType("xontrib.conda",
                        "Autogenerated from $({conda_exe} shell.xonsh hook)")
        __xonsh__.execer.exec($("{conda_exe}" "shell.xonsh" "hook"),
                            glbs=_mod.__dict__,
                            filename="$({conda_exe} shell.xonsh hook)")
        _sys.modules["xontrib.conda"] = _mod
        del _sys, _mod, _ModuleType
    # <<< conda initialize <<<
    """
    ).format(conda_exe=conda_exe)
    return conda_initialize_content


def init_xonsh_user(target_path, conda_prefix, reverse):
    # target_path: ~/.xonshrc
    user_rc_path = target_path

    try:
        with open_utf8(user_rc_path) as fh:
            rc_content = fh.read()
    except FileNotFoundError:
        rc_content = ""
    except:
        raise

    rc_original_content = rc_content

    conda_init_comment = "# commented out by conda initialize"
    conda_initialize_content = _config_xonsh_content(conda_prefix)
    if reverse:
        # uncomment any lines that were commented by prior conda init run
        rc_content = re.sub(
            rf"#\s(.*?)\s*{conda_init_comment}",
            r"\1",
            rc_content,
            flags=re.MULTILINE,
        )

        # remove any conda init sections added
        rc_content = re.sub(
            r"^\s*" + CONDA_INITIALIZE_RE_BLOCK,
            "",
            rc_content,
            flags=re.DOTALL | re.MULTILINE,
        )
    else:
        replace_str = "__CONDA_REPLACE_ME_123__"
        rc_content = re.sub(
            CONDA_INITIALIZE_RE_BLOCK,
            replace_str,
            rc_content,
            flags=re.MULTILINE,
        )
        # TODO: maybe remove all but last of replace_str, if there's more than one occurrence
        rc_content = rc_content.replace(replace_str, conda_initialize_content)

        if "# >>> conda initialize >>>" not in rc_content:
            rc_content += f"\n{conda_initialize_content}\n"

    if rc_content != rc_original_content:
        if context.verbose:
            print("\n")
            print(target_path)
            print(make_diff(rc_original_content, rc_content))
        if not context.dry_run:
            # Make the directory if needed.
            if not exists(dirname(user_rc_path)):
                mkdir_p(dirname(user_rc_path))
            with open_utf8(user_rc_path, "w") as fh:
                fh.write(rc_content)
        return Result.MODIFIED
    else:
        return Result.NO_CHANGE


def _bashrc_content(conda_prefix, shell):
    conda_exe = join(conda_prefix, BIN_DIRECTORY, "conda.exe" if on_win else "conda")
    if on_win:
        from ..activate import native_path_to_unix

        conda_exe = native_path_to_unix(conda_exe)
        conda_initialize_content = dals(
            """
        # >>> conda initialize >>>
        # !! Contents within this block are managed by 'conda init' !!
        if [ -f '%(conda_exe)s' ]; then
            eval "$('%(conda_exe)s' 'shell.%(shell)s' 'hook')"
        fi
        # <<< conda initialize <<<
        """
        ) % {
            "conda_exe": conda_exe,
            "shell": shell,
        }
    else:
        if shell in ("csh", "tcsh"):
            conda_initialize_content = dals(
                """
            # >>> conda initialize >>>
            # !! Contents within this block are managed by 'conda init' !!
            if ( -f "%(conda_prefix)s/etc/profile.d/conda.csh" ) then
                source "%(conda_prefix)s/etc/profile.d/conda.csh"
            else
                setenv PATH "%(conda_bin)s:$PATH"
            endif
            # <<< conda initialize <<<
            """
            ) % {
                "conda_exe": conda_exe,
                "shell": shell,
                "conda_bin": dirname(conda_exe),
                "conda_prefix": conda_prefix,
            }
        else:
            conda_initialize_content = dals(
                """
            # >>> conda initialize >>>
            # !! Contents within this block are managed by 'conda init' !!
            __conda_setup="$('%(conda_exe)s' 'shell.%(shell)s' 'hook' 2> /dev/null)"
            if [ $? -eq 0 ]; then
                eval "$__conda_setup"
            else
                if [ -f "%(conda_prefix)s/etc/profile.d/conda.sh" ]; then
                    . "%(conda_prefix)s/etc/profile.d/conda.sh"
                else
                    export PATH="%(conda_bin)s:$PATH"
                fi
            fi
            unset __conda_setup
            # <<< conda initialize <<<
            """
            ) % {
                "conda_exe": conda_exe,
                "shell": shell,
                "conda_bin": dirname(conda_exe),
                "conda_prefix": conda_prefix,
            }
    return conda_initialize_content


def init_sh_user(target_path, conda_prefix, shell, reverse=False):
    # target_path: ~/.bash_profile
    user_rc_path = target_path

    try:
        with open_utf8(user_rc_path) as fh:
            rc_content = fh.read()
    except FileNotFoundError:
        rc_content = ""
    except:
        raise

    rc_original_content = rc_content

    conda_initialize_content = _bashrc_content(conda_prefix, shell)
    conda_init_comment = "# commented out by conda initialize"

    if reverse:
        # uncomment any lines that were commented by prior conda init run
        rc_content = re.sub(
            rf"#\s(.*?)\s*{conda_init_comment}",
            r"\1",
            rc_content,
            flags=re.MULTILINE,
        )

        # remove any conda init sections added
        rc_content = re.sub(
            r"^\s*" + CONDA_INITIALIZE_RE_BLOCK,
            "",
            rc_content,
            flags=re.DOTALL | re.MULTILINE,
        )
    else:
        if not on_win:
            rc_content = re.sub(
                rf"^[ \t]*?(export PATH=[\'\"].*?{basename(conda_prefix)}\/bin:\$PATH[\'\"])"
                r"",
                rf"# \1  {conda_init_comment}",
                rc_content,
                flags=re.MULTILINE,
            )

        rc_content = re.sub(
            r"^[ \t]*[^#\n]?[ \t]*((?:source|\.) .*etc\/profile\.d\/conda\.sh.*?)\n"
            r"(conda activate.*?)$",
            rf"# \1  {conda_init_comment}\n# \2  {conda_init_comment}",
            rc_content,
            flags=re.MULTILINE,
        )
        rc_content = re.sub(
            r"^[ \t]*[^#\n]?[ \t]*((?:source|\.) .*etc\/profile\.d\/conda\.sh.*?)$",
            rf"# \1  {conda_init_comment}",
            rc_content,
            flags=re.MULTILINE,
        )

        if on_win:
            rc_content = re.sub(
                r"^[ \t]*^[ \t]*[^#\n]?[ \t]*((?:source|\.) .*Scripts[/\\]activate.*?)$",
                r"# \1  # commented out by conda initialize",
                rc_content,
                flags=re.MULTILINE,
            )
        else:
            rc_content = re.sub(
                r"^[ \t]*^[ \t]*[^#\n]?[ \t]*((?:source|\.) .*bin/activate.*?)$",
                r"# \1  # commented out by conda initialize",
                rc_content,
                flags=re.MULTILINE,
            )

        replace_str = "__CONDA_REPLACE_ME_123__"
        rc_content = re.sub(
            CONDA_INITIALIZE_RE_BLOCK,
            replace_str,
            rc_content,
            flags=re.MULTILINE,
        )
        # TODO: maybe remove all but last of replace_str, if there's more than one occurrence
        rc_content = rc_content.replace(replace_str, conda_initialize_content)

        if "# >>> conda initialize >>>" not in rc_content:
            rc_content += f"\n{conda_initialize_content}\n"

    if rc_content != rc_original_content:
        if context.verbose:
            print("\n")
            print(target_path)
            print(make_diff(rc_original_content, rc_content))
        if not context.dry_run:
            with open_utf8(user_rc_path, "w") as fh:
                fh.write(rc_content)
        return Result.MODIFIED
    else:
        return Result.NO_CHANGE


def init_sh_system(target_path, conda_prefix, reverse=False):
    # target_path: '/etc/profile.d/conda.sh'
    conda_sh_system_path = target_path

    if exists(conda_sh_system_path):
        with open_utf8(conda_sh_system_path) as fh:
            conda_sh_system_contents = fh.read()
    else:
        conda_sh_system_contents = ""
    if reverse:
        if exists(conda_sh_system_path):
            os.remove(conda_sh_system_path)
            return Result.MODIFIED
    else:
        conda_sh_contents = _bashrc_content(conda_prefix, "posix")
        if conda_sh_system_contents != conda_sh_contents:
            if context.verbose:
                print("\n")
                print(target_path)
                print(make_diff(conda_sh_contents, conda_sh_system_contents))
            if not context.dry_run:
                if lexists(conda_sh_system_path):
                    rm_rf(conda_sh_system_path)
                mkdir_p(dirname(conda_sh_system_path))
                with open_utf8(conda_sh_system_path, "w") as fh:
                    fh.write(conda_sh_contents)
            return Result.MODIFIED
    return Result.NO_CHANGE


def _read_windows_registry(target_path):  # pragma: no cover
    # HKEY_LOCAL_MACHINE\Software\Microsoft\Command Processor\AutoRun
    # HKEY_CURRENT_USER\Software\Microsoft\Command Processor\AutoRun
    # returns value_value, value_type  -or-  None, None if target does not exist
    main_key, the_rest = target_path.split("\\", 1)
    subkey_str, value_name = the_rest.rsplit("\\", 1)
    main_key = getattr(winreg, main_key)

    try:
        key = winreg.OpenKey(main_key, subkey_str, 0, winreg.KEY_READ)
    except OSError as e:
        if e.errno != ENOENT:
            raise
        return None, None

    try:
        value_tuple = winreg.QueryValueEx(key, value_name)
        value_value = value_tuple[0]
        if isinstance(value_value, str):
            value_value = value_value.strip()
        value_type = value_tuple[1]
        return value_value, value_type
    except Exception:
        # [WinError 2] The system cannot find the file specified
        winreg.CloseKey(key)
        return None, None
    finally:
        winreg.CloseKey(key)


def _write_windows_registry(target_path, value_value, value_type):  # pragma: no cover
    main_key, the_rest = target_path.split("\\", 1)
    subkey_str, value_name = the_rest.rsplit("\\", 1)
    main_key = getattr(winreg, main_key)
    try:
        key = winreg.OpenKey(main_key, subkey_str, 0, winreg.KEY_WRITE)
    except OSError as e:
        if e.errno != ENOENT:
            raise
        key = winreg.CreateKey(main_key, subkey_str)
    try:
        winreg.SetValueEx(key, value_name, 0, value_type, value_value)
    finally:
        winreg.CloseKey(key)


def init_cmd_exe_registry(target_path, conda_prefix, reverse=False):
    # HKEY_LOCAL_MACHINE\Software\Microsoft\Command Processor\AutoRun
    # HKEY_CURRENT_USER\Software\Microsoft\Command Processor\AutoRun

    prev_value, value_type = _read_windows_registry(target_path)
    if prev_value is None:
        prev_value = ""
        value_type = winreg.REG_EXPAND_SZ

    old_hook_path = '"{}"'.format(join(conda_prefix, "condabin", "conda_hook.bat"))
    new_hook = f"if exist {old_hook_path} {old_hook_path}"
    if reverse:
        # we can't just reset it to None and remove it, because there may be other contents here.
        #   We need to strip out our part, and if there's nothing left, remove the key.
        # Break up string by parts joined with "&"
        autorun_parts = prev_value.split("&")
        autorun_parts = [part.strip() for part in autorun_parts if new_hook not in part]
        # We must remove the old hook path too if it is there
        autorun_parts = [
            part.strip() for part in autorun_parts if old_hook_path not in part
        ]
        new_value = " & ".join(autorun_parts)
    else:
        replace_str = "__CONDA_REPLACE_ME_123__"
        # Replace new (if exist checked) hook
        new_value = re.sub(
            r"(if exist \"[^\"]*?conda[-_]hook\.bat\" \"[^\"]*?conda[-_]hook\.bat\")",
            replace_str,
            prev_value,
            count=1,
            flags=re.IGNORECASE | re.UNICODE,
        )
        # Replace old hook
        new_value = re.sub(
            r"(\"[^\"]*?conda[-_]hook\.bat\")",
            replace_str,
            new_value,
            flags=re.IGNORECASE | re.UNICODE,
        )

        # Fold repeats of 'HOOK & HOOK'
        new_value_2 = new_value.replace(replace_str + " & " + replace_str, replace_str)
        while new_value_2 != new_value:
            new_value = new_value_2
            new_value_2 = new_value.replace(
                replace_str + " & " + replace_str, replace_str
            )
        new_value = new_value_2.replace(replace_str, new_hook)
        if new_hook not in new_value:
            if new_value:
                new_value += " & " + new_hook
            else:
                new_value = new_hook

    if prev_value != new_value:
        if context.verbose:
            print("\n")
            print(target_path)
            print(make_diff(prev_value, new_value))
        if not context.dry_run:
            _write_windows_registry(target_path, new_value, value_type)
        return Result.MODIFIED
    else:
        return Result.NO_CHANGE


def init_long_path(target_path):
    win_ver, _, win_rev = context.os_distribution_name_version[1].split(".")
    # win10, build 14352 was the first preview release that supported this
    if int(win_ver) >= 10 and int(win_rev) >= 14352:
        prev_value, value_type = _read_windows_registry(target_path)
        if str(prev_value) != "1":
            if context.verbose:
                print("\n")
                print(target_path)
                print(make_diff(str(prev_value), "1"))
            if not context.dry_run:
                _write_windows_registry(target_path, 1, winreg.REG_DWORD)
            return Result.MODIFIED
        else:
            return Result.NO_CHANGE
    else:
        if context.verbose:
            print("\n")
            print(
                "Not setting long path registry key; Windows version must be at least 10 with "
                'the fall 2016 "Anniversary update" or newer.'
            )
            return Result.NO_CHANGE


def _powershell_profile_content(conda_prefix):
    conda_exe = join(conda_prefix, BIN_DIRECTORY, "conda.exe" if on_win else "conda")

    conda_powershell_module = dals(
        f"""
    #region conda initialize
    # !! Contents within this block are managed by 'conda init' !!
    If (Test-Path "{conda_exe}") {{
        (& "{conda_exe}" "shell.powershell" "hook") | Out-String | ?{{$_}} | Invoke-Expression
    }}
    #endregion
    """
    )

    return conda_powershell_module


def init_powershell_user(target_path, conda_prefix, reverse):
    # target_path: $PROFILE
    profile_path = target_path

    # NB: the user may not have created a profile. We need to check
    #     if the file exists first.
    if os.path.exists(profile_path):
        with open_utf8(profile_path) as fp:
            profile_content = fp.read()
    else:
        profile_content = ""

    profile_original_content = profile_content

    # TODO: comment out old ipmos and Import-Modules.

    if reverse:
        profile_content = re.sub(
            CONDA_INITIALIZE_PS_RE_BLOCK,
            "",
            profile_content,
            count=1,
            flags=re.DOTALL | re.MULTILINE,
        )
    else:
        # Find what content we need to add.
        conda_initialize_content = _powershell_profile_content(conda_prefix)

        if "#region conda initialize" not in profile_content:
            profile_content += f"\n{conda_initialize_content}\n"
        else:
            profile_content = re.sub(
                CONDA_INITIALIZE_PS_RE_BLOCK,
                "__CONDA_REPLACE_ME_123__",
                profile_content,
                count=1,
                flags=re.DOTALL | re.MULTILINE,
            ).replace("__CONDA_REPLACE_ME_123__", conda_initialize_content)

    if profile_content != profile_original_content:
        if context.verbose:
            print("\n")
            print(target_path)
            print(make_diff(profile_original_content, profile_content))
        if not context.dry_run:
            # Make the directory if needed.
            if not exists(dirname(profile_path)):
                mkdir_p(dirname(profile_path))
            with open_utf8(profile_path, "w") as fp:
                fp.write(profile_content)
        return Result.MODIFIED
    else:
        return Result.NO_CHANGE


def remove_conda_in_sp_dir(target_path):
    # target_path: site_packages_dir
    modified = False
    site_packages_dir = target_path
    rm_rf_these = chain.from_iterable(
        (
            glob(join(site_packages_dir, "conda-*info")),
            glob(join(site_packages_dir, "conda.*")),
            glob(join(site_packages_dir, "conda-*.egg")),
        )
    )
    rm_rf_these = (p for p in rm_rf_these if not p.endswith("conda.egg-link"))
    for fn in rm_rf_these:
        print(f"rm -rf {join(site_packages_dir, fn)}", file=sys.stderr)
        if not context.dry_run:
            rm_rf(join(site_packages_dir, fn))
        modified = True
    others = (
        "conda",
        "conda_env",
    )
    for other in others:
        path = join(site_packages_dir, other)
        if lexists(path):
            print(f"rm -rf {path}", file=sys.stderr)
            if not context.dry_run:
                rm_rf(path)
            modified = True
    if modified:
        return Result.MODIFIED
    else:
        return Result.NO_CHANGE


def make_conda_egg_link(target_path, conda_source_root):
    # target_path: join(site_packages_dir, 'conda.egg-link')
    conda_egg_link_contents = conda_source_root + os.linesep

    if isfile(target_path):
        with open_utf8(target_path, "rb") as fh:
            conda_egg_link_contents_old = fh.read()
    else:
        conda_egg_link_contents_old = ""

    if conda_egg_link_contents_old != conda_egg_link_contents:
        if context.verbose:
            print("\n", file=sys.stderr)
            print(target_path, file=sys.stderr)
            print(
                make_diff(conda_egg_link_contents_old, conda_egg_link_contents),
                file=sys.stderr,
            )
        if not context.dry_run:
            with open_utf8(target_path, "wb") as fh:
                fh.write(ensure_utf8_encoding(conda_egg_link_contents))
        return Result.MODIFIED
    else:
        return Result.NO_CHANGE


def modify_easy_install_pth(target_path, conda_source_root):
    # target_path: join(site_packages_dir, 'easy-install.pth')
    easy_install_new_line = conda_source_root

    if isfile(target_path):
        with open_utf8(target_path) as fh:
            old_contents = fh.read()
    else:
        old_contents = ""

    old_contents_lines = old_contents.splitlines()
    if easy_install_new_line in old_contents_lines:
        return Result.NO_CHANGE

    ln_end = os.sep + "conda"
    old_contents_lines = tuple(
        ln for ln in old_contents_lines if not ln.endswith(ln_end)
    )
    new_contents = (
        easy_install_new_line
        + os.linesep
        + os.linesep.join(old_contents_lines)
        + os.linesep
    )

    if context.verbose:
        print("\n", file=sys.stderr)
        print(target_path, file=sys.stderr)
        print(make_diff(old_contents, new_contents), file=sys.stderr)
    if not context.dry_run:
        with open_utf8(target_path, "wb") as fh:
            fh.write(ensure_utf8_encoding(new_contents))
    return Result.MODIFIED


def make_dev_egg_info_file(target_path):
    # target_path: join(conda_source_root, 'conda.egg-info')

    if isfile(target_path):
        with open_utf8(target_path) as fh:
            old_contents = fh.read()
    else:
        old_contents = ""

    new_contents = (
        dals(
            """
    Metadata-Version: 1.1
    Name: conda
    Version: %s
    Platform: UNKNOWN
    Summary: OS-agnostic, system-level binary package manager.
    """
        )
        % CONDA_VERSION
    )

    if old_contents == new_contents:
        return Result.NO_CHANGE

    if context.verbose:
        print("\n", file=sys.stderr)
        print(target_path, file=sys.stderr)
        print(make_diff(old_contents, new_contents), file=sys.stderr)
    if not context.dry_run:
        if lexists(target_path):
            rm_rf(target_path)
        with open_utf8(target_path, "w") as fh:
            fh.write(new_contents)
    return Result.MODIFIED


# #####################################################
# helper functions
# #####################################################


def make_diff(old, new):
    return "\n".join(unified_diff(old.splitlines(), new.splitlines()))


def _get_python_info(prefix):
    python_exe = join(prefix, get_python_short_path())
    result = subprocess_call(f"{python_exe} --version")
    stdout, stderr = result.stdout.strip(), result.stderr.strip()
    if stderr:
        python_version = stderr.split()[1]
    elif stdout:  # pragma: no cover
        python_version = stdout.split()[1]
    else:  # pragma: no cover
        raise ValueError("No python version information available.")

    site_packages_dir = join(
        prefix, win_path_ok(get_python_site_packages_short_path(python_version))
    )
    return python_exe, python_version, site_packages_dir


if __name__ == "__main__":
    if on_win:
        temp_path = sys.argv[1]
        run_plan_from_temp_file(temp_path)
    else:
        run_plan_from_stdin()
