# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


import base64
import datetime
import json
import os
import time

import pretend
import pytest

import cryptography_vectors
from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from cryptography.hazmat.primitives.ciphers import algorithms, modes


def json_parametrize(keys, filename):
    vector_file = cryptography_vectors.open_vector_file(
        os.path.join("fernet", filename), "r"
    )
    with vector_file:
        data = json.load(vector_file)
        return pytest.mark.parametrize(
            keys,
            [tuple([entry[k] for k in keys]) for entry in data],
            ids=[f"{filename}[{i}]" for i in range(len(data))],
        )


@pytest.mark.supported(
    only_if=lambda backend: backend.cipher_supported(
        algorithms.AES(b"\x00" * 32), modes.CBC(b"\x00" * 16)
    ),
    skip_message="Does not support AES CBC",
)
class TestFernet:
    @json_parametrize(
        ("secret", "now", "iv", "src", "token"),
        "generate.json",
    )
    def test_generate(self, secret, now, iv, src, token, backend):
        f = Fernet(secret.encode("ascii"), backend=backend)
        actual_token = f._encrypt_from_parts(
            src.encode("ascii"),
            int(datetime.datetime.fromisoformat(now).timestamp()),
            bytes(iv),
        )
        assert actual_token == token.encode("ascii")

    @json_parametrize(
        ("secret", "now", "src", "ttl_sec", "token"),
        "verify.json",
    )
    def test_verify(
        self, secret, now, src, ttl_sec, token, backend, monkeypatch
    ):
        # secret & token are both str
        f = Fernet(secret.encode("ascii"), backend=backend)
        current_time = int(datetime.datetime.fromisoformat(now).timestamp())
        payload = f.decrypt_at_time(
            token,  # str
            ttl=ttl_sec,
            current_time=current_time,
        )
        assert payload == src.encode("ascii")

        payload = f.decrypt_at_time(
            token.encode("ascii"),  # bytes
            ttl=ttl_sec,
            current_time=current_time,
        )
        assert payload == src.encode("ascii")

        monkeypatch.setattr(time, "time", lambda: current_time)

        payload = f.decrypt(token, ttl=ttl_sec)  # str
        assert payload == src.encode("ascii")

        payload = f.decrypt(token.encode("ascii"), ttl=ttl_sec)  # bytes
        assert payload == src.encode("ascii")

    @json_parametrize(("secret", "token", "now", "ttl_sec"), "invalid.json")
    def test_invalid(self, secret, token, now, ttl_sec, backend, monkeypatch):
        f = Fernet(secret.encode("ascii"), backend=backend)
        current_time = int(datetime.datetime.fromisoformat(now).timestamp())
        with pytest.raises(InvalidToken):
            f.decrypt_at_time(
                token.encode("ascii"),
                ttl=ttl_sec,
                current_time=current_time,
            )
        monkeypatch.setattr(time, "time", lambda: current_time)
        with pytest.raises(InvalidToken):
            f.decrypt(token.encode("ascii"), ttl=ttl_sec)

    def test_invalid_start_byte(self, backend):
        f = Fernet(base64.urlsafe_b64encode(b"\x00" * 32), backend=backend)
        with pytest.raises(InvalidToken):
            f.decrypt(base64.urlsafe_b64encode(b"\x81"))

    def test_timestamp_too_short(self, backend):
        f = Fernet(base64.urlsafe_b64encode(b"\x00" * 32), backend=backend)
        with pytest.raises(InvalidToken):
            f.decrypt(base64.urlsafe_b64encode(b"\x80abc"))

    def test_non_base64_token(self, backend):
        f = Fernet(base64.urlsafe_b64encode(b"\x00" * 32), backend=backend)
        with pytest.raises(InvalidToken):
            f.decrypt(b"\x00")
        with pytest.raises(InvalidToken):
            f.decrypt("nonsensetoken")

    def test_invalid_types(self, backend):
        f = Fernet(base64.urlsafe_b64encode(b"\x00" * 32), backend=backend)
        with pytest.raises(TypeError):
            f.encrypt("")  # type: ignore[arg-type]
        with pytest.raises(TypeError):
            f.decrypt(12345)  # type: ignore[arg-type]

    def test_timestamp_ignored_no_ttl(self, monkeypatch, backend):
        f = Fernet(base64.urlsafe_b64encode(b"\x00" * 32), backend=backend)
        pt = b"encrypt me"
        token = f.encrypt(pt)
        monkeypatch.setattr(time, "time", pretend.raiser(ValueError))
        assert f.decrypt(token, ttl=None) == pt

    def test_ttl_required_in_decrypt_at_time(self, backend):
        f = Fernet(base64.urlsafe_b64encode(b"\x00" * 32), backend=backend)
        pt = b"encrypt me"
        token = f.encrypt(pt)
        with pytest.raises(ValueError):
            f.decrypt_at_time(
                token,
                ttl=None,  # type: ignore[arg-type]
                current_time=int(time.time()),
            )

    @pytest.mark.parametrize("message", [b"", b"Abc!", b"\x00\xff\x00\x80"])
    def test_roundtrips(self, message, backend):
        f = Fernet(Fernet.generate_key(), backend=backend)
        assert f.decrypt(f.encrypt(message)) == message

    @pytest.mark.parametrize("key", [base64.urlsafe_b64encode(b"abc"), b"abc"])
    def test_bad_key(self, backend, key):
        with pytest.raises(ValueError):
            Fernet(key, backend=backend)

    def test_extract_timestamp(self, backend):
        f = Fernet(base64.urlsafe_b64encode(b"\x00" * 32), backend=backend)
        current_time = 1526138327
        token = f.encrypt_at_time(b"encrypt me", current_time)
        assert f.extract_timestamp(token) == current_time
        assert f.extract_timestamp(token.decode("ascii")) == current_time
        with pytest.raises(InvalidToken):
            f.extract_timestamp(b"nonsensetoken")


