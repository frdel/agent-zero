import os
import sys

import pytest
from conda.cli.python_api import run_command

if sys.platform == "win32":
    import menuinst._legacy as menuinst
    from menuinst._legacy.win32 import dirs_src


def file_exist(mode, name):
    file = os.path.join(
        dirs_src[mode]['start'][0], 'Anaconda3 (64-bit) - Test Menu', '%s.lnk' % name
    )
    return os.path.exists(file)


menu_dir = os.path.dirname(__file__)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only tests")
class TestWindowsShortcuts(object):
    def test_install_folders_exist(self):
        for mode in ["user", "system"]:
            for path, _ in dirs_src[mode].values():
                assert os.path.exists(path)

    def test_create_and_remove_shortcut(self):
        nonadmin = os.path.join(sys.prefix, ".nonadmin")
        shortcut = os.path.join(menu_dir, "menu-windows.json")
        has_nonadmin = os.path.exists(nonadmin)
        name = 'Anaconda Prompt'
        for mode in ["user", "system"]:
            if mode == "user":
                open(nonadmin, 'a').close()
            menuinst.install(shortcut, remove=False)
            assert file_exist(mode, name)
            menuinst.install(shortcut, remove=True)
            assert not file_exist(mode, name)
            if os.path.exists(nonadmin):
                os.remove(nonadmin)
        if has_nonadmin:
            open(nonadmin, 'a').close()

    def test_create_shortcut_env(self):
        nonadmin = os.path.join(sys.prefix, ".nonadmin")
        open(nonadmin, 'a').close()
        shortcut = os.path.join(menu_dir, "menu-windows.json")
        test_env_name = 'test_env'
        run_command("create", "-n", test_env_name, "python")
        prefix = os.path.join(sys.prefix, 'envs', test_env_name)
        name = 'Anaconda Prompt (%s)' % test_env_name
        menuinst.install(shortcut, prefix=prefix, remove=False)
        assert file_exist('user', name)
        menuinst.install(shortcut, prefix=prefix, remove=True)
        assert not file_exist('user', name)
        run_command("remove", "-n", test_env_name, "--all")

    def test_root_prefix(self):
        nonadmin = os.path.join(sys.prefix, ".nonadmin")
        open(nonadmin, 'a').close()
        shortcut = os.path.join(menu_dir, "menu-windows.json")
        root_prefix = os.path.join(menu_dir, 'temp_env')
        run_command("create", "-p", root_prefix, "python")
        name = 'Anaconda Prompt (%s)' % os.path.split(sys.prefix)[1]
        menuinst.install(shortcut, remove=False, root_prefix=root_prefix)
        assert file_exist('user', name)
        menuinst.install(shortcut, remove=True, root_prefix=root_prefix)
        assert not file_exist('user', name)
        run_command("remove", "-p", root_prefix, "--all")
