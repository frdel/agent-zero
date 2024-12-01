# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers import (
    BlockCipherAlgorithm,
    CipherAlgorithm,
)
from cryptography.hazmat.primitives.ciphers.modes import Mode


class DummyCipherAlgorithm(CipherAlgorithm):
    name = "dummy-cipher"
    block_size = 128
    key_size = 256
    key_sizes = frozenset([256])


class DummyBlockCipherAlgorithm(DummyCipherAlgorithm, BlockCipherAlgorithm):
    def __init__(self, _: object) -> None:
        pass

    name = "dummy-block-cipher"


class DummyMode(Mode):
    name = "dummy-mode"

    def validate_for_algorithm(self, algorithm: CipherAlgorithm) -> None:
        pass


class DummyHashAlgorithm(hashes.HashAlgorithm):
    name = "dummy-hash"
    block_size = None
    digest_size = 32


class DummyKeySerializationEncryption(
    serialization.KeySerializationEncryption
):
    pass


class DummyAsymmetricPadding(padding.AsymmetricPadding):
    name = "dummy-padding"
