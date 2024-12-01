# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Collection of helper functions used in conda tests."""

import json
import os
from contextlib import contextmanager
from functools import lru_cache
from os.path import abspath, dirname, join
from pathlib import Path
from tempfile import gettempdir, mkdtemp
from unittest.mock import patch
from uuid import uuid4

import pytest

from ..base.context import conda_tests_ctxt_mgmt_def_pol, context
from ..common.io import captured as common_io_captured
from ..common.io import env_var
from ..core.prefix_data import PrefixData
from ..core.subdir_data import SubdirData
from ..gateways.disk.delete import rm_rf
from ..gateways.disk.read import lexists
from ..history import History
from ..models.channel import Channel
from ..models.records import PackageRecord, PrefixRecord
from ..resolve import Resolve

# The default value will only work if we have installed conda in development mode!
TEST_DATA_DIR = os.environ.get(
    "CONDA_TEST_DATA_DIR", abspath(join(dirname(__file__), "..", "..", "tests", "data"))
)
CHANNEL_DIR = CHANNEL_DIR_V1 = abspath(join(TEST_DATA_DIR, "conda_format_repo"))
CHANNEL_DIR_V2 = abspath(join(TEST_DATA_DIR, "base_url_channel"))
EXPORTED_CHANNELS_DIR = mkdtemp(suffix="-test-conda-channels")


expected_error_prefix = "Using Anaconda Cloud api site https://api.anaconda.org"


def strip_expected(stderr):
    if expected_error_prefix and stderr.startswith(expected_error_prefix):
        stderr = stderr[len(expected_error_prefix) :].lstrip()  # noqa
    return stderr


def raises(exception, func, string=None):
    try:
        a = func()
    except exception as e:
        if string:
            assert string in e.args[0]
        print(e)
        return True
    raise Exception(f"did not raise, gave {a}")


@contextmanager
def captured(disallow_stderr=True):
    # same as common.io.captured but raises Exception if unexpected output was written to stderr
    try:
        with common_io_captured() as c:
            yield c
    finally:
        c.stderr = strip_expected(c.stderr)
        if disallow_stderr and c.stderr:
            raise Exception(f"Got stderr output: {c.stderr}")


def assert_equals(a, b, output=""):
    output = f"{a.lower()!r} != {b.lower()!r}" + "\n\n" + output
    assert a.lower() == b.lower(), output


def assert_not_in(a, b, output=""):
    assert (
        a.lower() not in b.lower()
    ), f"{output} {a.lower()!r} should not be found in {b.lower()!r}"


def assert_in(a, b, output=""):
    assert (
        a.lower() in b.lower()
    ), f"{output} {a.lower()!r} cannot be found in {b.lower()!r}"


def add_subdir(dist_string):
    channel_str, package_str = dist_string.split("::")
    channel_str = channel_str + "/" + context.subdir
    return "::".join([channel_str, package_str])


def add_subdir_to_iter(iterable):
    if isinstance(iterable, dict):
        return {add_subdir(k): v for k, v in iterable.items()}
    elif isinstance(iterable, list):
        return list(map(add_subdir, iterable))
    elif isinstance(iterable, set):
        return set(map(add_subdir, iterable))
    elif isinstance(iterable, tuple):
        return tuple(map(add_subdir, iterable))
    else:
        raise Exception("Unable to add subdir to object of unknown type.")


@contextmanager
def tempdir():
    tempdirdir = gettempdir()
    dirname = str(uuid4())[:8]
    prefix = join(tempdirdir, dirname)
    try:
        os.makedirs(prefix)
        yield prefix
    finally:
        if lexists(prefix):
            rm_rf(prefix)


