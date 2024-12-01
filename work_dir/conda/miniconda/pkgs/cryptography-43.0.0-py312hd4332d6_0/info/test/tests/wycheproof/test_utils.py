# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.

from ..utils import WycheproofTest


def test_wycheproof_test_repr():
    wycheproof = WycheproofTest({}, {}, {"tcId": 3})
    assert repr(wycheproof) == "<WycheproofTest({}, {}, {'tcId': 3}, tcId=3)>"
