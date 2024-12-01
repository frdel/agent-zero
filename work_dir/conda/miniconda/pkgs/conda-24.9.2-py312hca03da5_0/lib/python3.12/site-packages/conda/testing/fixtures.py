# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Collection of pytest fixtures used in conda tests."""

from __future__ import annotations

import json
import os
import uuid
import warnings
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from logging import getLogger
from pathlib import Path
from shutil import copyfile
from typing import TYPE_CHECKING, Literal, TypeVar, overload

import py
import pytest

from ..auxlib.entity import EntityEncoder
from ..auxlib.ish import dals
from ..base.constants import PACKAGE_CACHE_MAGIC_FILE
from ..base.context import conda_tests_ctxt_mgmt_def_pol, context, reset_context
from ..cli.main import main_subshell
from ..common.configuration import YamlRawParameter
from ..common.io import env_vars
from ..common.serialize import yaml_round_trip_load
from ..common.url import path_to_url
from ..core.package_cache_data import PackageCacheData
from ..core.subdir_data import SubdirData
from ..exceptions import CondaExitZero
from ..gateways.disk.create import TemporaryDirectory
from ..models.records import PackageRecord

if TYPE_CHECKING:
    from typing import Iterable, Iterator

    from _pytest.capture import MultiCapture
    from pytest import (
        CaptureFixture,
        ExceptionInfo,
        FixtureRequest,
        MonkeyPatch,
        TempPathFactory,
    )
    from pytest_mock import MockerFixture


log = getLogger(__name__)


@pytest.fixture(autouse=True)
def suppress_resource_warning():
    """
    Suppress `Unclosed Socket Warning`

    It seems urllib3 keeps a socket open to avoid costly recreation costs.

    xref: https://github.com/kennethreitz/requests/issues/1882
    """
    warnings.filterwarnings("ignore", category=ResourceWarning)


@pytest.fixture(scope="function")
def tmpdir(tmpdir, request):
    tmpdir = TemporaryDirectory(dir=str(tmpdir))
    request.addfinalizer(tmpdir.cleanup)
    return py.path.local(tmpdir.name)


@pytest.fixture(autouse=True)
def clear_subdir_cache():
    SubdirData.clear_cached_local_channel_data()


@pytest.fixture(scope="function")
def disable_channel_notices():
    """
    Fixture that will set "context.number_channel_notices" to 0 and then set
    it back to its original value.

    This is also a good example of how to override values in the context object.
    """
    yaml_str = dals(
        """
        number_channel_notices: 0
        """
    )
    reset_context(())
    rd = {
        "testdata": YamlRawParameter.make_raw_parameters(
            "testdata", yaml_round_trip_load(yaml_str)
        )
    }
    context._set_raw_data(rd)

    yield

    reset_context(())


@pytest.fixture(scope="function")
def reset_conda_context():
    """Resets the context object after each test function is run."""
    yield

    reset_context()


@pytest.fixture()
def temp_package_cache(tmp_path_factory):
    """
    Used to isolate package or index cache from other tests.
    """
    pkgs_dir = tmp_path_factory.mktemp("pkgs")
    with env_vars(
        {"CONDA_PKGS_DIRS": str(pkgs_dir)}, stack_callback=conda_tests_ctxt_mgmt_def_pol
    ):
        yield pkgs_dir


@pytest.fixture(
    # allow CI to set the solver backends via the CONDA_TEST_SOLVERS env var
    params=os.environ.get("CONDA_TEST_SOLVERS", "libmamba,classic").split(",")
)
def parametrized_solver_fixture(
    request: FixtureRequest,
    monkeypatch: MonkeyPatch,
) -> Iterable[Literal["libmamba", "classic"]]:
    """
    A parameterized fixture that sets the solver backend to (1) libmamba
    and (2) classic for each test. It's using autouse=True, so only import it in
    modules that actually need it.

    Note that skips and xfails need to be done _inside_ the test body.
    Decorators can't be used because they are evaluated before the
    fixture has done its work!

    So, instead of:

        @pytest.mark.skipif(context.solver == "libmamba", reason="...")
        def test_foo():
            ...

    Do:

        def test_foo():
            if context.solver == "libmamba":
                pytest.skip("...")
            ...
    """
    yield from _solver_helper(request, monkeypatch, request.param)


@pytest.fixture
def solver_classic(
    request: FixtureRequest,
    monkeypatch: MonkeyPatch,
) -> Iterable[Literal["classic"]]:
    yield from _solver_helper(request, monkeypatch, "classic")


@pytest.fixture
def solver_libmamba(
    request: FixtureRequest,
    monkeypatch: MonkeyPatch,
) -> Iterable[Literal["libmamba"]]:
    yield from _solver_helper(request, monkeypatch, "libmamba")


