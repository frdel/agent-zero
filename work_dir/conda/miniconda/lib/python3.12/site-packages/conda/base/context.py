# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Conda's global configuration object.

The context aggregates all configuration files, environment variables, and command line arguments
into one global stateful object to be used across all of conda.
"""

from __future__ import annotations

import logging
import os
import platform
import struct
import sys
from collections import defaultdict
from contextlib import contextmanager
from errno import ENOENT
from functools import cached_property, lru_cache
from itertools import chain
from os.path import abspath, exists, expanduser, isdir, isfile, join
from os.path import split as path_split
from typing import TYPE_CHECKING, Mapping

from boltons.setutils import IndexedSet

from .. import CONDA_SOURCE_ROOT
from .. import __version__ as CONDA_VERSION
from ..auxlib.decorators import memoizedproperty
from ..auxlib.ish import dals
from ..common._os.linux import linux_get_libc_version
from ..common.compat import NoneType, on_win
from ..common.configuration import (
    Configuration,
    ConfigurationLoadError,
    ConfigurationType,
    EnvRawParameter,
    MapParameter,
    ParameterLoader,
    PrimitiveParameter,
    SequenceParameter,
    ValidationError,
    unique_sequence_map,
)
from ..common.constants import TRACE
from ..common.iterators import unique
from ..common.path import BIN_DIRECTORY, expand, paths_equal
from ..common.url import has_scheme, path_to_url, split_scheme_auth_token
from ..deprecations import deprecated
from .constants import (
    APP_NAME,
    DEFAULT_AGGRESSIVE_UPDATE_PACKAGES,
    DEFAULT_CHANNEL_ALIAS,
    DEFAULT_CHANNELS,
    DEFAULT_CHANNELS_UNIX,
    DEFAULT_CHANNELS_WIN,
    DEFAULT_CUSTOM_CHANNELS,
    DEFAULT_SOLVER,
    DEFAULTS_CHANNEL_NAME,
    ERROR_UPLOAD_URL,
    KNOWN_SUBDIRS,
    NO_PLUGINS,
    PREFIX_MAGIC_FILE,
    PREFIX_NAME_DISALLOWED_CHARS,
    REPODATA_FN,
    ROOT_ENV_NAME,
    SEARCH_PATH,
    ChannelPriority,
    DepsModifier,
    PathConflict,
    SafetyChecks,
    SatSolverChoice,
    UpdateModifier,
)

try:
    from frozendict import frozendict
except ImportError:
    from .._vendor.frozendict import frozendict

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Literal

    from ..common.configuration import Parameter, RawParameter
    from ..plugins.manager import CondaPluginManager

try:
    os.getcwd()
except OSError as e:
    if e.errno == ENOENT:
        # FileNotFoundError can occur when cwd has been deleted out from underneath the process.
        # To resolve #6584, let's go with setting cwd to sys.prefix, and see how far we get.
        os.chdir(sys.prefix)
    else:
        raise

log = logging.getLogger(__name__)

_platform_map = {
    "freebsd13": "freebsd",
    "linux2": "linux",
    "linux": "linux",
    "darwin": "osx",
    "win32": "win",
    "zos": "zos",
}
non_x86_machines = {
    "armv6l",
    "armv7l",
    "aarch64",
    "arm64",
    "ppc64",
    "ppc64le",
    "riscv64",
    "s390x",
}
_arch_names = {
    32: "x86",
    64: "x86_64",
}

user_rc_path = abspath(expanduser("~/.condarc"))
sys_rc_path = join(sys.prefix, ".condarc")


def user_data_dir(  # noqa: F811
    appname: str | None = None,
    appauthor: str | None | Literal[False] = None,
    version: str | None = None,
    roaming: bool = False,
):
    # Defer platformdirs import to reduce import time for conda activate.
    global user_data_dir
    from platformdirs import user_data_dir

    return user_data_dir(appname, appauthor=appauthor, version=version, roaming=roaming)


def mockable_context_envs_dirs(root_writable, root_prefix, _envs_dirs):
    if root_writable:
        fixed_dirs = [
            join(root_prefix, "envs"),
            join("~", ".conda", "envs"),
        ]
    else:
        fixed_dirs = [
            join("~", ".conda", "envs"),
            join(root_prefix, "envs"),
        ]
    if on_win:
        fixed_dirs.append(join(user_data_dir(APP_NAME, APP_NAME), "envs"))
    return tuple(IndexedSet(expand(path) for path in (*_envs_dirs, *fixed_dirs)))


def channel_alias_validation(value):
    if value and not has_scheme(value):
        return f"channel_alias value '{value}' must have scheme/protocol."
    return True


def default_python_default():
    ver = sys.version_info
    return "%d.%d" % (ver.major, ver.minor)


def default_python_validation(value):
    if value:
        if len(value) >= 3 and value[1] == ".":
            try:
                value = float(value)
                if 2.0 <= value < 4.0:
                    return True
            except ValueError:  # pragma: no cover
                pass
    else:
        # Set to None or '' meaning no python pinning
        return True

    return f"default_python value '{value}' not of the form '[23].[0-9][0-9]?' or ''"


def ssl_verify_validation(value):
    if isinstance(value, str):
        if sys.version_info < (3, 10) and value == "truststore":
            return "`ssl_verify: truststore` is only supported on Python 3.10 or later"
        elif value != "truststore" and not exists(value):
            return (
                f"ssl_verify value '{value}' must be a boolean, a path to a "
                "certificate bundle file, a path to a directory containing "
                "certificates of trusted CAs, or 'truststore' to use the "
                "operating system certificate store."
            )
    return True


def _warn_defaults_deprecation():
    deprecated.topic(
        "24.9",
        "25.3",
        topic=f"Adding '{DEFAULTS_CHANNEL_NAME}' to channel list implicitly",
        addendum=(
            "\n\n"
            "To remove this warning, please choose a default channel explicitly "
            "with conda's regular configuration system, e.g. "
            f"by adding '{DEFAULTS_CHANNEL_NAME}' to the list of channels:\n\n"
            f"  conda config --add channels {DEFAULTS_CHANNEL_NAME}"
            "\n\n"
            "For more information see https://docs.conda.io/projects/conda/en/stable/user-guide/configuration/use-condarc.html\n"
        ),
        deprecation_type=FutureWarning,
    )


class Context(Configuration):
    add_pip_as_python_dependency = ParameterLoader(PrimitiveParameter(True))
    allow_conda_downgrades = ParameterLoader(PrimitiveParameter(False))
    # allow cyclical dependencies, or raise
    allow_cycles = ParameterLoader(PrimitiveParameter(True))
    allow_softlinks = ParameterLoader(PrimitiveParameter(False))
    auto_update_conda = ParameterLoader(
        PrimitiveParameter(True), aliases=("self_update",)
    )
    auto_activate_base = ParameterLoader(PrimitiveParameter(True))
    auto_stack = ParameterLoader(PrimitiveParameter(0))
    notify_outdated_conda = ParameterLoader(PrimitiveParameter(True))
    clobber = ParameterLoader(PrimitiveParameter(False))
    changeps1 = ParameterLoader(PrimitiveParameter(True))
    env_prompt = ParameterLoader(PrimitiveParameter("({default_env}) "))
    create_default_packages = ParameterLoader(
        SequenceParameter(PrimitiveParameter("", element_type=str))
    )
    register_envs = ParameterLoader(PrimitiveParameter(True))
    default_python = ParameterLoader(
        PrimitiveParameter(
            default_python_default(),
            element_type=(str, NoneType),
            validation=default_python_validation,
        )
    )
    download_only = ParameterLoader(PrimitiveParameter(False))
    enable_private_envs = ParameterLoader(PrimitiveParameter(False))
    force_32bit = ParameterLoader(PrimitiveParameter(False))
    non_admin_enabled = ParameterLoader(PrimitiveParameter(True))
    pip_interop_enabled = ParameterLoader(PrimitiveParameter(False))

    # multithreading in various places
    _default_threads = ParameterLoader(
        PrimitiveParameter(0, element_type=int), aliases=("default_threads",)
    )
    # download repodata
    _repodata_threads = ParameterLoader(
        PrimitiveParameter(0, element_type=int), aliases=("repodata_threads",)
    )
    # download packages
    _fetch_threads = ParameterLoader(
        PrimitiveParameter(0, element_type=int), aliases=("fetch_threads",)
    )
    _verify_threads = ParameterLoader(
        PrimitiveParameter(0, element_type=int), aliases=("verify_threads",)
    )
    # this one actually defaults to 1 - that is handled in the property below
    _execute_threads = ParameterLoader(
        PrimitiveParameter(0, element_type=int), aliases=("execute_threads",)
    )

    # Safety & Security
    _aggressive_update_packages = ParameterLoader(
        SequenceParameter(
            PrimitiveParameter("", element_type=str), DEFAULT_AGGRESSIVE_UPDATE_PACKAGES
        ),
        aliases=("aggressive_update_packages",),
    )
    safety_checks = ParameterLoader(PrimitiveParameter(SafetyChecks.warn))
    extra_safety_checks = ParameterLoader(PrimitiveParameter(False))
    _signing_metadata_url_base = ParameterLoader(
        PrimitiveParameter(None, element_type=(str, NoneType)),
        aliases=("signing_metadata_url_base",),
    )
    path_conflict = ParameterLoader(PrimitiveParameter(PathConflict.clobber))

    pinned_packages = ParameterLoader(
        SequenceParameter(
            PrimitiveParameter("", element_type=str), string_delimiter="&"
        )
    )  # TODO: consider a different string delimiter  # NOQA
    disallowed_packages = ParameterLoader(
        SequenceParameter(
            PrimitiveParameter("", element_type=str), string_delimiter="&"
        ),
        aliases=("disallow",),
    )
    rollback_enabled = ParameterLoader(PrimitiveParameter(True))
    track_features = ParameterLoader(
        SequenceParameter(PrimitiveParameter("", element_type=str))
    )
    use_index_cache = ParameterLoader(PrimitiveParameter(False))

    separate_format_cache = ParameterLoader(PrimitiveParameter(False))

    _root_prefix = ParameterLoader(
        PrimitiveParameter(""), aliases=("root_dir", "root_prefix")
    )
    _envs_dirs = ParameterLoader(
        SequenceParameter(
            PrimitiveParameter("", element_type=str), string_delimiter=os.pathsep
        ),
        aliases=("envs_dirs", "envs_path"),
        expandvars=True,
    )
    _pkgs_dirs = ParameterLoader(
        SequenceParameter(PrimitiveParameter("", str)),
        aliases=("pkgs_dirs",),
        expandvars=True,
    )
    _subdir = ParameterLoader(PrimitiveParameter(""), aliases=("subdir",))
    _subdirs = ParameterLoader(
        SequenceParameter(PrimitiveParameter("", str)), aliases=("subdirs",)
    )

    local_repodata_ttl = ParameterLoader(
        PrimitiveParameter(1, element_type=(bool, int))
    )
    # number of seconds to cache repodata locally
    #   True/1: respect Cache-Control max-age header
    #   False/0: always fetch remote repodata (HTTP 304 responses respected)

    # remote connection details
    ssl_verify = ParameterLoader(
        PrimitiveParameter(
            True, element_type=(str, bool), validation=ssl_verify_validation
        ),
        aliases=("verify_ssl",),
        expandvars=True,
    )
    client_ssl_cert = ParameterLoader(
        PrimitiveParameter(None, element_type=(str, NoneType)),
        aliases=("client_cert",),
        expandvars=True,
    )
    client_ssl_cert_key = ParameterLoader(
        PrimitiveParameter(None, element_type=(str, NoneType)),
        aliases=("client_cert_key",),
        expandvars=True,
    )
    proxy_servers = ParameterLoader(
        MapParameter(PrimitiveParameter(None, (str, NoneType))), expandvars=True
    )
    remote_connect_timeout_secs = ParameterLoader(PrimitiveParameter(9.15))
    remote_read_timeout_secs = ParameterLoader(PrimitiveParameter(60.0))
    remote_max_retries = ParameterLoader(PrimitiveParameter(3))
    remote_backoff_factor = ParameterLoader(PrimitiveParameter(1))

    add_anaconda_token = ParameterLoader(
        PrimitiveParameter(True), aliases=("add_binstar_token",)
    )

    _reporters = ParameterLoader(
        SequenceParameter(MapParameter(PrimitiveParameter("", element_type=str))),
        aliases=("reporters",),
    )

    ####################################################
    #               Channel Configuration              #
    ####################################################
    allow_non_channel_urls = ParameterLoader(PrimitiveParameter(False))
    _channel_alias = ParameterLoader(
        PrimitiveParameter(DEFAULT_CHANNEL_ALIAS, validation=channel_alias_validation),
        aliases=("channel_alias",),
        expandvars=True,
    )
    channel_priority = ParameterLoader(PrimitiveParameter(ChannelPriority.FLEXIBLE))
    _channels = ParameterLoader(
        SequenceParameter(PrimitiveParameter("", element_type=str), default=()),
        aliases=(
            "channels",
            "channel",
        ),
        expandvars=True,
    )  # channel for args.channel
    channel_settings = ParameterLoader(
        SequenceParameter(MapParameter(PrimitiveParameter("", element_type=str)))
    )
    _custom_channels = ParameterLoader(
        MapParameter(PrimitiveParameter("", element_type=str), DEFAULT_CUSTOM_CHANNELS),
        aliases=("custom_channels",),
        expandvars=True,
    )
    _custom_multichannels = ParameterLoader(
        MapParameter(SequenceParameter(PrimitiveParameter("", element_type=str))),
        aliases=("custom_multichannels",),
        expandvars=True,
    )
    _default_channels = ParameterLoader(
        SequenceParameter(PrimitiveParameter("", element_type=str), DEFAULT_CHANNELS),
        aliases=("default_channels",),
        expandvars=True,
    )
    _migrated_channel_aliases = ParameterLoader(
        SequenceParameter(PrimitiveParameter("", element_type=str)),
        aliases=("migrated_channel_aliases",),
    )
    migrated_custom_channels = ParameterLoader(
        MapParameter(PrimitiveParameter("", element_type=str)), expandvars=True
    )  # TODO: also take a list of strings
    override_channels_enabled = ParameterLoader(PrimitiveParameter(True))
    show_channel_urls = ParameterLoader(
        PrimitiveParameter(None, element_type=(bool, NoneType))
    )
    use_local = ParameterLoader(PrimitiveParameter(False))
    allowlist_channels = ParameterLoader(
        SequenceParameter(PrimitiveParameter("", element_type=str)),
        aliases=("whitelist_channels",),
        expandvars=True,
    )
    denylist_channels = ParameterLoader(
        SequenceParameter(PrimitiveParameter("", element_type=str)),
        expandvars=True,
    )
    restore_free_channel = ParameterLoader(PrimitiveParameter(False))
    repodata_fns = ParameterLoader(
        SequenceParameter(
            PrimitiveParameter("", element_type=str),
            ("current_repodata.json", REPODATA_FN),
        )
    )
    _use_only_tar_bz2 = ParameterLoader(
        PrimitiveParameter(None, element_type=(bool, NoneType)),
        aliases=("use_only_tar_bz2",),
    )

    always_softlink = ParameterLoader(PrimitiveParameter(False), aliases=("softlink",))
    always_copy = ParameterLoader(PrimitiveParameter(False), aliases=("copy",))
    always_yes = ParameterLoader(
        PrimitiveParameter(None, element_type=(bool, NoneType)), aliases=("yes",)
    )
    _debug = ParameterLoader(PrimitiveParameter(False), aliases=["debug"])
    _trace = ParameterLoader(PrimitiveParameter(False), aliases=["trace"])
    dev = ParameterLoader(PrimitiveParameter(False))
    dry_run = ParameterLoader(PrimitiveParameter(False))
    error_upload_url = ParameterLoader(PrimitiveParameter(ERROR_UPLOAD_URL))
    force = ParameterLoader(PrimitiveParameter(False))
    json = ParameterLoader(PrimitiveParameter(False))
    offline = ParameterLoader(PrimitiveParameter(False))
    quiet = ParameterLoader(PrimitiveParameter(False))
    ignore_pinned = ParameterLoader(PrimitiveParameter(False))
    report_errors = ParameterLoader(
        PrimitiveParameter(None, element_type=(bool, NoneType))
    )
    shortcuts = ParameterLoader(PrimitiveParameter(True))
    number_channel_notices = ParameterLoader(PrimitiveParameter(5, element_type=int))
    shortcuts = ParameterLoader(PrimitiveParameter(True))
    shortcuts_only = ParameterLoader(
        SequenceParameter(PrimitiveParameter("", element_type=str)), expandvars=True
    )
    _verbosity = ParameterLoader(
        PrimitiveParameter(0, element_type=int), aliases=("verbose", "verbosity")
    )
    experimental = ParameterLoader(SequenceParameter(PrimitiveParameter("", str)))
    no_lock = ParameterLoader(PrimitiveParameter(False))
    repodata_use_zst = ParameterLoader(PrimitiveParameter(True))
    envvars_force_uppercase = ParameterLoader(PrimitiveParameter(True))

    ####################################################
    #               Solver Configuration               #
    ####################################################
    deps_modifier = ParameterLoader(PrimitiveParameter(DepsModifier.NOT_SET))
    update_modifier = ParameterLoader(PrimitiveParameter(UpdateModifier.UPDATE_SPECS))
    sat_solver = ParameterLoader(PrimitiveParameter(SatSolverChoice.PYCOSAT))
    solver_ignore_timestamps = ParameterLoader(PrimitiveParameter(False))
    solver = ParameterLoader(
        PrimitiveParameter(DEFAULT_SOLVER),
        aliases=("experimental_solver",),
    )

    # # CLI-only
    # no_deps = ParameterLoader(PrimitiveParameter(NULL, element_type=(type(NULL), bool)))
    # # CLI-only
    # only_deps = ParameterLoader(PrimitiveParameter(NULL, element_type=(type(NULL), bool)))
    #
    # freeze_installed = ParameterLoader(PrimitiveParameter(False))
    # update_deps = ParameterLoader(PrimitiveParameter(False), aliases=('update_dependencies',))
    # update_specs = ParameterLoader(PrimitiveParameter(False))
    # update_all = ParameterLoader(PrimitiveParameter(False))

    force_remove = ParameterLoader(PrimitiveParameter(False))
    force_reinstall = ParameterLoader(PrimitiveParameter(False))

    target_prefix_override = ParameterLoader(PrimitiveParameter(""))

    unsatisfiable_hints = ParameterLoader(PrimitiveParameter(True))
    unsatisfiable_hints_check_depth = ParameterLoader(PrimitiveParameter(2))

    # conda_build
    bld_path = ParameterLoader(PrimitiveParameter(""))
    anaconda_upload = ParameterLoader(
        PrimitiveParameter(None, element_type=(bool, NoneType)),
        aliases=("binstar_upload",),
    )
    _croot = ParameterLoader(PrimitiveParameter(""), aliases=("croot",))
    _conda_build = ParameterLoader(
        MapParameter(PrimitiveParameter("", element_type=str)),
        aliases=("conda-build", "conda_build"),
    )

    ####################################################
    #               Plugin Configuration               #
    ####################################################

    no_plugins = ParameterLoader(PrimitiveParameter(NO_PLUGINS))

    def __init__(self, search_path=None, argparse_args=None, **kwargs):
        super().__init__(argparse_args=argparse_args)

        self._set_search_path(
            SEARCH_PATH if search_path is None else search_path,
            # for proper search_path templating when --name/--prefix is used
            CONDA_PREFIX=determine_target_prefix(self, argparse_args),
        )
        self._set_env_vars(APP_NAME)
        self._set_argparse_args(argparse_args)

    def post_build_validation(self):
        errors = []
        if self.client_ssl_cert_key and not self.client_ssl_cert:
            error = ValidationError(
                "client_ssl_cert",
                self.client_ssl_cert,
                "<<merged>>",
                "'client_ssl_cert' is required when 'client_ssl_cert_key' "
                "is defined",
            )
            errors.append(error)
        if self.always_copy and self.always_softlink:
            error = ValidationError(
                "always_copy",
                self.always_copy,
                "<<merged>>",
                "'always_copy' and 'always_softlink' are mutually exclusive. "
                "Only one can be set to 'True'.",
            )
            errors.append(error)
        return errors

    @property
    def plugin_manager(self) -> CondaPluginManager:
        """
        This is the preferred way of accessing the ``PluginManager`` object for this application
        and is located here to avoid problems with cyclical imports elsewhere in the code.
        """
        from ..plugins.manager import get_plugin_manager

        return get_plugin_manager()

    @cached_property
    def plugins(self) -> PluginConfig:
        """
        Preferred way of accessing settings introduced by the settings plugin hook
        """
        self.plugin_manager.load_settings()
        return PluginConfig(self.raw_data)

    @property
    def conda_build_local_paths(self):
        # does file system reads to make sure paths actually exist
        return tuple(
            unique(
                full_path
                for full_path in (
                    expand(d)
                    for d in (
                        self._croot,
                        self.bld_path,
                        self.conda_build.get("root-dir"),
                        join(self.root_prefix, "conda-bld"),
                        "~/conda-bld",
                    )
                    if d
                )
                if isdir(full_path)
            )
        )

    @property
    def conda_build_local_urls(self):
        return tuple(path_to_url(p) for p in self.conda_build_local_paths)

    @property
    def croot(self):
        """This is where source caches and work folders live"""
        if self._croot:
            return abspath(expanduser(self._croot))
        elif self.bld_path:
            return abspath(expanduser(self.bld_path))
        elif "root-dir" in self.conda_build:
            return abspath(expanduser(self.conda_build["root-dir"]))
        elif self.root_writable:
            return join(self.root_prefix, "conda-bld")
        else:
            return expand("~/conda-bld")

    @property
    def local_build_root(self):
        return self.croot

    @property
    def conda_build(self):
        # conda-build needs its config map to be mutable
        try:
            return self.__conda_build
        except AttributeError:
            self.__conda_build = __conda_build = dict(self._conda_build)
            return __conda_build

    @property
    def arch_name(self):
        m = platform.machine()
        if m in non_x86_machines:
            return m
        else:
            return _arch_names[self.bits]

    @property
    def platform(self):
        return _platform_map.get(sys.platform, "unknown")

    @property
    def default_threads(self) -> int | None:
        return self._default_threads or None

    @property
    def repodata_threads(self) -> int | None:
        return self._repodata_threads or self.default_threads

    @property
    def fetch_threads(self) -> int | None:
        """
        If both are not overriden (0), return experimentally-determined value of 5
        """
        if self._fetch_threads == 0 and self._default_threads == 0:
            return 5
        return self._fetch_threads or self.default_threads

    @property
    def verify_threads(self) -> int | None:
        if self._verify_threads:
            threads = self._verify_threads
        elif self.default_threads:
            threads = self.default_threads
        else:
            threads = 1
        return threads

    @property
    def execute_threads(self):
        if self._execute_threads:
            threads = self._execute_threads
        elif self.default_threads:
            threads = self.default_threads
        else:
            threads = 1
        return threads

    @property
    def subdir(self):
        if self._subdir:
            return self._subdir
        return self._native_subdir()

    @lru_cache(maxsize=None)
    def _native_subdir(self):
        m = platform.machine()
        if m in non_x86_machines:
            return f"{self.platform}-{m}"
        elif self.platform == "zos":
            return "zos-z"
        else:
            return "%s-%d" % (self.platform, self.bits)

    @property
    def subdirs(self):
        return self._subdirs or (self.subdir, "noarch")

    @memoizedproperty
    def known_subdirs(self):
        return frozenset((*KNOWN_SUBDIRS, *self.subdirs))

    @property
    def bits(self):
        if self.force_32bit:
            return 32
        else:
            return 8 * struct.calcsize("P")

    @property
    def root_writable(self):
        # rather than using conda.gateways.disk.test.prefix_is_writable
        # let's shortcut and assume the root prefix exists
        path = join(self.root_prefix, PREFIX_MAGIC_FILE)
        if isfile(path):
            try:
                fh = open(path, "a+")
            except OSError as e:
                log.debug(e)
                return False
            else:
                fh.close()
                return True
        return False

    @property
    def envs_dirs(self):
        return mockable_context_envs_dirs(
            self.root_writable, self.root_prefix, self._envs_dirs
        )

    @property
    def pkgs_dirs(self):
        if self._pkgs_dirs:
            return tuple(IndexedSet(expand(p) for p in self._pkgs_dirs))
        else:
            cache_dir_name = "pkgs32" if context.force_32bit else "pkgs"
            fixed_dirs = (
                self.root_prefix,
                join("~", ".conda"),
            )
            if on_win:
                fixed_dirs += (user_data_dir(APP_NAME, APP_NAME),)
            return tuple(
                IndexedSet(expand(join(p, cache_dir_name)) for p in (fixed_dirs))
            )

    @memoizedproperty
    def trash_dir(self):
        # TODO: this inline import can be cleaned up by moving pkgs_dir write detection logic
        from ..core.package_cache_data import PackageCacheData

        pkgs_dir = PackageCacheData.first_writable().pkgs_dir
        trash_dir = join(pkgs_dir, ".trash")
        from ..gateways.disk.create import mkdir_p

        mkdir_p(trash_dir)
        return trash_dir

    @property
    def default_prefix(self):
        if self.active_prefix:
            return self.active_prefix
        _default_env = os.getenv("CONDA_DEFAULT_ENV")
        if _default_env in (None, ROOT_ENV_NAME, "root"):
            return self.root_prefix
        elif os.sep in _default_env:
            return abspath(_default_env)
        else:
            for envs_dir in self.envs_dirs:
                default_prefix = join(envs_dir, _default_env)
                if isdir(default_prefix):
                    return default_prefix
        return join(self.envs_dirs[0], _default_env)

    @property
    def active_prefix(self):
        return os.getenv("CONDA_PREFIX")

    @property
    def shlvl(self):
        return int(os.getenv("CONDA_SHLVL", -1))

    @property
    def aggressive_update_packages(self):
        from ..models.match_spec import MatchSpec

        return tuple(MatchSpec(s) for s in self._aggressive_update_packages)

    @property
    def target_prefix(self):
        # used for the prefix that is the target of the command currently being executed
        # different from the active prefix, which is sometimes given by -p or -n command line flags
        return determine_target_prefix(self)

    @memoizedproperty
    def root_prefix(self):
        if self._root_prefix:
            return abspath(expanduser(self._root_prefix))
        else:
            return self.conda_prefix

    @property
    def conda_prefix(self):
        return abspath(sys.prefix)

    @property
    @deprecated(
        "23.9",
        "25.3",
        addendum="Please use `conda.base.context.context.conda_exe_vars_dict` instead",
    )
    def conda_exe(self):
        exe = "conda.exe" if on_win else "conda"
        return join(self.conda_prefix, BIN_DIRECTORY, exe)

    @property
    def av_data_dir(self):
        """Where critical artifact verification data (e.g., various public keys) can be found."""
        # TODO (AV): Find ways to make this user configurable?
        return join(self.conda_prefix, "etc", "conda")

    @property
    def signing_metadata_url_base(self):
        """Base URL for artifact verification signing metadata (*.root.json, key_mgr.json)."""
        if self._signing_metadata_url_base:
            return self._signing_metadata_url_base
        else:
            return None

    @property
    def conda_exe_vars_dict(self):
        """
        The vars can refer to each other if necessary since the dict is ordered.
        None means unset it.
        """
        if context.dev:
            return {
                "CONDA_EXE": sys.executable,
                # do not confuse with os.path.join, we are joining paths with ; or : delimiters
                "PYTHONPATH": os.pathsep.join(
                    (CONDA_SOURCE_ROOT, os.environ.get("PYTHONPATH", ""))
                ),
                "_CE_M": "-m",
                "_CE_CONDA": "conda",
                "CONDA_PYTHON_EXE": sys.executable,
            }
        else:
            exe = "conda.exe" if on_win else "conda"
            # I was going to use None to indicate a variable to unset, but that gets tricky with
            # error-on-undefined.
            return {
                "CONDA_EXE": os.path.join(sys.prefix, BIN_DIRECTORY, exe),
                "_CE_M": "",
                "_CE_CONDA": "",
                "CONDA_PYTHON_EXE": sys.executable,
            }

    @memoizedproperty
    def channel_alias(self):
        from ..models.channel import Channel

        location, scheme, auth, token = split_scheme_auth_token(self._channel_alias)
        return Channel(scheme=scheme, auth=auth, location=location, token=token)

    @property
    def migrated_channel_aliases(self):
        from ..models.channel import Channel

        return tuple(
            Channel(scheme=scheme, auth=auth, location=location, token=token)
            for location, scheme, auth, token in (
                split_scheme_auth_token(c) for c in self._migrated_channel_aliases
            )
        )

    @property
    def prefix_specified(self):
        return (
            self._argparse_args.get("prefix") is not None
            or self._argparse_args.get("name") is not None
        )

    @memoizedproperty
    def default_channels(self):
        # the format for 'default_channels' is a list of strings that either
        #   - start with a scheme
        #   - are meant to be prepended with channel_alias
        return self.custom_multichannels[DEFAULTS_CHANNEL_NAME]

    @memoizedproperty
    def custom_multichannels(self):
        from ..models.channel import Channel

        if (
            not on_win
            and self.subdir.startswith("win-")
            and self._default_channels == DEFAULT_CHANNELS_UNIX
        ):
            default_channels = list(DEFAULT_CHANNELS_WIN)
        else:
            default_channels = list(self._default_channels)

        if self.restore_free_channel:
            deprecated.topic(
                "24.9",
                "25.3",
                topic="Adding the 'free' channel as it existed prior to conda 4.7.",
                addendum="See "
                "https://docs.conda.io/projects/conda/en/stable/user-guide/configuration/free-channel.html "
                "for more details.",
                deprecation_type=FutureWarning,
            )
            default_channels.insert(1, "https://repo.anaconda.com/pkgs/free")

        reserved_multichannel_urls = {
            DEFAULTS_CHANNEL_NAME: default_channels,
            "local": self.conda_build_local_urls,
        }
        reserved_multichannels = {
            name: tuple(
                Channel.make_simple_channel(self.channel_alias, url) for url in urls
            )
            for name, urls in reserved_multichannel_urls.items()
        }
        custom_multichannels = {
            name: tuple(
                Channel.make_simple_channel(self.channel_alias, url) for url in urls
            )
            for name, urls in self._custom_multichannels.items()
        }
        return {
            name: channels
            for name, channels in (
                *custom_multichannels.items(),
                *reserved_multichannels.items(),  # order maters, reserved overrides custom
            )
        }

    @memoizedproperty
    def custom_channels(self):
        from ..models.channel import Channel

        return {
            channel.name: channel
            for channel in (
                *chain.from_iterable(
                    channel for channel in self.custom_multichannels.values()
                ),
                *(
                    Channel.make_simple_channel(self.channel_alias, url, name)
                    for name, url in self._custom_channels.items()
                ),
            )
        }

    @property
    def channels(self):
        local_add = ("local",) if self.use_local else ()
        if (
            self._argparse_args
            and "override_channels" in self._argparse_args
            and self._argparse_args["override_channels"]
        ):
            if not self.override_channels_enabled:
                from ..exceptions import OperationNotAllowed

                raise OperationNotAllowed("Overriding channels has been disabled.")
            elif not (
                self._argparse_args
                and "channel" in self._argparse_args
                and self._argparse_args["channel"]
            ):
                from ..exceptions import ArgumentError

                raise ArgumentError(
                    "At least one -c / --channel flag must be supplied when using "
                    "--override-channels."
                )
            else:
                return tuple(IndexedSet((*local_add, *self._argparse_args["channel"])))

        # add 'defaults' channel when necessary if --channel is given via the command line
        if self._argparse_args and "channel" in self._argparse_args:
            # TODO: it's args.channel right now, not channels
            argparse_channels = tuple(self._argparse_args["channel"] or ())
            # Add condition to make sure that sure that we add the 'defaults'
            # channel only when no channels are defined in condarc
            # We needs to get the config_files and then check that they
            # don't define channels
            channel_in_config_files = any(
                "channels" in context.raw_data[rc_file].keys()
                for rc_file in self.config_files
            )
            if argparse_channels and not channel_in_config_files:
                _warn_defaults_deprecation()
                return tuple(
                    IndexedSet((*local_add, *argparse_channels, DEFAULTS_CHANNEL_NAME))
                )
        if self._channels:
            _channels = self._channels
        else:
            _warn_defaults_deprecation()
            _channels = [DEFAULTS_CHANNEL_NAME]
        return tuple(IndexedSet((*local_add, *_channels)))

    @property
    def config_files(self):
        return tuple(
            path
            for path in context.collect_all()
            if path not in ("envvars", "cmd_line")
        )

    @property
    def use_only_tar_bz2(self):
        # we avoid importing this at the top to avoid PATH issues.  Ensure that this
        #    is only called when use_only_tar_bz2 is first called.
        import conda_package_handling.api

        return (
            not conda_package_handling.api.libarchive_enabled
        ) or self._use_only_tar_bz2

    @property
    def binstar_upload(self):
        # backward compatibility for conda-build
        return self.anaconda_upload

    @property
    def trace(self) -> bool:
        """Alias for context.verbosity >=4."""
        return self.verbosity >= 4

    @property
    def debug(self) -> bool:
        """Alias for context.verbosity >=3."""
        return self.verbosity >= 3

    @property
    def info(self) -> bool:
        """Alias for context.verbosity >=2."""
        return self.verbosity >= 2

    @property
    def verbose(self) -> bool:
        """Alias for context.verbosity >=1."""
        return self.verbosity >= 1

    @property
    def verbosity(self) -> int:
        """Verbosity level.

        For cleaner and readable code it is preferable to use the following alias properties:
            context.trace
            context.debug
            context.info
            context.verbose
            context.log_level
        """
        #                   0 → logging.WARNING, standard output
        #           -v    = 1 → logging.WARNING, detailed output
        #           -vv   = 2 → logging.INFO
        # --debug = -vvv  = 3 → logging.DEBUG
        # --trace = -vvvv = 4 → conda.gateways.logging.TRACE
        if self._trace:
            return 4
        elif self._debug:
            return 3
        else:
            return self._verbosity

    @property
    def log_level(self) -> int:
        """Map context.verbosity to logging level."""
        if 4 < self.verbosity:
            return logging.NOTSET  # 0
        elif 3 < self.verbosity <= 4:
            return TRACE  # 5
        elif 2 < self.verbosity <= 3:
            return logging.DEBUG  # 10
        elif 1 < self.verbosity <= 2:
            return logging.INFO  # 20
        else:
            return logging.WARNING  # 30

    def solver_user_agent(self):
        user_agent = f"solver/{self.solver}"
        try:
            solver_backend = self.plugin_manager.get_cached_solver_backend()
            # Solver.user_agent has to be a static or class method
            user_agent += f" {solver_backend.user_agent()}"
        except Exception as exc:
            log.debug(
                "User agent could not be fetched from solver class '%s'.",
                self.solver,
                exc_info=exc,
            )
        return user_agent

    @memoizedproperty
    def user_agent(self):
        builder = [f"conda/{CONDA_VERSION} requests/{self.requests_version}"]
        builder.append("{}/{}".format(*self.python_implementation_name_version))
        builder.append("{}/{}".format(*self.platform_system_release))
        builder.append("{}/{}".format(*self.os_distribution_name_version))
        if self.libc_family_version[0]:
            builder.append("{}/{}".format(*self.libc_family_version))
        if self.solver != "classic":
            builder.append(self.solver_user_agent())
        return " ".join(builder)

    @contextmanager
    def _override(self, key, value):
        """
        TODO: This might be broken in some ways. Unsure what happens if the `old`
        value is a property and gets set to a new value. Or if the new value
        overrides the validation logic on the underlying ParameterLoader instance.

        Investigate and implement in a safer way.
        """
        old = getattr(self, key)
        setattr(self, key, value)
        try:
            yield
        finally:
            setattr(self, key, old)

    @memoizedproperty
    def requests_version(self):
        # used in User-Agent as "requests/<version>"
        # if unable to detect a version we expect "requests/unknown"
        try:
            from requests import __version__ as requests_version
        except ImportError as err:
            # ImportError: requests is not installed
            log.error("Unable to import requests: %s", err)
            requests_version = "unknown"
        except Exception as err:
            log.error("Error importing requests: %s", err)
            requests_version = "unknown"
        return requests_version

    @memoizedproperty
    def python_implementation_name_version(self):
        # CPython, Jython
        # '2.7.14'
        return platform.python_implementation(), platform.python_version()

    @memoizedproperty
    def platform_system_release(self):
        # tuple of system name and release version
        #
        # `uname -s` Linux, Windows, Darwin, Java
        #
        # `uname -r`
        # '17.4.0' for macOS
        # '10' or 'NT' for Windows
        return platform.system(), platform.release()

    @memoizedproperty
    def os_distribution_name_version(self):
        # tuple of os distribution name and version
        # e.g.
        #   'debian', '9'
        #   'OSX', '10.13.6'
        #   'Windows', '10.0.17134'
        platform_name = self.platform_system_release[0]
        if platform_name == "Linux":
            try:
                import distro

                distinfo = distro.id(), distro.version(best=True)
            except Exception as e:
                log.debug("%r", e, exc_info=True)
                distinfo = ("Linux", "unknown")
            distribution_name, distribution_version = distinfo[0], distinfo[1]
        elif platform_name == "Darwin":
            distribution_name = "OSX"
            distribution_version = platform.mac_ver()[0]
        else:
            distribution_name = platform.system()
            distribution_version = platform.version()
        return distribution_name, distribution_version

    @memoizedproperty
    def libc_family_version(self):
        # tuple of lic_family and libc_version
        # None, None if not on Linux
        libc_family, libc_version = linux_get_libc_version()
        return libc_family, libc_version

    @memoizedproperty
    @unique_sequence_map(unique_key="backend")
    def reporters(self) -> tuple[Mapping[str, str]]:
        """
        Determine the value of reporters based on other settings and the ``self._reporters``
        value itself.
        """
        if not self._reporters:
            return (
                {
                    "backend": "json" if self.json else "console",
                    "output": "stdout",
                    "verbosity": self.verbosity,
                    "quiet": self.quiet,
                },
            )

        return self._reporters

    @property
    def category_map(self):
        return {
            "Channel Configuration": (
                "channels",
                "channel_alias",
                "channel_settings",
                "default_channels",
                "override_channels_enabled",
                "allowlist_channels",
                "denylist_channels",
                "custom_channels",
                "custom_multichannels",
                "migrated_channel_aliases",
                "migrated_custom_channels",
                "add_anaconda_token",
                "allow_non_channel_urls",
                "restore_free_channel",
                "repodata_fns",
                "use_only_tar_bz2",
                "repodata_threads",
                "fetch_threads",
                "experimental",
                "no_lock",
                "repodata_use_zst",
            ),
            "Basic Conda Configuration": (  # TODO: Is there a better category name here?
                "envs_dirs",
                "pkgs_dirs",
                "default_threads",
            ),
            "Network Configuration": (
                "client_ssl_cert",
                "client_ssl_cert_key",
                "local_repodata_ttl",
                "offline",
                "proxy_servers",
                "remote_connect_timeout_secs",
                "remote_max_retries",
                "remote_backoff_factor",
                "remote_read_timeout_secs",
                "ssl_verify",
            ),
            "Solver Configuration": (
                "aggressive_update_packages",
                "auto_update_conda",
                "channel_priority",
                "create_default_packages",
                "disallowed_packages",
                "force_reinstall",
                "pinned_packages",
                "pip_interop_enabled",
                "track_features",
                "solver",
            ),
            "Package Linking and Install-time Configuration": (
                "allow_softlinks",
                "always_copy",
                "always_softlink",
                "path_conflict",
                "rollback_enabled",
                "safety_checks",
                "extra_safety_checks",
                "signing_metadata_url_base",
                "shortcuts",
                "shortcuts_only",
                "non_admin_enabled",
                "separate_format_cache",
                "verify_threads",
                "execute_threads",
            ),
            "Conda-build Configuration": (
                "bld_path",
                "croot",
                "anaconda_upload",
                "conda_build",
            ),
            "Output, Prompt, and Flow Control Configuration": (
                "always_yes",
                "auto_activate_base",
                "auto_stack",
                "changeps1",
                "env_prompt",
                "json",
                "notify_outdated_conda",
                "quiet",
                "report_errors",
                "show_channel_urls",
                "verbosity",
                "unsatisfiable_hints",
                "unsatisfiable_hints_check_depth",
                "number_channel_notices",
                "envvars_force_uppercase",
            ),
            "CLI-only": (
                "deps_modifier",
                "update_modifier",
                "force",
                "force_remove",
                "clobber",
                "dry_run",
                "download_only",
                "ignore_pinned",
                "use_index_cache",
                "use_local",
            ),
            "Hidden and Undocumented": (
                "allow_cycles",  # allow cyclical dependencies, or raise
                "allow_conda_downgrades",
                "add_pip_as_python_dependency",
                "debug",
                "trace",
                "dev",
                "default_python",
                "enable_private_envs",
                "error_upload_url",  # should remain undocumented
                "force_32bit",
                "root_prefix",
                "sat_solver",
                "solver_ignore_timestamps",
                "subdir",
                "subdirs",
                # https://conda.io/docs/config.html#disable-updating-of-dependencies-update-dependencies # NOQA
                # I don't think this documentation is correct any longer. # NOQA
                "target_prefix_override",
                # used to override prefix rewriting, for e.g. building docker containers or RPMs  # NOQA
                "register_envs",
                # whether to add the newly created prefix to ~/.conda/environments.txt
                "reporters",
            ),
            "Plugin Configuration": ("no_plugins",),
        }

    def get_descriptions(self):
        return self.description_map

    @memoizedproperty
    def description_map(self):
        return frozendict(
            add_anaconda_token=dals(
                """
                In conjunction with the anaconda command-line client (installed with
                `conda install anaconda-client`), and following logging into an Anaconda
                Server API site using `anaconda login`, automatically apply a matching
                private token to enable access to private packages and channels.
                """
            ),
            # add_pip_as_python_dependency=dals(
            #     """
            #     Add pip, wheel and setuptools as dependencies of python. This ensures pip,
            #     wheel and setuptools will always be installed any time python is installed.
            #     """
            # ),
            aggressive_update_packages=dals(
                """
                A list of packages that, if installed, are always updated to the latest possible
                version.
                """
            ),
            allow_non_channel_urls=dals(
                """
                Warn, but do not fail, when conda detects a channel url is not a valid channel.
                """
            ),
            allow_softlinks=dals(
                """
                When allow_softlinks is True, conda uses hard-links when possible, and soft-links
                (symlinks) when hard-links are not possible, such as when installing on a
                different filesystem than the one that the package cache is on. When
                allow_softlinks is False, conda still uses hard-links when possible, but when it
                is not possible, conda copies files. Individual packages can override
                this setting, specifying that certain files should never be soft-linked (see the
                no_link option in the build recipe documentation).
                """
            ),
            always_copy=dals(
                """
                Register a preference that files be copied into a prefix during install rather
                than hard-linked.
                """
            ),
            always_softlink=dals(
                """
                Register a preference that files be soft-linked (symlinked) into a prefix during
                install rather than hard-linked. The link source is the 'pkgs_dir' package cache
                from where the package is being linked. WARNING: Using this option can result in
                corruption of long-lived conda environments. Package caches are *caches*, which
                means there is some churn and invalidation. With this option, the contents of
                environments can be switched out (or erased) via operations on other environments.
                """
            ),
            always_yes=dals(
                """
                Automatically choose the 'yes' option whenever asked to proceed with a conda
                operation, such as when running `conda install`.
                """
            ),
            anaconda_upload=dals(
                """
                Automatically upload packages built with conda build to anaconda.org.
                """
            ),
            auto_activate_base=dals(
                """
                Automatically activate the base environment during shell initialization.
                """
            ),
            auto_update_conda=dals(
                """
                Automatically update conda when a newer or higher priority version is detected.
                """
            ),
            auto_stack=dals(
                """
                Implicitly use --stack when using activate if current level of nesting
                (as indicated by CONDA_SHLVL environment variable) is less than or equal to
                specified value. 0 or false disables automatic stacking, 1 or true enables
                it for one level.
                """
            ),
            bld_path=dals(
                """
                The location where conda-build will put built packages. Same as 'croot', but
                'croot' takes precedence when both are defined. Also used in construction of the
                'local' multichannel.
                """
            ),
            changeps1=dals(
                """
                When using activate, change the command prompt ($PS1) to include the
                activated environment.
                """
            ),
            channel_alias=dals(
                """
                The prepended url location to associate with channel names.
                """
            ),
            channel_priority=dals(
                """
                Accepts values of 'strict', 'flexible', and 'disabled'. The default value
                is 'flexible'. With strict channel priority, packages in lower priority channels
                are not considered if a package with the same name appears in a higher
                priority channel. With flexible channel priority, the solver may reach into
                lower priority channels to fulfill dependencies, rather than raising an
                unsatisfiable error. With channel priority disabled, package version takes
                precedence, and the configured priority of channels is used only to break ties.
                In previous versions of conda, this parameter was configured as either True or
                False. True is now an alias to 'flexible'.
                """
            ),
            channels=dals(
                """
                The list of conda channels to include for relevant operations.
                """
            ),
            channel_settings=dals(
                """
                A list of mappings that allows overriding certain settings for a single channel.
                Each list item should include at least the "channel" key and the setting you would
                like to override.
                """
            ),
            client_ssl_cert=dals(
                """
                A path to a single file containing a private key and certificate (e.g. .pem
                file). Alternately, use client_ssl_cert_key in conjunction with client_ssl_cert
                for individual files.
                """
            ),
            client_ssl_cert_key=dals(
                """
                Used in conjunction with client_ssl_cert for a matching key file.
                """
            ),
            # clobber=dals(
            #     """
            #     Allow clobbering of overlapping file paths within packages, and suppress
            #     related warnings. Overrides the path_conflict configuration value when
            #     set to 'warn' or 'prevent'.
            #     """
            # ),
            # TODO: add shortened link to docs for conda_build at See https://conda.io/docs/user-guide/configuration/use-condarc.html#conda-build-configuration  # NOQA
            conda_build=dals(
                """
                General configuration parameters for conda-build.
                """
            ),
            # TODO: This is a bad parameter name. Consider an alternate.
            create_default_packages=dals(
                """
                Packages that are by default added to a newly created environments.
                """
            ),
            croot=dals(
                """
                The location where conda-build will put built packages. Same as 'bld_path', but
                'croot' takes precedence when both are defined. Also used in construction of the
                'local' multichannel.
                """
            ),
            custom_channels=dals(
                """
                A map of key-value pairs where the key is a channel name and the value is
                a channel location. Channels defined here override the default
                'channel_alias' value. The channel name (key) is not included in the channel
                location (value).  For example, to override the location of the 'conda-forge'
                channel where the url to repodata is
                https://anaconda-repo.dev/packages/conda-forge/linux-64/repodata.json, add an
                entry 'conda-forge: https://anaconda-repo.dev/packages'.
                """
            ),
            custom_multichannels=dals(
                """
                A multichannel is a metachannel composed of multiple channels. The two reserved
                multichannels are 'defaults' and 'local'. The 'defaults' multichannel is
                customized using the 'default_channels' parameter. The 'local'
                multichannel is a list of file:// channel locations where conda-build stashes
                successfully-built packages.  Other multichannels can be defined with
                custom_multichannels, where the key is the multichannel name and the value is
                a list of channel names and/or channel urls.
                """
            ),
            default_channels=dals(
                """
                The list of channel names and/or urls used for the 'defaults' multichannel.
                """
            ),
            # default_python=dals(
            #     """
            #     specifies the default major & minor version of Python to be used when
            #     building packages with conda-build. Also used to determine the major
            #     version of Python (2/3) to be used in new environments. Defaults to
            #     the version used by conda itself.
            #     """
            # ),
            default_threads=dals(
                """
                Threads to use by default for parallel operations.  Default is None,
                which allows operations to choose themselves.  For more specific
                control, see the other *_threads parameters:
                    * repodata_threads - for fetching/loading repodata
                    * verify_threads - for verifying package contents in transactions
                    * execute_threads - for carrying out the unlinking and linking steps
                """
            ),
            disallowed_packages=dals(
                """
                Package specifications to disallow installing. The default is to allow
                all packages.
                """
            ),
            download_only=dals(
                """
                Solve an environment and ensure package caches are populated, but exit
                prior to unlinking and linking packages into the prefix
                """
            ),
            envs_dirs=dals(
                """
                The list of directories to search for named environments. When creating a new
                named environment, the environment will be placed in the first writable
                location.
                """
            ),
            env_prompt=dals(
                """
                Template for prompt modification based on the active environment. Currently
                supported template variables are '{prefix}', '{name}', and '{default_env}'.
                '{prefix}' is the absolute path to the active environment. '{name}' is the
                basename of the active environment prefix. '{default_env}' holds the value
                of '{name}' if the active environment is a conda named environment ('-n'
                flag), or otherwise holds the value of '{prefix}'. Templating uses python's
                str.format() method.
                """
            ),
            execute_threads=dals(
                """
                Threads to use when performing the unlink/link transaction.  When not set,
                defaults to 1.  This step is pretty strongly I/O limited, and you may not
                see much benefit here.
                """
            ),
            fetch_threads=dals(
                """
                Threads to use when downloading packages.  When not set,
                defaults to None, which uses the default ThreadPoolExecutor behavior.
                """
            ),
            force_reinstall=dals(
                """
                Ensure that any user-requested package for the current operation is uninstalled
                and reinstalled, even if that package already exists in the environment.
                """
            ),
            # force=dals(
            #     """
            #     Override any of conda's objections and safeguards for installing packages and
            #     potentially breaking environments. Also re-installs the package, even if the
            #     package is already installed. Implies --no-deps.
            #     """
            # ),
            # force_32bit=dals(
            #     """
            #     CONDA_FORCE_32BIT should only be used when running conda-build (in order
            #     to build 32-bit packages on a 64-bit system).  We don't want to mention it
            #     in the documentation, because it can mess up a lot of things.
            #     """
            # ),
            json=dals(
                """
                Ensure all output written to stdout is structured json.
                """
            ),
            local_repodata_ttl=dals(
                """
                For a value of False or 0, always fetch remote repodata (HTTP 304 responses
                respected). For a value of True or 1, respect the HTTP Cache-Control max-age
                header. Any other positive integer values is the number of seconds to locally
                cache repodata before checking the remote server for an update.
                """
            ),
            migrated_channel_aliases=dals(
                """
                A list of previously-used channel_alias values. Useful when switching between
                different Anaconda Repository instances.
                """
            ),
            migrated_custom_channels=dals(
                """
                A map of key-value pairs where the key is a channel name and the value is
                the previous location of the channel.
                """
            ),
            # no_deps=dals(
            #     """
            #     Do not install, update, remove, or change dependencies. This WILL lead to broken
            #     environments and inconsistent behavior. Use at your own risk.
            #     """
            # ),
            no_plugins=dals(
                """
                Disable all currently-registered plugins, except built-in conda plugins.
                """
            ),
            non_admin_enabled=dals(
                """
                Allows completion of conda's create, install, update, and remove operations, for
                non-privileged (non-root or non-administrator) users.
                """
            ),
            notify_outdated_conda=dals(
                """
                Notify if a newer version of conda is detected during a create, install, update,
                or remove operation.
                """
            ),
            offline=dals(
                """
                Restrict conda to cached download content and file:// based urls.
                """
            ),
            override_channels_enabled=dals(
                """
                Permit use of the --override-channels command-line flag.
                """
            ),
            path_conflict=dals(
                """
                The method by which conda handle's conflicting/overlapping paths during a
                create, install, or update operation. The value must be one of 'clobber',
                'warn', or 'prevent'. The '--clobber' command-line flag or clobber
                configuration parameter overrides path_conflict set to 'prevent'.
                """
            ),
            pinned_packages=dals(
                """
                A list of package specs to pin for every environment resolution.
                This parameter is in BETA, and its behavior may change in a future release.
                """
            ),
            pip_interop_enabled=dals(
                """
                Allow the conda solver to interact with non-conda-installed python packages.
                """
            ),
            pkgs_dirs=dals(
                """
                The list of directories where locally-available packages are linked from at
                install time. Packages not locally available are downloaded and extracted
                into the first writable directory.
                """
            ),
            proxy_servers=dals(
                """
                A mapping to enable proxy settings. Keys can be either (1) a scheme://hostname
                form, which will match any request to the given scheme and exact hostname, or
                (2) just a scheme, which will match requests to that scheme. Values are are
                the actual proxy server, and are of the form
                'scheme://[user:password@]host[:port]'. The optional 'user:password' inclusion
                enables HTTP Basic Auth with your proxy.
                """
            ),
            quiet=dals(
                """
                Disable progress bar display and other output.
                """
            ),
            reporters=dals(
                """
                A list of mappings that allow the configuration of one or more output streams
                (e.g. stdout or file).
                """
            ),
            remote_connect_timeout_secs=dals(
                """
                The number seconds conda will wait for your client to establish a connection
                to a remote url resource.
                """
            ),
            remote_max_retries=dals(
                """
                The maximum number of retries each HTTP connection should attempt.
                """
            ),
            remote_backoff_factor=dals(
                """
                The factor determines the time HTTP connection should wait for attempt.
                """
            ),
            remote_read_timeout_secs=dals(
                """
                Once conda has connected to a remote resource and sent an HTTP request, the
                read timeout is the number of seconds conda will wait for the server to send
                a response.
                """
            ),
            repodata_threads=dals(
                """
                Threads to use when downloading and reading repodata.  When not set,
                defaults to None, which uses the default ThreadPoolExecutor behavior.
                """
            ),
            report_errors=dals(
                """
                Opt in, or opt out, of automatic error reporting to core maintainers. Error
                reports are anonymous, with only the error stack trace and information given
                by `conda info` being sent.
                """
            ),
            restore_free_channel=dals(
                """"
                Add the "free" channel back into defaults, behind "main" in priority. The "free"
                channel was removed from the collection of default channels in conda 4.7.0.
                """
            ),
            rollback_enabled=dals(
                """
                Should any error occur during an unlink/link transaction, revert any disk
                mutations made to that point in the transaction.
                """
            ),
            safety_checks=dals(
                """
                Enforce available safety guarantees during package installation.
                The value must be one of 'enabled', 'warn', or 'disabled'.
                """
            ),
            separate_format_cache=dals(
                """
                Treat .tar.bz2 files as different from .conda packages when
                filenames are otherwise similar. This defaults to False, so
                that your package cache doesn't churn when rolling out the new
                package format. If you'd rather not assume that a .tar.bz2 and
                .conda from the same place represent the same content, set this
                to True.
                """
            ),
            extra_safety_checks=dals(
                """
                Spend extra time validating package contents.  Currently, runs sha256 verification
                on every file within each package during installation.
                """
            ),
            signing_metadata_url_base=dals(
                """
                Base URL for obtaining trust metadata updates (i.e., the `*.root.json` and
                `key_mgr.json` files) used to verify metadata and (eventually) package signatures.
                """
            ),
            shortcuts=dals(
                """
                Allow packages to create OS-specific shortcuts (e.g. in the Windows Start
                Menu) at install time.
                """
            ),
            shortcuts_only=dals(
                """
                Create shortcuts only for the specified package names.
                """
            ),
            show_channel_urls=dals(
                """
                Show channel URLs when displaying what is going to be downloaded.
                """
            ),
            ssl_verify=dals(
                """
                Conda verifies SSL certificates for HTTPS requests, just like a web
                browser. By default, SSL verification is enabled, and conda operations will
                fail if a required url's certificate cannot be verified. Setting ssl_verify to
                False disables certification verification. The value for ssl_verify can also
                be (1) a path to a CA bundle file, (2) a path to a directory containing
                certificates of trusted CA, or (3) 'truststore' to use the
                operating system certificate store.
                """
            ),
            track_features=dals(
                """
                A list of features that are tracked by default. An entry here is similar to
                adding an entry to the create_default_packages list.
                """
            ),
            repodata_fns=dals(
                """
                Specify filenames for repodata fetching. The default is ('current_repodata.json',
                'repodata.json'), which tries a subset of the full index containing only the
                latest version for each package, then falls back to repodata.json.  You may
                want to specify something else to use an alternate index that has been reduced
                somehow.
                """
            ),
            use_index_cache=dals(
                """
                Use cache of channel index files, even if it has expired.
                """
            ),
            use_only_tar_bz2=dals(
                """
                A boolean indicating that only .tar.bz2 conda packages should be downloaded.
                This is forced to True if conda-build is installed and older than 3.18.3,
                because older versions of conda break when conda feeds it the new file format.
                """
            ),
            verbosity=dals(
                """
                Sets output log level. 0 is warn. 1 is info. 2 is debug. 3 is trace.
                """
            ),
            verify_threads=dals(
                """
                Threads to use when performing the transaction verification step.  When not set,
                defaults to 1.
                """
            ),
            allowlist_channels=dals(
                """
                The exclusive list of channels allowed to be used on the system. Use of any
                other channels will result in an error. If conda-build channels are to be
                allowed, along with the --use-local command line flag, be sure to include the
                'local' channel in the list. If the list is empty or left undefined, no
                channel exclusions will be enforced.
                """
            ),
            denylist_channels=dals(
                """
                The list of channels that are denied to be used on the system. Use of any
                of these channels will result in an error. If conda-build channels are to be
                allowed, along with the --use-local command line flag, be sure to not include
                the 'local' channel in the list. If the list is empty or left undefined, no
                channel exclusions will be enforced.
                """
            ),
            unsatisfiable_hints=dals(
                """
                A boolean to determine if conda should find conflicting packages in the case
                of a failed install.
                """
            ),
            unsatisfiable_hints_check_depth=dals(
                """
                An integer that specifies how many levels deep to search for unsatisfiable
                dependencies. If this number is 1 it will complete the unsatisfiable hints
                fastest (but perhaps not the most complete). The higher this number, the
                longer the generation of the unsat hint will take. Defaults to 3.
                """
            ),
            solver=dals(
                """
                A string to choose between the different solver logics implemented in
                conda. A solver logic takes care of turning your requested packages into a
                list of specs to add and/or remove from a given environment, based on their
                dependencies and specified constraints.
                """
            ),
            number_channel_notices=dals(
                """
                Sets the number of channel notices to be displayed when running commands
                the "install", "create", "update", "env create", and "env update" . Defaults
                to 5. In order to completely suppress channel notices, set this to 0.
                """
            ),
            experimental=dals(
                """
                List of experimental features to enable.
                """
            ),
            no_lock=dals(
                """
                Disable index cache lock (defaults to enabled).
                """
            ),
            repodata_use_zst=dals(
                """
                Disable check for `repodata.json.zst`; use `repodata.json` only.
                """
            ),
            envvars_force_uppercase=dals(
                """
                Force uppercase for new environment variable names. Defaults to True.
                """
            ),
        )


