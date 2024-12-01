"""
Test conda-package-handling can work in `.tar.bz2`-only mode if zstandard is not
available. (Giving the user a chance to immediately install zstandard.)
"""

import importlib
import subprocess
import sys
import warnings


def test_degraded():
    try:
        sys.modules["zstandard"] = None  # type: ignore
        sys.modules["conda_package_streaming.transmute"] = None  # type: ignore
        sys.modules["conda_package_handling.conda_fmt"] = None  # type: ignore

        # this is only testing conda_package_handling's code, and does not test
        # that conda_package_streaming works without zstandard.

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")  # Ensure warnings are sent
            import conda_package_handling.api

            importlib.reload(conda_package_handling.api)

            assert len(w) == 1
            assert issubclass(w[-1].category, UserWarning)
            assert "zstandard" in str(w[-1].message)
            assert conda_package_handling.api.libarchive_enabled is False

    finally:
        sys.modules.pop("zstandard", None)
        sys.modules.pop("conda_package_handling.conda_fmt", None)
        sys.modules.pop("conda_package_streaming.transmute", None)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")  # Ensure warnings are sent
            import conda_package_handling.api

            importlib.reload(conda_package_handling.api)
            assert len(w) == 0
            assert conda_package_handling.api.libarchive_enabled is True


def test_degraded_subprocess():
    """
    More reliable way to mock 'zstandard not available'
    """
    subprocess.check_call(
        [
            sys.executable,
            "-c",
            "import sys; sys.modules['zstandard'] = None; import conda_package_handling.api",
        ]
    )
