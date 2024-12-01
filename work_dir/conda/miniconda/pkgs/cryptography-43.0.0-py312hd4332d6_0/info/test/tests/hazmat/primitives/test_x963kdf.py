# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


import binascii

import pytest

from cryptography.exceptions import AlreadyFinalized, InvalidKey
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.x963kdf import X963KDF


class TestX963KDF:
    def test_length_limit(self, backend):
        big_length = hashes.SHA256().digest_size * (2**32 - 1) + 1

        with pytest.raises(ValueError):
            X963KDF(hashes.SHA256(), big_length, None, backend)

    def test_already_finalized(self, backend):
        xkdf = X963KDF(hashes.SHA256(), 16, None, backend)

        xkdf.derive(b"\x01" * 16)

        with pytest.raises(AlreadyFinalized):
            xkdf.derive(b"\x02" * 16)

    def test_derive(self, backend):
        key = binascii.unhexlify(
            b"96c05619d56c328ab95fe84b18264b08725b85e33fd34f08"
        )

        derivedkey = binascii.unhexlify(b"443024c3dae66b95e6f5670601558f71")

        xkdf = X963KDF(hashes.SHA256(), 16, None, backend)

        assert xkdf.derive(key) == derivedkey

    def test_buffer_protocol(self, backend):
        key = bytearray(
            binascii.unhexlify(
                b"96c05619d56c328ab95fe84b18264b08725b85e33fd34f08"
            )
        )

        derivedkey = binascii.unhexlify(b"443024c3dae66b95e6f5670601558f71")

        xkdf = X963KDF(hashes.SHA256(), 16, None, backend)

        assert xkdf.derive(key) == derivedkey

    def test_verify(self, backend):
        key = binascii.unhexlify(
            b"22518b10e70f2a3f243810ae3254139efbee04aa57c7af7d"
        )

        sharedinfo = binascii.unhexlify(b"75eef81aa3041e33b80971203d2c0c52")

        derivedkey = binascii.unhexlify(
            b"c498af77161cc59f2962b9a713e2b215152d139766ce34a776df11866a69bf2e"
            b"52a13d9c7c6fc878c50c5ea0bc7b00e0da2447cfd874f6cf92f30d0097111485"
            b"500c90c3af8b487872d04685d14c8d1dc8d7fa08beb0ce0ababc11f0bd496269"
            b"142d43525a78e5bc79a17f59676a5706dc54d54d4d1f0bd7e386128ec26afc21"
        )

        xkdf = X963KDF(hashes.SHA256(), 128, sharedinfo, backend)

        xkdf.verify(key, derivedkey)

    def test_invalid_verify(self, backend):
        key = binascii.unhexlify(
            b"96c05619d56c328ab95fe84b18264b08725b85e33fd34f08"
        )

        xkdf = X963KDF(hashes.SHA256(), 16, None, backend)

        with pytest.raises(InvalidKey):
            xkdf.verify(key, b"wrong derived key")

    def test_unicode_typeerror(self, backend):
        with pytest.raises(TypeError):
            X963KDF(
                hashes.SHA256(),
                16,
                sharedinfo="foo",  # type: ignore[arg-type]
                backend=backend,
            )

        with pytest.raises(TypeError):
            xkdf = X963KDF(
                hashes.SHA256(), 16, sharedinfo=None, backend=backend
            )

            xkdf.derive("foo")  # type: ignore[arg-type]

        with pytest.raises(TypeError):
            xkdf = X963KDF(
                hashes.SHA256(), 16, sharedinfo=None, backend=backend
            )

            xkdf.verify("foo", b"bar")  # type: ignore[arg-type]

        with pytest.raises(TypeError):
            xkdf = X963KDF(
                hashes.SHA256(), 16, sharedinfo=None, backend=backend
            )

            xkdf.verify(b"foo", "bar")  # type: ignore[arg-type]
