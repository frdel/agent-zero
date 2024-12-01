# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


import binascii
import mmap
import os
import sys

import pytest

from cryptography import utils
from cryptography.exceptions import AlreadyFinalized
from cryptography.hazmat.primitives import ciphers
from cryptography.hazmat.primitives.ciphers import modes
from cryptography.hazmat.primitives.ciphers.algorithms import (
    AES,
    Camellia,
)

from ...utils import load_nist_vectors, load_vectors_from_file


def test_deprecated_ciphers_import_with_warning():
    with pytest.warns(utils.CryptographyDeprecationWarning):
        from cryptography.hazmat.primitives.ciphers.algorithms import (
            Blowfish,  # noqa: F401
        )
    with pytest.warns(utils.CryptographyDeprecationWarning):
        from cryptography.hazmat.primitives.ciphers.algorithms import (
            CAST5,  # noqa: F401
        )
    with pytest.warns(utils.CryptographyDeprecationWarning):
        from cryptography.hazmat.primitives.ciphers.algorithms import (
            IDEA,  # noqa: F401
        )
    with pytest.warns(utils.CryptographyDeprecationWarning):
        from cryptography.hazmat.primitives.ciphers.algorithms import (
            SEED,  # noqa: F401
        )
    with pytest.warns(utils.CryptographyDeprecationWarning):
        from cryptography.hazmat.primitives.ciphers.algorithms import (
            ARC4,  # noqa: F401
        )
    with pytest.warns(utils.CryptographyDeprecationWarning):
        from cryptography.hazmat.primitives.ciphers.algorithms import (
            TripleDES,  # noqa: F401
        )


class TestAES:
    @pytest.mark.parametrize(
        ("key", "keysize"),
        [(b"0" * 32, 128), (b"0" * 48, 192), (b"0" * 64, 256)],
    )
    def test_key_size(self, key, keysize):
        cipher = AES(binascii.unhexlify(key))
        assert cipher.key_size == keysize

    def test_invalid_key_size(self):
        with pytest.raises(ValueError):
            AES(binascii.unhexlify(b"0" * 12))

    def test_invalid_key_type(self):
        with pytest.raises(TypeError, match="key must be bytes"):
            AES("0" * 32)  # type: ignore[arg-type]


class TestAESXTS:
    @pytest.mark.parametrize(
        "mode", (modes.CBC, modes.CTR, modes.CFB, modes.CFB8, modes.OFB)
    )
    def test_invalid_key_size_with_mode(self, mode, backend):
        with pytest.raises(ValueError):
            ciphers.Cipher(AES(b"0" * 64), mode(b"0" * 16), backend)

    def test_xts_tweak_not_bytes(self):
        with pytest.raises(TypeError):
            modes.XTS(32)  # type: ignore[arg-type]

    def test_xts_tweak_too_small(self):
        with pytest.raises(ValueError):
            modes.XTS(b"0")

    def test_xts_wrong_key_size(self, backend):
        with pytest.raises(ValueError):
            ciphers.Cipher(AES(b"0" * 16), modes.XTS(b"0" * 16), backend)


class TestGCM:
    @pytest.mark.parametrize("size", [7, 129])
    def test_gcm_min_max(self, size):
        with pytest.raises(ValueError):
            modes.GCM(b"0" * size)


class TestCamellia:
    @pytest.mark.parametrize(
        ("key", "keysize"),
        [(b"0" * 32, 128), (b"0" * 48, 192), (b"0" * 64, 256)],
    )
    def test_key_size(self, key, keysize):
        cipher = Camellia(binascii.unhexlify(key))
        assert cipher.key_size == keysize

    def test_invalid_key_size(self):
        with pytest.raises(ValueError):
            Camellia(binascii.unhexlify(b"0" * 12))

    def test_invalid_key_type(self):
        with pytest.raises(TypeError, match="key must be bytes"):
            Camellia("0" * 32)  # type: ignore[arg-type]


