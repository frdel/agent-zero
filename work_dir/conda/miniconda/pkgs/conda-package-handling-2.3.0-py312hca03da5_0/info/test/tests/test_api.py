import json
import os
import pathlib
import platform
import shutil
import sys
import tarfile
import time
import zipfile
from datetime import datetime
from tempfile import TemporaryDirectory

import pytest

import conda_package_handling
import conda_package_handling.tarball
from conda_package_handling import api, exceptions

this_dir = os.path.dirname(__file__)
data_dir = os.path.join(this_dir, "data")
version_file = pathlib.Path(this_dir).parent / "src" / "conda_package_handling" / "__init__.py"
test_package_name = "mock-2.0.0-py37_1000"
test_package_name_2 = "cph_test_data-0.0.1-0"


@pytest.mark.skipif(
    bool(os.environ.get("GITHUB_ACTIONS", False)), reason="Fails on GitHub Actions"
)
@pytest.mark.skipif(not version_file.exists(), reason=f"Could not find {version_file}")
def test_correct_version():
    """
    Prevent accidentally running tests against a globally installed different version.
    """
    assert conda_package_handling.__version__ in version_file.read_text()


def test_api_extract_tarball_implicit_path(testing_workdir):
    tarfile = os.path.join(data_dir, test_package_name + ".tar.bz2")
    local_tarfile = os.path.join(testing_workdir, os.path.basename(tarfile))
    shutil.copy2(tarfile, local_tarfile)
    api.extract(local_tarfile)
    assert os.path.isfile(os.path.join(testing_workdir, test_package_name, "info", "index.json"))


def test_api_tarball_details(testing_workdir):
    tarfile = os.path.join(data_dir, test_package_name + ".tar.bz2")
    results = api.get_pkg_details(tarfile)
    assert results["size"] == 106576
    assert results["md5"] == "0f9cce120a73803a70abb14bd4d4900b"
    assert results["sha256"] == "34c659b0fdc53d28ae721fd5717446fb8abebb1016794bd61e25937853f4c29c"


def test_api_conda_v2_details(testing_workdir):
    condafile = os.path.join(data_dir, test_package_name + ".conda")
    results = api.get_pkg_details(condafile)
    assert results["size"] == 113421
    assert results["sha256"] == "181ec44eb7b06ebb833eae845bcc466ad96474be1f33ee55cab7ac1b0fdbbfa3"
    assert results["md5"] == "23c226430e35a3bd994db6c36b9ac8ae"


def test_api_extract_tarball_explicit_path(testing_workdir):
    tarfile = os.path.join(data_dir, test_package_name + ".tar.bz2")
    local_tarfile = os.path.join(testing_workdir, os.path.basename(tarfile))
    shutil.copy2(tarfile, local_tarfile)

    api.extract(local_tarfile, "manual_path")
    assert os.path.isfile(os.path.join(testing_workdir, "manual_path", "info", "index.json"))


def test_api_extract_conda_v2_implicit_path(testing_workdir):
    condafile = os.path.join(data_dir, test_package_name + ".conda")
    local_condafile = os.path.join(testing_workdir, os.path.basename(condafile))
    shutil.copy2(condafile, local_condafile)
    api.extract(local_condafile)
    assert os.path.isfile(os.path.join(testing_workdir, test_package_name, "info", "index.json"))


def test_api_extract_conda_v2_no_destdir_relative_path(testing_workdir):
    cwd = os.getcwd()
    os.chdir(testing_workdir)
    try:
        condafile = os.path.join(data_dir, test_package_name + ".conda")
        local_condafile = os.path.join(testing_workdir, os.path.basename(condafile))
        shutil.copy2(condafile, local_condafile)

        condafile = os.path.basename(local_condafile)
        assert os.path.exists(condafile)
        # cli passes dest=None, prefix=None
        api.extract(condafile, None, prefix=None)
    finally:
        os.chdir(cwd)


