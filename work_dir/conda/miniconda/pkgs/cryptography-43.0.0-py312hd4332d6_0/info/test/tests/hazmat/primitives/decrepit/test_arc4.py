# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


import binascii
import os

import pytest

from cryptography.hazmat.decrepit.ciphers import algorithms

from ....utils import load_nist_vectors
from ..utils import generate_stream_encryption_test


@pytest.mark.supported(
    only_if=lambda backend: backend.cipher_supported(
        algorithms.ARC4(b"\x00" * 16), None
    ),
    skip_message="Does not support ARC4",
)
class TestARC4:
    test_rfc = generate_stream_encryption_test(
        load_nist_vectors,
        os.path.join("ciphers", "ARC4"),
        [
            "rfc-6229-40.txt",
            "rfc-6229-56.txt",
            "rfc-6229-64.txt",
            "rfc-6229-80.txt",
            "rfc-6229-128.txt",
            "rfc-6229-192.txt",
            "rfc-6229-256.txt",
            "arc4.txt",
        ],
        lambda key, **kwargs: algorithms.ARC4(binascii.unhexlify(key)),
    )
