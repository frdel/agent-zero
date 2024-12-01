# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


import re

import pytest

from cryptography.exceptions import AlreadyFinalized, InvalidKey, _Reasons
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import algorithms
from cryptography.hazmat.primitives.kdf.kbkdf import (
    KBKDFCMAC,
    KBKDFHMAC,
    CounterLocation,
    Mode,
)

from ...doubles import (
    DummyBlockCipherAlgorithm,
    DummyCipherAlgorithm,
    DummyHashAlgorithm,
)
from ...utils import raises_unsupported_algorithm


class TestKBKDFHMAC:
    def test_invalid_key(self, backend):
        kdf = KBKDFHMAC(
            hashes.SHA256(),
            Mode.CounterMode,
            32,
            4,
            4,
            CounterLocation.BeforeFixed,
            b"label",
            b"context",
            None,
            backend=backend,
        )

        key = kdf.derive(b"material")

        kdf = KBKDFHMAC(
            hashes.SHA256(),
            Mode.CounterMode,
            32,
            4,
            4,
            CounterLocation.BeforeFixed,
            b"label",
            b"context",
            None,
            backend=backend,
        )

        with pytest.raises(InvalidKey):
            kdf.verify(b"material2", key)

    def test_already_finalized(self, backend):
        kdf = KBKDFHMAC(
            hashes.SHA256(),
            Mode.CounterMode,
            32,
            4,
            4,
            CounterLocation.BeforeFixed,
            b"label",
            b"context",
            None,
            backend=backend,
        )

        kdf.derive(b"material")

        with pytest.raises(AlreadyFinalized):
            kdf.derive(b"material2")

        kdf = KBKDFHMAC(
            hashes.SHA256(),
            Mode.CounterMode,
            32,
            4,
            4,
            CounterLocation.BeforeFixed,
            b"label",
            b"context",
            None,
            backend=backend,
        )

        key = kdf.derive(b"material")

        with pytest.raises(AlreadyFinalized):
            kdf.verify(b"material", key)

        kdf = KBKDFHMAC(
            hashes.SHA256(),
            Mode.CounterMode,
            32,
            4,
            4,
            CounterLocation.BeforeFixed,
            b"label",
            b"context",
            None,
            backend=backend,
        )
        kdf.verify(b"material", key)

        with pytest.raises(AlreadyFinalized):
            kdf.verify(b"material", key)

    def test_key_length(self, backend):
        kdf = KBKDFHMAC(
            hashes.SHA1(),
            Mode.CounterMode,
            85899345920,
            4,
            4,
            CounterLocation.BeforeFixed,
            b"label",
            b"context",
            None,
            backend=backend,
        )

        with pytest.raises(ValueError):
            kdf.derive(b"material")

    def test_rlen(self, backend):
        with pytest.raises(ValueError):
            KBKDFHMAC(
                hashes.SHA256(),
                Mode.CounterMode,
                32,
                5,
                4,
                CounterLocation.BeforeFixed,
                b"label",
                b"context",
                None,
                backend=backend,
            )

    def test_r_type(self, backend):
        with pytest.raises(TypeError):
            KBKDFHMAC(
                hashes.SHA1(),
                Mode.CounterMode,
                32,
                b"r",  # type: ignore[arg-type]
                4,
                CounterLocation.BeforeFixed,
                b"label",
                b"context",
                None,
                backend=backend,
            )

    def test_zero_llen(self, backend):
        with pytest.raises(ValueError):
            KBKDFHMAC(
                hashes.SHA256(),
                Mode.CounterMode,
                32,
                4,
                0,
                CounterLocation.BeforeFixed,
                b"label",
                b"context",
                None,
                backend=backend,
            )

    def test_l_type(self, backend):
        with pytest.raises(TypeError):
            KBKDFHMAC(
                hashes.SHA1(),
                Mode.CounterMode,
                32,
                4,
                b"l",  # type: ignore[arg-type]
                CounterLocation.BeforeFixed,
                b"label",
                b"context",
                None,
                backend=backend,
            )

    def test_l(self, backend):
        with pytest.raises(ValueError):
            KBKDFHMAC(
                hashes.SHA1(),
                Mode.CounterMode,
                32,
                4,
                None,
                CounterLocation.BeforeFixed,
                b"label",
                b"context",
                None,
                backend=backend,
            )

    def test_unsupported_mode(self, backend):
        with pytest.raises(TypeError):
            KBKDFHMAC(
                hashes.SHA256(),
                None,  # type: ignore[arg-type]
                32,
                4,
                4,
                CounterLocation.BeforeFixed,
                b"label",
                b"context",
                None,
                backend=backend,
            )

    def test_unsupported_location(self, backend):
        with pytest.raises(TypeError):
            KBKDFHMAC(
                hashes.SHA256(),
                Mode.CounterMode,
                32,
                4,
                4,
                None,  # type: ignore[arg-type]
                b"label",
                b"context",
                None,
                backend=backend,
            )

    def test_unsupported_parameters(self, backend):
        with pytest.raises(ValueError):
            KBKDFHMAC(
                hashes.SHA256(),
                Mode.CounterMode,
                32,
                4,
                4,
                CounterLocation.BeforeFixed,
                b"label",
                b"context",
                b"fixed",
                backend=backend,
            )

    def test_missing_break_location(self, backend):
        with pytest.raises(
            ValueError, match=re.escape("Please specify a break_location")
        ):
            KBKDFHMAC(
                hashes.SHA256(),
                Mode.CounterMode,
                32,
                4,
                4,
                CounterLocation.MiddleFixed,
                b"label",
                b"context",
                None,
                backend=backend,
            )

        with pytest.raises(
            ValueError, match=re.escape("Please specify a break_location")
        ):
            KBKDFHMAC(
                hashes.SHA256(),
                Mode.CounterMode,
                32,
                4,
                4,
                CounterLocation.MiddleFixed,
                b"label",
                b"context",
                None,
                backend=backend,
                break_location=None,
            )

    def test_keyword_only_break_location(self, backend):
        with pytest.raises(
            TypeError, match=r"\d+ positional arguments but \d+ were given\Z"
        ):
            KBKDFHMAC(
                hashes.SHA256(),
                Mode.CounterMode,
                32,
                4,
                4,
                CounterLocation.MiddleFixed,
                b"label",
                b"context",
                None,
                backend,
                0,  # break_location
            )  # type: ignore

    def test_invalid_break_location(self, backend):
        with pytest.raises(
            TypeError, match=re.escape("break_location must be an integer")
        ):
            KBKDFHMAC(
                hashes.SHA256(),
                Mode.CounterMode,
                32,
                4,
                4,
                CounterLocation.MiddleFixed,
                b"label",
                b"context",
                None,
                backend=backend,
                break_location="0",  # type: ignore[arg-type]
            )

        with pytest.raises(
            ValueError,
            match=re.escape("break_location must be a positive integer"),
        ):
            KBKDFHMAC(
                hashes.SHA256(),
                Mode.CounterMode,
                32,
                4,
                4,
                CounterLocation.MiddleFixed,
                b"label",
                b"context",
                None,
                backend=backend,
                break_location=-1,
            )

        with pytest.raises(
            ValueError, match=re.escape("break_location offset > len(fixed)")
        ):
            kdf = KBKDFHMAC(
                hashes.SHA256(),
                Mode.CounterMode,
                32,
                4,
                4,
                CounterLocation.MiddleFixed,
                b"label",
                b"context",
                None,
                backend=backend,
                break_location=18,
            )
            kdf.derive(b"input key")

    def test_ignored_break_location_before(self, backend):
        with pytest.raises(
            ValueError,
            match=re.escape(
                "break_location is ignored when location is not"
                " CounterLocation.MiddleFixed"
            ),
        ):
            KBKDFHMAC(
                hashes.SHA256(),
                Mode.CounterMode,
                32,
                4,
                4,
                CounterLocation.BeforeFixed,
                b"label",
                b"context",
                None,
                backend=backend,
                break_location=0,
            )

    def test_ignored_break_location_after(self, backend):
        with pytest.raises(
            ValueError,
            match=re.escape(
                "break_location is ignored when location is not"
                " CounterLocation.MiddleFixed"
            ),
        ):
            KBKDFHMAC(
                hashes.SHA256(),
                Mode.CounterMode,
                32,
                4,
                4,
                CounterLocation.AfterFixed,
                b"label",
                b"context",
                None,
                backend=backend,
                break_location=0,
            )

    def test_unsupported_hash(self, backend):
        with raises_unsupported_algorithm(_Reasons.UNSUPPORTED_HASH):
            KBKDFHMAC(
                object(),  # type: ignore[arg-type]
                Mode.CounterMode,
                32,
                4,
                4,
                CounterLocation.BeforeFixed,
                b"label",
                b"context",
                None,
                backend=backend,
            )

    def test_unsupported_algorithm(self, backend):
        with raises_unsupported_algorithm(_Reasons.UNSUPPORTED_HASH):
            KBKDFHMAC(
                DummyHashAlgorithm(),
                Mode.CounterMode,
                32,
                4,
                4,
                CounterLocation.BeforeFixed,
                b"label",
                b"context",
                None,
                backend=backend,
            )

    def test_unicode_error_label(self, backend):
        with pytest.raises(TypeError):
            KBKDFHMAC(
                hashes.SHA256(),
                Mode.CounterMode,
                32,
                4,
                4,
                CounterLocation.BeforeFixed,
                "label",  # type: ignore[arg-type]
                b"context",
                None,
                backend=backend,
            )

    def test_unicode_error_context(self, backend):
        with pytest.raises(TypeError):
            KBKDFHMAC(
                hashes.SHA256(),
                Mode.CounterMode,
                32,
                4,
                4,
                CounterLocation.BeforeFixed,
                b"label",
                "context",  # type: ignore[arg-type]
                None,
                backend=backend,
            )

    def test_unicode_error_key_material(self, backend):
        with pytest.raises(TypeError):
            kdf = KBKDFHMAC(
                hashes.SHA256(),
                Mode.CounterMode,
                32,
                4,
                4,
                CounterLocation.BeforeFixed,
                b"label",
                b"context",
                None,
                backend=backend,
            )
            kdf.derive("material")  # type: ignore[arg-type]

    def test_buffer_protocol(self, backend):
        kdf = KBKDFHMAC(
            hashes.SHA256(),
            Mode.CounterMode,
            10,
            4,
            4,
            CounterLocation.BeforeFixed,
            b"label",
            b"context",
            None,
            backend=backend,
        )

        key = kdf.derive(bytearray(b"material"))
        assert key == b"\xb7\x01\x05\x98\xf5\x1a\x12L\xc7."


