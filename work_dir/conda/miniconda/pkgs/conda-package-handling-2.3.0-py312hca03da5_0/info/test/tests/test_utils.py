import os
import sys
from errno import EACCES, ENOENT, EPERM, EROFS

import pytest

from conda_package_handling import utils


def test_rm_rf_file(testing_workdir):
    with open("dummy", "w") as f:
        f.write("weeee")
    utils.rm_rf("dummy")

    with open("dummy", "w") as f:
        f.write("weeee")
    utils.rm_rf(os.path.join(testing_workdir, "dummy"))


@pytest.mark.parametrize("errno", (ENOENT, EACCES, EPERM, EROFS))
def test_rename_to_trash(testing_workdir, mocker, errno):
    unlink = mocker.patch("os.unlink")
    unlink.side_effect = EnvironmentError(errno, "")
    with open("dummy", "w") as f:
        f.write("weeee")
    utils.unlink_or_rename_to_trash("dummy")
    assert os.path.isfile("dummy.conda_trash")

    # force a second error for the inner rename try (after unlink fails)
    if sys.platform == "win32":
        with open("dummy", "w") as f:
            f.write("weeee")
        mocker.patch("os.rename")
        unlink.side_effect = EnvironmentError(errno, "")
        utils.unlink_or_rename_to_trash("dummy")
        assert os.path.isfile("dummy.conda_trash")


def test_delete_trash(testing_workdir, mocker):
    isdir = mocker.patch("conda_package_handling.utils.isdir")
    isdir.return_value = True
    lexists = mocker.patch("conda_package_handling.utils.lexists")
    lexists.return_value = False
    mocker.patch("conda_package_handling.utils.rmdir")

    os.makedirs("folder")
    with open("folder/dummy.conda_trash", "w") as f:
        f.write("weeee")

    utils.rm_rf("folder")
    assert not os.path.isfile("folder/dummy.conda_trash")
