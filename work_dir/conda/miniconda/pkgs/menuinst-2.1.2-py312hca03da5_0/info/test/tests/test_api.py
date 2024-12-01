""""""

import json
import os
import plistlib
import shlex
import subprocess
import sys
import warnings
from pathlib import Path
from tempfile import NamedTemporaryFile, mkdtemp
from time import sleep, time
from typing import Iterable, Tuple
from xml.etree import ElementTree

import pytest
from conftest import DATA, PLATFORM

from menuinst.api import install, remove
from menuinst.platforms.osx import _lsregister
from menuinst.utils import DEFAULT_PREFIX, logged_run, slugify


def _poll_for_file_contents(path, timeout=10):
    t0 = time()
    while not os.path.isfile(path):
        sleep(1)
        if time() >= t0 + timeout / 2:
            raise RuntimeError(f"Timeout. File '{path}' was not created!")

    out = ""
    while not (out := Path(path).read_text()):
        sleep(1)
        if time() >= t0 + timeout:
            raise RuntimeError(f"Timeout. File '{path}' was empty!")
    return out


def check_output_from_shortcut(
    delete_files,
    json_path,
    remove_after=True,
    expected_output=None,
    action="run_shortcut",
    file_to_open=None,
    url_to_open=None,
) -> Tuple[Path, Iterable[Path], str]:
    assert action in ("run_shortcut", "open_file", "open_url", None)

    output = None
    output_file = None
    abs_json_path = DATA / "jsons" / json_path
    contents = abs_json_path.read_text()
    if "__OUTPUT_FILE__" in contents:
        with NamedTemporaryFile(suffix=json_path, mode="w", delete=False) as tmp:
            output_file = str(Path(tmp.name).resolve()) + ".out"
            contents = contents.replace("__OUTPUT_FILE__", output_file.replace("\\", "\\\\"))
            tmp.write(contents)
        abs_json_path = tmp.name
        delete_files.append(abs_json_path)

    tmp_base_path = mkdtemp()
    delete_files.append(tmp_base_path)
    (Path(tmp_base_path) / ".nonadmin").touch()
    paths = install(abs_json_path, base_prefix=tmp_base_path)
    try:
        if action == "run_shortcut":
            if PLATFORM == "win":
                lnk = next(p for p in paths if p.suffix == ".lnk")
                assert lnk.is_file()
                os.startfile(lnk)
                output = _poll_for_file_contents(output_file)
            else:
                if PLATFORM == "linux":
                    desktop = next(p for p in paths if p.suffix == ".desktop")
                    with open(desktop) as f:
                        for line in f:
                            if line.startswith("Exec="):
                                cmd = shlex.split(line.split("=", 1)[1].strip())
                                break
                        else:
                            raise ValueError("Didn't find Exec line")
                elif PLATFORM == "osx":
                    app_location = paths[0]
                    executable = next(
                        p
                        for p in (app_location / "Contents" / "MacOS").iterdir()
                        if not p.name.endswith("-script")
                    )
                    cmd = [str(executable)]
                process = logged_run(cmd, check=True)
                output = process.stdout
        elif action is not None:
            if action == "open_file":
                assert file_to_open is not None
                with NamedTemporaryFile(suffix=file_to_open, delete=False) as f:
                    # file cannot be empty; otherwise mimetype detection fails on Linux
                    f.write(b"1234")
                delete_files.append(f.name)
                arg = f.name
            elif action == "open_url":
                assert url_to_open is not None
                arg = url_to_open
            app_location = paths[0]
            cmd = {
                "linux": ["xdg-open"],
                "osx": ["open"],
                "win": ["cmd", "/C", "start"],
            }[PLATFORM]
            process = logged_run([*cmd, arg], check=True)
            output = _poll_for_file_contents(output_file)
    finally:
        if paths:
            delete_files += list(paths)
        if remove_after:
            remove(abs_json_path, base_prefix=tmp_base_path)
        if PLATFORM == "osx" and action in ("open_file", "open_url"):
            _lsregister(
                "-kill",
                "-r",
                "-domain",
                "local",
                "-domain",
                "user",
                "-domain",
                "system",
            )
            sleep(5)
            if "menuinst" in _lsregister("-dump", log=False).stdout:
                warnings.warn(
                    "menuinst still registered with LaunchServices! "
                    "This usually fixes itself after a couple minutes. "
                    "Run '/System/Library/Frameworks/CoreServices.framework/Frameworks/"
                    "LaunchServices.framework/Support/lsregister -dump | grep menuinst' "
                    "to double check."
                )

    if expected_output is not None:
        assert output.strip() == expected_output

    return abs_json_path, paths, tmp_base_path, output