def reset_context(search_path=SEARCH_PATH, argparse_args=None):
    global context

    # reset plugin config params
    remove_all_plugin_settings()

    context.__init__(search_path, argparse_args)
    context.__dict__.pop("_Context__conda_build", None)
    from ..models.channel import Channel

    Channel._reset_state()
    # need to import here to avoid circular dependency
    return context


@contextmanager
def fresh_context(env=None, search_path=SEARCH_PATH, argparse_args=None, **kwargs):
    if env or kwargs:
        old_env = os.environ.copy()
        os.environ.update(env or {})
        os.environ.update(kwargs)
    yield reset_context(search_path=search_path, argparse_args=argparse_args)
    if env or kwargs:
        os.environ.clear()
        os.environ.update(old_env)
        reset_context()


class ContextStackObject:
    def __init__(self, search_path=SEARCH_PATH, argparse_args=None):
        self.set_value(search_path, argparse_args)

    def set_value(self, search_path=SEARCH_PATH, argparse_args=None):
        self.search_path = search_path
        self.argparse_args = argparse_args

    def apply(self):
        reset_context(self.search_path, self.argparse_args)


class ContextStack:
    def __init__(self):
        self._stack = [ContextStackObject() for _ in range(3)]
        self._stack_idx = 0
        self._last_search_path = None
        self._last_argparse_args = None

    def push(self, search_path, argparse_args):
        self._stack_idx += 1
        old_len = len(self._stack)
        if self._stack_idx >= old_len:
            self._stack.extend([ContextStackObject() for _ in range(old_len)])
        self._stack[self._stack_idx].set_value(search_path, argparse_args)
        self.apply()

    def apply(self):
        if (
            self._last_search_path != self._stack[self._stack_idx].search_path
            or self._last_argparse_args != self._stack[self._stack_idx].argparse_args
        ):
            # Expensive:
            self._stack[self._stack_idx].apply()
            self._last_search_path = self._stack[self._stack_idx].search_path
            self._last_argparse_args = self._stack[self._stack_idx].argparse_args

    def pop(self):
        self._stack_idx -= 1
        self._stack[self._stack_idx].apply()

    def replace(self, search_path, argparse_args):
        self._stack[self._stack_idx].set_value(search_path, argparse_args)
        self._stack[self._stack_idx].apply()


