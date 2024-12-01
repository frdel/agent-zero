# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


import binascii
import os
import typing

import pytest

from cryptography.exceptions import (
    AlreadyFinalized,
    AlreadyUpdated,
    InvalidSignature,
    InvalidTag,
    NotYetFinalized,
)
from cryptography.hazmat.decrepit.ciphers import (
    algorithms as decrepit_algorithms,
)
from cryptography.hazmat.primitives import hashes, hmac, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.ciphers import (
    BlockCipherAlgorithm,
    Cipher,
    algorithms,
)
from cryptography.hazmat.primitives.ciphers.modes import GCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF, HKDFExpand
from cryptography.hazmat.primitives.kdf.kbkdf import (
    KBKDFCMAC,
    KBKDFHMAC,
    CounterLocation,
    Mode,
)

from ...utils import load_vectors_from_file


def _load_all_params(path, file_names, param_loader):
    all_params = []
    for file_name in file_names:
        all_params.extend(
            load_vectors_from_file(os.path.join(path, file_name), param_loader)
        )
    return all_params


def generate_encrypt_test(
    param_loader, path, file_names, cipher_factory, mode_factory
):
    def test_encryption(self, backend, subtests):
        for params in _load_all_params(path, file_names, param_loader):
            with subtests.test():
                encrypt_test(backend, cipher_factory, mode_factory, params)

    return test_encryption


def encrypt_test(backend, cipher_factory, mode_factory, params):
    assert backend.cipher_supported(
        cipher_factory(**params), mode_factory(**params)
    )

    plaintext = params["plaintext"]
    ciphertext = params["ciphertext"]
    cipher = Cipher(
        cipher_factory(**params), mode_factory(**params), backend=backend
    )
    encryptor = cipher.encryptor()
    actual_ciphertext = encryptor.update(binascii.unhexlify(plaintext))
    actual_ciphertext += encryptor.finalize()
    assert actual_ciphertext == binascii.unhexlify(ciphertext)
    decryptor = cipher.decryptor()
    actual_plaintext = decryptor.update(binascii.unhexlify(ciphertext))
    actual_plaintext += decryptor.finalize()
    assert actual_plaintext == binascii.unhexlify(plaintext)


def generate_aead_test(
    param_loader, path, file_names, cipher_factory, mode_factory
):
    assert mode_factory is GCM

    def test_aead(self, backend, subtests):
        all_params = _load_all_params(path, file_names, param_loader)
        # We don't support IVs < 64-bit in GCM mode so just strip them out
        all_params = [i for i in all_params if len(i["iv"]) >= 16]
        for params in all_params:
            with subtests.test():
                aead_test(backend, cipher_factory, mode_factory, params)

    return test_aead


def aead_test(backend, cipher_factory, mode_factory, params):
    if (
        mode_factory is GCM
        and backend._fips_enabled
        and len(params["iv"]) != 24
    ):
        # Red Hat disables non-96-bit IV support as part of its FIPS
        # patches. The check is for a byte length of 24 because the value is
        # hex encoded.
        pytest.skip("Non-96-bit IVs unsupported in FIPS mode.")

    tag = binascii.unhexlify(params["tag"])
    mode = mode_factory(
        binascii.unhexlify(params["iv"]),
        tag,
        len(tag),
    )
    assert isinstance(mode, GCM)
    if params.get("pt") is not None:
        plaintext = binascii.unhexlify(params["pt"])
    ciphertext = binascii.unhexlify(params["ct"])
    aad = binascii.unhexlify(params["aad"])
    if params.get("fail") is True:
        cipher = Cipher(
            cipher_factory(binascii.unhexlify(params["key"])),
            mode,
            backend,
        )
        decryptor = cipher.decryptor()
        decryptor.authenticate_additional_data(aad)
        actual_plaintext = decryptor.update(ciphertext)
        with pytest.raises(InvalidTag):
            decryptor.finalize()
    else:
        cipher = Cipher(
            cipher_factory(binascii.unhexlify(params["key"])),
            mode_factory(binascii.unhexlify(params["iv"]), None),
            backend,
        )
        encryptor = cipher.encryptor()
        encryptor.authenticate_additional_data(aad)
        actual_ciphertext = encryptor.update(plaintext)
        actual_ciphertext += encryptor.finalize()
        assert encryptor.tag[: len(tag)] == tag
        cipher = Cipher(
            cipher_factory(binascii.unhexlify(params["key"])),
            mode_factory(
                binascii.unhexlify(params["iv"]),
                tag,
                min_tag_length=len(tag),
            ),
            backend,
        )
        decryptor = cipher.decryptor()
        decryptor.authenticate_additional_data(aad)
        actual_plaintext = decryptor.update(ciphertext)
        actual_plaintext += decryptor.finalize()
        assert actual_plaintext == plaintext


