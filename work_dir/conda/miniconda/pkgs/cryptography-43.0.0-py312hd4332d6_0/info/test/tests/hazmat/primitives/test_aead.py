# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


import binascii
import mmap
import os
import sys

import pytest

from cryptography.exceptions import InvalidTag, UnsupportedAlgorithm, _Reasons
from cryptography.hazmat.primitives.ciphers.aead import (
    AESCCM,
    AESGCM,
    AESGCMSIV,
    AESOCB3,
    AESSIV,
    ChaCha20Poly1305,
)

from ...utils import (
    load_nist_ccm_vectors,
    load_nist_vectors,
    load_vectors_from_file,
    raises_unsupported_algorithm,
)
from .utils import _load_all_params


def _aead_supported(cls):
    try:
        cls(b"0" * 32)
        return True
    except UnsupportedAlgorithm:
        return False


def large_mmap():
    return mmap.mmap(-1, 2**32, prot=mmap.PROT_READ)


@pytest.mark.skipif(
    _aead_supported(ChaCha20Poly1305),
    reason="Requires OpenSSL without ChaCha20Poly1305 support",
)
def test_chacha20poly1305_unsupported_on_older_openssl(backend):
    with raises_unsupported_algorithm(_Reasons.UNSUPPORTED_CIPHER):
        ChaCha20Poly1305(ChaCha20Poly1305.generate_key())


@pytest.mark.skipif(
    not _aead_supported(ChaCha20Poly1305),
    reason="Does not support ChaCha20Poly1305",
)
class TestChaCha20Poly1305:
    @pytest.mark.skipif(
        sys.platform not in {"linux", "darwin"} or sys.maxsize < 2**31,
        reason="mmap and 64-bit platform required",
    )
    def test_data_too_large(self):
        key = ChaCha20Poly1305.generate_key()
        chacha = ChaCha20Poly1305(key)
        nonce = b"0" * 12

        large_data = large_mmap()

        with pytest.raises(OverflowError):
            chacha.encrypt(nonce, large_data, b"")

        with pytest.raises(OverflowError):
            chacha.encrypt(nonce, b"", large_data)

    def test_generate_key(self):
        key = ChaCha20Poly1305.generate_key()
        assert len(key) == 32

    def test_bad_key(self, backend):
        with pytest.raises(TypeError):
            ChaCha20Poly1305(object())  # type:ignore[arg-type]

        with pytest.raises(ValueError):
            ChaCha20Poly1305(b"0" * 31)

    @pytest.mark.parametrize(
        ("nonce", "data", "associated_data"),
        [
            [object(), b"data", b""],
            [b"0" * 12, object(), b""],
            [b"0" * 12, b"data", object()],
        ],
    )
    def test_params_not_bytes_encrypt(
        self, nonce, data, associated_data, backend
    ):
        key = ChaCha20Poly1305.generate_key()
        chacha = ChaCha20Poly1305(key)
        with pytest.raises(TypeError):
            chacha.encrypt(nonce, data, associated_data)

        with pytest.raises(TypeError):
            chacha.decrypt(nonce, data, associated_data)

    def test_nonce_not_12_bytes(self, backend):
        key = ChaCha20Poly1305.generate_key()
        chacha = ChaCha20Poly1305(key)
        with pytest.raises(ValueError):
            chacha.encrypt(b"00", b"hello", b"")

        with pytest.raises(ValueError):
            chacha.decrypt(b"00", b"hello", b"")

    def test_decrypt_data_too_short(self, backend):
        key = ChaCha20Poly1305.generate_key()
        chacha = ChaCha20Poly1305(key)
        with pytest.raises(InvalidTag):
            chacha.decrypt(b"0" * 12, b"0", None)

    def test_associated_data_none_equal_to_empty_bytestring(self, backend):
        key = ChaCha20Poly1305.generate_key()
        chacha = ChaCha20Poly1305(key)
        nonce = os.urandom(12)
        ct1 = chacha.encrypt(nonce, b"some_data", None)
        ct2 = chacha.encrypt(nonce, b"some_data", b"")
        assert ct1 == ct2
        pt1 = chacha.decrypt(nonce, ct1, None)
        pt2 = chacha.decrypt(nonce, ct2, b"")
        assert pt1 == pt2

    def test_openssl_vectors(self, subtests, backend):
        vectors = load_vectors_from_file(
            os.path.join("ciphers", "ChaCha20Poly1305", "openssl.txt"),
            load_nist_vectors,
        )
        for vector in vectors:
            with subtests.test():
                key = binascii.unhexlify(vector["key"])
                nonce = binascii.unhexlify(vector["iv"])
                aad = binascii.unhexlify(vector["aad"])
                tag = binascii.unhexlify(vector["tag"])
                pt = binascii.unhexlify(vector["plaintext"])
                ct = binascii.unhexlify(vector["ciphertext"])
                chacha = ChaCha20Poly1305(key)
                if vector.get("result") == b"CIPHERFINAL_ERROR":
                    with pytest.raises(InvalidTag):
                        chacha.decrypt(nonce, ct + tag, aad)
                else:
                    computed_pt = chacha.decrypt(nonce, ct + tag, aad)
                    assert computed_pt == pt
                    computed_ct = chacha.encrypt(nonce, pt, aad)
                    assert computed_ct == ct + tag

    def test_boringssl_vectors(self, subtests, backend):
        vectors = load_vectors_from_file(
            os.path.join("ciphers", "ChaCha20Poly1305", "boringssl.txt"),
            load_nist_vectors,
        )
        for vector in vectors:
            with subtests.test():
                key = binascii.unhexlify(vector["key"])
                nonce = binascii.unhexlify(vector["nonce"])
                if vector["ad"].startswith(b'"'):
                    aad = vector["ad"][1:-1]
                else:
                    aad = binascii.unhexlify(vector["ad"])
                tag = binascii.unhexlify(vector["tag"])
                if vector["in"].startswith(b'"'):
                    pt = vector["in"][1:-1]
                else:
                    pt = binascii.unhexlify(vector["in"])
                ct = binascii.unhexlify(vector["ct"].strip(b'"'))
                chacha = ChaCha20Poly1305(key)
                computed_pt = chacha.decrypt(nonce, ct + tag, aad)
                assert computed_pt == pt
                computed_ct = chacha.encrypt(nonce, pt, aad)
                assert computed_ct == ct + tag

    def test_buffer_protocol(self, backend):
        key = ChaCha20Poly1305.generate_key()
        chacha = ChaCha20Poly1305(key)
        pt = b"encrypt me"
        ad = b"additional"
        nonce = os.urandom(12)
        ct = chacha.encrypt(nonce, pt, ad)
        computed_pt = chacha.decrypt(nonce, ct, ad)
        assert computed_pt == pt
        chacha2 = ChaCha20Poly1305(bytearray(key))
        ct2 = chacha2.encrypt(bytearray(nonce), pt, ad)
        assert ct2 == ct
        computed_pt2 = chacha2.decrypt(bytearray(nonce), ct2, ad)
        assert computed_pt2 == pt


