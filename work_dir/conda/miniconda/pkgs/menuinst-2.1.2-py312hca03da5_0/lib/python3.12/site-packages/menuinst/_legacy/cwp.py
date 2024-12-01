# this script is used on windows to wrap shortcuts so that they are executed within an environment
#   It only sets the appropriate prefix PATH entries - it does not actually activate environments

import argparse
import os
import subprocess
import sys
from os.path import join, pathsep

# this must be an absolute import since the cwp.py script is copied to $PREFIX
from menuinst.knownfolders import FOLDERID, get_folder_path


def main(argv=None):
    # call as: python cwp.py [--no-console] PREFIX ARGs...
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--no-console", action="store_true", help="Create subprocess with CREATE_NO_WINDOW flag."
    )
    parser.add_argument("prefix", help="Prefix to be 'activated' before calling `args`.")
    parser.add_argument(
        "args", nargs=argparse.REMAINDER, help="Command (and arguments) to be executed."
    )
    parsed_args = parser.parse_args(argv)

    no_console = parsed_args.no_console
    prefix = parsed_args.prefix
    args = parsed_args.args

    new_paths = pathsep.join(
        [
            prefix,
            join(prefix, "Library", "mingw-w64", "bin"),
            join(prefix, "Library", "usr", "bin"),
            join(prefix, "Library", "bin"),
            join(prefix, "Scripts"),
        ]
    )
    env = os.environ.copy()
    env["PATH"] = new_paths + pathsep + env["PATH"]
    env["CONDA_PREFIX"] = prefix

    documents_folder, exception = get_folder_path(FOLDERID.Documents)
    if exception:
        documents_folder, exception = get_folder_path(FOLDERID.PublicDocuments)
    if not exception:
        os.chdir(documents_folder)

    creationflags = {}
    if no_console:
        creationflags["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    sys.exit(subprocess.call(args, env=env, **creationflags))


if __name__ == "__main__":
    main()
