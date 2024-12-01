# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


import sys
import types
import typing
import warnings

import pytest

from cryptography.utils import deprecated


class TestDeprecated:
    @typing.no_type_check
    def test_deprecated(self, monkeypatch):
        mod = types.ModuleType("TestDeprecated/test_deprecated")
        monkeypatch.setitem(sys.modules, mod.__name__, mod)
        deprecated(
            name="X",
            value=1,
            module_name=mod.__name__,
            message="deprecated message text",
            warning_class=DeprecationWarning,
        )
        mod.Y = deprecated(
            value=2,
            module_name=mod.__name__,
            message="more deprecated text",
            warning_class=PendingDeprecationWarning,
        )
        mod = sys.modules[mod.__name__]
        mod.Z = 3

        with warnings.catch_warnings(record=True) as log:
            warnings.simplefilter("always", PendingDeprecationWarning)
            warnings.simplefilter("always", DeprecationWarning)
            assert mod.X == 1
            assert mod.Y == 2
            assert mod.Z == 3

        [msg1, msg2] = log
        assert msg1.category is DeprecationWarning
        assert msg1.message.args == ("deprecated message text",)

        assert msg2.category is PendingDeprecationWarning
        assert msg2.message.args == ("more deprecated text",)

        assert "Y" in dir(mod)

    @typing.no_type_check
    def test_deleting_deprecated_members(self, monkeypatch):
        mod = types.ModuleType("TestDeprecated/test_deprecated")
        monkeypatch.setitem(sys.modules, mod.__name__, mod)
        deprecated(
            name="X",
            value=1,
            module_name=mod.__name__,
            message="deprecated message text",
            warning_class=DeprecationWarning,
        )
        mod.Y = deprecated(
            value=2,
            module_name=mod.__name__,
            message="more deprecated text",
            warning_class=PendingDeprecationWarning,
        )
        mod = sys.modules[mod.__name__]
        mod.Z = 3

        with warnings.catch_warnings(record=True) as log:
            warnings.simplefilter("always", PendingDeprecationWarning)
            warnings.simplefilter("always", DeprecationWarning)
            del mod.X
            del mod.Y
            del mod.Z

        [msg1, msg2] = log
        assert msg1.category is DeprecationWarning
        assert msg1.message.args == ("deprecated message text",)

        assert msg2.category is PendingDeprecationWarning
        assert msg2.message.args == ("more deprecated text",)

        assert "X" not in dir(mod)
        assert "Y" not in dir(mod)
        assert "Z" not in dir(mod)

        with pytest.raises(AttributeError):
            del mod.X