@pytest.mark.skipif(
    not _aead_supported(AESCCM),
    reason="Does not support AESCCM",
)
class TestAESCCM:
    @pytest.mark.skipif(
        sys.platform not in {"linux", "darwin"} or sys.maxsize < 2**31,
        reason="mmap and 64-bit platform required",
    )
    def test_data_too_large(self):
        key = AESCCM.generate_key(128)
        aesccm = AESCCM(key)
        nonce = b"0" * 12

        large_data = large_mmap()

        with pytest.raises(OverflowError):
            aesccm.encrypt(nonce, large_data, b"")

        with pytest.raises(OverflowError):
            aesccm.encrypt(nonce, b"", large_data)

    def test_default_tag_length(self, backend):
        key = AESCCM.generate_key(128)
        aesccm = AESCCM(key)
        nonce = os.urandom(12)
        pt = b"hello"
        ct = aesccm.encrypt(nonce, pt, None)
        assert len(ct) == len(pt) + 16

    def test_invalid_tag_length(self, backend):
        key = AESCCM.generate_key(128)
        with pytest.raises(ValueError):
            AESCCM(key, tag_length=7)

        with pytest.raises(ValueError):
            AESCCM(key, tag_length=2)

        with pytest.raises(TypeError):
            AESCCM(key, tag_length="notanint")  # type:ignore[arg-type]

    def test_invalid_nonce_length(self, backend):
        key = AESCCM.generate_key(128)
        aesccm = AESCCM(key)
        pt = b"hello"
        nonce = os.urandom(14)
        with pytest.raises(ValueError):
            aesccm.encrypt(nonce, pt, None)

        with pytest.raises(ValueError):
            aesccm.encrypt(nonce[:6], pt, None)

    def test_vectors(self, subtests, backend):
        vectors = _load_all_params(
            os.path.join("ciphers", "AES", "CCM"),
            [
                "DVPT128.rsp",
                "DVPT192.rsp",
                "DVPT256.rsp",
                "VADT128.rsp",
                "VADT192.rsp",
                "VADT256.rsp",
                "VNT128.rsp",
                "VNT192.rsp",
                "VNT256.rsp",
                "VPT128.rsp",
                "VPT192.rsp",
                "VPT256.rsp",
            ],
            load_nist_ccm_vectors,
        )
        for vector in vectors:
            with subtests.test():
                key = binascii.unhexlify(vector["key"])
                nonce = binascii.unhexlify(vector["nonce"])
                adata = binascii.unhexlify(vector["adata"])[: vector["alen"]]
                ct = binascii.unhexlify(vector["ct"])
                pt = binascii.unhexlify(vector["payload"])[: vector["plen"]]
                aesccm = AESCCM(key, vector["tlen"])
                if vector.get("fail"):
                    with pytest.raises(InvalidTag):
                        aesccm.decrypt(nonce, ct, adata)
                else:
                    computed_pt = aesccm.decrypt(nonce, ct, adata)
                    assert computed_pt == pt
                    assert aesccm.encrypt(nonce, pt, adata) == ct

    def test_roundtrip(self, backend):
        key = AESCCM.generate_key(128)
        aesccm = AESCCM(key)
        pt = b"encrypt me"
        ad = b"additional"
        nonce = os.urandom(12)
        ct = aesccm.encrypt(nonce, pt, ad)
        computed_pt = aesccm.decrypt(nonce, ct, ad)
        assert computed_pt == pt

    def test_nonce_too_long(self, backend):
        key = AESCCM.generate_key(128)
        aesccm = AESCCM(key)
        pt = b"encrypt me" * 6600
        # pt can be no more than 65536 bytes when nonce is 13 bytes
        nonce = os.urandom(13)
        with pytest.raises(ValueError):
            aesccm.encrypt(nonce, pt, None)

        with pytest.raises(ValueError):
            aesccm.decrypt(nonce, pt, None)

    @pytest.mark.parametrize(
        ("nonce", "data", "associated_data"),
        [
            [object(), b"data", b""],
            [b"0" * 12, object(), b""],
            [b"0" * 12, b"data", object()],
        ],
    )
    def test_params_not_bytes(self, nonce, data, associated_data, backend):
        key = AESCCM.generate_key(128)
        aesccm = AESCCM(key)
        with pytest.raises(TypeError):
            aesccm.encrypt(nonce, data, associated_data)

    def test_bad_key(self, backend):
        with pytest.raises(TypeError):
            AESCCM(object())  # type:ignore[arg-type]

        with pytest.raises(ValueError):
            AESCCM(b"0" * 31)

    def test_bad_generate_key(self, backend):
        with pytest.raises(TypeError):
            AESCCM.generate_key(object())  # type:ignore[arg-type]

        with pytest.raises(ValueError):
            AESCCM.generate_key(129)

    def test_associated_data_none_equal_to_empty_bytestring(self, backend):
        key = AESCCM.generate_key(128)
        aesccm = AESCCM(key)
        nonce = os.urandom(12)
        ct1 = aesccm.encrypt(nonce, b"some_data", None)
        ct2 = aesccm.encrypt(nonce, b"some_data", b"")
        assert ct1 == ct2
        pt1 = aesccm.decrypt(nonce, ct1, None)
        pt2 = aesccm.decrypt(nonce, ct2, b"")
        assert pt1 == pt2

    def test_decrypt_data_too_short(self, backend):
        key = AESCCM.generate_key(128)
        aesccm = AESCCM(key)
        with pytest.raises(InvalidTag):
            aesccm.decrypt(b"0" * 12, b"0", None)

    def test_buffer_protocol(self, backend):
        key = AESCCM.generate_key(128)
        aesccm = AESCCM(key)
        pt = b"encrypt me"
        ad = b"additional"
        nonce = os.urandom(12)
        ct = aesccm.encrypt(nonce, pt, ad)
        computed_pt = aesccm.decrypt(nonce, ct, ad)
        assert computed_pt == pt
        aesccm2 = AESCCM(bytearray(key))
        ct2 = aesccm2.encrypt(bytearray(nonce), pt, ad)
        assert ct2 == ct
        computed_pt2 = aesccm2.decrypt(bytearray(nonce), ct2, ad)
        assert computed_pt2 == pt


