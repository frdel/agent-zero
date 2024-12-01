# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.

import binascii
import os

import pytest

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from ...utils import load_nist_vectors, load_vectors_from_file


@pytest.mark.supported(
    only_if=lambda backend: backend.pbkdf2_hmac_supported(hashes.SHA1()),
    skip_message="Does not support SHA1 for PBKDF2HMAC",
)
def test_pbkdf2_hmacsha1_vectors(subtests, backend):
    params = load_vectors_from_file(
        os.path.join("KDF", "rfc-6070-PBKDF2-SHA1.txt"),
        load_nist_vectors,
    )
    for param in params:
        with subtests.test():
            iterations = int(param["iterations"])
            if iterations > 1_000_000:
                pytest.skip("Skipping test due to iteration count")
            kdf = PBKDF2HMAC(
                hashes.SHA1(),
                int(param["length"]),
                param["salt"],
                iterations,
            )
            derived_key = kdf.derive(param["password"])
            assert binascii.hexlify(derived_key) == param["derived_key"]