def test_api_extract_conda_v2_explicit_path(testing_workdir):
    condafile = os.path.join(data_dir, test_package_name + ".conda")
    local_condafile = os.path.join(testing_workdir, os.path.basename(condafile))
    shutil.copy2(condafile, local_condafile)

    api.extract(condafile, "manual_path")
    assert os.path.isfile(os.path.join(testing_workdir, "manual_path", "info", "index.json"))


def test_api_extract_conda_v2_explicit_path_prefix(testing_workdir):
    tarfile = os.path.join(data_dir, test_package_name + ".conda")
    api.extract(tarfile, prefix=os.path.join(testing_workdir, "folder"))
    assert os.path.isfile(
        os.path.join(testing_workdir, "folder", test_package_name, "info", "index.json")
    )

    api.extract(tarfile, dest_dir="steve", prefix=os.path.join(testing_workdir, "folder"))
    assert os.path.isfile(os.path.join(testing_workdir, "folder", "steve", "info", "index.json"))


def test_api_extract_dest_dir_and_prefix_both_abs_raises():
    tarfile = os.path.join(data_dir, test_package_name + ".conda")
    with pytest.raises(ValueError):
        api.extract(tarfile, prefix=os.path.dirname(tarfile), dest_dir=os.path.dirname(tarfile))


def test_api_extract_info_conda_v2(testing_workdir):
    condafile = os.path.join(data_dir, test_package_name + ".conda")
    local_condafile = os.path.join(testing_workdir, os.path.basename(condafile))
    shutil.copy2(condafile, local_condafile)
    api.extract(local_condafile, "manual_path", components="info")
    assert os.path.isfile(os.path.join(testing_workdir, "manual_path", "info", "index.json"))
    assert not os.path.isdir(os.path.join(testing_workdir, "manual_path", "lib"))


def check_conda_v2_metadata(condafile):
    with zipfile.ZipFile(condafile) as zf:
        d = json.loads(zf.read("metadata.json"))
    assert d["conda_pkg_format_version"] == 2


def test_api_transmute_tarball_to_conda_v2(testing_workdir):
    tarfile = os.path.join(data_dir, test_package_name + ".tar.bz2")
    # lower compress level makes the test run much faster, even 15 is much
    # better than 22
    errors = api.transmute(tarfile, ".conda", testing_workdir, zstd_compress_level=3)
    assert not errors
    condafile = os.path.join(testing_workdir, test_package_name + ".conda")
    assert os.path.isfile(condafile)
    check_conda_v2_metadata(condafile)


def test_api_transmute_tarball_info_sorts_first(testing_workdir):
    test_packages = [test_package_name]
    test_packages_with_symlinks = [test_package_name_2]
    if sys.platform != "win32":
        test_packages += test_packages_with_symlinks
    for test_package in test_packages:
        test_file = os.path.join(data_dir, test_package + ".tar.bz2")

        # transmute/convert doesn't re-sort files; extract to folder.
        api.extract(test_file, testing_workdir)
        out_fn = os.path.join(testing_workdir, test_package + ".tar.bz2")
        out = api.create(testing_workdir, None, out_fn)
        assert out == out_fn

        # info must be first
        with tarfile.open(out_fn, "r:bz2") as repacked:
            info_seen = False
            not_info_seen = False
            for member in repacked:
                if member.name.startswith("info"):
                    assert (
                        not_info_seen is False
                    ), f"{test_package} package info/ must sort first, "
                    f"but {[m.name for m in repacked.getmembers()]}"
                    info_seen = True
                else:
                    not_info_seen = True
            assert info_seen, "package had no info/ files"