class TestKBKDFCMAC:
    _KEY_MATERIAL = bytes(32)
    _KEY_MATERIAL2 = _KEY_MATERIAL.replace(b"\x00", b"\x01", 1)

    def test_invalid_key(self, backend):
        kdf = KBKDFCMAC(
            algorithms.AES,
            Mode.CounterMode,
            32,
            4,
            4,
            CounterLocation.BeforeFixed,
            b"label",
            b"context",
            None,
            backend=backend,
        )

        key = kdf.derive(self._KEY_MATERIAL)

        kdf = KBKDFCMAC(
            algorithms.AES,
            Mode.CounterMode,
            32,
            4,
            4,
            CounterLocation.BeforeFixed,
            b"label",
            b"context",
            None,
            backend=backend,
        )

        with pytest.raises(InvalidKey):
            kdf.verify(self._KEY_MATERIAL2, key)

    def test_already_finalized(self, backend):
        kdf = KBKDFCMAC(
            algorithms.AES,
            Mode.CounterMode,
            32,
            4,
            4,
            CounterLocation.BeforeFixed,
            b"label",
            b"context",
            None,
            backend=backend,
        )

        kdf.derive(self._KEY_MATERIAL)

        with pytest.raises(AlreadyFinalized):
            kdf.derive(self._KEY_MATERIAL2)

        kdf = KBKDFCMAC(
            algorithms.AES,
            Mode.CounterMode,
            32,
            4,
            4,
            CounterLocation.BeforeFixed,
            b"label",
            b"context",
            None,
            backend=backend,
        )

        key = kdf.derive(self._KEY_MATERIAL)

        with pytest.raises(AlreadyFinalized):
            kdf.verify(self._KEY_MATERIAL, key)

        kdf = KBKDFCMAC(
            algorithms.AES,
            Mode.CounterMode,
            32,
            4,
            4,
            CounterLocation.BeforeFixed,
            b"label",
            b"context",
            None,
            backend=backend,
        )
        kdf.verify(self._KEY_MATERIAL, key)

        with pytest.raises(AlreadyFinalized):
            kdf.verify(self._KEY_MATERIAL, key)

    def test_key_length(self, backend):
        kdf = KBKDFCMAC(
            algorithms.AES,
            Mode.CounterMode,
            85899345920,
            4,
            4,
            CounterLocation.BeforeFixed,
            b"label",
            b"context",
            None,
            backend=backend,
        )

        with pytest.raises(ValueError):
            kdf.derive(self._KEY_MATERIAL)

    def test_rlen(self, backend):
        with pytest.raises(ValueError):
            KBKDFCMAC(
                algorithms.AES,
                Mode.CounterMode,
                32,
                5,
                4,
                CounterLocation.BeforeFixed,
                b"label",
                b"context",
                None,
                backend=backend,
            )

    def test_r_type(self, backend):
        with pytest.raises(TypeError):
            KBKDFCMAC(
                algorithms.AES,
                Mode.CounterMode,
                32,
                b"r",  # type: ignore[arg-type]
                4,
                CounterLocation.BeforeFixed,
                b"label",
                b"context",
                None,
                backend=backend,
            )

    def test_zero_llen(self, backend):
        with pytest.raises(ValueError):
            KBKDFCMAC(
                algorithms.AES,
                Mode.CounterMode,
                32,
                4,
                0,
                CounterLocation.BeforeFixed,
                b"label",
                b"context",
                None,
                backend=backend,
            )

    def test_l_type(self, backend):
        with pytest.raises(TypeError):
            KBKDFCMAC(
                algorithms.AES,
                Mode.CounterMode,
                32,
                4,
                b"l",  # type: ignore[arg-type]
                CounterLocation.BeforeFixed,
                b"label",
                b"context",
                None,
                backend=backend,
            )

    def test_l(self, backend):
        with pytest.raises(ValueError):
            KBKDFCMAC(
                algorithms.AES,
                Mode.CounterMode,
                32,
                4,
                None,
                CounterLocation.BeforeFixed,
                b"label",
                b"context",
                None,
                backend=backend,
            )

    def test_unsupported_mode(self, backend):
        with pytest.raises(TypeError):
            KBKDFCMAC(
                algorithms.AES,
                None,  # type: ignore[arg-type]
                32,
                4,
                4,
                CounterLocation.BeforeFixed,
                b"label",
                b"context",
                None,
                backend=backend,
            )

    def test_unsupported_location(self, backend):
        with pytest.raises(TypeError):
            KBKDFCMAC(
                algorithms.AES,
                Mode.CounterMode,
                32,
                4,
                4,
                None,  # type: ignore[arg-type]
                b"label",
                b"context",
                None,
                backend=backend,
            )

    def test_unsupported_parameters(self, backend):
        with pytest.raises(ValueError):
            KBKDFCMAC(
                algorithms.AES,
                Mode.CounterMode,
                32,
                4,
                4,
                CounterLocation.BeforeFixed,
                b"label",
                b"context",
                b"fixed",
                backend=backend,
            )

    def test_missing_break_location(self, backend):
        with pytest.raises(
            ValueError, match=re.escape("Please specify a break_location")
        ):
            KBKDFCMAC(
                algorithms.AES,
                Mode.CounterMode,
                32,
                4,
                4,
                CounterLocation.MiddleFixed,
                b"label",
                b"context",
                None,
                backend=backend,
            )

        with pytest.raises(
            ValueError, match=re.escape("Please specify a break_location")
        ):
            KBKDFCMAC(
                algorithms.AES,
                Mode.CounterMode,
                32,
                4,
                4,
                CounterLocation.MiddleFixed,
                b"label",
                b"context",
                None,
                backend=backend,
                break_location=None,
            )

    def test_keyword_only_break_location(self, backend):
        with pytest.raises(
            TypeError, match=r"\d+ positional arguments but \d+ were given\Z"
        ):
            KBKDFCMAC(
                algorithms.AES,
                Mode.CounterMode,
                32,
                4,
                4,
                CounterLocation.MiddleFixed,
                b"label",
                b"context",
                None,
                backend,
                0,  # break_location
            )  # type: ignore

    def test_invalid_break_location(self, backend):
        with pytest.raises(
            TypeError, match=re.escape("break_location must be an integer")
        ):
            KBKDFCMAC(
                algorithms.AES,
                Mode.CounterMode,
                32,
                4,
                4,
                CounterLocation.MiddleFixed,
                b"label",
                b"context",
                None,
                backend=backend,
                break_location="0",  # type: ignore[arg-type]
            )

        with pytest.raises(
            ValueError,
            match=re.escape("break_location must be a positive integer"),
        ):
            KBKDFCMAC(
                algorithms.AES,
                Mode.CounterMode,
                32,
                4,
                4,
                CounterLocation.MiddleFixed,
                b"label",
                b"context",
                None,
                backend=backend,
                break_location=-1,
            )

        with pytest.raises(
            ValueError, match=re.escape("break_location offset > len(fixed)")
        ):
            kdf = KBKDFCMAC(
                algorithms.AES,
                Mode.CounterMode,
                32,
                4,
                4,
                CounterLocation.MiddleFixed,
                b"label",
                b"context",
                None,
                backend=backend,
                break_location=18,
            )
            kdf.derive(b"32 bytes long input key material")

    def test_ignored_break_location_before(self, backend):
        with pytest.raises(
            ValueError,
            match=re.escape(
                "break_location is ignored when location is not"
                " CounterLocation.MiddleFixed"
            ),
        ):
            KBKDFCMAC(
                algorithms.AES,
                Mode.CounterMode,
                32,
                4,
                4,
                CounterLocation.BeforeFixed,
                b"label",
                b"context",
                None,
                backend=backend,
                break_location=0,
            )

    def test_ignored_break_location_after(self, backend):
        with pytest.raises(
            ValueError,
            match=re.escape(
                "break_location is ignored when location is not"
                " CounterLocation.MiddleFixed"
            ),
        ):
            KBKDFCMAC(
                algorithms.AES,
                Mode.CounterMode,
                32,
                4,
                4,
                CounterLocation.AfterFixed,
                b"label",
                b"context",
                None,
                backend=backend,
                break_location=0,
            )

    def test_unsupported_algorithm(self, backend):
        with raises_unsupported_algorithm(_Reasons.UNSUPPORTED_CIPHER):
            KBKDFCMAC(
                object,
                Mode.CounterMode,
                32,
                4,
                4,
                CounterLocation.BeforeFixed,
                b"label",
                b"context",
                None,
                backend=backend,
            )

        with raises_unsupported_algorithm(_Reasons.UNSUPPORTED_CIPHER):
            KBKDFCMAC(
                DummyCipherAlgorithm,
                Mode.CounterMode,
                32,
                4,
                4,
                CounterLocation.BeforeFixed,
                b"label",
                b"context",
                None,
                backend=backend,
            )

        with raises_unsupported_algorithm(_Reasons.UNSUPPORTED_CIPHER):
            KBKDFCMAC(
                algorithms.ChaCha20,
                Mode.CounterMode,
                32,
                4,
                4,
                CounterLocation.BeforeFixed,
                b"label",
                b"context",
                None,
                backend=backend,
            )

    def test_unicode_error_label(self, backend):
        with pytest.raises(TypeError):
            KBKDFCMAC(
                algorithms.AES,
                Mode.CounterMode,
                32,
                4,
                4,
                CounterLocation.BeforeFixed,
                "label",  # type: ignore[arg-type]
                b"context",
                None,
                backend=backend,
            )

    def test_unicode_error_context(self, backend):
        with pytest.raises(TypeError):
            KBKDFCMAC(
                algorithms.AES,
                Mode.CounterMode,
                32,
                4,
                4,
                CounterLocation.BeforeFixed,
                b"label",
                "context",  # type: ignore[arg-type]
                None,
                backend=backend,
            )

    def test_unsupported_cipher(self, backend):
        kdf = KBKDFCMAC(
            DummyBlockCipherAlgorithm,
            Mode.CounterMode,
            32,
            4,
            4,
            CounterLocation.BeforeFixed,
            b"label",
            b"context",
            None,
            backend=backend,
        )
        with raises_unsupported_algorithm(_Reasons.UNSUPPORTED_CIPHER):
            kdf.derive(self._KEY_MATERIAL)

    def test_unicode_error_key_material(self, backend):
        kdf = KBKDFCMAC(
            algorithms.AES,
            Mode.CounterMode,
            32,
            4,
            4,
            CounterLocation.BeforeFixed,
            b"label",
            b"context",
            None,
            backend=backend,
        )
        with pytest.raises(TypeError):
            kdf.derive("material")  # type: ignore[arg-type]

    def test_wrong_key_material_length(self, backend):
        kdf = KBKDFCMAC(
            algorithms.AES,
            Mode.CounterMode,
            32,
            4,
            4,
            CounterLocation.BeforeFixed,
            b"label",
            b"context",
            None,
            backend=backend,
        )
        with pytest.raises(ValueError):
            kdf.derive(b"material")

    def test_buffer_protocol(self, backend):
        kdf = KBKDFCMAC(
            algorithms.AES,
            Mode.CounterMode,
            10,
            4,
            4,
            CounterLocation.BeforeFixed,
            b"label",
            b"context",
            None,
            backend=backend,
        )

        key = kdf.derive(bytearray(self._KEY_MATERIAL))
        assert key == b"\x19\xcd\xbe\x17Lb\x115<\xd0"
