# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


import binascii
import os
import struct

import pytest

from cryptography.exceptions import AlreadyFinalized
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

from ...utils import load_nist_vectors
from .utils import _load_all_params


@pytest.mark.supported(
    only_if=lambda backend: backend.cipher_supported(
        algorithms.ChaCha20(b"\x00" * 32, b"0" * 16), None
    ),
    skip_message="Does not support ChaCha20",
)
class TestChaCha20:
    @pytest.mark.parametrize(
        "vector",
        _load_all_params(
            os.path.join("ciphers", "ChaCha20"),
            ["counter-overflow.txt", "rfc7539.txt"],
            load_nist_vectors,
        ),
    )
    def test_vectors(self, vector, backend):
        key = binascii.unhexlify(vector["key"])
        nonce = binascii.unhexlify(vector["nonce"])
        ibc = struct.pack("<Q", int(vector["initial_block_counter"]))
        pt = binascii.unhexlify(vector["plaintext"])
        encryptor = Cipher(
            algorithms.ChaCha20(key, ibc + nonce), None, backend
        ).encryptor()
        computed_ct = encryptor.update(pt) + encryptor.finalize()
        assert binascii.hexlify(computed_ct) == vector["ciphertext"]

    def test_buffer_protocol(self, backend):
        key = bytearray(os.urandom(32))
        nonce = bytearray(os.urandom(16))
        cipher = Cipher(algorithms.ChaCha20(key, nonce), None, backend)
        enc = cipher.encryptor()
        ct = enc.update(bytearray(b"hello")) + enc.finalize()
        dec = cipher.decryptor()
        pt = dec.update(ct) + dec.finalize()
        assert pt == b"hello"

    def test_key_size(self):
        chacha = algorithms.ChaCha20(b"0" * 32, b"0" * 16)
        assert chacha.key_size == 256

    def test_invalid_key_size(self):
        with pytest.raises(ValueError):
            algorithms.ChaCha20(b"wrongsize", b"0" * 16)

    def test_invalid_nonce(self):
        with pytest.raises(ValueError):
            algorithms.ChaCha20(b"0" * 32, b"0")

        with pytest.raises(TypeError):
            algorithms.ChaCha20(b"0" * 32, object())  # type:ignore[arg-type]

    def test_invalid_key_type(self):
        with pytest.raises(TypeError, match="key must be bytes"):
            algorithms.ChaCha20("0" * 32, b"0" * 16)  # type:ignore[arg-type]

    def test_partial_blocks(self, backend):
        # Test that partial blocks and counter increments are handled
        # correctly. Successive calls to update should return the same
        # as if the entire input was passed in a single call:
        # update(pt[0:n]) + update(pt[n:m]) + update(pt[m:]) == update(pt)
        key = bytearray(os.urandom(32))
        nonce = bytearray(os.urandom(16))
        cipher = Cipher(algorithms.ChaCha20(key, nonce), None, backend)
        pt = bytearray(os.urandom(96 * 3))

        enc_full = cipher.encryptor()
        ct_full = enc_full.update(pt)

        enc_partial = cipher.encryptor()
        len_partial = len(pt) // 3
        ct_partial_1 = enc_partial.update(pt[:len_partial])
        ct_partial_2 = enc_partial.update(pt[len_partial : len_partial * 2])
        ct_partial_3 = enc_partial.update(pt[len_partial * 2 :])

        assert ct_full == ct_partial_1 + ct_partial_2 + ct_partial_3

    def test_reset_nonce(self, backend):
        data = b"helloworld" * 10
        key = b"\x00" * 32
        nonce = b"\x00" * 16
        nonce_alt = b"\xee" * 16
        cipher = Cipher(algorithms.ChaCha20(key, nonce), None)
        cipher_alt = Cipher(algorithms.ChaCha20(key, nonce_alt), None)
        enc = cipher.encryptor()
        ct1 = enc.update(data)
        assert len(ct1) == len(data)
        for _ in range(2):
            enc.reset_nonce(nonce)
            assert enc.update(data) == ct1
        # Reset the nonce to a different value
        # and check it matches with a different context
        enc_alt = cipher_alt.encryptor()
        ct2 = enc_alt.update(data)
        enc.reset_nonce(nonce_alt)
        assert enc.update(data) == ct2
        enc_alt.finalize()
        enc.finalize()
        with pytest.raises(AlreadyFinalized):
            enc.reset_nonce(nonce)
        dec = cipher.decryptor()
        assert dec.update(ct1) == data
        for _ in range(2):
            dec.reset_nonce(nonce)
            assert dec.update(ct1) == data
        # Reset the nonce to a different value
        # and check it matches with a different context
        dec_alt = cipher_alt.decryptor()
        dec.reset_nonce(nonce_alt)
        assert dec.update(ct2) == dec_alt.update(ct2)
        dec_alt.finalize()
        dec.finalize()
        with pytest.raises(AlreadyFinalized):
            dec.reset_nonce(nonce)

    def test_nonce_reset_invalid_length(self, backend):
        key = b"\x00" * 32
        nonce = b"\x00" * 16
        cipher = Cipher(algorithms.ChaCha20(key, nonce), None)
        enc = cipher.encryptor()
        with pytest.raises(ValueError):
            enc.reset_nonce(nonce[:-1])
        with pytest.raises(ValueError):
            enc.reset_nonce(nonce + b"\x00")