def test_install_prefix(delete_files):
    check_output_from_shortcut(delete_files, "sys-prefix.json", expected_output=sys.prefix)


def test_install_remove(tmp_path, delete_files):
    metadata = DATA / "jsons" / "sys-prefix.json"
    (tmp_path / ".nonadmin").touch()
    paths = set(install(metadata, target_prefix=tmp_path, base_prefix=tmp_path, _mode="user"))
    delete_files.extend(paths)
    files_found = set(filter(lambda x: x.exists(), paths))
    assert files_found == paths
    if PLATFORM != "osx":
        metadata_2 = json.loads(metadata.read_text())
        metadata_2["menu_items"][0]["name"] = "Sys.Prefix.2"
        paths_2 = set(
            install(metadata_2, target_prefix=tmp_path, base_prefix=tmp_path, _mode="user")
        )
        delete_files.extend(paths_2)
        files_found = set(filter(lambda x: x.exists(), paths_2.union(paths)))
        assert files_found == paths_2.union(paths)
        remove(metadata_2, target_prefix=tmp_path, base_prefix=tmp_path, _mode="user")
        files_found = set(filter(lambda x: x.exists(), paths_2.union(paths)))
        assert files_found == paths
    remove(metadata, target_prefix=tmp_path, base_prefix=tmp_path, _mode="user")
    files_found = set(filter(lambda x: x.exists(), paths))
    assert files_found == set()


def test_overwrite_existing_shortcuts(delete_files, caplog):
    """Test that overwriting shortcuts works without errors by running installation twice."""
    check_output_from_shortcut(
        delete_files,
        "precommands.json",
        remove_after=False,
    )
    if PLATFORM == "osx":
        with pytest.raises(RuntimeError):
            check_output_from_shortcut(
                delete_files,
                "precommands.json",
                remove_after=True,
            )
    else:
        caplog.clear()
        check_output_from_shortcut(
            delete_files,
            "precommands.json",
            remove_after=True,
        )
        assert any(line.startswith("Overwriting existing") for line in caplog.messages)


@pytest.mark.skipif(PLATFORM == "osx", reason="No menu names on MacOS")
def test_placeholders_in_menu_name(delete_files):
    _, paths, tmp_base_path, _ = check_output_from_shortcut(
        delete_files,
        "sys-prefix.json",
        expected_output=sys.prefix,
        remove_after=False,
    )
    if PLATFORM == "win":
        for path in paths:
            if path.suffix == ".lnk" and "Start Menu" in path.parts:
                assert path.parent.name == f"Sys.Prefix {Path(tmp_base_path).name}"
                break
        else:
            raise AssertionError("Didn't find Start Menu")
    elif PLATFORM == "linux":
        config_directory = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser()
        desktop_directory = (
            Path(os.environ.get("XDG_DATA_HOME", "~/.local/share")).expanduser()
            / "desktop-directories"
        )
        menu_config_location = config_directory / "menus" / "applications.menu"
        rendered_name = f"Sys.Prefix {Path(tmp_base_path).name}"
        slugified_name = slugify(rendered_name)

        entry_file = desktop_directory / f"{slugified_name}.directory"
        assert entry_file.exists()
        entry = entry_file.read_text().splitlines()
        assert f"Name={rendered_name}" in entry

        tree = ElementTree.parse(menu_config_location)
        root = tree.getroot()
        assert rendered_name in [elt.text for elt in root.findall("Menu/Name")]
        assert f"{slugified_name}.directory" in [
            elt.text for elt in root.findall("Menu/Directory")
        ]
        assert rendered_name in [elt.text for elt in root.findall("Menu/Include/Category")]