context_stack = ContextStack()


def stack_context(pushing, search_path=SEARCH_PATH, argparse_args=None):
    if pushing:
        # Fast
        context_stack.push(search_path, argparse_args)
    else:
        # Slow
        context_stack.pop()


# Default means "The configuration when there are no condarc files present". It is
# all the settings and defaults that are built in to the code and *not* the default
# value of search_path=SEARCH_PATH. It means search_path=().
def stack_context_default(pushing, argparse_args=None):
    return stack_context(pushing, search_path=(), argparse_args=argparse_args)


def replace_context(pushing=None, search_path=SEARCH_PATH, argparse_args=None):
    # pushing arg intentionally not used here, but kept for API compatibility
    return context_stack.replace(search_path, argparse_args)


def replace_context_default(pushing=None, argparse_args=None):
    # pushing arg intentionally not used here, but kept for API compatibility
    return context_stack.replace(search_path=(), argparse_args=argparse_args)


# Tests that want to only declare 'I support the project-wide default for how to
# manage stacking of contexts'. Tests that are known to be careful with context
# can use `replace_context_default` which might be faster, though it should
# be a stated goal to set conda_tests_ctxt_mgmt_def_pol to replace_context_default
# and not to stack_context_default.
conda_tests_ctxt_mgmt_def_pol = replace_context_default


