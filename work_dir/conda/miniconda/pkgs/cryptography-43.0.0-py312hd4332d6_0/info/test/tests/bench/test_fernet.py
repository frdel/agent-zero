# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.

from cryptography import fernet


def test_fernet_encrypt(benchmark):
    f = fernet.Fernet(fernet.Fernet.generate_key())
    benchmark(f.encrypt, b"\x00" * 256)