def generate_stream_encryption_test(
    param_loader, path, file_names, cipher_factory
):
    def test_stream_encryption(self, backend, subtests):
        for params in _load_all_params(path, file_names, param_loader):
            with subtests.test():
                stream_encryption_test(backend, cipher_factory, params)

    return test_stream_encryption


def stream_encryption_test(backend, cipher_factory, params):
    plaintext = params["plaintext"]
    ciphertext = params["ciphertext"]
    offset = params["offset"]
    cipher = Cipher(cipher_factory(**params), None, backend=backend)
    encryptor = cipher.encryptor()
    # throw away offset bytes
    encryptor.update(b"\x00" * int(offset))
    actual_ciphertext = encryptor.update(binascii.unhexlify(plaintext))
    actual_ciphertext += encryptor.finalize()
    assert actual_ciphertext == binascii.unhexlify(ciphertext)
    decryptor = cipher.decryptor()
    decryptor.update(b"\x00" * int(offset))
    actual_plaintext = decryptor.update(binascii.unhexlify(ciphertext))
    actual_plaintext += decryptor.finalize()
    assert actual_plaintext == binascii.unhexlify(plaintext)


def generate_hash_test(param_loader, path, file_names, hash_cls):
    def test_hash(self, backend, subtests):
        for params in _load_all_params(path, file_names, param_loader):
            with subtests.test():
                hash_test(backend, hash_cls, params)

    return test_hash


def hash_test(backend, algorithm, params):
    msg, md = params
    m = hashes.Hash(algorithm, backend=backend)
    m.update(binascii.unhexlify(msg))
    expected_md = md.replace(" ", "").lower().encode("ascii")
    assert m.finalize() == binascii.unhexlify(expected_md)


def generate_base_hash_test(algorithm, digest_size):
    def test_base_hash(self, backend):
        base_hash_test(backend, algorithm, digest_size)

    return test_base_hash


def base_hash_test(backend, algorithm, digest_size):
    m = hashes.Hash(algorithm, backend=backend)
    assert m.algorithm.digest_size == digest_size
    m_copy = m.copy()
    assert m != m_copy

    m.update(b"abc")
    copy = m.copy()
    copy.update(b"123")
    m.update(b"123")
    assert copy.finalize() == m.finalize()


def generate_base_hmac_test(hash_cls):
    def test_base_hmac(self, backend):
        base_hmac_test(backend, hash_cls)

    return test_base_hmac


def base_hmac_test(backend, algorithm):
    key = b"ab"
    h = hmac.HMAC(binascii.unhexlify(key), algorithm, backend=backend)
    h_copy = h.copy()
    assert h != h_copy


def generate_hmac_test(param_loader, path, file_names, algorithm):
    def test_hmac(self, backend, subtests):
        for params in _load_all_params(path, file_names, param_loader):
            with subtests.test():
                hmac_test(backend, algorithm, params)

    return test_hmac


