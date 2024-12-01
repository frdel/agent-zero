# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


import os

from ...utils import load_nist_kbkdf_vectors
from .utils import generate_kbkdf_counter_mode_test


class TestCounterKDFCounterMode:
    test_kbkdfctr = generate_kbkdf_counter_mode_test(
        load_nist_kbkdf_vectors,
        os.path.join("KDF"),
        ["nist-800-108-KBKDF-CTR.txt"],
    )
