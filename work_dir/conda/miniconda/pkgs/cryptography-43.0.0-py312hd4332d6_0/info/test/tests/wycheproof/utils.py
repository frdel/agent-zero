# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.

import pytest

from ..utils import load_wycheproof_tests


def wycheproof_tests(*paths, subdir="testvectors"):
    def wrapper(func):
        @pytest.mark.parametrize("path", paths)
        def run_wycheproof(backend, subtests, pytestconfig, path):
            wycheproof_root = pytestconfig.getoption(
                "--wycheproof-root", skip=True
            )
            for test in load_wycheproof_tests(wycheproof_root, path, subdir):
                with subtests.test():
                    func(backend, test)

        return run_wycheproof

    return wrapper
