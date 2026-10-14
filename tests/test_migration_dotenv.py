import os
from pathlib import Path
import runpy
import sys

import pytest

from helpers import dotenv, files, migration, runtime, settings


@pytest.fixture
def env_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(files, "_base_dir", str(tmp_path))
    (tmp_path / "usr").mkdir()
    return tmp_path / ".env", tmp_path / "usr/.env"


def test_legacy_dotenv_migrates_once(env_paths):
    source, destination = env_paths
    source.write_text("ROOT_PASSWORD=legacy\nMIGRATION_TEST_VALUE=keep\n")
    source.chmod(0o600)

    migration.migrate_user_data()
    migration.migrate_user_data()

    assert not source.exists()
    assert destination.read_text() == "ROOT_PASSWORD=legacy\nMIGRATION_TEST_VALUE=keep\n"
    assert destination.stat().st_mode & 0o777 == 0o600


def test_existing_dotenv_wins_without_discarding_legacy_file(env_paths, capsys):
    source, destination = env_paths
    source.write_text("ROOT_PASSWORD=old-secret\n")
    destination.write_text("ROOT_PASSWORD=current-secret\n")

    migration.migrate_user_data()
    migration.migrate_user_data()

    assert source.read_text() == "ROOT_PASSWORD=old-secret\n"
    assert destination.read_text() == "ROOT_PASSWORD=current-secret\n"
    output = capsys.readouterr().out
    assert ".env" in output
    assert "old-secret" not in output
    assert "current-secret" not in output


@pytest.mark.parametrize("layout", ["root-link", "usr-link", "hardlink"])
def test_dotenv_aliases_are_left_intact(env_paths, layout):
    source, destination = env_paths
    if layout == "root-link":
        destination.write_text("MIGRATION_TEST_VALUE=keep\n")
        source.symlink_to("usr/.env")
    else:
        source.write_text("MIGRATION_TEST_VALUE=keep\n")
        if layout == "usr-link":
            destination.symlink_to("../.env")
        else:
            os.link(source, destination)

    migration.migrate_user_data()
    migration.migrate_user_data()

    assert source.read_text() == destination.read_text() == "MIGRATION_TEST_VALUE=keep\n"
    assert os.path.samefile(source, destination)
    assert source.is_symlink() == (layout == "root-link")
    assert destination.is_symlink() == (layout == "usr-link")


@pytest.mark.parametrize("absolute", [False, True])
@pytest.mark.parametrize("indirect", [False, True])
@pytest.mark.parametrize("linked_usr", [False, True])
def test_legacy_symlink_keeps_following_external_configuration(env_paths, absolute, indirect, linked_usr):
    source, destination = env_paths
    if linked_usr:
        data = source.parent / "data/config"
        data.parent.mkdir()
        destination.parent.rename(data)
        destination.parent.symlink_to(data, target_is_directory=True)
    external = source.parent / "external.env"
    external.write_text("MIGRATION_TEST_VALUE=keep\n")
    external.chmod(0o600)
    target = external
    if indirect:
        target = source.parent / "current.env"
        target.symlink_to(external.name)
    source.symlink_to(target if absolute else target.name)

    migration.migrate_user_data()
    migration.migrate_user_data()

    assert source.is_symlink()
    assert external.read_text() == destination.read_text() == "MIGRATION_TEST_VALUE=keep\n"
    assert destination.is_symlink()
    assert os.path.samefile(source, destination)
    assert os.path.isabs(os.readlink(destination)) == absolute
    assert destination.stat().st_mode & 0o777 == 0o600

    replacement = source.parent / "replacement.env"
    replacement.write_text("MIGRATION_TEST_VALUE=updated\n")
    replacement.replace(target)
    migration.migrate_user_data()

    assert source.read_text() == destination.read_text() == "MIGRATION_TEST_VALUE=updated\n"


def test_symlink_creation_failure_preserves_original(env_paths, monkeypatch):
    source, destination = env_paths
    external = source.parent / "external.env"
    external.write_text("MIGRATION_TEST_VALUE=keep\n")
    source.symlink_to("external.env")

    def fail_symlink(src, dst):
        raise OSError("symlink creation failed")

    monkeypatch.setattr(migration.os, "symlink", fail_symlink)
    with pytest.raises(OSError, match="symlink creation failed"):
        migration.migrate_user_data()

    assert source.is_symlink()
    assert source.read_text() == "MIGRATION_TEST_VALUE=keep\n"
    assert list(destination.parent.iterdir()) == []


