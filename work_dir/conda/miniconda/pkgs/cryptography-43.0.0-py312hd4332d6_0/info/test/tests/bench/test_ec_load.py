# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.

from ..hazmat.primitives.fixtures_ec import EC_KEY_SECP256R1


def test_load_ec_public_numbers(benchmark):
    benchmark(EC_KEY_SECP256R1.public_numbers.public_key)


def test_load_ec_private_numbers(benchmark):
    benchmark(EC_KEY_SECP256R1.private_key)