def supplement_index_with_repodata(index, repodata, channel, priority):
    repodata_info = repodata["info"]
    arch = repodata_info.get("arch")
    platform = repodata_info.get("platform")
    subdir = repodata_info.get("subdir")
    if not subdir:
        subdir = "{}-{}".format(repodata_info["platform"], repodata_info["arch"])
    auth = channel.auth
    for fn, info in repodata["packages"].items():
        rec = PackageRecord.from_objects(
            info,
            fn=fn,
            arch=arch,
            platform=platform,
            channel=channel,
            subdir=subdir,
            # schannel=schannel,
            priority=priority,
            # url=join_url(channel_url, fn),
            auth=auth,
        )
        index[rec] = rec


def add_feature_records_legacy(index):
    all_features = set()
    for rec in index.values():
        if rec.track_features:
            all_features.update(rec.track_features)

    for feature_name in all_features:
        rec = PackageRecord.feature(feature_name)
        index[rec] = rec


def _export_subdir_data_to_repodata(subdir_data: SubdirData):
    """
    This function is only temporary and meant to patch wrong / undesirable
    testing behaviour. It should end up being replaced with the new class-based,
    backend-agnostic solver tests.
    """
    state = subdir_data._internal_state
    subdir = subdir_data.channel.subdir
    packages = {}
    packages_conda = {}
    for pkg in subdir_data.iter_records():
        if pkg.timestamp:
            # ensure timestamp is dumped as int in milliseconds
            # (pkg.timestamp is a kept as a float in seconds)
            pkg.__fields__["timestamp"]._in_dump = True
        data = pkg.dump()
        if subdir == "noarch" and getattr(pkg, "noarch", None):
            data["subdir"] = "noarch"
            data["platform"] = data["arch"] = None
        if "features" in data:
            # Features are deprecated, so they are not implemented
            # in modern solvers like mamba. Mamba does implement
            # track_features minimization, so we are exposing the
            # features as track_features, which seems to make the
            # tests pass
            data["track_features"] = data["features"]
            del data["features"]
        if pkg.fn.endswith(".conda"):
            packages_conda[pkg.fn] = data
        else:
            packages[pkg.fn] = data
    return {
        "_cache_control": state["_cache_control"],
        "_etag": state["_etag"],
        "_mod": state["_mod"],
        "_url": state["_url"],
        "_add_pip": state["_add_pip"],
        "info": {
            "subdir": subdir,
        },
        "packages": packages,
        "packages.conda": packages_conda,
    }


def _sync_channel_to_disk(subdir_data: SubdirData):
    """
    This function is only temporary and meant to patch wrong / undesirable
    testing behaviour. It should end up being replaced with the new class-based,
    backend-agnostic solver tests.
    """
    base = Path(EXPORTED_CHANNELS_DIR) / subdir_data.channel.name
    subdir_path = base / subdir_data.channel.subdir
    subdir_path.mkdir(parents=True, exist_ok=True)
    with open(subdir_path / "repodata.json", "w") as f:
        json.dump(
            _export_subdir_data_to_repodata(subdir_data), f, indent=2, sort_keys=True
        )
        f.flush()
        os.fsync(f.fileno())


def _alias_canonical_channel_name_cache_to_file_prefixed(name, subdir_data=None):
    """
    This function is only temporary and meant to patch wrong / undesirable
    testing behaviour. It should end up being replaced with the new class-based,
    backend-agnostic solver tests.
    """
    # export repodata state to disk for other solvers to test
    if subdir_data is None:
        cache_key = Channel(name).url(with_credentials=True), "repodata.json"
        subdir_data = SubdirData._cache_.get(cache_key)
    if subdir_data:
        local_proxy_channel = Channel(f"{EXPORTED_CHANNELS_DIR}/{name}")
        SubdirData._cache_[
            (local_proxy_channel.url(with_credentials=True), "repodata.json")
        ] = subdir_data


def _patch_for_local_exports(name, subdir_data):
    """
    This function is only temporary and meant to patch wrong / undesirable
    testing behaviour. It should end up being replaced with the new class-based,
    backend-agnostic solver tests.
    """
    _alias_canonical_channel_name_cache_to_file_prefixed(name, subdir_data)

    # we need to override the modification time here so the
    # cache hits this subdir_data object from the local copy too
    # - without this, the legacy solver will use the local dump too
    # and there's no need for that extra work
    # (check conda.core.subdir_data.SubdirDataType.__call__ for
    # details)
    _sync_channel_to_disk(subdir_data)
    subdir_data._mtime = float("inf")


