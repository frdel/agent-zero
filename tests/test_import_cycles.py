import subprocess
import sys
from pathlib import Path


def test_strings_module_imports_before_files():
    repo_root = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        [sys.executable, "-c", "import helpers.strings; import helpers.files"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