def test_precommands(delete_files):
    check_output_from_shortcut(
        delete_files, "precommands.json", expected_output="rhododendron and bees"
    )


@pytest.mark.skipif(PLATFORM != "osx", reason="macOS only")
def test_entitlements(delete_files):
    json_path, paths, *_ = check_output_from_shortcut(
        delete_files, "entitlements.json", remove_after=False, expected_output="entitlements"
    )
    # verify signature
    app_dir = next(p for p in paths if p.name.endswith(".app"))
    subprocess.check_call(["/usr/bin/codesign", "--verbose", "--verify", str(app_dir)])

    launcher = next(
        p for p in (app_dir / "Contents" / "MacOS").iterdir() if not p.name.endswith("-script")
    )
    subprocess.check_call(["/usr/bin/codesign", "--verbose", "--verify", str(launcher)])

    for path in app_dir.rglob("Info.plist"):
        plist = plistlib.loads(path.read_bytes())
        assert plist
        assert "entitlements" not in plist
        break
    else:
        raise AssertionError("Didn't find Info.plist")

    for path in app_dir.rglob("Entitlements.plist"):
        plist = plistlib.loads(path.read_bytes())
        assert plist
        break
    else:
        raise AssertionError("Didn't find Entitlements.plist")

    remove(json_path)


@pytest.mark.skipif(PLATFORM != "osx", reason="macOS only")
def test_no_entitlements_no_signature(delete_files):
    json_path, paths, *_ = check_output_from_shortcut(
        delete_files, "sys-prefix.json", remove_after=False, expected_output=sys.prefix
    )
    app_dir = next(p for p in paths if p.name.endswith(".app"))
    launcher = next(
        p for p in (app_dir / "Contents" / "MacOS").iterdir() if not p.name.endswith("-script")
    )
    with pytest.raises(subprocess.CalledProcessError):
        subprocess.check_call(["/usr/bin/codesign", "--verbose", "--verify", str(app_dir)])
    with pytest.raises(subprocess.CalledProcessError):
        subprocess.check_call(["/usr/bin/codesign", "--verbose", "--verify", str(launcher)])
    remove(json_path)


@pytest.mark.skipif(PLATFORM != "osx", reason="macOS only")
def test_info_plist(delete_files):
    json_path, paths, *_ = check_output_from_shortcut(
        delete_files, "entitlements.json", remove_after=False, expected_output="entitlements"
    )
    app_dir = next(p for p in paths if p.name.endswith(".app"))

    for path in app_dir.rglob("Info.plist"):
        plist = plistlib.loads(path.read_bytes())
        assert plist
        break
    else:
        raise AssertionError("Didn't find file")

    assert plist["LSEnvironment"]["example_var"] == "example_value"

    remove(json_path)


@pytest.mark.skipif(PLATFORM != "osx", reason="macOS only")
def test_osx_symlinks(delete_files):
    json_path, paths, _, output = check_output_from_shortcut(
        delete_files, "osx_symlinks.json", remove_after=False
    )
    app_dir = next(p for p in paths if p.name.endswith(".app"))
    symlinked_python = app_dir / "Contents" / "Resources" / "python"
    assert output.strip() == str(symlinked_python)
    assert symlinked_python.resolve() == (Path(DEFAULT_PREFIX) / "bin" / "python").resolve()
    remove(json_path)


def _dump_ls_services():
    lsservicesplist = Path(
        os.environ["HOME"],
        "Library/Preferences/com.apple.LaunchServices/com.apple.launchservices.secure.plist",
    )
    plist = plistlib.loads(lsservicesplist.read_bytes())
    print(json.dumps(plist, indent=2))


@pytest.mark.skipif("CI" not in os.environ, reason="Only run on CI. Export CI=1 to run locally.")
def test_file_type_association(delete_files):
    test_file = "test.menuinst"
    *_, output = check_output_from_shortcut(
        delete_files,
        "file_types.json",
        action="open_file",
        file_to_open=test_file,
    )
    assert output.strip().endswith(test_file)