def _load_gcm_vectors():
    vectors = _load_all_params(
        os.path.join("ciphers", "AES", "GCM"),
        [
            "gcmDecrypt128.rsp",
            "gcmDecrypt192.rsp",
            "gcmDecrypt256.rsp",
            "gcmEncryptExtIV128.rsp",
            "gcmEncryptExtIV192.rsp",
            "gcmEncryptExtIV256.rsp",
        ],
        load_nist_vectors,
    )
    return [x for x in vectors if len(x["tag"]) == 32 and len(x["iv"]) >= 16]


class TestAESGCM:
    @pytest.mark.skipif(
        sys.platform not in {"linux", "darwin"} or sys.maxsize < 2**31,
        reason="mmap and 64-bit platform required",
    )
    def test_data_too_large(self):
        key = AESGCM.generate_key(128)
        aesgcm = AESGCM(key)
        nonce = b"0" * 12

        large_data = large_mmap()

        with pytest.raises(OverflowError):
            aesgcm.encrypt(nonce, large_data, b"")

        with pytest.raises(OverflowError):
            aesgcm.encrypt(nonce, b"", large_data)

    def test_decrypt_data_too_short(self):
        key = AESGCM.generate_key(128)
        aesgcm = AESGCM(key)
        with pytest.raises(InvalidTag):
            aesgcm.decrypt(b"0" * 12, b"0", None)

    def test_vectors(self, backend, subtests):
        vectors = _load_gcm_vectors()
        for vector in vectors:
            with subtests.test():
                nonce = binascii.unhexlify(vector["iv"])

                if backend._fips_enabled and len(nonce) != 12:
                    # Red Hat disables non-96-bit IV support as part of its
                    # FIPS patches.
                    pytest.skip("Non-96-bit IVs unsupported in FIPS mode.")

                key = binascii.unhexlify(vector["key"])
                aad = binascii.unhexlify(vector["aad"])
                ct = binascii.unhexlify(vector["ct"])
                pt = binascii.unhexlify(vector.get("pt", b""))
                tag = binascii.unhexlify(vector["tag"])
                aesgcm = AESGCM(key)
                if vector.get("fail") is True:
                    with pytest.raises(InvalidTag):
                        aesgcm.decrypt(nonce, ct + tag, aad)
                else:
                    computed_ct = aesgcm.encrypt(nonce, pt, aad)
                    assert computed_ct[:-16] == ct
                    assert computed_ct[-16:] == tag
                    computed_pt = aesgcm.decrypt(nonce, ct + tag, aad)
                    assert computed_pt == pt

    @pytest.mark.parametrize(
        ("nonce", "data", "associated_data"),
        [
            [object(), b"data", b""],
            [b"0" * 12, object(), b""],
            [b"0" * 12, b"data", object()],
        ],
    )
    def test_params_not_bytes(self, nonce, data, associated_data, backend):
        key = AESGCM.generate_key(128)
        aesgcm = AESGCM(key)
        with pytest.raises(TypeError):
            aesgcm.encrypt(nonce, data, associated_data)

        with pytest.raises(TypeError):
            aesgcm.decrypt(nonce, data, associated_data)

    @pytest.mark.parametrize("length", [7, 129])
    def test_invalid_nonce_length(self, length, backend):
        if backend._fips_enabled:
            # Red Hat disables non-96-bit IV support as part of its FIPS
            # patches.
            pytest.skip("Non-96-bit IVs unsupported in FIPS mode.")

        key = AESGCM.generate_key(128)
        aesgcm = AESGCM(key)
        with pytest.raises(ValueError):
            aesgcm.encrypt(b"\x00" * length, b"hi", None)
        with pytest.raises(ValueError):
            aesgcm.decrypt(b"\x00" * length, b"hi", None)

    def test_bad_key(self, backend):
        with pytest.raises(TypeError):
            AESGCM(object())  # type:ignore[arg-type]

        with pytest.raises(ValueError):
            AESGCM(b"0" * 31)

    def test_bad_generate_key(self, backend):
        with pytest.raises(TypeError):
            AESGCM.generate_key(object())  # type:ignore[arg-type]

        with pytest.raises(ValueError):
            AESGCM.generate_key(129)

    def test_associated_data_none_equal_to_empty_bytestring(self, backend):
        key = AESGCM.generate_key(128)
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)
        ct1 = aesgcm.encrypt(nonce, b"some_data", None)
        ct2 = aesgcm.encrypt(nonce, b"some_data", b"")
        assert ct1 == ct2
        pt1 = aesgcm.decrypt(nonce, ct1, None)
        pt2 = aesgcm.decrypt(nonce, ct2, b"")
        assert pt1 == pt2

    def test_buffer_protocol(self, backend):
        key = AESGCM.generate_key(128)
        aesgcm = AESGCM(key)
        pt = b"encrypt me"
        ad = b"additional"
        nonce = os.urandom(12)
        ct = aesgcm.encrypt(nonce, pt, ad)
        computed_pt = aesgcm.decrypt(nonce, ct, ad)
        assert computed_pt == pt
        aesgcm2 = AESGCM(bytearray(key))
        ct2 = aesgcm2.encrypt(bytearray(nonce), bytearray(pt), bytearray(ad))
        assert ct2 == ct
        b_nonce = bytearray(nonce)
        b_ct2 = bytearray(ct2)
        b_ad = bytearray(ad)
        computed_pt2 = aesgcm2.decrypt(b_nonce, b_ct2, b_ad)
        assert computed_pt2 == pt
        aesgcm3 = AESGCM(memoryview(key))
        m_nonce = memoryview(nonce)
        m_pt = memoryview(pt)
        m_ad = memoryview(ad)
        ct3 = aesgcm3.encrypt(m_nonce, m_pt, m_ad)
        assert ct3 == ct
        m_ct3 = memoryview(ct3)
        computed_pt3 = aesgcm3.decrypt(m_nonce, m_ct3, m_ad)
        assert computed_pt3 == pt