def env_name(prefix):
    # counter part to `locate_prefix_by_name()` below
    if not prefix:
        return None
    if paths_equal(prefix, context.root_prefix):
        return ROOT_ENV_NAME
    maybe_envs_dir, maybe_name = path_split(prefix)
    for envs_dir in context.envs_dirs:
        if paths_equal(envs_dir, maybe_envs_dir):
            return maybe_name
    return prefix


def locate_prefix_by_name(name, envs_dirs=None):
    """Find the location of a prefix given a conda env name.  If the location does not exist, an
    error is raised.
    """
    assert name
    if name in (ROOT_ENV_NAME, "root"):
        return context.root_prefix
    if envs_dirs is None:
        envs_dirs = context.envs_dirs
    for envs_dir in envs_dirs:
        if not isdir(envs_dir):
            continue
        prefix = join(envs_dir, name)
        if isdir(prefix):
            return abspath(prefix)

    from ..exceptions import EnvironmentNameNotFound

    raise EnvironmentNameNotFound(name)


def validate_prefix_name(prefix_name: str, ctx: Context, allow_base=True) -> str:
    """Run various validations to make sure prefix_name is valid"""
    from ..exceptions import CondaValueError

    if PREFIX_NAME_DISALLOWED_CHARS.intersection(prefix_name):
        raise CondaValueError(
            dals(
                f"""
                Invalid environment name: {prefix_name!r}
                Characters not allowed: {PREFIX_NAME_DISALLOWED_CHARS}
                If you are specifying a path to an environment, the `-p`
                flag should be used instead.
                """
            )
        )

    if prefix_name in (ROOT_ENV_NAME, "root"):
        if allow_base:
            return ctx.root_prefix
        else:
            raise CondaValueError(
                "Use of 'base' as environment name is not allowed here."
            )

    else:
        from ..exceptions import EnvironmentNameNotFound

        try:
            return locate_prefix_by_name(prefix_name)
        except EnvironmentNameNotFound:
            return join(_first_writable_envs_dir(), prefix_name)


