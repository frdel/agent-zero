import importlib.metadata
import subprocess
import sys

import pytest

from extensions.python.startup_migration import _05_framework_dependencies as migration


@pytest.fixture
def installed(monkeypatch):
    requirements = migration._requirements()
    versions = {req.name: next(iter(req.specifier)).version for req in requirements}
    versions["psycopg-binary"] = versions["psycopg"]

    def version(name):
        if name not in versions:
            raise importlib.metadata.PackageNotFoundError(name)
        return versions[name]

    monkeypatch.setattr(migration.runtime, "is_dockerized", lambda: True)
    monkeypatch.setattr(migration.process, "restart_process", lambda: pytest.fail("Unexpected restart"))
    monkeypatch.setattr(migration.importlib.metadata, "version", version)
    monkeypatch.setattr(migration.shutil, "which", lambda _name: "/usr/bin/uv")
    return versions


@pytest.mark.parametrize("package,old_version", [
    ("litellm", "1.88.1"), ("openai", "2.41.1"),
    ("aiohttp", "3.14.0"), ("filelock", None), ("psycopg", None), ("psycopg-binary", None),
])
def test_self_update_installs_requirements_and_restarts_once(monkeypatch, installed, package, old_version):
    target = installed.copy()
    installed.pop(package)
    if old_version:
        installed[package] = old_version
    calls = []
    restarts = []

    def install(command, **kwargs):
        calls.append((command, kwargs))
        installed.update(target)

    monkeypatch.setattr(migration.subprocess, "check_call", install)
    monkeypatch.setattr(migration.process, "restart_process", lambda: restarts.append(True))
    extension = migration.FrameworkDependencies(None)
    extension.execute()
    extension.execute()
    assert restarts == [True]
    assert len(calls) == 1
    command, kwargs = calls[0]
    assert command[:5] == ["/usr/bin/uv", "pip", "install", "--python", sys.executable]
    assert set(command[5:]) == {
        "litellm==1.104.0", "openai==2.54.0", "python-dotenv==1.2.2",
        "aiohttp>=3.14.3", "anyio>=4.14.2", "urllib3>=2.8.0",
        "filelock>=3.20.3", "fsspec>=2026.6.0", "multidict>=6.9.1",
        "psycopg[binary]==3.3.6",
    }
    assert kwargs == {"timeout": 60}


def test_current_image_skips_installer_and_restart(monkeypatch, installed):
    installed["filelock"] = "3.32.7"
    monkeypatch.setattr(migration.shutil, "which", lambda _name: pytest.fail("Installer lookup"))
    migration.FrameworkDependencies(None).execute()


@pytest.mark.parametrize("error", [
    subprocess.CalledProcessError(1, "uv"), subprocess.TimeoutExpired("uv", 60),
])
def test_failed_install_stops_startup_without_restart(monkeypatch, installed, error):
    installed.pop("litellm")

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(migration.subprocess, "check_call", fail)
    with pytest.raises(type(error)):
        migration.FrameworkDependencies(None).execute()


def test_install_must_satisfy_requirements_before_restart(monkeypatch, installed):
    installed["openai"] = "2.41.1"
    monkeypatch.setattr(migration.subprocess, "check_call", lambda *args, **kwargs: None)
    with pytest.raises(RuntimeError, match="still unavailable"):
        migration.FrameworkDependencies(None).execute()


def test_non_docker_environment_skips_dependency_migration(monkeypatch):
    monkeypatch.setattr(migration.runtime, "is_dockerized", lambda: False)
    monkeypatch.setattr(migration, "_requirements", lambda: pytest.fail("Requirements check"))
    migration.FrameworkDependencies(None).execute()