def _get_index_r_base(
    json_filename_or_packages,
    channel_name,
    subdir=context.subdir,
    add_pip=False,
    merge_noarch=False,
):
    if isinstance(json_filename_or_packages, (str, os.PathLike)):
        with open(join(TEST_DATA_DIR, json_filename_or_packages)) as fi:
            all_packages = json.load(fi)
    elif isinstance(json_filename_or_packages, dict):
        all_packages = json_filename_or_packages
    else:
        raise ValueError("'json_filename_or_data' must be path-like or dict")

    if merge_noarch:
        packages = {subdir: all_packages}
    else:
        packages = {subdir: {}, "noarch": {}}
        for key, pkg in all_packages.items():
            if pkg.get("subdir") == "noarch" or pkg.get("noarch"):
                packages["noarch"][key] = pkg
            else:
                packages[subdir][key] = pkg

    subdir_datas = []
    channels = []
    for subchannel, subchannel_pkgs in packages.items():
        repodata = {
            "info": {
                "subdir": subchannel,
                "arch": context.arch_name,
                "platform": context.platform,
            },
            "packages": subchannel_pkgs,
        }

        channel = Channel(f"https://conda.anaconda.org/{channel_name}/{subchannel}")
        channels.append(channel)
        sd = SubdirData(channel)
        subdir_datas.append(sd)
        with env_var(
            "CONDA_ADD_PIP_AS_PYTHON_DEPENDENCY",
            str(add_pip).lower(),
            stack_callback=conda_tests_ctxt_mgmt_def_pol,
        ):
            sd._process_raw_repodata_str(json.dumps(repodata))
        sd._loaded = True
        SubdirData._cache_[channel.url(with_credentials=True)] = sd
        _patch_for_local_exports(channel_name, sd)

    # this is for the classic solver only, which is fine with a single collapsed index
    index = {}
    for sd in subdir_datas:
        index.update({prec: prec for prec in sd.iter_records()})
    r = Resolve(index, channels=channels)

    return index, r


# this fixture appears to introduce a test-order dependency if cached
def get_index_r_1(subdir=context.subdir, add_pip=True, merge_noarch=False):
    return _get_index_r_base(
        "index.json",
        "channel-1",
        subdir=subdir,
        add_pip=add_pip,
        merge_noarch=merge_noarch,
    )


@lru_cache(maxsize=None)
def get_index_r_2(subdir=context.subdir, add_pip=True, merge_noarch=False):
    return _get_index_r_base(
        "index2.json",
        "channel-2",
        subdir=subdir,
        add_pip=add_pip,
        merge_noarch=merge_noarch,
    )


@lru_cache(maxsize=None)
def get_index_r_4(subdir=context.subdir, add_pip=True, merge_noarch=False):
    return _get_index_r_base(
        "index4.json",
        "channel-4",
        subdir=subdir,
        add_pip=add_pip,
        merge_noarch=merge_noarch,
    )


@lru_cache(maxsize=None)
def get_index_r_5(subdir=context.subdir, add_pip=False, merge_noarch=False):
    return _get_index_r_base(
        "index5.json",
        "channel-5",
        subdir=subdir,
        add_pip=add_pip,
        merge_noarch=merge_noarch,
    )


