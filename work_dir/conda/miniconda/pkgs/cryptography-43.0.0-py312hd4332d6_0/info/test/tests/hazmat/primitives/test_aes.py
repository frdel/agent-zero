# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


import binascii
import os

import pytest

from cryptography.exceptions import AlreadyFinalized, _Reasons
from cryptography.hazmat.bindings._rust import openssl as rust_openssl
from cryptography.hazmat.primitives.ciphers import algorithms, base, modes

from ...doubles import DummyMode
from ...utils import load_nist_vectors, raises_unsupported_algorithm
from .utils import _load_all_params, generate_encrypt_test


@pytest.mark.supported(
    only_if=lambda backend: backend.cipher_supported(
        algorithms.AES(b"\x00" * 32), modes.XTS(b"\x00" * 16)
    ),
    skip_message="Does not support AES XTS",
)
class TestAESModeXTS:
    def test_xts_vectors(self, backend, subtests):
        # This list comprehension excludes any vector that does not have a
        # data unit length that is divisible by 8. The NIST vectors include
        # tests for implementations that support encryption of data that is
        # not divisible modulo 8, but OpenSSL is not such an implementation.
        vectors = [
            x
            for x in _load_all_params(
                os.path.join("ciphers", "AES", "XTS", "tweak-128hexstr"),
                ["XTSGenAES128.rsp", "XTSGenAES256.rsp"],
                load_nist_vectors,
            )
            if int(x["dataunitlen"]) / 8.0 == int(x["dataunitlen"]) // 8
        ]
        for vector in vectors:
            with subtests.test():
                key = binascii.unhexlify(vector["key"])
                tweak = binascii.unhexlify(vector["i"])
                pt = binascii.unhexlify(vector["pt"])
                ct = binascii.unhexlify(vector["ct"])
                cipher = base.Cipher(
                    algorithms.AES(key), modes.XTS(tweak), backend
                )
                enc = cipher.encryptor()
                computed_ct = enc.update(pt) + enc.finalize()
                assert computed_ct == ct
                dec = cipher.decryptor()
                computed_pt = dec.update(ct) + dec.finalize()
                assert computed_pt == pt

    def test_xts_too_short(self, backend):
        key = b"thirty_two_byte_keys_are_great!!"
        tweak = b"\x00" * 16
        cipher = base.Cipher(algorithms.AES(key), modes.XTS(tweak))
        enc = cipher.encryptor()
        with pytest.raises(ValueError):
            enc.update(b"0" * 15)

    @pytest.mark.supported(
        only_if=lambda backend: not rust_openssl.CRYPTOGRAPHY_IS_LIBRESSL,
        skip_message="duplicate key encryption error added in OpenSSL 1.1.1d",
    )
    def test_xts_no_duplicate_keys_encryption(self, backend):
        key = bytes(range(16)) * 2
        tweak = b"\x00" * 16
        cipher = base.Cipher(algorithms.AES(key), modes.XTS(tweak))
        with pytest.raises(ValueError, match="duplicated keys"):
            cipher.encryptor()

    def test_xts_unsupported_with_aes128_aes256_classes(self):
        with pytest.raises(TypeError):
            base.Cipher(algorithms.AES128(b"0" * 16), modes.XTS(b"\x00" * 16))

        with pytest.raises(TypeError):
            base.Cipher(algorithms.AES256(b"0" * 32), modes.XTS(b"\x00" * 16))


@pytest.mark.supported(
    only_if=lambda backend: backend.cipher_supported(
        algorithms.AES(b"\x00" * 16), modes.CBC(b"\x00" * 16)
    ),
    skip_message="Does not support AES CBC",
)
class TestAESModeCBC:
    test_cbc = generate_encrypt_test(
        load_nist_vectors,
        os.path.join("ciphers", "AES", "CBC"),
        [
            "CBCGFSbox128.rsp",
            "CBCGFSbox192.rsp",
            "CBCGFSbox256.rsp",
            "CBCKeySbox128.rsp",
            "CBCKeySbox192.rsp",
            "CBCKeySbox256.rsp",
            "CBCVarKey128.rsp",
            "CBCVarKey192.rsp",
            "CBCVarKey256.rsp",
            "CBCVarTxt128.rsp",
            "CBCVarTxt192.rsp",
            "CBCVarTxt256.rsp",
            "CBCMMT128.rsp",
            "CBCMMT192.rsp",
            "CBCMMT256.rsp",
        ],
        lambda key, **kwargs: algorithms.AES(binascii.unhexlify(key)),
        lambda iv, **kwargs: modes.CBC(binascii.unhexlify(iv)),
    )


