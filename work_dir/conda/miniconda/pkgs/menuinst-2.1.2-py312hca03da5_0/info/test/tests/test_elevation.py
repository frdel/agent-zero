import os

from menuinst.utils import _test_elevation, elevate_as_needed, user_is_admin


def test_elevation(tmp_path, capfd):
    os.environ["MENUINST_TEST"] = "TEST"
    if os.name == "nt":
        on_ci = os.environ.get("CI")
        is_admin = user_is_admin()
        if not on_ci:
            # Windows runners on GHA always run as admin
            assert not is_admin

        _test_elevation(target_prefix=str(tmp_path), base_prefix=str(tmp_path))
        output = (tmp_path / "_test_output.txt").read_text().strip()
        if on_ci:
            assert output.endswith("env_var: TEST _mode: user")
        else:
            assert output.endswith("user_is_admin(): False env_var: TEST _mode: user")

        elevate_as_needed(_test_elevation)(target_prefix=str(tmp_path), base_prefix=str(tmp_path))
        output = (tmp_path / "_test_output.txt").read_text().strip()
        if on_ci:
            assert output.endswith("env_var: TEST _mode: system")
        else:
            assert output.endswith("user_is_admin(): True env_var: TEST _mode: system")
    else:
        assert not user_is_admin()  # We need to start as a non-root user

        _test_elevation(str(tmp_path))
        assert capfd.readouterr().out.strip() == "user_is_admin(): False env_var: TEST _mode: user"

        # make tmp_path not writable by the current user to force elevation
        tmp_path.chmod(0o500)
        elevate_as_needed(_test_elevation)(target_prefix=str(tmp_path), base_prefix=str(tmp_path))
        assert (
            capfd.readouterr().out.strip() == "user_is_admin(): True env_var: TEST _mode: system"
        )
        assert not (tmp_path / ".nonadmin").exists()

        # restore permissions
        tmp_path.chmod(0o700)
        elevate_as_needed(_test_elevation)(target_prefix=str(tmp_path), base_prefix=str(tmp_path))
        assert capfd.readouterr().out.strip() == "user_is_admin(): False env_var: TEST _mode: user"
        assert (tmp_path / ".nonadmin").exists()