@lru_cache(maxsize=None)
def get_index_must_unfreeze(subdir=context.subdir, add_pip=True, merge_noarch=False):
    repodata = {
        "foobar-1.0-0.tar.bz2": {
            "build": "0",
            "build_number": 0,
            "depends": ["libbar 2.0.*", "libfoo 1.0.*"],
            "md5": "11ec1194bcc56b9a53c127142a272772",
            "name": "foobar",
            "timestamp": 1562861325613,
            "version": "1.0",
        },
        "foobar-2.0-0.tar.bz2": {
            "build": "0",
            "build_number": 0,
            "depends": ["libbar 2.0.*", "libfoo 2.0.*"],
            "md5": "f8eb5a7fa1ff6dead4e360631a6cd048",
            "name": "foobar",
            "version": "2.0",
        },
        "libbar-1.0-0.tar.bz2": {
            "build": "0",
            "build_number": 0,
            "depends": [],
            "md5": "f51f4d48a541b7105b5e343704114f0f",
            "name": "libbar",
            "timestamp": 1562858881022,
            "version": "1.0",
        },
        "libbar-2.0-0.tar.bz2": {
            "build": "0",
            "build_number": 0,
            "depends": [],
            "md5": "27f4e717ed263f909074f64d9cbf935d",
            "name": "libbar",
            "timestamp": 1562858881748,
            "version": "2.0",
        },
        "libfoo-1.0-0.tar.bz2": {
            "build": "0",
            "build_number": 0,
            "depends": [],
            "md5": "ad7c088566ffe2389958daedf8ff312c",
            "name": "libfoo",
            "timestamp": 1562858763881,
            "version": "1.0",
        },
        "libfoo-2.0-0.tar.bz2": {
            "build": "0",
            "build_number": 0,
            "depends": [],
            "md5": "daf7af7086d8f22be49ae11bdc41f332",
            "name": "libfoo",
            "timestamp": 1562858836924,
            "version": "2.0",
        },
        "qux-1.0-0.tar.bz2": {
            "build": "0",
            "build_number": 0,
            "depends": ["libbar 2.0.*", "libfoo 1.0.*"],
            "md5": "18604cbe4f789fe853232eef4babd4f9",
            "name": "qux",
            "timestamp": 1562861393808,
            "version": "1.0",
        },
        "qux-2.0-0.tar.bz2": {
            "build": "0",
            "build_number": 0,
            "depends": ["libbar 1.0.*", "libfoo 2.0.*"],
            "md5": "892aa4b9ec64b67045a46866ef1ea488",
            "name": "qux",
            "timestamp": 1562861394828,
            "version": "2.0",
        },
    }
    _get_index_r_base(
        repodata,
        "channel-freeze",
        subdir=subdir,
        add_pip=add_pip,
        merge_noarch=merge_noarch,
    )


# Do not memoize this get_index to allow different CUDA versions to be detected
def get_index_cuda(subdir=context.subdir, add_pip=True, merge_noarch=False):
    return _get_index_r_base(
        "index.json",
        "channel-1",
        subdir=subdir,
        add_pip=add_pip,
        merge_noarch=merge_noarch,
    )


def record(
    name="a",
    version="1.0",
    depends=None,
    build="0",
    build_number=0,
    timestamp=0,
    channel=None,
    **kwargs,
):
    return PackageRecord(
        name=name,
        version=version,
        depends=depends or [],
        build=build,
        build_number=build_number,
        timestamp=timestamp,
        channel=channel,
        **kwargs,
    )