Solver = TypeVar("Solver", Literal["libmamba"], Literal["classic"])


def _solver_helper(
    request: FixtureRequest,
    monkeypatch: MonkeyPatch,
    solver: Solver,
) -> Iterable[Solver]:
    # clear cached solver backends before & after each test
    context.plugin_manager.get_cached_solver_backend.cache_clear()
    request.addfinalizer(context.plugin_manager.get_cached_solver_backend.cache_clear)

    monkeypatch.setenv("CONDA_SOLVER", solver)
    reset_context()
    assert context.solver == solver

    yield solver


@pytest.fixture(scope="session")
def session_capsys(request) -> Iterator[MultiCapture]:
    # https://github.com/pytest-dev/pytest/issues/2704#issuecomment-603387680
    capmanager = request.config.pluginmanager.getplugin("capturemanager")
    with capmanager.global_and_fixture_disabled():
        yield capmanager._global_capturing


@dataclass
class CondaCLIFixture:
    capsys: CaptureFixture | MultiCapture

    @overload
    def __call__(
        self,
        *argv: str | os.PathLike | Path,
        raises: type[Exception] | tuple[type[Exception], ...],
    ) -> tuple[str, str, ExceptionInfo]: ...

    @overload
    def __call__(self, *argv: str | os.PathLike | Path) -> tuple[str, str, int]: ...

    def __call__(
        self,
        *argv: str | os.PathLike | Path,
        raises: type[Exception] | tuple[type[Exception], ...] | None = None,
    ) -> tuple[str, str, int | ExceptionInfo]:
        """Test conda CLI. Mimic what is done in `conda.cli.main.main`.

        `conda ...` == `conda_cli(...)`

        :param argv: Arguments to parse.
        :param raises: Expected exception to intercept. If provided, the raised exception
            will be returned instead of exit code (see pytest.raises and pytest.ExceptionInfo).
        :return: Command results (stdout, stderr, exit code or pytest.ExceptionInfo).
        """
        # clear output
        self.capsys.readouterr()

        # ensure arguments are string
        argv = tuple(map(str, argv))

        # run command
        code = None
        with pytest.raises(raises) if raises else nullcontext() as exception:
            code = main_subshell(*argv)
        # capture output
        out, err = self.capsys.readouterr()

        # restore to prior state
        reset_context()

        return out, err, exception if raises else code


@pytest.fixture
def conda_cli(capsys: CaptureFixture) -> Iterator[CondaCLIFixture]:
    """A function scoped fixture returning CondaCLIFixture instance.

    Use this for any commands that are local to the current test (e.g., creating a
    conda environment only used in the test).
    """
    yield CondaCLIFixture(capsys)


@pytest.fixture(scope="session")
def session_conda_cli(session_capsys: MultiCapture) -> Iterator[CondaCLIFixture]:
    """A session scoped fixture returning CondaCLIFixture instance.

    Use this for any commands that are global to the test session (e.g., creating a
    conda environment shared across tests, `conda info`, etc.).
    """
    yield CondaCLIFixture(session_capsys)


@dataclass
class PathFactoryFixture:
    tmp_path: Path

    def __call__(
        self,
        name: str | None = None,
        prefix: str | None = None,
        suffix: str | None = None,
    ) -> Path:
        """Unique, non-existent path factory.

        Extends pytest's `tmp_path` fixture with a new unique, non-existent path for usage in cases
        where we need a temporary path that doesn't exist yet.

        :param name: Path name to append to `tmp_path`
        :param prefix: Prefix to prepend to unique name generated
        :param suffix: Suffix to append to unique name generated
        :return: A new unique path
        """
        prefix = prefix or ""
        name = name or uuid.uuid4().hex
        suffix = suffix or ""
        return self.tmp_path / (prefix + name + suffix)


@pytest.fixture
def path_factory(tmp_path: Path) -> Iterator[PathFactoryFixture]:
    """A function scoped fixture returning PathFactoryFixture instance.

    Use this to generate any number of temporary paths for the test that are unique and
    do not exist yet.
    """
    yield PathFactoryFixture(tmp_path)


@dataclass
class TmpEnvFixture:
    path_factory: PathFactoryFixture | TempPathFactory
    conda_cli: CondaCLIFixture

    def get_path(self) -> Path:
        if isinstance(self.path_factory, PathFactoryFixture):
            # scope=function
            return self.path_factory()
        else:
            # scope=session
            return self.path_factory.mktemp("tmp_env-")

    @contextmanager
    def __call__(
        self,
        *packages: str,
        prefix: str | os.PathLike | None = None,
    ) -> Iterator[Path]:
        """Generate a conda environment with the provided packages.

        :param packages: The packages to install into environment
        :param prefix: The prefix at which to install the conda environment
        :return: The conda environment's prefix
        """
        prefix = Path(prefix or self.get_path())

        self.conda_cli("create", "--prefix", prefix, *packages, "--yes", "--quiet")
        yield prefix

        # no need to remove prefix since it is in a temporary directory