@pytest.mark.supported(
    only_if=lambda backend: backend.cipher_supported(
        algorithms.AES(b"\x00" * 32), modes.CBC(b"\x00" * 16)
    ),
    skip_message="Does not support AES CBC",
)
class TestMultiFernet:
    def test_encrypt(self, backend):
        f1 = Fernet(base64.urlsafe_b64encode(b"\x00" * 32), backend=backend)
        f2 = Fernet(base64.urlsafe_b64encode(b"\x01" * 32), backend=backend)
        f = MultiFernet([f1, f2])

        assert f1.decrypt(f.encrypt(b"abc")) == b"abc"

    def test_decrypt(self, backend):
        f1 = Fernet(base64.urlsafe_b64encode(b"\x00" * 32), backend=backend)
        f2 = Fernet(base64.urlsafe_b64encode(b"\x01" * 32), backend=backend)
        f = MultiFernet([f1, f2])

        # token as bytes
        assert f.decrypt(f1.encrypt(b"abc")) == b"abc"
        assert f.decrypt(f2.encrypt(b"abc")) == b"abc"

        # token as str
        assert f.decrypt(f1.encrypt(b"abc").decode("ascii")) == b"abc"
        assert f.decrypt(f2.encrypt(b"abc").decode("ascii")) == b"abc"

        with pytest.raises(InvalidToken):
            f.decrypt(b"\x00" * 16)

    def test_decrypt_at_time(self, backend):
        f1 = Fernet(base64.urlsafe_b64encode(b"\x00" * 32), backend=backend)
        f = MultiFernet([f1])
        pt = b"encrypt me"
        token = f.encrypt_at_time(pt, current_time=100)
        assert f.decrypt_at_time(token, ttl=1, current_time=100) == pt
        with pytest.raises(InvalidToken):
            f.decrypt_at_time(token, ttl=1, current_time=102)
        with pytest.raises(ValueError):
            f.decrypt_at_time(
                token,
                ttl=None,  # type: ignore[arg-type]
                current_time=100,
            )

    def test_no_fernets(self, backend):
        with pytest.raises(ValueError):
            MultiFernet([])

    def test_non_iterable_argument(self, backend):
        with pytest.raises(TypeError):
            MultiFernet(None)  # type: ignore[arg-type]

    def test_rotate_bytes(self, backend):
        f1 = Fernet(base64.urlsafe_b64encode(b"\x00" * 32), backend=backend)
        f2 = Fernet(base64.urlsafe_b64encode(b"\x01" * 32), backend=backend)

        mf1 = MultiFernet([f1])
        mf2 = MultiFernet([f2, f1])

        plaintext = b"abc"
        mf1_ciphertext = mf1.encrypt(plaintext)

        assert mf2.decrypt(mf1_ciphertext) == plaintext

        rotated = mf2.rotate(mf1_ciphertext)

        assert rotated != mf1_ciphertext
        assert mf2.decrypt(rotated) == plaintext

        with pytest.raises(InvalidToken):
            mf1.decrypt(rotated)

    def test_rotate_str(self, backend):
        f1 = Fernet(base64.urlsafe_b64encode(b"\x00" * 32), backend=backend)
        f2 = Fernet(base64.urlsafe_b64encode(b"\x01" * 32), backend=backend)

        mf1 = MultiFernet([f1])
        mf2 = MultiFernet([f2, f1])

        plaintext = b"abc"
        mf1_ciphertext = mf1.encrypt(plaintext).decode("ascii")

        assert mf2.decrypt(mf1_ciphertext) == plaintext
        rotated = mf2.rotate(mf1_ciphertext).decode("ascii")

        assert rotated != mf1_ciphertext
        assert mf2.decrypt(rotated) == plaintext

        with pytest.raises(InvalidToken):
            mf1.decrypt(rotated)

    def test_rotate_preserves_timestamp(self, backend):
        f1 = Fernet(base64.urlsafe_b64encode(b"\x00" * 32), backend=backend)
        f2 = Fernet(base64.urlsafe_b64encode(b"\x01" * 32), backend=backend)

        mf1 = MultiFernet([f1])
        mf2 = MultiFernet([f2, f1])

        plaintext = b"abc"
        original_time = int(time.time()) - 5 * 60
        mf1_ciphertext = mf1.encrypt_at_time(plaintext, original_time)

        rotated_time, _ = Fernet._get_unverified_token_data(
            mf2.rotate(mf1_ciphertext)
        )

        assert int(time.time()) != rotated_time
        assert original_time == rotated_time

    def test_rotate_decrypt_no_shared_keys(self, backend):
        f1 = Fernet(base64.urlsafe_b64encode(b"\x00" * 32), backend=backend)
        f2 = Fernet(base64.urlsafe_b64encode(b"\x01" * 32), backend=backend)

        mf1 = MultiFernet([f1])
        mf2 = MultiFernet([f2])

        with pytest.raises(InvalidToken):
            mf2.rotate(mf1.encrypt(b"abc"))
