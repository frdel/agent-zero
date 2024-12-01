# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


import binascii
import os
import typing

import pytest

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.x963kdf import X963KDF

from ...doubles import DummyHashAlgorithm
from ...utils import load_vectors_from_file, load_x963_vectors


def _skip_hashfn_unsupported(backend, hashfn):
    if not backend.hash_supported(hashfn):
        pytest.skip(
            f"Hash {hashfn.name} is not supported by this backend {backend}"
        )


class TestX963:
    _algorithms_dict: typing.ClassVar[
        typing.Dict[str, typing.Type[hashes.HashAlgorithm]]
    ] = {
        "SHA-1": hashes.SHA1,
        "SHA-224": hashes.SHA224,
        "SHA-256": hashes.SHA256,
        "SHA-384": hashes.SHA384,
        "SHA-512": hashes.SHA512,
    }

    def test_x963(self, backend, subtests):
        vectors = load_vectors_from_file(
            os.path.join("KDF", "ansx963_2001.txt"), load_x963_vectors
        )
        for vector in vectors:
            with subtests.test():
                hashfn = self._algorithms_dict[vector["hash"]]
                _skip_hashfn_unsupported(backend, hashfn())

                key = binascii.unhexlify(vector["Z"])
                sharedinfo = None
                if vector["sharedinfo_length"] != 0:
                    sharedinfo = binascii.unhexlify(vector["sharedinfo"])
                key_data_len = vector["key_data_length"] // 8
                key_data = binascii.unhexlify(vector["key_data"])

                xkdf = X963KDF(
                    algorithm=hashfn(),
                    length=key_data_len,
                    sharedinfo=sharedinfo,
                    backend=backend,
                )
                xkdf.verify(key, key_data)

    def test_unsupported_hash(self, backend):
        with pytest.raises(pytest.skip.Exception):
            _skip_hashfn_unsupported(backend, DummyHashAlgorithm())
