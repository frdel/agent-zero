# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.

import binascii

import pytest

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESCCM, AESGCM

from ..hazmat.primitives.test_aead import _aead_supported
from .utils import wycheproof_tests


@wycheproof_tests("aes_cbc_pkcs5_test.json")
def test_aes_cbc_pkcs5(backend, wycheproof):
    key = binascii.unhexlify(wycheproof.testcase["key"])
    iv = binascii.unhexlify(wycheproof.testcase["iv"])
    msg = binascii.unhexlify(wycheproof.testcase["msg"])
    ct = binascii.unhexlify(wycheproof.testcase["ct"])

    padder = padding.PKCS7(128).padder()

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend)
    enc = cipher.encryptor()
    computed_ct = (
        enc.update(padder.update(msg) + padder.finalize()) + enc.finalize()
    )
    dec = cipher.decryptor()
    padded_msg = dec.update(ct) + dec.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    if wycheproof.valid or wycheproof.acceptable:
        assert computed_ct == ct
        computed_msg = unpadder.update(padded_msg) + unpadder.finalize()
        assert computed_msg == msg
    else:
        assert computed_ct != ct
        with pytest.raises(ValueError):
            unpadder.update(padded_msg) + unpadder.finalize()


@wycheproof_tests("aes_gcm_test.json")
def test_aes_gcm(backend, wycheproof):
    key = binascii.unhexlify(wycheproof.testcase["key"])
    iv = binascii.unhexlify(wycheproof.testcase["iv"])
    aad = binascii.unhexlify(wycheproof.testcase["aad"])
    msg = binascii.unhexlify(wycheproof.testcase["msg"])
    ct = binascii.unhexlify(wycheproof.testcase["ct"])
    tag = binascii.unhexlify(wycheproof.testcase["tag"])
    if len(iv) < 8 or len(iv) > 128:
        pytest.skip(
            "Less than 64-bit IVs (and greater than 1024-bit) are no longer "
            "supported"
        )
    if backend._fips_enabled and len(iv) != 12:
        # Red Hat disables non-96-bit IV support as part of its FIPS
        # patches.
        pytest.skip("Non-96-bit IVs unsupported in FIPS mode.")
    if wycheproof.valid or wycheproof.acceptable:
        enc = Cipher(algorithms.AES(key), modes.GCM(iv), backend).encryptor()
        enc.authenticate_additional_data(aad)
        computed_ct = enc.update(msg) + enc.finalize()
        computed_tag = enc.tag
        assert computed_ct == ct
        assert computed_tag == tag
        dec = Cipher(
            algorithms.AES(key),
            modes.GCM(iv, tag, min_tag_length=len(tag)),
            backend,
        ).decryptor()
        dec.authenticate_additional_data(aad)
        computed_msg = dec.update(ct) + dec.finalize()
        assert computed_msg == msg
    else:
        dec = Cipher(
            algorithms.AES(key),
            modes.GCM(iv, tag, min_tag_length=len(tag)),
            backend,
        ).decryptor()
        dec.authenticate_additional_data(aad)
        dec.update(ct)
        with pytest.raises(InvalidTag):
            dec.finalize()


@wycheproof_tests("aes_gcm_test.json")
def test_aes_gcm_aead_api(backend, wycheproof):
    key = binascii.unhexlify(wycheproof.testcase["key"])
    iv = binascii.unhexlify(wycheproof.testcase["iv"])
    aad = binascii.unhexlify(wycheproof.testcase["aad"])
    msg = binascii.unhexlify(wycheproof.testcase["msg"])
    ct = binascii.unhexlify(wycheproof.testcase["ct"])
    tag = binascii.unhexlify(wycheproof.testcase["tag"])
    if len(iv) < 8 or len(iv) > 128:
        pytest.skip(
            "Less than 64-bit IVs (and greater than 1024-bit) are no longer "
            "supported"
        )

    if backend._fips_enabled and len(iv) != 12:
        # Red Hat disables non-96-bit IV support as part of its FIPS
        # patches.
        pytest.skip("Non-96-bit IVs unsupported in FIPS mode.")
    aesgcm = AESGCM(key)
    if wycheproof.valid or wycheproof.acceptable:
        computed_ct = aesgcm.encrypt(iv, msg, aad)
        assert computed_ct == ct + tag
        computed_msg = aesgcm.decrypt(iv, ct + tag, aad)
        assert computed_msg == msg
    else:
        with pytest.raises(InvalidTag):
            aesgcm.decrypt(iv, ct + tag, aad)


@pytest.mark.skipif(
    not _aead_supported(AESCCM),
    reason="Requires OpenSSL with AES-CCM support",
)
@wycheproof_tests("aes_ccm_test.json")
def test_aes_ccm_aead_api(backend, wycheproof):
    key = binascii.unhexlify(wycheproof.testcase["key"])
    iv = binascii.unhexlify(wycheproof.testcase["iv"])
    aad = binascii.unhexlify(wycheproof.testcase["aad"])
    msg = binascii.unhexlify(wycheproof.testcase["msg"])
    ct = binascii.unhexlify(wycheproof.testcase["ct"])
    tag = binascii.unhexlify(wycheproof.testcase["tag"])

    if (
        wycheproof.invalid
        and wycheproof.testcase["comment"] == "Invalid tag size"
    ):
        with pytest.raises(ValueError):
            AESCCM(key, tag_length=wycheproof.testgroup["tagSize"] // 8)
        return

    aesccm = AESCCM(key, tag_length=wycheproof.testgroup["tagSize"] // 8)
    if wycheproof.valid or wycheproof.acceptable:
        computed_ct = aesccm.encrypt(iv, msg, aad)
        assert computed_ct == ct + tag
        computed_msg = aesccm.decrypt(iv, ct + tag, aad)
        assert computed_msg == msg
    elif not 7 <= len(iv) <= 13:
        with pytest.raises(ValueError):
            aesccm.decrypt(iv, ct + tag, aad)
    else:
        with pytest.raises(InvalidTag):
            aesccm.decrypt(iv, ct + tag, aad)