def test_symlink_migration_does_not_overwrite_a_concurrent_destination(env_paths, monkeypatch):
    source, destination = env_paths
    external = source.parent / "external.env"
    external.write_text("MIGRATION_TEST_VALUE=legacy\n")
    source.symlink_to("external.env")
    symlink = os.symlink

    def create_destination(src, dst):
        destination.write_text("MIGRATION_TEST_VALUE=current\n")
        symlink(src, dst)

    monkeypatch.setattr(migration.os, "symlink", create_destination)
    with pytest.raises(FileExistsError):
        migration.migrate_user_data()

    assert source.is_symlink()
    assert source.read_text() == "MIGRATION_TEST_VALUE=legacy\n"
    assert destination.read_text() == "MIGRATION_TEST_VALUE=current\n"
    assert list(destination.parent.iterdir()) == [destination]


@pytest.mark.parametrize("invalid_path", ["source", "destination"])
def test_broken_dotenv_symlink_stops_migration_without_replacing_files(env_paths, invalid_path):
    source, destination = env_paths
    broken = source if invalid_path == "source" else destination
    broken.symlink_to("missing.env")
    if invalid_path == "destination":
        source.write_text("MIGRATION_TEST_VALUE=keep\n")

    with pytest.raises(ValueError, match=r"\.env"):
        migration.migrate_user_data()

    assert broken.is_symlink()
    assert not broken.exists()
    if invalid_path == "destination":
        assert source.read_text() == "MIGRATION_TEST_VALUE=keep\n"
    else:
        assert not destination.exists()


def test_prepare_migrates_and_loads_legacy_env_before_writing_root_password(env_paths, monkeypatch):
    source, destination = env_paths
    source.write_text("ROOT_PASSWORD=legacy\nMIGRATION_TEST_VALUE=keep\n")
    monkeypatch.delenv("ROOT_PASSWORD", raising=False)
    monkeypatch.delenv("MIGRATION_TEST_VALUE", raising=False)
    monkeypatch.setattr(sys, "argv", ["prepare.py"])
    monkeypatch.setattr(runtime, "initialize", lambda: None)
    passwords = []

    def set_root_password(password):
        passwords.append(password)
        dotenv.save_dotenv_value(dotenv.KEY_ROOT_PASSWORD, password)

    monkeypatch.setattr(settings, "set_root_password", set_root_password)
    prepare = Path(__file__).resolve().parents[1] / "prepare.py"
    runpy.run_path(str(prepare), run_name="__main__")
    migration.migrate_user_data()

    assert passwords == ["legacy"]
    assert "MIGRATION_TEST_VALUE=keep" in destination.read_text()
    assert os.environ["MIGRATION_TEST_VALUE"] == "keep"


@pytest.mark.parametrize("invalid_path", ["source", "destination"])
def test_prepare_stops_before_password_writes_when_dotenv_is_invalid(env_paths, monkeypatch, invalid_path):
    source, destination = env_paths
    broken = source if invalid_path == "source" else destination
    broken.symlink_to("missing.env")
    if invalid_path == "destination":
        source.write_text("ROOT_PASSWORD=legacy\nAUTH_LOGIN=example\nAUTH_PASSWORD=dummy\n")
    monkeypatch.setattr(sys, "argv", ["prepare.py"])
    monkeypatch.setattr(runtime, "initialize", lambda: None)
    passwords = []
    monkeypatch.setattr(settings, "set_root_password", passwords.append)
    prepare = Path(__file__).resolve().parents[1] / "prepare.py"

    with pytest.raises(ValueError, match=r"\.env"):
        runpy.run_path(str(prepare), run_name="__main__")

    assert passwords == []
    assert broken.is_symlink()
    assert not broken.exists()
    if invalid_path == "destination":
        assert source.read_text() == "ROOT_PASSWORD=legacy\nAUTH_LOGIN=example\nAUTH_PASSWORD=dummy\n"
    else:
        assert not destination.exists()
