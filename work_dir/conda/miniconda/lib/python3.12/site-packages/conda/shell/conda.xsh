# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
# Much of this forked from https://github.com/gforsyth/xonda
# Copyright (c) 2016, Gil Forsyth, All rights reserved.
# Original code licensed under BSD-3-Clause.

try:
    # xonsh >= 0.18.0
    from xonsh.lib.lazyasd import lazyobject
except:
    # xonsh < 0.18.0
    from xonsh.lazyasd import lazyobject

if 'CONDA_EXE' not in ${...}:
    ![python -m conda init --dev out> conda-dev-init.sh]
    source-bash conda-dev-init.sh
    import os
    os.remove("conda-dev-init.sh")

_REACTIVATE_COMMANDS = ('install', 'update', 'upgrade', 'remove', 'uninstall')


@lazyobject
def Env():
    from collections import namedtuple
    return namedtuple('Env', ['name', 'path', 'bin_dir', 'envs_dir'])


def _parse_args(args=None):
    from argparse import ArgumentParser
    p = ArgumentParser(add_help=False)
    p.add_argument('command', nargs='?')
    p.add_argument('-h', '--help', dest='help', action='store_true', default=False)
    p.add_argument('-v', '--version', dest='version', action='store_true', default=False)
    ns, _ = p.parse_known_args(args)
    if ns.command == 'activate':
        p.add_argument('env_name_or_prefix', default='base')
    elif ns.command in _REACTIVATE_COMMANDS:
        p.add_argument('-n', '--name')
        p.add_argument('-p', '--prefix')
    parsed_args, _ = p.parse_known_args(args)
    return parsed_args


def _raise_pipeline_error(pipeline):
    stdout = pipeline.out
    stderr = pipeline.err
    if pipeline.returncode != 0:
        message = ("exited with %s\nstdout: %s\nstderr: %s\n"
                   "" % (pipeline.returncode, stdout, stderr))
        raise RuntimeError(message)
    return stdout.strip()


def _conda_activate_handler(env_name_or_prefix):
    import os

    __xonsh__.execer.exec($($CONDA_EXE shell.xonsh activate @(env_name_or_prefix)),
                          glbs=__xonsh__.ctx,
                          filename="$(conda shell.xonsh activate " + env_name_or_prefix + ")")
    if $CONDA_DEFAULT_ENV != os.path.split(env_name_or_prefix)[1]:
        import sys as _sys

        print("WARNING: conda environment not activated properly. "
              "This is likely because you have a conda init inside of your "
              "~/.bashrc (unix) or *.bat activation file (windows). This is "
              "causing conda to activate twice in xonsh. Please remove the conda "
              "init block from your other shell.", file=_sys.stderr)


def _conda_deactivate_handler():
    __xonsh__.execer.exec($($CONDA_EXE shell.xonsh deactivate),
                          glbs=__xonsh__.ctx,
                          filename="$(conda shell.xonsh deactivate)")


def _conda_passthrough_handler(args):
    pipeline = ![$CONDA_EXE @(args)]
    _raise_pipeline_error(pipeline)


def _conda_reactivate_handler(args, name_or_prefix_given):
    pipeline = ![$CONDA_EXE @(args)]
    _raise_pipeline_error(pipeline)
    if not name_or_prefix_given:
        __xonsh__.execer.exec($($CONDA_EXE shell.xonsh reactivate),
                              glbs=__xonsh__.ctx,
                              filename="$(conda shell.xonsh reactivate)")


def _conda_main(args=None):
    parsed_args = _parse_args(args)
    if parsed_args.command == 'activate':
        _conda_activate_handler(parsed_args.env_name_or_prefix)
    elif parsed_args.command == 'deactivate':
        _conda_deactivate_handler()
    elif parsed_args.command in _REACTIVATE_COMMANDS:
        name_or_prefix_given = bool(parsed_args.name or parsed_args.prefix)
        _conda_reactivate_handler(args, name_or_prefix_given)
    else:
        _conda_passthrough_handler(args)


if 'CONDA_SHLVL' not in ${...}:
    $CONDA_SHLVL = '0'
    import os as _os
    import sys as _sys
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.dirname($CONDA_EXE)), "condabin"))
    del _os, _sys

aliases['conda'] = _conda_main


def _list_dirs(path):
    """Generator that lists the directories in a given path."""
    import os
    for entry in os.scandir(path):
        if not entry.name.startswith('.') and entry.is_dir():
            yield entry.name


def _get_envs_unfiltered():
    """Grab a list of all conda env dirs from conda, allowing all warnings."""
    import os
    import importlib

    try:
        # breaking changes introduced in Anaconda 4.4.7
        # try to import newer library structure first
        context = importlib.import_module('conda.base.context')
        config = context.context
    except ModuleNotFoundError:
        config = importlib.import_module('conda.config')

    # create the list of environments
    env_list = []
    for envs_dir in config.envs_dirs:
        # skip non-existing environments directories
        if not os.path.exists(envs_dir):
            continue
        # for each environment in the environments directory
        for env_name in _list_dirs(envs_dir):
            # check for duplicates names
            if env_name in [env.name for env in env_list]:
                raise ValueError('Multiple environments with the same name '
                                 "in the system is not supported by conda's xonsh tools.")
            # add the environment to the list
            env_list.append(Env(name=env_name,
                                path=os.path.join(envs_dir, env_name),
                                bin_dir=os.path.join(envs_dir, env_name, 'bin'),
                                envs_dir=envs_dir,
                            ))
    return env_list


def _get_envs():
    """Grab a list of all conda env dirs from conda, ignoring all warnings."""
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return _get_envs_unfiltered()


def _conda_completer(prefix, line, start, end, ctx):
    """Completion for conda."""
    args = line.split(' ')
    possible = set()
    if len(args) == 0 or args[0] not in ['xonda', 'conda']:
        return None
    curix = args.index(prefix)
    if curix == 1:
        possible = {'activate', 'deactivate', 'install', 'remove', 'info',
                    'help', 'list', 'search', 'update', 'upgrade', 'uninstall',
                    'config', 'init', 'clean', 'package', 'bundle', 'env',
                    'select', 'create', '-h', '--help', '-V', '--version'}

    elif curix == 2:
        if args[1] in ['activate', 'select']:
            possible = set([env.name for env in _get_envs()])
        elif args[1] == 'create':
            possible = {'-p', '-n'}
        elif args[1] == 'env':
            possible = {'attach', 'create', 'export', 'list', 'remove',
                        'upload', 'update'}

    elif curix == 3:
        if args[2] == 'export':
            possible = {'-n', '--name'}
        elif args[2] == 'create':
            possible = {'-h', '--help', '-f', '--file', '-n', '--name', '-p',
                        '--prefix', '-q', '--quiet', '--force', '--json',
                        '--debug', '-v', '--verbose'}

    elif curix == 4:
        if args[2] == 'export' and args[3] in ['-n','--name']:
            possible = set([env.name for env in _get_envs()])

    return {i for i in possible if i.startswith(prefix)}


# add _xonda_completer to list of completers
__xonsh__.completers['conda'] = _conda_completer
# bump to top of list
__xonsh__.completers.move_to_end('conda', last=False)
