# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.

import os
import pkgutil
import subprocess
import sys
import typing

import cryptography


def find_all_modules() -> typing.List[str]:
    return sorted(
        mod
        for _, mod, _ in pkgutil.walk_packages(
            cryptography.__path__,
            prefix=cryptography.__name__ + ".",
        )
    )


def test_no_circular_imports(subtests):
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(sys.path)

    # When using pytest-cov it attempts to instrument subprocesses. This
    # causes the memleak tests to raise exceptions.
    # we don't need coverage so we remove the env vars.
    env.pop("COV_CORE_CONFIG", None)
    env.pop("COV_CORE_DATAFILE", None)
    env.pop("COV_CORE_SOURCE", None)

    for module in find_all_modules():
        with subtests.test():
            argv = [sys.executable, "-c", f"__import__({module!r})"]
            subprocess.check_call(argv, env=env)