@pytest.mark.skipif(sys.platform == "win32", reason="windows and symlinks are not great")
def test_api_transmute_to_conda_v2_contents(testing_workdir):
    def _walk(path):
        for entry in os.scandir(path):
            if entry.is_dir(follow_symlinks=False):
                yield from _walk(entry.path)
                continue
            yield entry

    tar_path = os.path.join(data_dir, test_package_name_2 + ".tar.bz2")
    conda_path = os.path.join(testing_workdir, test_package_name_2 + ".conda")
    api.transmute(tar_path, ".conda", testing_workdir, zstd_compress_level=3)

    # Verify original contents were all put in the right place
    pkg_tarbz2 = tarfile.open(tar_path, mode="r:bz2")
    info_items = [item for item in pkg_tarbz2.getmembers() if item.path.startswith("info/")]
    pkg_items = [item for item in pkg_tarbz2.getmembers() if not item.path.startswith("info/")]

    errors = []
    for component, expected in (("info", info_items), ("pkg", pkg_items)):
        with TemporaryDirectory() as root:
            api.extract(conda_path, root, components=component)

            contents = {
                os.path.relpath(entry.path, root): {
                    "is_symlink": entry.is_symlink(),
                    "target": os.readlink(entry.path) if entry.is_symlink() else None,
                }
                for entry in _walk(root)
            }

            for item in expected:
                if item.path not in contents:
                    errors.append(f"'{item.path}' not found in {component} contents")
                    continue

                ct = contents.pop(item.path)
                if item.issym():
                    if not ct["is_symlink"] or ct["target"] != item.linkname:
                        errors.append(
                            f"{item.name} -> {item.linkname} incorrect in {component} contents"
                        )
                elif not item.isfile():
                    # Raise an exception rather than appending to `errors`
                    # because getting to this point is an indication that our
                    # test data (i.e., .tar.bz2 package) is corrupt, rather
                    # than the `.transmute` function having problems (which is
                    # what `errors` is meant to track).  For context, conda
                    # packages should only contain regular files and symlinks.
                    raise ValueError(f"unexpected item '{item.path}' in test .tar.bz2")
            if contents:
                errors.append(f"extra files [{', '.join(contents)}] in {component} contents")
    assert not errors


def test_api_transmute_conda_v2_to_tarball(testing_workdir):
    condafile = os.path.join(data_dir, test_package_name + ".conda")
    outfile = pathlib.Path(testing_workdir, test_package_name + ".tar.bz2")
    # one quiet=True in the test suite for coverage
    api.transmute(condafile, ".tar.bz2", testing_workdir, quiet=True)
    assert outfile.is_file()

    # test that no-force keeps file, and force overwrites file
    for force in False, True:
        mtime = outfile.stat().st_mtime
        time.sleep(2 if platform.platform() == "Windows" else 0)
        api.transmute(condafile, ".tar.bz2", testing_workdir, force=force)
        mtime2 = outfile.stat().st_mtime
        assert (mtime2 == mtime) != force


def test_warning_when_bundling_no_metadata(testing_workdir):
    pass


