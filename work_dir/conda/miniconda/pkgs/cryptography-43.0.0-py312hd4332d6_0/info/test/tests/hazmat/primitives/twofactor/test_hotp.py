# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


import os

import pytest

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.hashes import MD5, SHA1
from cryptography.hazmat.primitives.twofactor import InvalidToken
from cryptography.hazmat.primitives.twofactor.hotp import HOTP

from ....utils import load_nist_vectors, load_vectors_from_file

vectors = load_vectors_from_file("twofactor/rfc-4226.txt", load_nist_vectors)


@pytest.mark.supported(
    only_if=lambda backend: backend.hmac_supported(hashes.SHA1()),
    skip_message="Does not support HMAC-SHA1.",
)
class TestHOTP:
    def test_invalid_key_length(self, backend):
        secret = os.urandom(10)

        with pytest.raises(ValueError):
            HOTP(secret, 6, SHA1(), backend)

    def test_unenforced_invalid_kwy_length(self, backend):
        secret = os.urandom(10)
        HOTP(secret, 6, SHA1(), backend, enforce_key_length=False)

    def test_invalid_hotp_length(self, backend):
        secret = os.urandom(16)

        with pytest.raises(ValueError):
            HOTP(secret, 4, SHA1(), backend)

    def test_invalid_algorithm(self, backend):
        secret = os.urandom(16)

        with pytest.raises(TypeError):
            HOTP(secret, 6, MD5(), backend)  # type: ignore[arg-type]

    @pytest.mark.parametrize("params", vectors)
    def test_truncate(self, backend, params):
        secret = params["secret"]
        counter = int(params["counter"])
        truncated = params["truncated"]

        hotp = HOTP(secret, 6, SHA1(), backend)

        assert hotp._dynamic_truncate(counter) == int(truncated.decode(), 16)

    @pytest.mark.parametrize("params", vectors)
    def test_generate(self, backend, params):
        secret = params["secret"]
        counter = int(params["counter"])
        hotp_value = params["hotp"]

        hotp = HOTP(secret, 6, SHA1(), backend)

        assert hotp.generate(counter) == hotp_value

    @pytest.mark.parametrize("params", vectors)
    def test_verify(self, backend, params):
        secret = params["secret"]
        counter = int(params["counter"])
        hotp_value = params["hotp"]

        hotp = HOTP(secret, 6, SHA1(), backend)
        hotp.verify(hotp_value, counter)

    def test_invalid_verify(self, backend):
        secret = b"12345678901234567890"
        counter = 0

        hotp = HOTP(secret, 6, SHA1(), backend)

        with pytest.raises(InvalidToken):
            hotp.verify(b"123456", counter)

    def test_length_not_int(self, backend):
        secret = b"12345678901234567890"

        with pytest.raises(TypeError):
            HOTP(secret, b"foo", SHA1(), backend)  # type: ignore[arg-type]

    def test_get_provisioning_uri(self, backend):
        secret = b"12345678901234567890"
        hotp = HOTP(secret, 6, SHA1(), backend)

        assert hotp.get_provisioning_uri("Alice Smith", 1, None) == (
            "otpauth://hotp/Alice%20Smith?digits=6&secret=GEZDGNBV"
            "GY3TQOJQGEZDGNBVGY3TQOJQ&algorithm=SHA1&counter=1"
        )

        assert hotp.get_provisioning_uri("Alice Smith", 1, "Foo") == (
            "otpauth://hotp/Foo:Alice%20Smith?digits=6&secret=GEZD"
            "GNBVGY3TQOJQGEZDGNBVGY3TQOJQ&algorithm=SHA1&issuer=Foo"
            "&counter=1"
        )

    def test_buffer_protocol(self, backend):
        key = bytearray(b"a long key with lots of entropy goes here")
        hotp = HOTP(key, 6, SHA1(), backend)
        assert hotp.generate(10) == b"559978"