def hmac_test(backend, algorithm, params):
    msg, md, key = params
    h = hmac.HMAC(binascii.unhexlify(key), algorithm, backend=backend)
    h.update(binascii.unhexlify(msg))
    assert h.finalize() == binascii.unhexlify(md.encode("ascii"))


def generate_aead_exception_test(cipher_factory, mode_factory):
    def test_aead_exception(self, backend):
        aead_exception_test(backend, cipher_factory, mode_factory)

    return test_aead_exception


def aead_exception_test(backend, cipher_factory, mode_factory):
    mode = mode_factory(binascii.unhexlify(b"0" * 24))
    assert isinstance(mode, GCM)
    cipher = Cipher(
        cipher_factory(binascii.unhexlify(b"0" * 32)),
        mode,
        backend,
    )
    encryptor = cipher.encryptor()
    encryptor.update(b"a" * 16)
    with pytest.raises(NotYetFinalized):
        encryptor.tag
    with pytest.raises(AlreadyUpdated):
        encryptor.authenticate_additional_data(b"b" * 16)
    encryptor.finalize()
    with pytest.raises(AlreadyFinalized):
        encryptor.authenticate_additional_data(b"b" * 16)
    with pytest.raises(AlreadyFinalized):
        encryptor.update(b"b" * 16)
    with pytest.raises(AlreadyFinalized):
        encryptor.finalize()

    mode2 = mode_factory(binascii.unhexlify(b"0" * 24), b"0" * 16)
    assert isinstance(mode2, GCM)
    cipher = Cipher(
        cipher_factory(binascii.unhexlify(b"0" * 32)),
        mode2,
        backend,
    )
    decryptor = cipher.decryptor()
    decryptor.update(b"a" * 16)
    with pytest.raises(AlreadyUpdated):
        decryptor.authenticate_additional_data(b"b" * 16)
    with pytest.raises(AttributeError):
        decryptor.tag  # type: ignore[attr-defined]


def generate_aead_tag_exception_test(cipher_factory, mode_factory):
    def test_aead_tag_exception(self, backend):
        aead_tag_exception_test(backend, cipher_factory, mode_factory)

    return test_aead_tag_exception


def aead_tag_exception_test(backend, cipher_factory, mode_factory):
    cipher = Cipher(
        cipher_factory(binascii.unhexlify(b"0" * 32)),
        mode_factory(binascii.unhexlify(b"0" * 24)),
        backend,
    )

    with pytest.raises(ValueError):
        mode_factory(binascii.unhexlify(b"0" * 24), b"000")

    with pytest.raises(ValueError):
        Cipher(
            cipher_factory(binascii.unhexlify(b"0" * 32)),
            mode_factory(binascii.unhexlify(b"0" * 24), b"toolong" * 12),
            backend,
        )

    with pytest.raises(ValueError):
        mode_factory(binascii.unhexlify(b"0" * 24), b"000000", 2)

    cipher = Cipher(
        cipher_factory(binascii.unhexlify(b"0" * 32)),
        mode_factory(binascii.unhexlify(b"0" * 24), b"0" * 16),
        backend,
    )
    with pytest.raises(ValueError):
        cipher.encryptor()


def hkdf_derive_test(backend, algorithm, params):
    hkdf = HKDF(
        algorithm,
        int(params["l"]),
        salt=binascii.unhexlify(params["salt"]) or None,
        info=binascii.unhexlify(params["info"]) or None,
        backend=backend,
    )

    okm = hkdf.derive(binascii.unhexlify(params["ikm"]))

    assert okm == binascii.unhexlify(params["okm"])


def hkdf_extract_test(backend, algorithm, params):
    hkdf = HKDF(
        algorithm,
        int(params["l"]),
        salt=binascii.unhexlify(params["salt"]) or None,
        info=binascii.unhexlify(params["info"]) or None,
        backend=backend,
    )

    prk = hkdf._extract(binascii.unhexlify(params["ikm"]))

    assert prk == binascii.unhexlify(params["prk"])