@pytest.mark.supported(
    only_if=lambda backend: backend.cipher_supported(
        algorithms.AES(b"\x00" * 16), modes.ECB()
    ),
    skip_message="Does not support AES ECB",
)
class TestAESModeECB:
    test_ecb = generate_encrypt_test(
        load_nist_vectors,
        os.path.join("ciphers", "AES", "ECB"),
        [
            "ECBGFSbox128.rsp",
            "ECBGFSbox192.rsp",
            "ECBGFSbox256.rsp",
            "ECBKeySbox128.rsp",
            "ECBKeySbox192.rsp",
            "ECBKeySbox256.rsp",
            "ECBVarKey128.rsp",
            "ECBVarKey192.rsp",
            "ECBVarKey256.rsp",
            "ECBVarTxt128.rsp",
            "ECBVarTxt192.rsp",
            "ECBVarTxt256.rsp",
            "ECBMMT128.rsp",
            "ECBMMT192.rsp",
            "ECBMMT256.rsp",
        ],
        lambda key, **kwargs: algorithms.AES(binascii.unhexlify(key)),
        lambda **kwargs: modes.ECB(),
    )


@pytest.mark.supported(
    only_if=lambda backend: backend.cipher_supported(
        algorithms.AES(b"\x00" * 16), modes.OFB(b"\x00" * 16)
    ),
    skip_message="Does not support AES OFB",
)
class TestAESModeOFB:
    test_ofb = generate_encrypt_test(
        load_nist_vectors,
        os.path.join("ciphers", "AES", "OFB"),
        [
            "OFBGFSbox128.rsp",
            "OFBGFSbox192.rsp",
            "OFBGFSbox256.rsp",
            "OFBKeySbox128.rsp",
            "OFBKeySbox192.rsp",
            "OFBKeySbox256.rsp",
            "OFBVarKey128.rsp",
            "OFBVarKey192.rsp",
            "OFBVarKey256.rsp",
            "OFBVarTxt128.rsp",
            "OFBVarTxt192.rsp",
            "OFBVarTxt256.rsp",
            "OFBMMT128.rsp",
            "OFBMMT192.rsp",
            "OFBMMT256.rsp",
        ],
        lambda key, **kwargs: algorithms.AES(binascii.unhexlify(key)),
        lambda iv, **kwargs: modes.OFB(binascii.unhexlify(iv)),
    )


@pytest.mark.supported(
    only_if=lambda backend: backend.cipher_supported(
        algorithms.AES(b"\x00" * 16), modes.CFB(b"\x00" * 16)
    ),
    skip_message="Does not support AES CFB",
)
class TestAESModeCFB:
    test_cfb = generate_encrypt_test(
        load_nist_vectors,
        os.path.join("ciphers", "AES", "CFB"),
        [
            "CFB128GFSbox128.rsp",
            "CFB128GFSbox192.rsp",
            "CFB128GFSbox256.rsp",
            "CFB128KeySbox128.rsp",
            "CFB128KeySbox192.rsp",
            "CFB128KeySbox256.rsp",
            "CFB128VarKey128.rsp",
            "CFB128VarKey192.rsp",
            "CFB128VarKey256.rsp",
            "CFB128VarTxt128.rsp",
            "CFB128VarTxt192.rsp",
            "CFB128VarTxt256.rsp",
            "CFB128MMT128.rsp",
            "CFB128MMT192.rsp",
            "CFB128MMT256.rsp",
        ],
        lambda key, **kwargs: algorithms.AES(binascii.unhexlify(key)),
        lambda iv, **kwargs: modes.CFB(binascii.unhexlify(iv)),
    )