@pytest.mark.skipif(sys.platform != "darwin", reason="Only run on macOS")
@pytest.mark.skipif("CI" not in os.environ, reason="Only run on CI. Export CI=1 to run locally.")
def test_file_type_association_no_event_handler(delete_files, request):
    test_file = "test.menuinst-no-event-handler"
    abs_json_path, paths, tmp_base_path, _ = check_output_from_shortcut(
        delete_files,
        "file_types_no_event_handler.json",
        action=None,
        file_to_open=test_file,
        remove_after=False,
    )
    request.addfinalizer(lambda: remove(abs_json_path, base_prefix=tmp_base_path))
    app_dir = next(p for p in paths if p.name.endswith(".app"))
    info = app_dir / "Contents" / "Info.plist"
    plist = plistlib.loads(info.read_bytes())
    cf_bundle_type_name = "org.conda.menuinst.filetype-example-no-event-handler"
    assert plist["CFBundleDocumentTypes"][0]["CFBundleTypeName"] == cf_bundle_type_name


@pytest.mark.skipif("CI" not in os.environ, reason="Only run on CI. Export CI=1 to run locally.")
def test_url_protocol_association(delete_files):
    url = "menuinst://test/"
    check_output_from_shortcut(
        delete_files,
        "url_protocols.json",
        action="open_url",
        url_to_open=url,
        expected_output=url,
    )


@pytest.mark.skipif(PLATFORM != "win", reason="Windows only")
def test_windows_terminal_profiles(tmp_path, run_as_user):
    settings_file = Path(
        tmp_path, "localappdata", "Microsoft", "Windows Terminal", "settings.json"
    )
    settings_file.parent.mkdir(parents=True)
    (tmp_path / ".nonadmin").touch()
    metadata_file = DATA / "jsons" / "windows-terminal.json"
    install(metadata_file, target_prefix=tmp_path, base_prefix=tmp_path)
    try:
        settings = json.loads(settings_file.read_text())
        profiles = {
            profile.get("name", ""): profile.get("commandline", "")
            for profile in settings.get("profiles", {}).get("list", [])
        }
        assert profiles.get("A Terminal") == "testcommand_a.exe"
        assert "B" not in profiles
    except Exception as exc:
        remove(metadata_file, target_prefix=tmp_path, base_prefix=tmp_path)
        raise exc
    else:
        remove(metadata_file, target_prefix=tmp_path, base_prefix=tmp_path)


@pytest.mark.parametrize("target_env_is_base", (True, False))
def test_name_dictionary(target_env_is_base):
    tmp_base_path = mkdtemp()
    tmp_target_path = tmp_base_path if target_env_is_base else mkdtemp()
    (Path(tmp_base_path) / ".nonadmin").touch()
    if not target_env_is_base:
        (Path(tmp_target_path) / ".nonadmin").touch()
    abs_json_path = DATA / "jsons" / "menu-name.json"
    menu_items = install(abs_json_path, target_prefix=tmp_target_path, base_prefix=tmp_base_path)
    try:
        if PLATFORM == "linux":
            expected = {
                "package_a" if target_env_is_base else "package_a-not-in-base",
                "package_b",
                "package",
            }
        else:
            expected = {
                "A" if target_env_is_base else "A_not_in_base",
                "B",
            }
            if PLATFORM == "win":
                expected.update(["Package"])
        item_names = {item.stem for item in menu_items}
        assert item_names == expected
    finally:
        remove(abs_json_path, target_prefix=tmp_target_path, base_prefix=tmp_base_path)


def test_vars_in_working_dir(tmp_path, monkeypatch, delete_files):
    if PLATFORM == "win":
        expected_directory = Path(os.environ["TEMP"], "working_dir_test")
    elif PLATFORM == "osx":
        expected_directory = Path(os.environ["TMPDIR"], "working_dir_test")
    else:
        # Linux often does not have an environment variable for the tmp directory
        monkeypatch.setenv("TMP", "/tmp")
        expected_directory = Path("/tmp/working_dir_test")
    delete_files.append(expected_directory)
    datafile = str(DATA / "jsons" / "working-dir.json")
    try:
        install(datafile, base_prefix=tmp_path, target_prefix=tmp_path)
        assert expected_directory.exists()
    finally:
        remove(datafile, base_prefix=tmp_path, target_prefix=tmp_path)
