"""
Integration tests with conda
"""

import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from subprocess import check_output
from tempfile import NamedTemporaryFile

import pytest
from conda.models.version import VersionOrder
from conda.testing.integration import run_command
from conftest import BASE_PREFIX, DATA, PLATFORM

from menuinst._schema import validate
from menuinst.platforms import Menu, MenuItem

ENV_VARS = {
    k: v
    for (k, v) in os.environ.copy().items()
    if not k.startswith(("CONDA", "_CONDA", "MAMBA", "_MAMBA"))
}
ENV_VARS["CONDA_VERBOSITY"] = "3"


@contextmanager
def new_environment(tmpdir, *packages):
    try:
        prefix = str(tmpdir / "prefix")
        print("--- CREATING", prefix, "---")
        stdout, stderr, retcode = run_command(
            "create", prefix, "-y", "--offline", *[str(p) for p in packages]
        )
        assert not retcode
        for stream in (stdout, stderr):
            if "menuinst Exception" in stream:
                raise RuntimeError(
                    f"Creation command exited with 0 but stdout contained exception:\n{stream}"
                )

        yield prefix
    finally:
        print("--- REMOVING", prefix, "---")
        stdout, stderr, retcode = run_command("remove", prefix, "--offline", "--all")
        assert not retcode
        for stream in (stdout, stderr):
            if "menuinst Exception" in stream:
                raise RuntimeError(
                    f"Deletion Command exited with 0 but stdout contained exception:\n{stream}"
                )


@contextmanager
def install_package_1(tmpdir):
    """
    This package is shipped with the test data and contains two menu items.

    Both will echo the `CONDA_PREFIX` environment variable. However, the
    first one preactivates the environment, while the second does not. This
    means that the first shortcut will successfully echo the prefix path,
    while the second one will be empty (Windows) or "N/A" (Unix).
    """
    with new_environment(tmpdir, DATA / "pkgs" / "noarch" / "package_1-0.1-0.tar.bz2") as prefix:
        menu_file = Path(prefix) / "Menu" / "package_1.json"
        with open(menu_file) as f:
            meta = json.load(f)
            assert len(meta["menu_items"]) == 2
        assert menu_file.is_file()
        yield prefix, menu_file
    assert not menu_file.is_file()


def test_conda_recent_enough():
    data = json.loads(check_output([sys.executable, "-I", "-m", "conda", "info", "--json"]))
    assert VersionOrder(data["conda_version"]) >= VersionOrder("4.12a0")


@pytest.mark.skipif(PLATFORM != "linux", reason="Linux only")
def test_package_1_linux(tmpdir):
    applications_menu = Path(tmpdir) / "config" / "menus" / "applications.menu"
    if applications_menu.is_file():
        original_xml = applications_menu.read_text()
    else:
        original_xml = None
    with install_package_1(tmpdir) as (prefix, menu_file):
        meta = validate(menu_file)
        menu = Menu(meta.menu_name, str(prefix), BASE_PREFIX)
        menu_items = [item.dict() for item in meta.menu_items]
        items = [menu]

        # First case, activation is on, output should be the prefix path
        # Second case, activation is off, output should be N/A
        for item, expected_output in zip(menu_items, (str(prefix), "N/A")):
            item = MenuItem(menu, item)
            items.append(item)
            command = item._command()
            print(command)
            print("-----")
            output = check_output(command, shell=True, universal_newlines=True, env=ENV_VARS)
            assert output.strip() == expected_output

    assert not Path(prefix).exists()
    for item in items:
        for path in item._paths():
            assert not path.exists()

    if original_xml:
        assert original_xml == applications_menu.read_text()


@pytest.mark.skipif(PLATFORM != "osx", reason="MacOS only")
def test_package_1_osx(tmpdir):
    with install_package_1(tmpdir) as (prefix, menu_file):
        meta = validate(menu_file)
        menu_items = [item.dict() for item in meta.menu_items]
        menu = Menu(meta.menu_name, str(prefix), BASE_PREFIX)
        items = [menu]
        # First case, activation is on, output should be the prefix path
        # Second case, activation is off, output should be N/A
        for item, expected_output in zip(menu_items, (str(prefix), "N/A")):
            item = MenuItem(menu, item)
            items.append(item)
            script = item._write_script(
                script_path=NamedTemporaryFile(suffix=".sh", delete=False).name
            )
            print(item._command())
            print("-------------")
            output = check_output(["bash", script], universal_newlines=True, env=ENV_VARS)
            Path(script).unlink()
            assert output.strip() == expected_output

    assert not Path(prefix).exists()
    for item in items:
        for path in item._paths():
            assert not path.exists()


@pytest.mark.skipif(PLATFORM != "win", reason="Windows only")
def test_package_1_windows(tmpdir):
    with install_package_1(tmpdir) as (prefix, menu_file):
        meta = validate(menu_file)
        menu = Menu(meta.menu_name, str(prefix), BASE_PREFIX)
        menu_items = [item.dict() for item in meta.menu_items]
        items = [menu]
        # First case, activation is on, output should be the prefix path
        # Second case, activation is off, output should be empty
        for item, expected_output in zip(menu_items, (str(prefix), "!CONDA_PREFIX!")):
            item = MenuItem(menu, item)
            items.append(item)
            script = item._write_script(
                script_path=NamedTemporaryFile(suffix=".bat", delete=False).name
            )
            print(item._command())
            print("-------------")
            output = check_output(
                ["cmd.exe", "/C", f"conda deactivate && conda deactivate && {script}"],
                universal_newlines=True,
                env=ENV_VARS,
            )
            Path(script).unlink()
            output = output.replace("ECHO is off.", "")
            assert output.splitlines()[0].strip() == expected_output

    assert not Path(prefix).exists()
    for item in items:
        for path in item._paths():
            assert not path.exists()
