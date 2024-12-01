# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.

import pytest

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives.ciphers.aead import (
    AESCCM,
    AESGCM,
    AESOCB3,
    AESSIV,
    ChaCha20Poly1305,
)


def _aead_supported(cls):
    try:
        cls(b"0" * 32)
        return True
    except UnsupportedAlgorithm:
        return False


@pytest.mark.skipif(
    not _aead_supported(ChaCha20Poly1305),
    reason="Requires OpenSSL with ChaCha20Poly1305 support",
)
def test_chacha20poly1305_encrypt(benchmark):
    chacha = ChaCha20Poly1305(b"\x00" * 32)
    benchmark(chacha.encrypt, b"\x00" * 12, b"hello world plaintext", b"")


@pytest.mark.skipif(
    not _aead_supported(ChaCha20Poly1305),
    reason="Requires OpenSSL with ChaCha20Poly1305 support",
)
def test_chacha20poly1305_decrypt(benchmark):
    chacha = ChaCha20Poly1305(b"\x00" * 32)
    ct = chacha.encrypt(b"\x00" * 12, b"hello world plaintext", b"")
    benchmark(chacha.decrypt, b"\x00" * 12, ct, b"")


def test_aesgcm_encrypt(benchmark):
    aes = AESGCM(b"\x00" * 32)
    benchmark(aes.encrypt, b"\x00" * 12, b"hello world plaintext", None)


def test_aesgcm_decrypt(benchmark):
    aes = AESGCM(b"\x00" * 32)
    ct = aes.encrypt(b"\x00" * 12, b"hello world plaintext", None)
    benchmark(aes.decrypt, b"\x00" * 12, ct, None)


@pytest.mark.skipif(
    not _aead_supported(AESSIV),
    reason="Requires OpenSSL with AES-SIV support",
)
def test_aessiv_encrypt(benchmark):
    aes = AESSIV(b"\x00" * 32)
    benchmark(aes.encrypt, b"hello world plaintext", None)


@pytest.mark.skipif(
    not _aead_supported(AESSIV),
    reason="Requires OpenSSL with AES-SIV support",
)
def test_aessiv_decrypt(benchmark):
    aes = AESSIV(b"\x00" * 32)
    ct = aes.encrypt(b"hello world plaintext", None)
    benchmark(aes.decrypt, ct, None)


@pytest.mark.skipif(
    not _aead_supported(AESOCB3),
    reason="Requires OpenSSL with AES-OCB3 support",
)
def test_aesocb3_encrypt(benchmark):
    aes = AESOCB3(b"\x00" * 32)
    benchmark(aes.encrypt, b"\x00" * 12, b"hello world plaintext", None)


@pytest.mark.skipif(
    not _aead_supported(AESOCB3),
    reason="Requires OpenSSL with AES-OCB3 support",
)
def test_aesocb3_decrypt(benchmark):
    aes = AESOCB3(b"\x00" * 32)
    ct = aes.encrypt(b"\x00" * 12, b"hello world plaintext", None)
    benchmark(aes.decrypt, b"\x00" * 12, ct, None)


@pytest.mark.skipif(
    not _aead_supported(AESCCM),
    reason="Requires OpenSSL with AES-CCM support",
)
def test_aesccm_encrypt(benchmark):
    aes = AESCCM(b"\x00" * 32)
    benchmark(aes.encrypt, b"\x00" * 12, b"hello world plaintext", None)


@pytest.mark.skipif(
    not _aead_supported(AESCCM),
    reason="Requires OpenSSL with AES-CCM support",
)
def test_aesccm_decrypt(benchmark):
    aes = AESCCM(b"\x00" * 32)
    ct = aes.encrypt(b"\x00" * 12, b"hello world plaintext", None)
    benchmark(aes.decrypt, b"\x00" * 12, ct, None)
