# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.

"""
Test using the NIST Test Vectors
"""

import binascii
import os

import pytest

from cryptography.hazmat.decrepit.ciphers.algorithms import RC2
from cryptography.hazmat.primitives.ciphers import modes

from ....utils import load_nist_vectors
from ..utils import generate_encrypt_test


@pytest.mark.supported(
    only_if=lambda backend: backend.cipher_supported(
        RC2(b"\x00" * 16), modes.CBC(b"\x00" * 8)
    ),
    skip_message="Does not support RC2 CBC",
)
class TestRC2ModeCBC:
    test_kat = generate_encrypt_test(
        load_nist_vectors,
        os.path.join("ciphers", "RC2"),
        [
            "rc2-cbc.txt",
        ],
        lambda key, **kwargs: RC2(binascii.unhexlify(key)),
        lambda iv, **kwargs: modes.CBC(binascii.unhexlify(iv)),
    )
