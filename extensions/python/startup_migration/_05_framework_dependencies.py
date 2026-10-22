import importlib.metadata
from pathlib import Path
import shutil
import subprocess
import sys

from packaging.requirements import Requirement

from helpers import files, process, runtime
from helpers.extension import Extension
from helpers.print_style import PrintStyle


_REQUIREMENTS_FILE = Path(files.get_abs_path("requirements.txt"))
_PACKAGES = {
    "litellm", "openai", "python-dotenv", "aiohttp", "anyio", "urllib3",
    "filelock", "fsspec", "multidict", "psycopg",
}


class FrameworkDependencies(Extension):
    def execute(self, **kwargs):
        if not runtime.is_dockerized():
            return
        requirements = _requirements()
        outdated = _outdated(requirements)
        if not outdated:
            return
        uv = shutil.which("uv")
        if not uv:
            raise RuntimeError("Framework dependency update requires 'uv'.")
        PrintStyle.info("Updating framework dependencies:", ", ".join(outdated))
        subprocess.check_call(
            [uv, "pip", "install", "--python", sys.executable, *map(str, requirements)],
            timeout=60,
        )
        outdated = _outdated(requirements)
        if outdated:
            raise RuntimeError(f"Framework dependencies still unavailable after installation: {outdated}")
        # Models were imported before startup migrations; load the upgraded SDKs.
        process.restart_process()


def _requirements() -> list[Requirement]:
    requirements = []
    for line in _REQUIREMENTS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.partition("#")[0].strip()
        if line:
            requirement = Requirement(line)
            if requirement.name in _PACKAGES:
                requirements.append(requirement)
    missing = _PACKAGES - {requirement.name for requirement in requirements}
    if missing:
        raise RuntimeError(f"Framework requirements missing from {_REQUIREMENTS_FILE}: {sorted(missing)}")
    return requirements


def _outdated(requirements: list[Requirement]) -> list[str]:
    outdated = []
    for requirement in requirements:
        try:
            installed = importlib.metadata.version(requirement.name)
        except importlib.metadata.PackageNotFoundError:
            installed = None
        if installed is None or installed not in requirement.specifier:
            outdated.append(str(requirement))
        elif requirement.name == "psycopg" and "binary" in requirement.extras:
            try:
                binary = importlib.metadata.version("psycopg-binary")
            except importlib.metadata.PackageNotFoundError:
                binary = None
            if binary is None or binary not in requirement.specifier:
                outdated.append(str(requirement))
    return outdated