def hkdf_expand_test(backend, algorithm, params):
    hkdf = HKDFExpand(
        algorithm,
        int(params["l"]),
        info=binascii.unhexlify(params["info"]) or None,
        backend=backend,
    )

    okm = hkdf.derive(binascii.unhexlify(params["prk"]))

    assert okm == binascii.unhexlify(params["okm"])


def generate_hkdf_test(param_loader, path, file_names, algorithm):
    def test_hkdf(self, backend, subtests):
        for params in _load_all_params(path, file_names, param_loader):
            with subtests.test():
                hkdf_extract_test(backend, algorithm, params)
            with subtests.test():
                hkdf_expand_test(backend, algorithm, params)
            with subtests.test():
                hkdf_derive_test(backend, algorithm, params)

    return test_hkdf


def generate_kbkdf_counter_mode_test(param_loader, path, file_names):
    def test_kbkdf(self, backend, subtests):
        for params in _load_all_params(path, file_names, param_loader):
            with subtests.test():
                kbkdf_counter_mode_test(backend, params)

    return test_kbkdf


def _kbkdf_hmac_counter_mode_test(backend, prf, ctr_loc, brk_loc, params):
    supported_hash_algorithms: typing.Dict[
        str, typing.Type[hashes.HashAlgorithm]
    ] = {
        "hmac_sha1": hashes.SHA1,
        "hmac_sha224": hashes.SHA224,
        "hmac_sha256": hashes.SHA256,
        "hmac_sha384": hashes.SHA384,
        "hmac_sha512": hashes.SHA512,
    }

    algorithm = supported_hash_algorithms.get(prf)
    assert algorithm is not None
    assert backend.hmac_supported(algorithm())

    ctrkdf = KBKDFHMAC(
        algorithm(),
        Mode.CounterMode,
        params["l"] // 8,
        params["rlen"] // 8,
        None,
        ctr_loc,
        None,
        None,
        binascii.unhexlify(params["fixedinputdata"]),
        backend=backend,
        break_location=brk_loc,
    )

    ko = ctrkdf.derive(binascii.unhexlify(params["ki"]))
    assert binascii.hexlify(ko) == params["ko"]


def _kbkdf_cmac_counter_mode_test(backend, prf, ctr_loc, brk_loc, params):
    supported_cipher_algorithms: typing.Dict[
        str, typing.Type[BlockCipherAlgorithm]
    ] = {
        "cmac_aes128": algorithms.AES,
        "cmac_aes192": algorithms.AES,
        "cmac_aes256": algorithms.AES,
        "cmac_tdes2": decrepit_algorithms.TripleDES,
        "cmac_tdes3": decrepit_algorithms.TripleDES,
    }

    algorithm = supported_cipher_algorithms.get(prf)
    assert algorithm is not None

    # TripleDES is disallowed in FIPS mode.
    if backend._fips_enabled and algorithm is decrepit_algorithms.TripleDES:
        pytest.skip("TripleDES is not supported in FIPS mode.")

    ctrkdf = KBKDFCMAC(
        algorithm,
        Mode.CounterMode,
        params["l"] // 8,
        params["rlen"] // 8,
        None,
        ctr_loc,
        None,
        None,
        binascii.unhexlify(params["fixedinputdata"]),
        backend=backend,
        break_location=brk_loc,
    )

    ko = ctrkdf.derive(binascii.unhexlify(params["ki"]))
    assert binascii.hexlify(ko) == params["ko"]