def _get_solver_base(
    channel_id,
    tmpdir,
    specs_to_add=(),
    specs_to_remove=(),
    prefix_records=(),
    history_specs=(),
    add_pip=False,
    merge_noarch=False,
):
    tmpdir = tmpdir.strpath
    pd = PrefixData(tmpdir)
    pd._PrefixData__prefix_records = {
        rec.name: PrefixRecord.from_objects(rec) for rec in prefix_records
    }
    spec_map = {spec.name: spec for spec in history_specs}
    if channel_id == "channel-1":
        get_index_r_1(context.subdir, add_pip, merge_noarch)
        _alias_canonical_channel_name_cache_to_file_prefixed("channel-1")
        channels = (Channel(f"{EXPORTED_CHANNELS_DIR}/channel-1"),)
    elif channel_id == "channel-2":
        get_index_r_2(context.subdir, add_pip, merge_noarch)
        _alias_canonical_channel_name_cache_to_file_prefixed("channel-2")
        channels = (Channel(f"{EXPORTED_CHANNELS_DIR}/channel-2"),)
    elif channel_id == "channel-4":
        get_index_r_4(context.subdir, add_pip, merge_noarch)
        _alias_canonical_channel_name_cache_to_file_prefixed("channel-4")
        channels = (Channel(f"{EXPORTED_CHANNELS_DIR}/channel-4"),)
    elif channel_id == "channel-5":
        get_index_r_5(context.subdir, add_pip, merge_noarch)
        _alias_canonical_channel_name_cache_to_file_prefixed("channel-5")
        channels = (Channel(f"{EXPORTED_CHANNELS_DIR}/channel-5"),)
    elif channel_id == "aggregate-1":
        get_index_r_2(context.subdir, add_pip, merge_noarch)
        get_index_r_4(context.subdir, add_pip, merge_noarch)
        _alias_canonical_channel_name_cache_to_file_prefixed("channel-2")
        _alias_canonical_channel_name_cache_to_file_prefixed("channel-4")
        channels = (
            Channel(f"{EXPORTED_CHANNELS_DIR}/channel-2"),
            Channel(f"{EXPORTED_CHANNELS_DIR}/channel-4"),
        )
    elif channel_id == "aggregate-2":
        get_index_r_2(context.subdir, add_pip, merge_noarch)
        get_index_r_4(context.subdir, add_pip, merge_noarch)
        _alias_canonical_channel_name_cache_to_file_prefixed("channel-4")
        _alias_canonical_channel_name_cache_to_file_prefixed("channel-2")
        # This is the only difference with aggregate-1: the priority
        channels = (
            Channel(f"{EXPORTED_CHANNELS_DIR}/channel-4"),
            Channel(f"{EXPORTED_CHANNELS_DIR}/channel-2"),
        )
    elif channel_id == "must-unfreeze":
        get_index_must_unfreeze(context.subdir, add_pip, merge_noarch)
        _alias_canonical_channel_name_cache_to_file_prefixed("channel-freeze")
        channels = (Channel(f"{EXPORTED_CHANNELS_DIR}/channel-freeze"),)
    elif channel_id == "cuda":
        get_index_cuda(context.subdir, add_pip, merge_noarch)
        _alias_canonical_channel_name_cache_to_file_prefixed("channel-1")
        channels = (Channel(f"{EXPORTED_CHANNELS_DIR}/channel-1"),)

    subdirs = (context.subdir,) if merge_noarch else (context.subdir, "noarch")

    with patch.object(
        History, "get_requested_specs_map", return_value=spec_map
    ), env_var(
        "CONDA_ADD_PIP_AS_PYTHON_DEPENDENCY",
        str(add_pip).lower(),
        stack_callback=conda_tests_ctxt_mgmt_def_pol,
    ):
        # We need CONDA_ADD_PIP_AS_PYTHON_DEPENDENCY=false here again (it's also in
        # get_index_r_*) to cover solver logics that need to load from disk instead of
        # hitting the SubdirData cache
        yield context.plugin_manager.get_solver_backend()(
            tmpdir,
            channels,
            subdirs,
            specs_to_add=specs_to_add,
            specs_to_remove=specs_to_remove,
        )


@contextmanager
def get_solver(
    tmpdir,
    specs_to_add=(),
    specs_to_remove=(),
    prefix_records=(),
    history_specs=(),
    add_pip=False,
    merge_noarch=False,
):
    yield from _get_solver_base(
        "channel-1",
        tmpdir,
        specs_to_add=specs_to_add,
        specs_to_remove=specs_to_remove,
        prefix_records=prefix_records,
        history_specs=history_specs,
        add_pip=add_pip,
        merge_noarch=merge_noarch,
    )


@contextmanager
def get_solver_2(
    tmpdir,
    specs_to_add=(),
    specs_to_remove=(),
    prefix_records=(),
    history_specs=(),
    add_pip=False,
    merge_noarch=False,
):
    yield from _get_solver_base(
        "channel-2",
        tmpdir,
        specs_to_add=specs_to_add,
        specs_to_remove=specs_to_remove,
        prefix_records=prefix_records,
        history_specs=history_specs,
        add_pip=add_pip,
        merge_noarch=merge_noarch,
    )