def determine_target_prefix(ctx, args=None):
    """Get the prefix to operate in.  The prefix may not yet exist.

    Args:
        ctx: the context of conda
        args: the argparse args from the command line

    Returns: the prefix
    Raises: CondaEnvironmentNotFoundError if the prefix is invalid
    """
    argparse_args = args or ctx._argparse_args
    try:
        prefix_name = argparse_args.name
    except AttributeError:
        prefix_name = None
    try:
        prefix_path = argparse_args.prefix
    except AttributeError:
        prefix_path = None

    if prefix_name is not None and not prefix_name.strip():  # pragma: no cover
        from ..exceptions import ArgumentError

        raise ArgumentError("Argument --name requires a value.")

    if prefix_path is not None and not prefix_path.strip():  # pragma: no cover
        from ..exceptions import ArgumentError

        raise ArgumentError("Argument --prefix requires a value.")

    if prefix_name is None and prefix_path is None:
        return ctx.default_prefix
    elif prefix_path is not None:
        return expand(prefix_path)
    else:
        return validate_prefix_name(prefix_name, ctx=ctx)


def _first_writable_envs_dir():
    # Calling this function will *create* an envs directory if one does not already
    # exist. Any caller should intend to *use* that directory for *writing*, not just reading.
    for envs_dir in context.envs_dirs:
        if envs_dir == os.devnull:
            continue

        # The magic file being used here could change in the future.  Don't write programs
        # outside this code base that rely on the presence of this file.
        # This value is duplicated in conda.gateways.disk.create.create_envs_directory().
        envs_dir_magic_file = join(envs_dir, ".conda_envs_dir_test")

        if isfile(envs_dir_magic_file):
            try:
                open(envs_dir_magic_file, "a").close()
                return envs_dir
            except OSError:
                log.log(TRACE, "Tried envs_dir but not writable: %s", envs_dir)
        else:
            from ..gateways.disk.create import create_envs_directory

            was_created = create_envs_directory(envs_dir)
            if was_created:
                return envs_dir

    from ..exceptions import NoWritableEnvsDirError

    raise NoWritableEnvsDirError(context.envs_dirs)