@pytest.mark.skipif(sys.platform == "win32", reason="windows and symlinks are not great")
def test_create_package_with_uncommon_conditions_captures_all_content(testing_workdir):
    os.makedirs("src/a_folder")
    os.makedirs("src/empty_folder")
    os.makedirs("src/symlink_stuff")
    with open("src/a_folder/text_file", "w") as f:
        f.write("weee")
    open("src/empty_file", "w").close()
    os.link("src/a_folder/text_file", "src/a_folder/hardlink_to_text_file")
    os.symlink("../a_folder", "src/symlink_stuff/symlink_to_a")
    os.symlink("../empty_file", "src/symlink_stuff/symlink_to_empty_file")
    os.symlink("../a_folder/text_file", "src/symlink_stuff/symlink_to_text_file")

    with tarfile.open("pinkie.tar.bz2", "w:bz2") as tf:

        def add(source, target):
            tf.add(source, target, recursive=False)

        add("src/empty_folder", "empty_folder")
        add("src/empty_file", "empty_file")
        add("src/a_folder", "a_folder")
        add("src/a_folder/text_file", "a_folder/text_file")
        add("src/a_folder/hardlink_to_text_file", "a_folder/hardlink_to_text_file")
        add("src/symlink_stuff/symlink_to_a", "symlink_stuff/symlink_to_a")
        add(
            "src/symlink_stuff/symlink_to_empty_file",
            "symlink_stuff/symlink_to_empty_file",
        )
        add(
            "src/symlink_stuff/symlink_to_text_file",
            "symlink_stuff/symlink_to_text_file",
        )

    api.create("src", None, "thebrain.tar.bz2")

    # test against both archives created manually and those created by cph.
    # They should be equal in all ways.
    for fn in ("pinkie.tar.bz2", "thebrain.tar.bz2"):
        api.extract(fn)
        target_dir = fn[:-8]
        flist = [
            "empty_folder",
            "empty_file",
            "a_folder/text_file",
            "a_folder/hardlink_to_text_file",
            "symlink_stuff/symlink_to_a",
            "symlink_stuff/symlink_to_text_file",
            "symlink_stuff/symlink_to_empty_file",
        ]

        # no symlinks on windows
        if sys.platform != "win32":
            # not directly included but checked symlink
            flist.append("symlink_stuff/symlink_to_a/text_file")

        missing_content = []
        for f in flist:
            path_that_should_be_there = os.path.join(testing_workdir, target_dir, f)
            if not (
                os.path.exists(path_that_should_be_there)
                or os.path.lexists(path_that_should_be_there)  # noqa
            ):
                missing_content.append(f)
        if missing_content:
            print("missing files in output package")
            print(missing_content)
            sys.exit(1)

        # hardlinks should be preserved, but they're currently not with libarchive
        # hardlinked_file = os.path.join(testing_workdir, target_dir, 'a_folder/text_file')
        # stat = os.stat(hardlinked_file)
        # assert stat.st_nlink == 2

        hardlinked_file = os.path.join(testing_workdir, target_dir, "empty_file")
        stat = os.stat(hardlinked_file)
        if sys.platform != "win32":
            assert stat.st_nlink == 1


@pytest.mark.skipif(
    datetime.now() <= datetime(2020, 12, 1),
    reason="Don't understand why this doesn't behave.  Punt.",
)
def test_secure_refusal_to_extract_abs_paths(testing_workdir):
    with tarfile.open("pinkie.tar.bz2", "w:bz2") as tf:
        open("thebrain", "w").close()
        tf.add(os.path.join(testing_workdir, "thebrain"), "/naughty/abs_path")
        try:
            tf.getmember("/naughty/abs_path")
        except KeyError:
            pytest.skip("Tar implementation does not generate unsafe paths in archive.")

    with pytest.raises(api.InvalidArchiveError):
        api.extract("pinkie.tar.bz2")


def tests_secure_refusal_to_extract_dotdot(testing_workdir):
    with tarfile.open("pinkie.tar.bz2", "w:bz2") as tf:
        open("thebrain", "w").close()
        tf.add(os.path.join(testing_workdir, "thebrain"), "../naughty/abs_path")

    with pytest.raises(api.InvalidArchiveError):
        api.extract("pinkie.tar.bz2")


def test_api_bad_filename(testing_workdir):
    with pytest.raises(ValueError):
        api.extract("pinkie.rar", testing_workdir)


def test_details_bad_extension():
    with pytest.raises(ValueError):
        # TODO this function should not exist
        api.get_pkg_details("pinkie.rar")


def test_convert_bad_extension(testing_workdir):
    api._convert("pinkie.rar", ".conda", testing_workdir)


