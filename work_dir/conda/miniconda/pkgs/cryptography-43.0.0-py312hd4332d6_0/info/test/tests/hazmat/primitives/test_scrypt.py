# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


import binascii
import os

import pytest

from cryptography.exceptions import AlreadyFinalized, InvalidKey
from cryptography.hazmat.primitives.kdf.scrypt import _MEM_LIMIT, Scrypt
from tests.utils import (
    load_nist_vectors,
    load_vectors_from_file,
    raises_unsupported_algorithm,
)

vectors = load_vectors_from_file(
    os.path.join("KDF", "scrypt.txt"), load_nist_vectors
)


def _skip_if_memory_limited(memory_limit, params):
    # Memory calc adapted from OpenSSL (URL split over 2 lines, thanks PEP8)
    # https://github.com/openssl/openssl/blob/6286757141a8c6e14d647ec733634a
    # e0c83d9887/crypto/evp/scrypt.c#L189-L221
    blen = int(params["p"]) * 128 * int(params["r"])
    vlen = 32 * int(params["r"]) * (int(params["n"]) + 2) * 4
    memory_required = blen + vlen
    if memory_limit < memory_required:
        pytest.skip(
            "Test exceeds Scrypt memory limit. "
            "This is likely a 32-bit platform."
        )


def test_memory_limit_skip():
    with pytest.raises(pytest.skip.Exception):
        _skip_if_memory_limited(1000, {"p": 16, "r": 64, "n": 1024})

    _skip_if_memory_limited(2**31, {"p": 16, "r": 64, "n": 1024})


@pytest.mark.supported(
    only_if=lambda backend: not backend.scrypt_supported(),
    skip_message="Supports scrypt so can't test unsupported path",
)
def test_unsupported_backend(backend):
    # This test is currently exercised by LibreSSL, which does
    # not support scrypt
    with raises_unsupported_algorithm(None):
        Scrypt(b"NaCl", 64, 1024, 8, 16)


@pytest.mark.supported(
    only_if=lambda backend: backend.scrypt_supported(),
    skip_message="Does not support Scrypt",
)
class TestScrypt:
    @pytest.mark.parametrize("params", vectors)
    def test_derive(self, backend, params):
        _skip_if_memory_limited(_MEM_LIMIT, params)
        password = params["password"]
        work_factor = int(params["n"])
        block_size = int(params["r"])
        parallelization_factor = int(params["p"])
        length = int(params["length"])
        salt = params["salt"]
        derived_key = params["derived_key"]

        scrypt = Scrypt(
            salt,
            length,
            work_factor,
            block_size,
            parallelization_factor,
            backend,
        )
        assert binascii.hexlify(scrypt.derive(password)) == derived_key

    def test_salt_not_bytes(self, backend):
        work_factor = 1024
        block_size = 8
        parallelization_factor = 16
        length = 64
        salt = 1

        with pytest.raises(TypeError):
            Scrypt(
                salt,  # type: ignore[arg-type]
                length,
                work_factor,
                block_size,
                parallelization_factor,
                backend,
            )

    def test_scrypt_malloc_failure(self, backend):
        password = b"NaCl"
        work_factor = 1024**3
        block_size = 589824
        parallelization_factor = 16
        length = 64
        salt = b"NaCl"

        scrypt = Scrypt(
            salt,
            length,
            work_factor,
            block_size,
            parallelization_factor,
            backend,
        )

        with pytest.raises(MemoryError):
            scrypt.derive(password)

    def test_password_not_bytes(self, backend):
        password = 1
        work_factor = 1024
        block_size = 8
        parallelization_factor = 16
        length = 64
        salt = b"NaCl"

        scrypt = Scrypt(
            salt,
            length,
            work_factor,
            block_size,
            parallelization_factor,
            backend,
        )

        with pytest.raises(TypeError):
            scrypt.derive(password)  # type: ignore[arg-type]

    def test_buffer_protocol(self, backend):
        password = bytearray(b"password")
        work_factor = 256
        block_size = 8
        parallelization_factor = 16
        length = 10
        salt = b"NaCl"

        scrypt = Scrypt(
            salt,
            length,
            work_factor,
            block_size,
            parallelization_factor,
            backend,
        )

        assert scrypt.derive(password) == b"\xf4\x92\x86\xb2\x06\x0c\x848W\x87"

    @pytest.mark.parametrize("params", vectors)
    def test_verify(self, backend, params):
        _skip_if_memory_limited(_MEM_LIMIT, params)
        password = params["password"]
        work_factor = int(params["n"])
        block_size = int(params["r"])
        parallelization_factor = int(params["p"])
        length = int(params["length"])
        salt = params["salt"]
        derived_key = params["derived_key"]

        scrypt = Scrypt(
            salt,
            length,
            work_factor,
            block_size,
            parallelization_factor,
            backend,
        )
        scrypt.verify(password, binascii.unhexlify(derived_key))

    def test_invalid_verify(self, backend):
        password = b"password"
        work_factor = 1024
        block_size = 8
        parallelization_factor = 16
        length = 64
        salt = b"NaCl"
        derived_key = b"fdbabe1c9d3472007856e7190d01e9fe7c6ad7cbc8237830e773"

        scrypt = Scrypt(
            salt,
            length,
            work_factor,
            block_size,
            parallelization_factor,
            backend,
        )

        with pytest.raises(InvalidKey):
            scrypt.verify(password, binascii.unhexlify(derived_key))

    def test_already_finalized(self, backend):
        password = b"password"
        work_factor = 1024
        block_size = 8
        parallelization_factor = 16
        length = 64
        salt = b"NaCl"

        scrypt = Scrypt(
            salt,
            length,
            work_factor,
            block_size,
            parallelization_factor,
            backend,
        )
        scrypt.derive(password)
        with pytest.raises(AlreadyFinalized):
            scrypt.derive(password)

    def test_invalid_n(self, backend):
        # n is less than 2
        with pytest.raises(ValueError):
            Scrypt(b"NaCl", 64, 1, 8, 16, backend)

        # n is not a power of 2
        with pytest.raises(ValueError):
            Scrypt(b"NaCl", 64, 3, 8, 16, backend)

    def test_invalid_r(self, backend):
        with pytest.raises(ValueError):
            Scrypt(b"NaCl", 64, 2, 0, 16, backend)

    def test_invalid_p(self, backend):
        with pytest.raises(ValueError):
            Scrypt(b"NaCl", 64, 2, 8, 0, backend)
