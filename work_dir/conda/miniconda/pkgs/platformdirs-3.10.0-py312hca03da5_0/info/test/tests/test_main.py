from __future__ import annotations

import sys
from subprocess import check_output

from platformdirs import __version__
from platformdirs.__main__ import PROPS


def test_props_same_as_test(props: tuple[str, ...]) -> None:
    assert props == PROPS


def test_run_as_module() -> None:
    out = check_output([sys.executable, "-m", "platformdirs"], text=True)

    assert out.startswith(f"-- platformdirs {__version__} --")
    for prop in PROPS:
        assert prop in out