@contextmanager
def get_solver_4(
    tmpdir,
    specs_to_add=(),
    specs_to_remove=(),
    prefix_records=(),
    history_specs=(),
    add_pip=False,
    merge_noarch=False,
):
    yield from _get_solver_base(
        "channel-4",
        tmpdir,
        specs_to_add=specs_to_add,
        specs_to_remove=specs_to_remove,
        prefix_records=prefix_records,
        history_specs=history_specs,
        add_pip=add_pip,
        merge_noarch=merge_noarch,
    )


@contextmanager
def get_solver_5(
    tmpdir,
    specs_to_add=(),
    specs_to_remove=(),
    prefix_records=(),
    history_specs=(),
    add_pip=False,
    merge_noarch=False,
):
    yield from _get_solver_base(
        "channel-5",
        tmpdir,
        specs_to_add=specs_to_add,
        specs_to_remove=specs_to_remove,
        prefix_records=prefix_records,
        history_specs=history_specs,
        add_pip=add_pip,
        merge_noarch=merge_noarch,
    )


@contextmanager
def get_solver_aggregate_1(
    tmpdir,
    specs_to_add=(),
    specs_to_remove=(),
    prefix_records=(),
    history_specs=(),
    add_pip=False,
    merge_noarch=False,
):
    yield from _get_solver_base(
        "aggregate-1",
        tmpdir,
        specs_to_add=specs_to_add,
        specs_to_remove=specs_to_remove,
        prefix_records=prefix_records,
        history_specs=history_specs,
        add_pip=add_pip,
        merge_noarch=merge_noarch,
    )


@contextmanager
def get_solver_aggregate_2(
    tmpdir,
    specs_to_add=(),
    specs_to_remove=(),
    prefix_records=(),
    history_specs=(),
    add_pip=False,
    merge_noarch=False,
):
    yield from _get_solver_base(
        "aggregate-2",
        tmpdir,
        specs_to_add=specs_to_add,
        specs_to_remove=specs_to_remove,
        prefix_records=prefix_records,
        history_specs=history_specs,
        add_pip=add_pip,
        merge_noarch=merge_noarch,
    )


@contextmanager
def get_solver_must_unfreeze(
    tmpdir,
    specs_to_add=(),
    specs_to_remove=(),
    prefix_records=(),
    history_specs=(),
    add_pip=False,
    merge_noarch=False,
):
    yield from _get_solver_base(
        "must-unfreeze",
        tmpdir,
        specs_to_add=specs_to_add,
        specs_to_remove=specs_to_remove,
        prefix_records=prefix_records,
        history_specs=history_specs,
        add_pip=add_pip,
        merge_noarch=merge_noarch,
    )


@contextmanager
def get_solver_cuda(
    tmpdir,
    specs_to_add=(),
    specs_to_remove=(),
    prefix_records=(),
    history_specs=(),
    add_pip=False,
    merge_noarch=False,
):
    yield from _get_solver_base(
        "cuda",
        tmpdir,
        specs_to_add=specs_to_add,
        specs_to_remove=specs_to_remove,
        prefix_records=prefix_records,
        history_specs=history_specs,
        add_pip=add_pip,
        merge_noarch=merge_noarch,
    )


def convert_to_dist_str(solution):
    dist_str = []
    for prec in solution:
        # This is needed to remove the local path prefix in the
        # dist_str() calls, otherwise we cannot compare them
        canonical_name = prec.channel._Channel__canonical_name
        prec.channel._Channel__canonical_name = prec.channel.name
        dist_str.append(prec.dist_str())
        prec.channel._Channel__canonical_name = canonical_name
    return tuple(dist_str)


@pytest.fixture()
def solver_class():
    return context.plugin_manager.get_solver_backend()