@pytest.mark.supported(
    only_if=lambda backend: backend.cipher_supported(
        algorithms.AES(b"\x00" * 16), modes.CFB8(b"\x00" * 16)
    ),
    skip_message="Does not support AES CFB8",
)
class TestAESModeCFB8:
    test_cfb8 = generate_encrypt_test(
        load_nist_vectors,
        os.path.join("ciphers", "AES", "CFB"),
        [
            "CFB8GFSbox128.rsp",
            "CFB8GFSbox192.rsp",
            "CFB8GFSbox256.rsp",
            "CFB8KeySbox128.rsp",
            "CFB8KeySbox192.rsp",
            "CFB8KeySbox256.rsp",
            "CFB8VarKey128.rsp",
            "CFB8VarKey192.rsp",
            "CFB8VarKey256.rsp",
            "CFB8VarTxt128.rsp",
            "CFB8VarTxt192.rsp",
            "CFB8VarTxt256.rsp",
            "CFB8MMT128.rsp",
            "CFB8MMT192.rsp",
            "CFB8MMT256.rsp",
        ],
        lambda key, **kwargs: algorithms.AES(binascii.unhexlify(key)),
        lambda iv, **kwargs: modes.CFB8(binascii.unhexlify(iv)),
    )


@pytest.mark.supported(
    only_if=lambda backend: backend.cipher_supported(
        algorithms.AES(b"\x00" * 16), modes.CTR(b"\x00" * 16)
    ),
    skip_message="Does not support AES CTR",
)
class TestAESModeCTR:
    test_ctr = generate_encrypt_test(
        load_nist_vectors,
        os.path.join("ciphers", "AES", "CTR"),
        ["aes-128-ctr.txt", "aes-192-ctr.txt", "aes-256-ctr.txt"],
        lambda key, **kwargs: algorithms.AES(binascii.unhexlify(key)),
        lambda iv, **kwargs: modes.CTR(binascii.unhexlify(iv)),
    )


@pytest.mark.parametrize(
    "mode",
    [
        modes.CBC(bytearray(b"\x00" * 16)),
        modes.CTR(bytearray(b"\x00" * 16)),
        modes.OFB(bytearray(b"\x00" * 16)),
        modes.CFB(bytearray(b"\x00" * 16)),
        modes.CFB8(bytearray(b"\x00" * 16)),
        modes.XTS(bytearray(b"\x00" * 16)),
        # Add a dummy mode for coverage of the cipher_supported check.
        DummyMode(),
    ],
)
def test_buffer_protocol_alternate_modes(mode, backend):
    data = bytearray(b"sixteen_byte_msg")
    key = algorithms.AES(bytearray(os.urandom(32)))
    if not backend.cipher_supported(key, mode):
        pytest.skip(f"AES in {mode.name} mode not supported")
    cipher = base.Cipher(key, mode, backend)
    enc = cipher.encryptor()
    ct = enc.update(data) + enc.finalize()
    dec = cipher.decryptor()
    pt = dec.update(ct) + dec.finalize()
    assert pt == data


@pytest.mark.parametrize(
    "mode",
    [
        modes.ECB(),
        modes.CBC(bytearray(b"\x00" * 16)),
        modes.CTR(bytearray(b"\x00" * 16)),
        modes.OFB(bytearray(b"\x00" * 16)),
        modes.CFB(bytearray(b"\x00" * 16)),
        modes.CFB8(bytearray(b"\x00" * 16)),
    ],
)
@pytest.mark.parametrize("alg_cls", [algorithms.AES128, algorithms.AES256])
def test_alternate_aes_classes(mode, alg_cls, backend):
    alg = alg_cls(b"0" * (alg_cls.key_size // 8))
    if not backend.cipher_supported(alg, mode):
        pytest.skip(f"AES in {mode.name} mode not supported")
    data = bytearray(b"sixteen_byte_msg")
    cipher = base.Cipher(alg, mode, backend)
    enc = cipher.encryptor()
    ct = enc.update(data) + enc.finalize()
    dec = cipher.decryptor()
    pt = dec.update(ct) + dec.finalize()
    assert pt == data


def test_reset_nonce(backend):
    data = b"helloworld" * 10
    nonce = b"\x00" * 16
    nonce_alt = b"\xee" * 16
    cipher = base.Cipher(
        algorithms.AES(b"\x00" * 16),
        modes.CTR(nonce),
    )
    cipher_alt = base.Cipher(
        algorithms.AES(b"\x00" * 16),
        modes.CTR(nonce_alt),
    )
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


def test_reset_nonce_invalid_mode(backend):
    iv = b"\x00" * 16
    c = base.Cipher(
        algorithms.AES(b"\x00" * 16),
        modes.CBC(iv),
    )
    enc = c.encryptor()
    with raises_unsupported_algorithm(_Reasons.UNSUPPORTED_CIPHER):
        enc.reset_nonce(iv)
    dec = c.decryptor()
    with raises_unsupported_algorithm(_Reasons.UNSUPPORTED_CIPHER):
        dec.reset_nonce(iv)