def test_convert_keyerror(tmpdir, mocker):
    tarfile = os.path.join(data_dir, test_package_name + ".tar.bz2")

    mocker.patch(
        "conda_package_streaming.transmute.transmute",
        side_effect=KeyboardInterrupt(),
    )

    # interrupted before ".conda" was created
    with pytest.raises(KeyboardInterrupt):
        api._convert(tarfile, ".conda", tmpdir)

    def create_file_and_raise(*args, **kwargs):
        out_fn = pathlib.Path(tmpdir, pathlib.Path(tarfile[: -len(".tar.bz2")] + ".conda").name)
        print("out fn", out_fn)
        out_fn.write_text("")
        raise KeyboardInterrupt()

    mocker.patch("conda_package_streaming.transmute.transmute", side_effect=create_file_and_raise)

    # interrupted after ".conda" was created
    with pytest.raises(KeyboardInterrupt):
        api._convert(tarfile, ".conda", tmpdir)


def test_create_filelist(tmpdir, mocker):
    # another bad API, tested for coverage
    filelist = pathlib.Path(tmpdir, "filelist.txt")
    filelist.write_text("\n".join(["filelist.txt", "anotherfile"]))

    # when looking for filelist-not-found.txt
    with pytest.raises(FileNotFoundError):
        api.create(str(tmpdir), "filelist-not-found.txt", str(tmpdir / "newconda.conda"))

    # when adding anotherfile
    with pytest.raises(FileNotFoundError):
        api.create(str(tmpdir), str(filelist), str(tmpdir / "newconda.conda"))

    # unrecognized target extension
    with pytest.raises(ValueError):
        api.create(str(tmpdir), str(filelist), str(tmpdir / "newpackage.rar"))

    def create_file_and_raise(prefix, file_list, out_fn, *args, **kwargs):
        pathlib.Path(prefix, out_fn).write_text("")
        raise KeyboardInterrupt()

    mocker.patch(
        "conda_package_handling.conda_fmt.CondaFormat_v2.create",
        side_effect=create_file_and_raise,
    )

    # failure inside inner create()
    with pytest.raises(KeyboardInterrupt):
        api.create(str(tmpdir), str(filelist), str(tmpdir / "newpackage.conda"))


def test_api_transmute_fail_validation(tmpdir, mocker):
    package = os.path.join(data_dir, test_package_name + ".conda")

    # this code is only called for .conda -> .tar.bz2; a streaming validate for
    # .tar.bz2 -> .conda would be a good idea.
    mocker.patch(
        "conda_package_handling.validate.validate_converted_files_match_streaming",
        return_value=(str(package), {"missing-file.txt"}, {"mismatched-size.txt"}),
    )

    errors = api.transmute(package, ".tar.bz2", tmpdir)
    assert errors


def test_api_transmute_fail_validation_to_conda(tmpdir, mocker):
    package = os.path.join(data_dir, test_package_name + ".tar.bz2")

    mocker.patch(
        "conda_package_handling.validate.validate_converted_files_match_streaming",
        return_value=(str(package), {"missing-file.txt"}, {"mismatched-size.txt"}),
    )

    errors = api.transmute(package, ".conda", tmpdir, zstd_compress_level=3)
    assert errors


def test_api_transmute_fail_validation_2(tmpdir, mocker):
    package = os.path.join(data_dir, test_package_name + ".conda")
    tmptarfile = tmpdir / pathlib.Path(package).name
    shutil.copy(package, tmptarfile)

    mocker.patch(
        "conda_package_handling.validate.validate_converted_files_match_streaming",
        side_effect=Exception("not today"),
    )

    # run with out_folder=None
    errors = api.transmute(str(tmptarfile), ".tar.bz2")
    assert errors


def test_api_translates_exception(mocker, tmpdir):
    from conda_package_streaming.extract import exceptions as cps_exceptions

    tarfile = os.path.join(data_dir, test_package_name + ".tar.bz2")

    # translates their exception to our exception of the same name
    mocker.patch(
        "conda_package_streaming.package_streaming.stream_conda_component",
        side_effect=cps_exceptions.CaseInsensitiveFileSystemError(),
    )

    # should this be exported from the api or inherit from InvalidArchiveError?
    with pytest.raises(exceptions.CaseInsensitiveFileSystemError):
        api.extract(tarfile, tmpdir)
