import sys
from subprocess import check_output

import pytest

cwp = pytest.importorskip("menuinst._legacy.cwp", reason="Windows only")


def test_cwp():
    out = check_output(
        [
            sys.executable,
            cwp.__file__,
            sys.prefix,
            "python",
            "-c",
            "import sys; print(sys.prefix)",
        ],
        text=True,
    )
    assert out.strip() == sys.prefix