def kbkdf_counter_mode_test(backend, params):
    supported_counter_locations = {
        "before_fixed": CounterLocation.BeforeFixed,
        "after_fixed": CounterLocation.AfterFixed,
        "middle_fixed": CounterLocation.MiddleFixed,
    }

    ctr_loc = supported_counter_locations[params.pop("ctrlocation")]
    brk_loc = None

    if ctr_loc == CounterLocation.MiddleFixed:
        assert "fixedinputdata" not in params
        params["fixedinputdata"] = params.pop(
            "databeforectrdata"
        ) + params.pop("dataafterctrdata")

        brk_loc = params.pop("databeforectrlen")
        assert isinstance(brk_loc, int)

    prf = params.get("prf")
    assert prf is not None
    assert isinstance(prf, str)
    del params["prf"]
    if prf.startswith("hmac"):
        _kbkdf_hmac_counter_mode_test(backend, prf, ctr_loc, brk_loc, params)
    else:
        assert prf.startswith("cmac")
        _kbkdf_cmac_counter_mode_test(backend, prf, ctr_loc, brk_loc, params)


def generate_rsa_verification_test(
    param_loader, path, file_names, hash_alg, pad_factory
):
    def test_rsa_verification(self, backend, subtests):
        all_params = _load_all_params(path, file_names, param_loader)
        all_params = [
            i for i in all_params if i["algorithm"] == hash_alg.name.upper()
        ]
        for params in all_params:
            with subtests.test():
                rsa_verification_test(backend, params, hash_alg, pad_factory)

    return test_rsa_verification


def rsa_verification_test(backend, params, hash_alg, pad_factory):
    public_numbers = rsa.RSAPublicNumbers(
        e=params["public_exponent"], n=params["modulus"]
    )
    public_key = public_numbers.public_key(backend)
    pad = pad_factory(params, hash_alg)
    signature = binascii.unhexlify(params["s"])
    msg = binascii.unhexlify(params["msg"])
    if params["fail"]:
        with pytest.raises(InvalidSignature):
            public_key.verify(signature, msg, pad, hash_alg)
    else:
        public_key.verify(signature, msg, pad, hash_alg)


def _rsa_recover_euler_private_exponent(e: int, p: int, q: int) -> int:
    """
    Compute the RSA private_exponent (d) given the public exponent (e)
    and the RSA primes p and q, following the usage of the original
    RSA paper.

    As in the original RSA paper, this uses the Euler totient function
    instead of the Carmichael totient function, and thus may generate a
    larger value of the private exponent than necessary.

    See cryptography.hazmat.primitives.asymmetric.rsa_recover_private_exponent
    for the public-facing version of this function, which uses the
    preferred Carmichael totient function.
    """
    phi_n = (p - 1) * (q - 1)
    return rsa._modinv(e, phi_n)


def _check_rsa_private_numbers(skey):
    assert skey
    pkey = skey.public_numbers
    assert pkey
    assert pkey.e
    assert pkey.n

    # Historically there have been two ways to calculate valid values of the
    # private_exponent (d) given the public exponent (e):
    # - using the Carmichael totient function (gives smaller and more
    #   computationally-efficient values, and is required by some standards)
    # - using the Euler totient function (matching the original RSA paper)
    # Allow for either here.
    assert skey.d in (
        rsa.rsa_recover_private_exponent(pkey.e, skey.p, skey.q),
        _rsa_recover_euler_private_exponent(pkey.e, skey.p, skey.q),
    )

    assert skey.p * skey.q == pkey.n
    assert skey.dmp1 == rsa.rsa_crt_dmp1(skey.d, skey.p)
    assert skey.dmq1 == rsa.rsa_crt_dmq1(skey.d, skey.q)
    assert skey.iqmp == rsa.rsa_crt_iqmp(skey.p, skey.q)


def _check_dsa_private_numbers(skey):
    assert skey
    pkey = skey.public_numbers
    params = pkey.parameter_numbers
    assert pow(params.g, skey.x, params.p) == pkey.y


def skip_fips_traditional_openssl(backend, fmt):
    if (
        fmt is serialization.PrivateFormat.TraditionalOpenSSL
        and backend._fips_enabled
    ):
        pytest.skip(
            "Traditional OpenSSL key format is not supported in FIPS mode."
        )
