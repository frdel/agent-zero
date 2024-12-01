# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.

from cryptography.hazmat.primitives import hashes


def test_sha256(benchmark):
    def bench():
        h = hashes.Hash(hashes.SHA256())
        h.update(b"I love hashing. So much. The best.")
        return h.finalize()

    benchmark(bench)