@pytest.fixture
def tmp_env(
    path_factory: PathFactoryFixture,
    conda_cli: CondaCLIFixture,
) -> Iterator[TmpEnvFixture]:
    """A function scoped fixture returning TmpEnvFixture instance.

    Use this when creating a conda environment that is local to the current test.
    """
    yield TmpEnvFixture(path_factory, conda_cli)


@pytest.fixture(scope="session")
def session_tmp_env(
    tmp_path_factory: TempPathFactory,
    session_conda_cli: CondaCLIFixture,
) -> Iterator[TmpEnvFixture]:
    """A session scoped fixture returning TmpEnvFixture instance.

    Use this when creating a conda environment that is shared across tests.
    """
    yield TmpEnvFixture(tmp_path_factory, session_conda_cli)


@dataclass
class TmpChannelFixture:
    path_factory: PathFactoryFixture
    conda_cli: CondaCLIFixture

    @contextmanager
    def __call__(self, *packages: str) -> Iterator[tuple[Path, str]]:
        # download packages
        self.conda_cli(
            "create",
            f"--prefix={self.path_factory()}",
            *packages,
            "--yes",
            "--quiet",
            "--download-only",
            raises=CondaExitZero,
        )

        pkgs_dir = Path(PackageCacheData.first_writable().pkgs_dir)
        pkgs_cache = PackageCacheData(pkgs_dir)

        channel = self.path_factory()
        subdir = channel / context.subdir
        subdir.mkdir(parents=True)
        noarch = channel / "noarch"
        noarch.mkdir(parents=True)

        repodata = {"info": {}, "packages": {}}
        for package in packages:
            for pkg_data in pkgs_cache.query(package):
                fname = pkg_data["fn"]

                copyfile(pkgs_dir / fname, subdir / fname)

                repodata["packages"][fname] = PackageRecord(
                    **{
                        field: value
                        for field, value in pkg_data.dump().items()
                        if field not in ("url", "channel", "schannel")
                    }
                )

        (subdir / "repodata.json").write_text(json.dumps(repodata, cls=EntityEncoder))
        (noarch / "repodata.json").write_text(json.dumps({}, cls=EntityEncoder))

        for package in packages:
            assert any(PackageCacheData.query_all(package))

        yield channel, path_to_url(str(channel))


@pytest.fixture
def tmp_channel(
    path_factory: PathFactoryFixture,
    conda_cli: CondaCLIFixture,
) -> Iterator[TmpChannelFixture]:
    """A function scoped fixture returning TmpChannelFixture instance."""
    yield TmpChannelFixture(path_factory, conda_cli)


@pytest.fixture(name="monkeypatch")
def context_aware_monkeypatch(monkeypatch: MonkeyPatch) -> MonkeyPatch:
    """A monkeypatch fixture that resets context after each test."""
    yield monkeypatch

    # reset context if any CONDA_ variables were set/unset
    if conda_vars := [
        name
        for obj, name, _ in monkeypatch._setitem
        if obj is os.environ and name.startswith("CONDA_")
    ]:
        log.debug(f"monkeypatch cleanup: undo & reset context: {', '.join(conda_vars)}")
        monkeypatch.undo()
        # reload context without search paths
        reset_context([])


@pytest.fixture
def tmp_pkgs_dir(
    path_factory: PathFactoryFixture, mocker: MockerFixture
) -> Iterator[Path]:
    """A function scoped fixture returning a temporary package cache directory."""
    pkgs_dir = path_factory() / "pkgs"
    pkgs_dir.mkdir(parents=True)
    (pkgs_dir / PACKAGE_CACHE_MAGIC_FILE).touch()

    mocker.patch(
        "conda.base.context.Context.pkgs_dirs",
        new_callable=mocker.PropertyMock,
        return_value=(pkgs_dir_str := str(pkgs_dir),),
    )
    assert context.pkgs_dirs == (pkgs_dir_str,)

    yield pkgs_dir

    PackageCacheData._cache_.pop(pkgs_dir_str, None)


@pytest.fixture
def tmp_envs_dir(
    path_factory: PathFactoryFixture, mocker: MockerFixture
) -> Iterator[Path]:
    """A function scoped fixture returning a temporary environment directory."""
    envs_dir = path_factory() / "envs"
    envs_dir.mkdir(parents=True)

    mocker.patch(
        "conda.base.context.Context.envs_dirs",
        new_callable=mocker.PropertyMock,
        return_value=(envs_dir_str := str(envs_dir),),
    )
    assert context.envs_dirs == (envs_dir_str,)

    yield envs_dir