def get_plugin_config_data(
    data: dict[Path, dict[str, RawParameter]],
) -> dict[Path, dict[str, RawParameter]]:
    """
    This is used to move everything under the key "plugins" from the provided dictionary
    to the top level of the returned dictionary. The returned dictionary is then passed
    to :class:`PluginConfig`.
    """
    new_data = defaultdict(dict)

    for source, config in data.items():
        if plugin_data := config.get("plugins"):
            plugin_data_value = plugin_data.value(None)

            if not isinstance(plugin_data_value, Mapping):
                continue

            for param_name, raw_param in plugin_data_value.items():
                new_data[source][param_name] = raw_param

        elif source == EnvRawParameter.source:
            for env_var, raw_param in config.items():
                if env_var.startswith("plugins_"):
                    _, param_name = env_var.split("plugins_")
                    new_data[source][param_name] = raw_param

    return new_data


class PluginConfig(metaclass=ConfigurationType):
    """
    Class used to hold settings for conda plugins.

    The object created by this class should only be accessed via
    :class:`conda.base.context.Context.plugins`.

    When this class is updated via the :func:`add_plugin_setting` function it adds new setting
    properties which can be accessed later via the context object.

    We currently call that function in
    :meth:`conda.plugins.manager.CondaPluginManager.load_settings`.
    because ``CondaPluginManager`` has access to all registered plugin settings via the settings
    plugin hook.
    """

    def __init__(self, data):
        self._cache_ = {}
        self.raw_data = get_plugin_config_data(data)


def add_plugin_setting(name: str, parameter: Parameter, aliases: tuple[str, ...] = ()):
    """
    Adds a setting to the :class:`PluginConfig` class
    """
    PluginConfig.parameter_names = PluginConfig.parameter_names + (name,)
    loader = ParameterLoader(parameter, aliases=aliases)
    name = loader._set_name(name)
    setattr(PluginConfig, name, loader)


def remove_all_plugin_settings() -> None:
    """
    Removes all attached settings from the :class:`PluginConfig` class
    """
    for name in PluginConfig.parameter_names:
        try:
            delattr(PluginConfig, name)
        except AttributeError:
            continue

    PluginConfig.parameter_names = tuple()


try:
    context = Context((), None)
except ConfigurationLoadError as e:  # pragma: no cover
    print(repr(e), file=sys.stderr)
    # Exception handler isn't loaded so use sys.exit
    sys.exit(1)
