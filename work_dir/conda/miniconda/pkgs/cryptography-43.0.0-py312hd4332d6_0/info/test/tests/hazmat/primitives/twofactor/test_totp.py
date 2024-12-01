# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


import pytest

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.twofactor import InvalidToken
from cryptography.hazmat.primitives.twofactor.totp import TOTP

from ....utils import load_nist_vectors, load_vectors_from_file

vectors = load_vectors_from_file("twofactor/rfc-6238.txt", load_nist_vectors)


class TestTOTP:
    @pytest.mark.supported(
        only_if=lambda backend: backend.hmac_supported(hashes.SHA1()),
        skip_message="Does not support HMAC-SHA1.",
    )
    @pytest.mark.parametrize(
        "params", [i for i in vectors if i["mode"] == b"SHA1"]
    )
    def test_generate_sha1(self, backend, params):
        secret = params["secret"]
        time = int(params["time"])
        totp_value = params["totp"]

        totp = TOTP(secret, 8, hashes.SHA1(), 30, backend)
        assert totp.generate(time) == totp_value

    @pytest.mark.supported(
        only_if=lambda backend: backend.hmac_supported(hashes.SHA256()),
        skip_message="Does not support HMAC-SHA256.",
    )
    @pytest.mark.parametrize(
        "params", [i for i in vectors if i["mode"] == b"SHA256"]
    )
    def test_generate_sha256(self, backend, params):
        secret = params["secret"]
        time = int(params["time"])
        totp_value = params["totp"]

        totp = TOTP(secret, 8, hashes.SHA256(), 30, backend)
        assert totp.generate(time) == totp_value

    @pytest.mark.supported(
        only_if=lambda backend: backend.hmac_supported(hashes.SHA512()),
        skip_message="Does not support HMAC-SHA512.",
    )
    @pytest.mark.parametrize(
        "params", [i for i in vectors if i["mode"] == b"SHA512"]
    )
    def test_generate_sha512(self, backend, params):
        secret = params["secret"]
        time = int(params["time"])
        totp_value = params["totp"]

        totp = TOTP(secret, 8, hashes.SHA512(), 30, backend)
        assert totp.generate(time) == totp_value

    @pytest.mark.supported(
        only_if=lambda backend: backend.hmac_supported(hashes.SHA1()),
        skip_message="Does not support HMAC-SHA1.",
    )
    @pytest.mark.parametrize(
        "params", [i for i in vectors if i["mode"] == b"SHA1"]
    )
    def test_verify_sha1(self, backend, params):
        secret = params["secret"]
        time = int(params["time"])
        totp_value = params["totp"]

        totp = TOTP(secret, 8, hashes.SHA1(), 30, backend)
        totp.verify(totp_value, time)

    @pytest.mark.supported(
        only_if=lambda backend: backend.hmac_supported(hashes.SHA256()),
        skip_message="Does not support HMAC-SHA256.",
    )
    @pytest.mark.parametrize(
        "params", [i for i in vectors if i["mode"] == b"SHA256"]
    )
    def test_verify_sha256(self, backend, params):
        secret = params["secret"]
        time = int(params["time"])
        totp_value = params["totp"]

        totp = TOTP(secret, 8, hashes.SHA256(), 30, backend)
        totp.verify(totp_value, time)

    @pytest.mark.supported(
        only_if=lambda backend: backend.hmac_supported(hashes.SHA512()),
        skip_message="Does not support HMAC-SHA512.",
    )
    @pytest.mark.parametrize(
        "params", [i for i in vectors if i["mode"] == b"SHA512"]
    )
    def test_verify_sha512(self, backend, params):
        secret = params["secret"]
        time = int(params["time"])
        totp_value = params["totp"]

        totp = TOTP(secret, 8, hashes.SHA512(), 30, backend)
        totp.verify(totp_value, time)

    def test_invalid_verify(self, backend):
        secret = b"12345678901234567890"
        time = 59

        totp = TOTP(secret, 8, hashes.SHA1(), 30, backend)

        with pytest.raises(InvalidToken):
            totp.verify(b"12345678", time)

    def test_floating_point_time_generate(self, backend):
        secret = b"12345678901234567890"
        time = 59.1

        totp = TOTP(secret, 8, hashes.SHA1(), 30, backend)

        assert totp.generate(time) == b"94287082"

    def test_get_provisioning_uri(self, backend):
        secret = b"12345678901234567890"
        totp = TOTP(secret, 6, hashes.SHA1(), 30, backend=backend)

        assert totp.get_provisioning_uri("Alice Smith", None) == (
            "otpauth://totp/Alice%20Smith?digits=6&secret=GEZDGNBVG"
            "Y3TQOJQGEZDGNBVGY3TQOJQ&algorithm=SHA1&period=30"
        )

        assert totp.get_provisioning_uri("Alice Smith", "World") == (
            "otpauth://totp/World:Alice%20Smith?digits=6&secret=GEZ"
            "DGNBVGY3TQOJQGEZDGNBVGY3TQOJQ&algorithm=SHA1&issuer=World"
            "&period=30"
        )

    def test_buffer_protocol(self, backend):
        key = bytearray(b"a long key with lots of entropy goes here")
        totp = TOTP(key, 8, hashes.SHA512(), 30, backend)
        time = 60
        assert totp.generate(time) == b"53049576"