@pytest.mark.skipif(
    _aead_supported(AESOCB3),
    reason="Requires OpenSSL without AESOCB3 support",
)
def test_aesocb3_unsupported_on_older_openssl(backend):
    with raises_unsupported_algorithm(_Reasons.UNSUPPORTED_CIPHER):
        AESOCB3(AESOCB3.generate_key(128))


@pytest.mark.skipif(
    not _aead_supported(AESOCB3),
    reason="Does not support AESOCB3",
)
class TestAESOCB3:
    @pytest.mark.skipif(
        sys.platform not in {"linux", "darwin"} or sys.maxsize < 2**31,
        reason="mmap and 64-bit platform required",
    )
    def test_data_too_large(self):
        key = AESOCB3.generate_key(128)
        aesocb3 = AESOCB3(key)
        nonce = b"0" * 12

        large_data = large_mmap()

        with pytest.raises(OverflowError):
            aesocb3.encrypt(nonce, large_data, b"")

        with pytest.raises(OverflowError):
            aesocb3.encrypt(nonce, b"", large_data)

    def test_vectors(self, backend, subtests):
        vectors = []
        for f in [
            "rfc7253.txt",
            "openssl.txt",
            "test-vector-1-nonce104.txt",
            "test-vector-1-nonce112.txt",
            "test-vector-1-nonce120.txt",
        ]:
            vectors.extend(
                load_vectors_from_file(
                    os.path.join("ciphers", "AES", "OCB3", f),
                    load_nist_vectors,
                )
            )

        for vector in vectors:
            with subtests.test():
                nonce = binascii.unhexlify(vector["nonce"])
                key = binascii.unhexlify(vector["key"])
                aad = binascii.unhexlify(vector["aad"])
                ct = binascii.unhexlify(vector["ciphertext"])
                pt = binascii.unhexlify(vector.get("plaintext", b""))
                aesocb3 = AESOCB3(key)
                computed_ct = aesocb3.encrypt(nonce, pt, aad)
                assert computed_ct == ct
                computed_pt = aesocb3.decrypt(nonce, ct, aad)
                assert computed_pt == pt

    def test_vectors_invalid(self, backend, subtests):
        vectors = load_vectors_from_file(
            os.path.join("ciphers", "AES", "OCB3", "rfc7253.txt"),
            load_nist_vectors,
        )
        for vector in vectors:
            with subtests.test():
                nonce = binascii.unhexlify(vector["nonce"])
                key = binascii.unhexlify(vector["key"])
                aad = binascii.unhexlify(vector["aad"])
                ct = binascii.unhexlify(vector["ciphertext"])
                aesocb3 = AESOCB3(key)
                with pytest.raises(InvalidTag):
                    badkey = AESOCB3(AESOCB3.generate_key(128))
                    badkey.decrypt(nonce, ct, aad)
                with pytest.raises(InvalidTag):
                    aesocb3.decrypt(nonce, b"nonsense", aad)
                with pytest.raises(InvalidTag):
                    aesocb3.decrypt(b"\x00" * 12, ct, aad)
                with pytest.raises(InvalidTag):
                    aesocb3.decrypt(nonce, ct, b"nonsense")

    @pytest.mark.parametrize(
        ("key_len", "expected"),
        [
            (128, b"g\xe9D\xd22V\xc5\xe0\xb6\xc6\x1f\xa2/\xdf\x1e\xa2"),
            (192, b"\xf6s\xf2\xc3\xe7\x17J\xae{\xae\x98l\xa9\xf2\x9e\x17"),
            (256, b"\xd9\x0e\xb8\xe9\xc9w\xc8\x8by\xddy=\x7f\xfa\x16\x1c"),
        ],
    )
    def test_rfc7253(self, backend, key_len, expected):
        # This is derived from page 18 of RFC 7253, with a tag length of
        # 128 bits.

        k = AESOCB3(b"\x00" * ((key_len - 8) // 8) + b"\x80")

        c = b""

        for i in range(0, 128):
            s = b"\x00" * i
            n = (3 * i + 1).to_bytes(12, "big")
            c += k.encrypt(n, s, s)
            n = (3 * i + 2).to_bytes(12, "big")
            c += k.encrypt(n, s, b"")
            n = (3 * i + 3).to_bytes(12, "big")
            c += k.encrypt(n, b"", s)

        assert len(c) == 22400

        n = (385).to_bytes(12, "big")
        output = k.encrypt(n, b"", c)

        assert output == expected

    @pytest.mark.parametrize(
        ("nonce", "data", "associated_data"),
        [
            [object(), b"data", b""],
            [b"0" * 12, object(), b""],
            [b"0" * 12, b"data", object()],
        ],
    )
    def test_params_not_bytes(self, nonce, data, associated_data, backend):
        key = AESOCB3.generate_key(128)
        aesocb3 = AESOCB3(key)
        with pytest.raises(TypeError):
            aesocb3.encrypt(nonce, data, associated_data)

        with pytest.raises(TypeError):
            aesocb3.decrypt(nonce, data, associated_data)

    def test_invalid_nonce_length(self, backend):
        key = AESOCB3.generate_key(128)
        aesocb3 = AESOCB3(key)
        with pytest.raises(ValueError):
            aesocb3.encrypt(b"\x00" * 11, b"hi", None)
        with pytest.raises(ValueError):
            aesocb3.encrypt(b"\x00" * 16, b"hi", None)

        with pytest.raises(ValueError):
            aesocb3.decrypt(b"\x00" * 11, b"hi", None)
        with pytest.raises(ValueError):
            aesocb3.decrypt(b"\x00" * 16, b"hi", None)

    def test_bad_key(self, backend):
        with pytest.raises(TypeError):
            AESOCB3(object())  # type:ignore[arg-type]

        with pytest.raises(ValueError):
            AESOCB3(b"0" * 31)

    def test_bad_generate_key(self, backend):
        with pytest.raises(TypeError):
            AESOCB3.generate_key(object())  # type:ignore[arg-type]

        with pytest.raises(ValueError):
            AESOCB3.generate_key(129)

    def test_associated_data_none_equal_to_empty_bytestring(self, backend):
        key = AESOCB3.generate_key(128)
        aesocb3 = AESOCB3(key)
        nonce = os.urandom(12)
        ct1 = aesocb3.encrypt(nonce, b"some_data", None)
        ct2 = aesocb3.encrypt(nonce, b"some_data", b"")
        assert ct1 == ct2
        pt1 = aesocb3.decrypt(nonce, ct1, None)
        pt2 = aesocb3.decrypt(nonce, ct2, b"")
        assert pt1 == pt2

    def test_buffer_protocol(self, backend):
        key = AESOCB3.generate_key(128)
        aesocb3 = AESOCB3(key)
        pt = b"encrypt me"
        ad = b"additional"
        nonce = os.urandom(12)
        ct = aesocb3.encrypt(nonce, pt, ad)
        computed_pt = aesocb3.decrypt(nonce, ct, ad)
        assert computed_pt == pt
        aesocb3_ = AESOCB3(bytearray(key))
        ct2 = aesocb3_.encrypt(bytearray(nonce), pt, ad)
        assert ct2 == ct
        computed_pt2 = aesocb3_.decrypt(bytearray(nonce), ct2, ad)
        assert computed_pt2 == pt


@pytest.mark.skipif(
    not _aead_supported(AESSIV),
    reason="Does not support AESSIV",
)
class TestAESSIV:
    @pytest.mark.skipif(
        sys.platform not in {"linux", "darwin"} or sys.maxsize < 2**31,
        reason="mmap and 64-bit platform required",
    )
    def test_data_too_large(self):
        key = AESSIV.generate_key(256)
        aessiv = AESSIV(key)

        large_data = large_mmap()

        with pytest.raises(OverflowError):
            aessiv.encrypt(large_data, None)

        with pytest.raises(OverflowError):
            aessiv.encrypt(b"irrelevant", [large_data])

        with pytest.raises(OverflowError):
            aessiv.decrypt(b"very very irrelevant", [large_data])

    def test_no_empty_encryption(self):
        key = AESSIV.generate_key(256)
        aessiv = AESSIV(key)

        with pytest.raises(ValueError):
            aessiv.encrypt(b"", None)

        with pytest.raises(InvalidTag):
            aessiv.decrypt(b"", None)

    def test_vectors(self, backend, subtests):
        vectors = load_vectors_from_file(
            os.path.join("ciphers", "AES", "SIV", "openssl.txt"),
            load_nist_vectors,
        )
        for vector in vectors:
            with subtests.test():
                key = binascii.unhexlify(vector["key"])
                aad1 = vector.get("aad", None)
                aad2 = vector.get("aad2", None)
                aad3 = vector.get("aad3", None)
                aad = [
                    binascii.unhexlify(a)
                    for a in (aad1, aad2, aad3)
                    if a is not None
                ]
                ct = binascii.unhexlify(vector["ciphertext"])
                tag = binascii.unhexlify(vector["tag"])
                pt = binascii.unhexlify(vector.get("plaintext", b""))
                aessiv = AESSIV(key)
                computed_ct = aessiv.encrypt(pt, aad)
                assert computed_ct[:16] == tag
                assert computed_ct[16:] == ct
                computed_pt = aessiv.decrypt(computed_ct, aad)
                assert computed_pt == pt

    def test_vectors_invalid(self, backend, subtests):
        vectors = load_vectors_from_file(
            os.path.join("ciphers", "AES", "SIV", "openssl.txt"),
            load_nist_vectors,
        )
        for vector in vectors:
            with subtests.test():
                key = binascii.unhexlify(vector["key"])
                aad1 = vector.get("aad", None)
                aad2 = vector.get("aad2", None)
                aad3 = vector.get("aad3", None)
                aad = [
                    binascii.unhexlify(a)
                    for a in (aad1, aad2, aad3)
                    if a is not None
                ]

                ct = binascii.unhexlify(vector["ciphertext"])
                aessiv = AESSIV(key)
                with pytest.raises(InvalidTag):
                    badkey = AESSIV(AESSIV.generate_key(256))
                    badkey.decrypt(ct, aad)
                with pytest.raises(InvalidTag):
                    aessiv.decrypt(ct, [*aad, b""])
                with pytest.raises(InvalidTag):
                    aessiv.decrypt(ct, [b"nonsense"])
                with pytest.raises(InvalidTag):
                    aessiv.decrypt(b"nonsense", aad)

    @pytest.mark.parametrize(
        ("data", "associated_data"),
        [
            [object(), [b""]],
            [b"data" * 5, [object()]],
            [b"data" * 5, b""],
        ],
    )
    def test_params_not_bytes(self, data, associated_data, backend):
        key = AESSIV.generate_key(256)
        aessiv = AESSIV(key)
        with pytest.raises(TypeError):
            aessiv.encrypt(data, associated_data)

        with pytest.raises(TypeError):
            aessiv.decrypt(data, associated_data)

    def test_bad_key(self, backend):
        with pytest.raises(TypeError):
            AESSIV(object())  # type:ignore[arg-type]

        with pytest.raises(ValueError):
            AESSIV(b"0" * 31)

    def test_bad_generate_key(self, backend):
        with pytest.raises(TypeError):
            AESSIV.generate_key(object())  # type:ignore[arg-type]

        with pytest.raises(ValueError):
            AESSIV.generate_key(128)

    def test_associated_data_none_equal_to_empty_list(self, backend):
        key = AESSIV.generate_key(256)
        aessiv = AESSIV(key)
        ct1 = aessiv.encrypt(b"some_data", None)
        ct2 = aessiv.encrypt(b"some_data", [])
        assert ct1 == ct2
        pt1 = aessiv.decrypt(ct1, None)
        pt2 = aessiv.decrypt(ct2, [])
        assert pt1 == pt2

    def test_buffer_protocol(self, backend):
        key = AESSIV.generate_key(256)
        aessiv = AESSIV(key)
        pt = b"encrypt me"
        ad = [b"additional"]
        ct = aessiv.encrypt(pt, ad)
        computed_pt = aessiv.decrypt(ct, ad)
        assert computed_pt == pt
        aessiv = AESSIV(bytearray(key))
        ct2 = aessiv.encrypt(pt, ad)
        assert ct2 == ct
        computed_pt2 = aessiv.decrypt(ct2, ad)
        assert computed_pt2 == pt


@pytest.mark.skipif(
    not _aead_supported(AESGCMSIV),
    reason="Does not support AESGCMSIV",
)
class TestAESGCMSIV:
    @pytest.mark.skipif(
        sys.platform not in {"linux", "darwin"} or sys.maxsize < 2**31,
        reason="mmap and 64-bit platform required",
    )
    def test_data_too_large(self):
        key = AESGCMSIV.generate_key(256)
        nonce = os.urandom(12)
        aesgcmsiv = AESGCMSIV(key)

        large_data = large_mmap()

        with pytest.raises(OverflowError):
            aesgcmsiv.encrypt(nonce, large_data, None)

        with pytest.raises(OverflowError):
            aesgcmsiv.encrypt(nonce, b"irrelevant", large_data)

        with pytest.raises(OverflowError):
            aesgcmsiv.decrypt(nonce, b"very very irrelevant", large_data)

    def test_invalid_nonce_length(self, backend):
        key = AESGCMSIV.generate_key(128)
        aesgcmsiv = AESGCMSIV(key)
        pt = b"hello"
        nonce = os.urandom(14)
        with pytest.raises(ValueError):
            aesgcmsiv.encrypt(nonce, pt, None)

        with pytest.raises(ValueError):
            aesgcmsiv.decrypt(nonce, pt, None)

    def test_no_empty_encryption(self):
        key = AESGCMSIV.generate_key(256)
        aesgcmsiv = AESGCMSIV(key)
        nonce = os.urandom(12)

        with pytest.raises(ValueError):
            aesgcmsiv.encrypt(nonce, b"", None)

        with pytest.raises(InvalidTag):
            aesgcmsiv.decrypt(nonce, b"", None)

    def test_vectors(self, backend, subtests):
        vectors = _load_all_params(
            os.path.join("ciphers", "AES", "GCM-SIV"),
            [
                "openssl.txt",
                "aes-192-gcm-siv.txt",
            ],
            load_nist_vectors,
        )
        for vector in vectors:
            with subtests.test():
                key = binascii.unhexlify(vector["key"])
                nonce = binascii.unhexlify(vector["iv"])
                aad = binascii.unhexlify(vector.get("aad", b""))
                ct = binascii.unhexlify(vector["ciphertext"])
                tag = binascii.unhexlify(vector["tag"])
                pt = binascii.unhexlify(vector.get("plaintext", b""))
                aesgcmsiv = AESGCMSIV(key)
                computed_ct = aesgcmsiv.encrypt(nonce, pt, aad)
                assert computed_ct[:-16] == ct
                assert computed_ct[-16:] == tag
                computed_pt = aesgcmsiv.decrypt(nonce, computed_ct, aad)
                assert computed_pt == pt

    def test_vectors_invalid(self, backend, subtests):
        vectors = _load_all_params(
            os.path.join("ciphers", "AES", "GCM-SIV"),
            [
                "openssl.txt",
                "aes-192-gcm-siv.txt",
            ],
            load_nist_vectors,
        )
        for vector in vectors:
            with subtests.test():
                key = binascii.unhexlify(vector["key"])
                nonce = binascii.unhexlify(vector["iv"])
                aad = binascii.unhexlify(vector.get("aad", b""))
                ct = binascii.unhexlify(vector["ciphertext"])
                aesgcmsiv = AESGCMSIV(key)
                with pytest.raises(InvalidTag):
                    badkey = AESGCMSIV(AESGCMSIV.generate_key(256))
                    badkey.decrypt(nonce, ct, aad)
                with pytest.raises(InvalidTag):
                    aesgcmsiv.decrypt(nonce, ct, b"nonsense")
                with pytest.raises(InvalidTag):
                    aesgcmsiv.decrypt(nonce, b"nonsense", aad)

    @pytest.mark.parametrize(
        ("nonce", "data", "associated_data"),
        [
            [object(), b"data", b""],
            [b"0" * 12, object(), b""],
            [b"0" * 12, b"data", object()],
        ],
    )
    def test_params_not_bytes(self, nonce, data, associated_data, backend):
        key = AESGCMSIV.generate_key(256)
        aesgcmsiv = AESGCMSIV(key)
        with pytest.raises(TypeError):
            aesgcmsiv.encrypt(nonce, data, associated_data)

        with pytest.raises(TypeError):
            aesgcmsiv.decrypt(nonce, data, associated_data)

    def test_bad_key(self, backend):
        with pytest.raises(TypeError):
            AESGCMSIV(object())  # type:ignore[arg-type]

        with pytest.raises(ValueError):
            AESGCMSIV(b"0" * 31)

    def test_bad_generate_key(self, backend):
        with pytest.raises(TypeError):
            AESGCMSIV.generate_key(object())  # type:ignore[arg-type]

        with pytest.raises(ValueError):
            AESGCMSIV.generate_key(129)

    def test_associated_data_none_equal_to_empty_bytestring(self, backend):
        key = AESGCMSIV.generate_key(256)
        aesgcmsiv = AESGCMSIV(key)
        nonce = os.urandom(12)
        ct1 = aesgcmsiv.encrypt(nonce, b"some_data", None)
        ct2 = aesgcmsiv.encrypt(nonce, b"some_data", b"")
        assert ct1 == ct2
        pt1 = aesgcmsiv.decrypt(nonce, ct1, None)
        pt2 = aesgcmsiv.decrypt(nonce, ct2, b"")
        assert pt1 == pt2

    def test_buffer_protocol(self, backend):
        key = AESGCMSIV.generate_key(256)
        aesgcmsiv = AESGCMSIV(key)
        nonce = os.urandom(12)
        pt = b"encrypt me"
        ad = b"additional"
        ct = aesgcmsiv.encrypt(nonce, pt, ad)
        computed_pt = aesgcmsiv.decrypt(nonce, ct, ad)
        assert computed_pt == pt
        aesgcmsiv = AESGCMSIV(bytearray(key))
        ct2 = aesgcmsiv.encrypt(nonce, pt, ad)
        assert ct2 == ct
        computed_pt2 = aesgcmsiv.decrypt(nonce, ct2, ad)
        assert computed_pt2 == pt