@pytest.mark.supported(
    only_if=lambda backend: backend.cipher_supported(
        AES(b"\x00" * 16), modes.ECB()
    ),
    skip_message="Does not support AES ECB",
)
class TestCipherUpdateInto:
    @pytest.mark.parametrize(
        "params",
        load_vectors_from_file(
            os.path.join("ciphers", "AES", "ECB", "ECBGFSbox128.rsp"),
            load_nist_vectors,
        ),
    )
    def test_update_into(self, params, backend):
        key = binascii.unhexlify(params["key"])
        pt = binascii.unhexlify(params["plaintext"])
        ct = binascii.unhexlify(params["ciphertext"])
        c = ciphers.Cipher(AES(key), modes.ECB(), backend)
        encryptor = c.encryptor()
        buf = bytearray(len(pt) + 15)
        res = encryptor.update_into(pt, buf)
        assert res == len(pt)
        assert bytes(buf)[:res] == ct

    @pytest.mark.supported(
        only_if=lambda backend: backend.cipher_supported(
            AES(b"\x00" * 16), modes.GCM(b"0" * 12)
        ),
        skip_message="Does not support AES GCM",
    )
    def test_update_into_gcm(self, backend):
        key = binascii.unhexlify(b"e98b72a9881a84ca6b76e0f43e68647a")
        iv = binascii.unhexlify(b"8b23299fde174053f3d652ba")
        ct = binascii.unhexlify(b"5a3c1cf1985dbb8bed818036fdd5ab42")
        pt = binascii.unhexlify(b"28286a321293253c3e0aa2704a278032")
        c = ciphers.Cipher(AES(key), modes.GCM(iv), backend)
        encryptor = c.encryptor()
        buf = bytearray(len(pt) + 15)
        res = encryptor.update_into(pt, buf)
        assert res == len(pt)
        assert bytes(buf)[:res] == ct
        encryptor.finalize()
        c = ciphers.Cipher(AES(key), modes.GCM(iv, encryptor.tag), backend)
        decryptor = c.decryptor()
        res = decryptor.update_into(ct, buf)
        decryptor.finalize()
        assert res == len(pt)
        assert bytes(buf)[:res] == pt

    @pytest.mark.supported(
        only_if=lambda backend: backend.cipher_supported(
            AES(b"\x00" * 16), modes.GCM(b"0" * 12)
        ),
        skip_message="Does not support AES GCM",
    )
    def test_finalize_with_tag_already_finalized(self, backend):
        key = binascii.unhexlify(b"e98b72a9881a84ca6b76e0f43e68647a")
        iv = binascii.unhexlify(b"8b23299fde174053f3d652ba")
        encryptor = ciphers.Cipher(
            AES(key), modes.GCM(iv), backend
        ).encryptor()
        ciphertext = encryptor.update(b"abc") + encryptor.finalize()

        decryptor = ciphers.Cipher(
            AES(key), modes.GCM(iv, tag=encryptor.tag), backend
        ).decryptor()
        decryptor.update(ciphertext)
        decryptor.finalize()
        with pytest.raises(AlreadyFinalized):
            decryptor.finalize_with_tag(encryptor.tag)

    @pytest.mark.supported(
        only_if=lambda backend: backend.cipher_supported(
            AES(b"\x00" * 16), modes.GCM(b"0" * 12)
        ),
        skip_message="Does not support AES GCM",
    )
    def test_finalize_with_tag_duplicate_tag(self, backend):
        decryptor = ciphers.Cipher(
            AES(b"\x00" * 16),
            modes.GCM(b"\x00" * 12, tag=b"\x00" * 16),
            backend,
        ).decryptor()
        with pytest.raises(ValueError):
            decryptor.finalize_with_tag(b"\x00" * 16)

    @pytest.mark.parametrize(
        "params",
        load_vectors_from_file(
            os.path.join("ciphers", "AES", "ECB", "ECBGFSbox128.rsp"),
            load_nist_vectors,
        ),
    )
    def test_update_into_multiple_calls(self, params, backend):
        key = binascii.unhexlify(params["key"])
        pt = binascii.unhexlify(params["plaintext"])
        ct = binascii.unhexlify(params["ciphertext"])
        c = ciphers.Cipher(AES(key), modes.ECB(), backend)
        encryptor = c.encryptor()
        buf = bytearray(len(pt) + 15)
        res = encryptor.update_into(pt[:3], buf)
        assert res == 0
        res = encryptor.update_into(pt[3:], buf)
        assert res == len(pt)
        assert bytes(buf)[:res] == ct

    def test_update_into_buffer_too_small(self, backend):
        key = b"\x00" * 16
        c = ciphers.Cipher(AES(key), modes.ECB(), backend)
        encryptor = c.encryptor()
        buf = bytearray(16)
        with pytest.raises(ValueError):
            encryptor.update_into(b"testing", buf)

    def test_update_into_immutable(self, backend):
        key = b"\x00" * 16
        c = ciphers.Cipher(AES(key), modes.ECB(), backend)
        encryptor = c.encryptor()
        buf = b"\x00" * 32
        with pytest.raises((TypeError, BufferError)):
            encryptor.update_into(b"testing", buf)

    @pytest.mark.supported(
        only_if=lambda backend: backend.cipher_supported(
            AES(b"\x00" * 16), modes.GCM(b"\x00" * 12)
        ),
        skip_message="Does not support AES GCM",
    )
    def test_update_into_buffer_too_small_gcm(self, backend):
        key = b"\x00" * 16
        c = ciphers.Cipher(AES(key), modes.GCM(b"\x00" * 12), backend)
        encryptor = c.encryptor()
        buf = bytearray(5)
        with pytest.raises(ValueError):
            encryptor.update_into(b"testing", buf)


@pytest.mark.skipif(
    sys.platform not in {"linux", "darwin"}, reason="mmap required"
)
def test_update_auto_chunking():
    large_data = mmap.mmap(-1, 2**29 + 2**20, prot=mmap.PROT_READ)

    key = b"\x00" * 16
    c = ciphers.Cipher(AES(key), modes.ECB())
    encryptor = c.encryptor()

    result = encryptor.update(memoryview(large_data))
    assert len(result) == len(large_data)

    decryptor = c.decryptor()
    result = decryptor.update(result)
    assert result == large_data[:]
