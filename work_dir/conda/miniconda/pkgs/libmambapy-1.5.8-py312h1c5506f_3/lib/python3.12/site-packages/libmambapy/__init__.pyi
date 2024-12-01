from __future__ import annotations
import libmambapy.bindings
import typing

__all__ = [
    "Channel",
    "ChannelPriority",
    "CompressedProblemsGraph",
    "Context",
    "DownloadTargetList",
    "ExtraPkgInfo",
    "History",
    "Key",
    "KeyMgr",
    "LockFile",
    "LogLevel",
    "MAMBA_CLEAN_ALL",
    "MAMBA_CLEAN_INDEX",
    "MAMBA_CLEAN_LOCKS",
    "MAMBA_CLEAN_PKGS",
    "MAMBA_CLEAN_TARBALLS",
    "MAMBA_DOWNLOAD_FAILFAST",
    "MAMBA_DOWNLOAD_SORT",
    "MAMBA_FORCE_REINSTALL",
    "MAMBA_NO_DEPS",
    "MAMBA_ONLY_DEPS",
    "MambaNativeException",
    "MatchSpec",
    "MultiPackageCache",
    "PackageInfo",
    "Path",
    "PkgMgr",
    "Pool",
    "PrefixData",
    "ProblemsGraph",
    "Query",
    "QueryFormat",
    "Repo",
    "RoleBase",
    "RoleBaseExtension",
    "RoleFullKeys",
    "RootImpl",
    "RootRole",
    "SOLVER_ALLOWUNINSTALL",
    "SOLVER_CLEANDEPS",
    "SOLVER_DISFAVOR",
    "SOLVER_DISTUPGRADE",
    "SOLVER_DROP_ORPHANED",
    "SOLVER_ERASE",
    "SOLVER_ESSENTIAL",
    "SOLVER_FAVOR",
    "SOLVER_FLAG_ADD_ALREADY_RECOMMENDED",
    "SOLVER_FLAG_ALLOW_ARCHCHANGE",
    "SOLVER_FLAG_ALLOW_DOWNGRADE",
    "SOLVER_FLAG_ALLOW_NAMECHANGE",
    "SOLVER_FLAG_ALLOW_UNINSTALL",
    "SOLVER_FLAG_ALLOW_VENDORCHANGE",
    "SOLVER_FLAG_BEST_OBEY_POLICY",
    "SOLVER_FLAG_BREAK_ORPHANS",
    "SOLVER_FLAG_DUP_ALLOW_ARCHCHANGE",
    "SOLVER_FLAG_DUP_ALLOW_DOWNGRADE",
    "SOLVER_FLAG_DUP_ALLOW_NAMECHANGE",
    "SOLVER_FLAG_DUP_ALLOW_VENDORCHANGE",
    "SOLVER_FLAG_FOCUS_BEST",
    "SOLVER_FLAG_FOCUS_INSTALLED",
    "SOLVER_FLAG_IGNORE_RECOMMENDED",
    "SOLVER_FLAG_INSTALL_ALSO_UPDATES",
    "SOLVER_FLAG_KEEP_EXPLICIT_OBSOLETES",
    "SOLVER_FLAG_KEEP_ORPHANS",
    "SOLVER_FLAG_NEED_UPDATEPROVIDE",
    "SOLVER_FLAG_NO_AUTOTARGET",
    "SOLVER_FLAG_NO_INFARCHCHECK",
    "SOLVER_FLAG_NO_UPDATEPROVIDE",
    "SOLVER_FLAG_ONLY_NAMESPACE_RECOMMENDED",
    "SOLVER_FLAG_SPLITPROVIDES",
    "SOLVER_FLAG_STRICT_REPO_PRIORITY",
    "SOLVER_FLAG_STRONG_RECOMMENDS",
    "SOLVER_FLAG_URPM_REORDER",
    "SOLVER_FLAG_YUM_OBSOLETES",
    "SOLVER_FORCEBEST",
    "SOLVER_INSTALL",
    "SOLVER_JOBMASK",
    "SOLVER_LOCK",
    "SOLVER_MULTIVERSION",
    "SOLVER_NOAUTOSET",
    "SOLVER_NOOP",
    "SOLVER_NOTBYUSER",
    "SOLVER_ORUPDATE",
    "SOLVER_SELECTMASK",
    "SOLVER_SETARCH",
    "SOLVER_SETEV",
    "SOLVER_SETEVR",
    "SOLVER_SETMASK",
    "SOLVER_SETNAME",
    "SOLVER_SETREPO",
    "SOLVER_SETVENDOR",
    "SOLVER_SOLVABLE",
    "SOLVER_SOLVABLE_ALL",
    "SOLVER_SOLVABLE_NAME",
    "SOLVER_SOLVABLE_ONE_OF",
    "SOLVER_SOLVABLE_PROVIDES",
    "SOLVER_SOLVABLE_REPO",
    "SOLVER_TARGETED",
    "SOLVER_UPDATE",
    "SOLVER_USERINSTALLED",
    "SOLVER_VERIFY",
    "SOLVER_WEAK",
    "SOLVER_WEAKENDEPS",
    "Solver",
    "SolverProblem",
    "SolverRuleinfo",
    "SpecBase",
    "SpecImpl",
    "SubdirData",
    "TimeRef",
    "Transaction",
    "cache_fn_url",
    "cancel_json_output",
    "clean",
    "create_cache_dir",
    "generate_ed25519_keypair",
    "get_channels",
    "get_virtual_packages",
    "init_console",
    "ostream_redirect",
    "sign",
    "simplify_conflicts",
    "transmute",
]

class Channel:
    def __init__(self, arg0: str) -> None: ...
    def __repr__(self) -> str: ...
    def platform_url(self, platform: str, with_credentials: bool = True) -> str: ...
    def platform_urls(
        self, with_credentials: bool = True
    ) -> typing.List[typing.Tuple[str, str]]: ...
    def urls(self, with_credentials: bool = True) -> typing.List[str]: ...
    @property
    def auth(self) -> typing.Optional[str]:
        """
        :type: typing.Optional[str]
        """
    @property
    def canonical_name(self) -> str:
        """
        :type: str
        """
    @property
    def location(self) -> str:
        """
        :type: str
        """
    @property
    def name(self) -> str:
        """
        :type: str
        """
    @property
    def package_filename(self) -> typing.Optional[str]:
        """
        :type: typing.Optional[str]
        """
    @property
    def platforms(self) -> typing.List[str]:
        """
        :type: typing.List[str]
        """
    @property
    def scheme(self) -> str:
        """
        :type: str
        """
    @property
    def token(self) -> typing.Optional[str]:
        """
        :type: typing.Optional[str]
        """
    pass

class ChannelPriority:
    """
    Members:

      kFlexible

      kStrict

      kDisabled
    """

    def __eq__(self, other: object) -> bool: ...
    def __getstate__(self) -> int: ...
    def __hash__(self) -> int: ...
    def __index__(self) -> int: ...
    def __init__(self, value: int) -> None: ...
    def __int__(self) -> int: ...
    def __ne__(self, other: object) -> bool: ...
    def __repr__(self) -> str: ...
    def __setstate__(self, state: int) -> None: ...
    @property
    def name(self) -> str:
        """
        :type: str
        """
    @property
    def value(self) -> int:
        """
        :type: int
        """
    __members__: dict  # value = {'kFlexible': <ChannelPriority.kFlexible: 1>, 'kStrict': <ChannelPriority.kStrict: 2>, 'kDisabled': <ChannelPriority.kDisabled: 0>}
    kDisabled: libmambapy.bindings.ChannelPriority  # value = <ChannelPriority.kDisabled: 0>
    kFlexible: libmambapy.bindings.ChannelPriority  # value = <ChannelPriority.kFlexible: 1>
    kStrict: libmambapy.bindings.ChannelPriority  # value = <ChannelPriority.kStrict: 2>
    pass

class CompressedProblemsGraph:
    class ConflictMap:
        def __bool__(self) -> bool: ...
        def __contains__(self, arg0: int) -> bool: ...
        def __init__(self) -> None: ...
        def __iter__(self) -> typing.Iterator: ...
        def __len__(self) -> int: ...
        def add(self, arg0: int, arg1: int) -> bool: ...
        def clear(self) -> None: ...
        def conflicts(self, arg0: int) -> typing.Set[int]: ...
        def has_conflict(self, arg0: int) -> bool: ...
        def in_conflict(self, arg0: int, arg1: int) -> bool: ...
        pass

    class ConstraintListNode:
        def __bool__(self) -> bool: ...
        def __init__(self) -> None: ...
        def __iter__(self) -> typing.Iterator: ...
        def __len__(self) -> int: ...
        def add(self, arg0: ProblemsGraph.ConstraintNode) -> None: ...
        def build_strings_trunc(
            self,
            sep: str = "|",
            etc: str = "...",
            threshold: int = 5,
            remove_duplicates: bool = True,
        ) -> typing.Tuple[str, int]: ...
        def clear(self) -> None: ...
        def name(self) -> str: ...
        def versions_and_build_strings_trunc(
            self,
            sep: str = "|",
            etc: str = "...",
            threshold: int = 5,
            remove_duplicates: bool = True,
        ) -> typing.Tuple[str, int]: ...
        def versions_trunc(
            self,
            sep: str = "|",
            etc: str = "...",
            threshold: int = 5,
            remove_duplicates: bool = True,
        ) -> typing.Tuple[str, int]: ...
        pass

    class DependencyList:
        def __bool__(self) -> bool: ...
        def __init__(self) -> None: ...
        def __iter__(self) -> typing.Iterator: ...
        def __len__(self) -> int: ...
        def add(self, arg0: MatchSpec) -> None: ...
        def build_strings_trunc(
            self,
            sep: str = "|",
            etc: str = "...",
            threshold: int = 5,
            remove_duplicates: bool = True,
        ) -> typing.Tuple[str, int]: ...
        def clear(self) -> None: ...
        def name(self) -> str: ...
        def versions_and_build_strings_trunc(
            self,
            sep: str = "|",
            etc: str = "...",
            threshold: int = 5,
            remove_duplicates: bool = True,
        ) -> typing.Tuple[str, int]: ...
        def versions_trunc(
            self,
            sep: str = "|",
            etc: str = "...",
            threshold: int = 5,
            remove_duplicates: bool = True,
        ) -> typing.Tuple[str, int]: ...
        pass

    class PackageListNode:
        def __bool__(self) -> bool: ...
        def __init__(self) -> None: ...
        def __iter__(self) -> typing.Iterator: ...
        def __len__(self) -> int: ...
        def add(self, arg0: ProblemsGraph.PackageNode) -> None: ...
        def build_strings_trunc(
            self,
            sep: str = "|",
            etc: str = "...",
            threshold: int = 5,
            remove_duplicates: bool = True,
        ) -> typing.Tuple[str, int]: ...
        def clear(self) -> None: ...
        def name(self) -> str: ...
        def versions_and_build_strings_trunc(
            self,
            sep: str = "|",
            etc: str = "...",
            threshold: int = 5,
            remove_duplicates: bool = True,
        ) -> typing.Tuple[str, int]: ...
        def versions_trunc(
            self,
            sep: str = "|",
            etc: str = "...",
            threshold: int = 5,
            remove_duplicates: bool = True,
        ) -> typing.Tuple[str, int]: ...
        pass

    class RootNode:
        def __init__(self) -> None: ...
        pass

    class UnresolvedDependencyListNode:
        def __bool__(self) -> bool: ...
        def __init__(self) -> None: ...
        def __iter__(self) -> typing.Iterator: ...
        def __len__(self) -> int: ...
        def add(self, arg0: ProblemsGraph.UnresolvedDependencyNode) -> None: ...
        def build_strings_trunc(
            self,
            sep: str = "|",
            etc: str = "...",
            threshold: int = 5,
            remove_duplicates: bool = True,
        ) -> typing.Tuple[str, int]: ...
        def clear(self) -> None: ...
        def name(self) -> str: ...
        def versions_and_build_strings_trunc(
            self,
            sep: str = "|",
            etc: str = "...",
            threshold: int = 5,
            remove_duplicates: bool = True,
        ) -> typing.Tuple[str, int]: ...
        def versions_trunc(
            self,
            sep: str = "|",
            etc: str = "...",
            threshold: int = 5,
            remove_duplicates: bool = True,
        ) -> typing.Tuple[str, int]: ...
        pass
    def conflicts(self) -> ProblemsGraph.ConflictMap: ...
    @staticmethod
    @typing.overload
    def from_problems_graph(
        arg0: ProblemsGraph, arg1: typing.Callable[[ProblemsGraph, int, int], bool]
    ) -> CompressedProblemsGraph: ...
    @staticmethod
    @typing.overload
    def from_problems_graph(arg0: ProblemsGraph) -> CompressedProblemsGraph: ...
    def graph(
        self,
    ) -> typing.Tuple[
        typing.Dict[
            int,
            typing.Union[
                ProblemsGraph.RootNode,
                CompressedProblemsGraph.PackageListNode,
                CompressedProblemsGraph.UnresolvedDependencyListNode,
                CompressedProblemsGraph.ConstraintListNode,
            ],
        ],
        typing.Dict[typing.Tuple[int, int], CompressedProblemsGraph.DependencyList],
    ]: ...
    def root_node(self) -> int: ...
    def tree_message(self) -> str: ...
    pass

class Context:
    class OutputParams:
        def __init__(self) -> None: ...
        @property
        def json(self) -> bool:
            """
            :type: bool
            """
        @json.setter
        def json(self, arg0: bool) -> None:
            pass
        @property
        def quiet(self) -> bool:
            """
            :type: bool
            """
        @quiet.setter
        def quiet(self, arg0: bool) -> None:
            pass
        @property
        def verbosity(self) -> int:
            """
            :type: int
            """
        @verbosity.setter
        def verbosity(self, arg0: int) -> None:
            pass
        pass

    class PrefixParams:
        def __init__(self) -> None: ...
        @property
        def conda_prefix(self) -> Path:
            """
            :type: Path
            """
        @conda_prefix.setter
        def conda_prefix(self, arg0: Path) -> None:
            pass
        @property
        def root_prefix(self) -> Path:
            """
            :type: Path
            """
        @root_prefix.setter
        def root_prefix(self, arg0: Path) -> None:
            pass
        @property
        def target_prefix(self) -> Path:
            """
            :type: Path
            """
        @target_prefix.setter
        def target_prefix(self, arg0: Path) -> None:
            pass
        pass

    class RemoteFetchParams:
        def __init__(self) -> None: ...
        @property
        def connect_timeout_secs(self) -> float:
            """
            :type: float
            """
        @connect_timeout_secs.setter
        def connect_timeout_secs(self, arg0: float) -> None:
            pass
        @property
        def max_retries(self) -> int:
            """
            :type: int
            """
        @max_retries.setter
        def max_retries(self, arg0: int) -> None:
            pass
        @property
        def proxy_servers(self) -> typing.Dict[str, str]:
            """
            :type: typing.Dict[str, str]
            """
        @proxy_servers.setter
        def proxy_servers(self, arg0: typing.Dict[str, str]) -> None:
            pass
        @property
        def retry_backoff(self) -> int:
            """
            :type: int
            """
        @retry_backoff.setter
        def retry_backoff(self, arg0: int) -> None:
            pass
        @property
        def retry_timeout(self) -> int:
            """
            :type: int
            """
        @retry_timeout.setter
        def retry_timeout(self, arg0: int) -> None:
            pass
        @property
        def ssl_verify(self) -> str:
            """
            :type: str
            """
        @ssl_verify.setter
        def ssl_verify(self, arg0: str) -> None:
            pass
        @property
        def user_agent(self) -> str:
            """
            :type: str
            """
        @user_agent.setter
        def user_agent(self, arg0: str) -> None:
            pass
        pass

    class ThreadsParams:
        def __init__(self) -> None: ...
        @property
        def download_threads(self) -> int:
            """
            :type: int
            """
        @download_threads.setter
        def download_threads(self, arg0: int) -> None:
            pass
        @property
        def extract_threads(self) -> int:
            """
            :type: int
            """
        @extract_threads.setter
        def extract_threads(self, arg0: int) -> None:
            pass
        pass
    def __init__(self) -> None: ...
    def set_log_level(self, arg0: LogLevel) -> None: ...
    def set_verbosity(self, arg0: int) -> None: ...
    @staticmethod
    def use_default_signal_handler(arg0: bool) -> None: ...
    @property
    def add_pip_as_python_dependency(self) -> bool:
        """
        :type: bool
        """
    @add_pip_as_python_dependency.setter
    def add_pip_as_python_dependency(self, arg0: bool) -> None:
        pass
    @property
    def always_yes(self) -> bool:
        """
        :type: bool
        """
    @always_yes.setter
    def always_yes(self, arg0: bool) -> None:
        pass
    @property
    def channel_alias(self) -> str:
        """
        :type: str
        """
    @channel_alias.setter
    def channel_alias(self, arg0: str) -> None:
        pass
    @property
    def channel_priority(self) -> ChannelPriority:
        """
        :type: ChannelPriority
        """
    @channel_priority.setter
    def channel_priority(self, arg0: ChannelPriority) -> None:
        pass
    @property
    def channels(self) -> typing.List[str]:
        """
        :type: typing.List[str]
        """
    @channels.setter
    def channels(self, arg0: typing.List[str]) -> None:
        pass
    @property
    def conda_build_local_paths(self) -> typing.List[str]:
        """
        :type: typing.List[str]
        """
    @conda_build_local_paths.setter
    def conda_build_local_paths(self, arg1: typing.List[str]) -> None:
        pass
    @property
    def conda_prefix(self) -> Path:
        """
        :type: Path
        """
    @conda_prefix.setter
    def conda_prefix(self, arg1: Path) -> None:
        pass
    @property
    def connect_timeout_secs(self) -> float:
        """
        :type: float
        """
    @connect_timeout_secs.setter
    def connect_timeout_secs(self, arg1: float) -> None:
        pass
    @property
    def custom_channels(self) -> typing.Dict[str, str]:
        """
        :type: typing.Dict[str, str]
        """
    @custom_channels.setter
    def custom_channels(self, arg0: typing.Dict[str, str]) -> None:
        pass
    @property
    def custom_multichannels(self) -> typing.Dict[str, typing.List[str]]:
        """
        :type: typing.Dict[str, typing.List[str]]
        """
    @custom_multichannels.setter
    def custom_multichannels(self, arg0: typing.Dict[str, typing.List[str]]) -> None:
        pass
    @property
    def default_channels(self) -> typing.List[str]:
        """
        :type: typing.List[str]
        """
    @default_channels.setter
    def default_channels(self, arg0: typing.List[str]) -> None:
        pass
    @property
    def download_only(self) -> bool:
        """
        :type: bool
        """
    @download_only.setter
    def download_only(self, arg0: bool) -> None:
        pass
    @property
    def download_threads(self) -> int:
        """
        :type: int
        """
    @download_threads.setter
    def download_threads(self, arg1: int) -> None:
        pass
    @property
    def dry_run(self) -> bool:
        """
        :type: bool
        """
    @dry_run.setter
    def dry_run(self, arg0: bool) -> None:
        pass
    @property
    def envs_dirs(self) -> typing.List[Path]:
        """
        :type: typing.List[Path]
        """
    @envs_dirs.setter
    def envs_dirs(self, arg0: typing.List[Path]) -> None:
        pass
    @property
    def experimental_sat_error_message(self) -> bool:
        """
        :type: bool
        """
    @experimental_sat_error_message.setter
    def experimental_sat_error_message(self, arg1: bool) -> None:
        pass
    @property
    def extract_threads(self) -> int:
        """
        :type: int
        """
    @extract_threads.setter
    def extract_threads(self, arg1: int) -> None:
        pass
    @property
    def json(self) -> bool:
        """
        :type: bool
        """
    @json.setter
    def json(self, arg1: bool) -> None:
        pass
    @property
    def local_repodata_ttl(self) -> int:
        """
        :type: int
        """
    @local_repodata_ttl.setter
    def local_repodata_ttl(self, arg0: int) -> None:
        pass
    @property
    def max_retries(self) -> int:
        """
        :type: int
        """
    @max_retries.setter
    def max_retries(self, arg1: int) -> None:
        pass
    @property
    def offline(self) -> bool:
        """
        :type: bool
        """
    @offline.setter
    def offline(self, arg0: bool) -> None:
        pass
    @property
    def output_params(self) -> Context.OutputParams:
        """
        :type: Context.OutputParams
        """
    @output_params.setter
    def output_params(self, arg0: Context.OutputParams) -> None:
        pass
    @property
    def pkgs_dirs(self) -> typing.List[Path]:
        """
        :type: typing.List[Path]
        """
    @pkgs_dirs.setter
    def pkgs_dirs(self, arg0: typing.List[Path]) -> None:
        pass
    @property
    def platform(self) -> str:
        """
        :type: str
        """
    @platform.setter
    def platform(self, arg0: str) -> None:
        pass
    @property
    def prefix_params(self) -> Context.PrefixParams:
        """
        :type: Context.PrefixParams
        """
    @prefix_params.setter
    def prefix_params(self, arg0: Context.PrefixParams) -> None:
        pass
    @property
    def proxy_servers(self) -> typing.Dict[str, str]:
        """
        :type: typing.Dict[str, str]
        """
    @proxy_servers.setter
    def proxy_servers(self, arg1: typing.Dict[str, str]) -> None:
        pass
    @property
    def quiet(self) -> bool:
        """
        :type: bool
        """
    @quiet.setter
    def quiet(self, arg1: bool) -> None:
        pass
    @property
    def remote_fetch_params(self) -> Context.RemoteFetchParams:
        """
        :type: Context.RemoteFetchParams
        """
    @remote_fetch_params.setter
    def remote_fetch_params(self, arg0: Context.RemoteFetchParams) -> None:
        pass
    @property
    def retry_backoff(self) -> int:
        """
        :type: int
        """
    @retry_backoff.setter
    def retry_backoff(self, arg1: int) -> None:
        pass
    @property
    def retry_timeout(self) -> int:
        """
        :type: int
        """
    @retry_timeout.setter
    def retry_timeout(self, arg1: int) -> None:
        pass
    @property
    def root_prefix(self) -> Path:
        """
        :type: Path
        """
    @root_prefix.setter
    def root_prefix(self, arg1: Path) -> None:
        pass
    @property
    def ssl_verify(self) -> str:
        """
        :type: str
        """
    @ssl_verify.setter
    def ssl_verify(self, arg1: str) -> None:
        pass
    @property
    def target_prefix(self) -> Path:
        """
        :type: Path
        """
    @target_prefix.setter
    def target_prefix(self, arg1: Path) -> None:
        pass
    @property
    def threads_params(self) -> Context.ThreadsParams:
        """
        :type: Context.ThreadsParams
        """
    @threads_params.setter
    def threads_params(self, arg0: Context.ThreadsParams) -> None:
        pass
    @property
    def use_index_cache(self) -> bool:
        """
        :type: bool
        """
    @use_index_cache.setter
    def use_index_cache(self, arg0: bool) -> None:
        pass
    @property
    def use_lockfiles(self) -> bool:
        """
        :type: bool
        """
    @use_lockfiles.setter
    def use_lockfiles(self, arg1: bool) -> None:
        pass
    @property
    def use_only_tar_bz2(self) -> bool:
        """
        :type: bool
        """
    @use_only_tar_bz2.setter
    def use_only_tar_bz2(self, arg0: bool) -> None:
        pass
    @property
    def user_agent(self) -> str:
        """
        :type: str
        """
    @user_agent.setter
    def user_agent(self, arg1: str) -> None:
        pass
    @property
    def verbosity(self) -> int:
        """
        :type: int
        """
    @verbosity.setter
    def verbosity(self, arg1: int) -> None:
        pass
    pass

class DownloadTargetList:
    def __init__(self) -> None: ...
    def add(self, arg0: SubdirData) -> None: ...
    def download(self, arg0: int) -> bool: ...
    pass

class ExtraPkgInfo:
    def __init__(self) -> None: ...
    @property
    def noarch(self) -> str:
        """
        :type: str
        """
    @noarch.setter
    def noarch(self, arg0: str) -> None:
        pass
    @property
    def repo_url(self) -> str:
        """
        :type: str
        """
    @repo_url.setter
    def repo_url(self, arg0: str) -> None:
        pass
    pass

class History:
    def __init__(self, arg0: Path) -> None: ...
    def get_requested_specs_map(self) -> typing.Dict[str, MatchSpec]: ...
    pass

class Key:
    @staticmethod
    def from_ed25519(arg0: str) -> Key: ...
    @property
    def json_str(self) -> str:
        """
        :type: str
        """
    @property
    def keytype(self) -> str:
        """
        :type: str
        """
    @keytype.setter
    def keytype(self, arg0: str) -> None:
        pass
    @property
    def keyval(self) -> str:
        """
        :type: str
        """
    @keyval.setter
    def keyval(self, arg0: str) -> None:
        pass
    @property
    def scheme(self) -> str:
        """
        :type: str
        """
    @scheme.setter
    def scheme(self, arg0: str) -> None:
        pass
    pass

class RoleBase:
    def all_keys(self) -> typing.Dict[str, RoleFullKeys]: ...
    @property
    def expired(self) -> bool:
        """
        :type: bool
        """
    @property
    def expires(self) -> str:
        """
        :type: str
        """
    @property
    def file_ext(self) -> str:
        """
        :type: str
        """
    @property
    def spec_version(self) -> SpecBase:
        """
        :type: SpecBase
        """
    @property
    def type(self) -> str:
        """
        :type: str
        """
    @property
    def version(self) -> int:
        """
        :type: int
        """
    pass

class LockFile:
    def __init__(self, arg0: Path) -> None: ...
    pass

class LogLevel:
    """
    Members:

      TRACE

      DEBUG

      INFO

      WARNING

      ERROR

      CRITICAL

      OFF
    """

    def __eq__(self, other: object) -> bool: ...
    def __getstate__(self) -> int: ...
    def __hash__(self) -> int: ...
    def __index__(self) -> int: ...
    def __init__(self, value: int) -> None: ...
    def __int__(self) -> int: ...
    def __ne__(self, other: object) -> bool: ...
    def __repr__(self) -> str: ...
    def __setstate__(self, state: int) -> None: ...
    @property
    def name(self) -> str:
        """
        :type: str
        """
    @property
    def value(self) -> int:
        """
        :type: int
        """
    CRITICAL: libmambapy.bindings.LogLevel  # value = <LogLevel.CRITICAL: 5>
    DEBUG: libmambapy.bindings.LogLevel  # value = <LogLevel.DEBUG: 1>
    ERROR: libmambapy.bindings.LogLevel  # value = <LogLevel.ERROR: 4>
    INFO: libmambapy.bindings.LogLevel  # value = <LogLevel.INFO: 2>
    OFF: libmambapy.bindings.LogLevel  # value = <LogLevel.OFF: 6>
    TRACE: libmambapy.bindings.LogLevel  # value = <LogLevel.TRACE: 0>
    WARNING: libmambapy.bindings.LogLevel  # value = <LogLevel.WARNING: 3>
    __members__: dict  # value = {'TRACE': <LogLevel.TRACE: 0>, 'DEBUG': <LogLevel.DEBUG: 1>, 'INFO': <LogLevel.INFO: 2>, 'WARNING': <LogLevel.WARNING: 3>, 'ERROR': <LogLevel.ERROR: 4>, 'CRITICAL': <LogLevel.CRITICAL: 5>, 'OFF': <LogLevel.OFF: 6>}
    pass

class MambaNativeException(Exception, BaseException):
    pass

class MatchSpec:
    @typing.overload
    def __init__(self) -> None: ...
    @typing.overload
    def __init__(self, arg0: str) -> None: ...
    def conda_build_form(self) -> str: ...
    pass

class MultiPackageCache:
    def __init__(self, arg0: typing.List[Path]) -> None: ...
    def get_tarball_path(self, arg0: PackageInfo, arg1: bool) -> Path: ...
    @property
    def first_writable_path(self) -> Path:
        """
        :type: Path
        """
    pass

class PackageInfo:
    @typing.overload
    def __init__(self, name: str) -> None: ...
    @typing.overload
    def __init__(
        self, name: str, version: str, build_string: str, build_number: int
    ) -> None: ...
    @property
    def build_number(self) -> int:
        """
        :type: int
        """
    @build_number.setter
    def build_number(self, arg0: int) -> None:
        pass
    @property
    def build_string(self) -> str:
        """
        :type: str
        """
    @build_string.setter
    def build_string(self, arg0: str) -> None:
        pass
    @property
    def channel(self) -> str:
        """
        :type: str
        """
    @channel.setter
    def channel(self, arg0: str) -> None:
        pass
    @property
    def constrains(self) -> typing.List[str]:
        """
        :type: typing.List[str]
        """
    @constrains.setter
    def constrains(self, arg0: typing.List[str]) -> None:
        pass
    @property
    def defaulted_keys(self) -> typing.Set[str]:
        """
        :type: typing.Set[str]
        """
    @defaulted_keys.setter
    def defaulted_keys(self, arg0: typing.Set[str]) -> None:
        pass
    @property
    def depends(self) -> typing.List[str]:
        """
        :type: typing.List[str]
        """
    @depends.setter
    def depends(self, arg0: typing.List[str]) -> None:
        pass
    @property
    def fn(self) -> str:
        """
        :type: str
        """
    @fn.setter
    def fn(self, arg0: str) -> None:
        pass
    @property
    def license(self) -> str:
        """
        :type: str
        """
    @license.setter
    def license(self, arg0: str) -> None:
        pass
    @property
    def md5(self) -> str:
        """
        :type: str
        """
    @md5.setter
    def md5(self, arg0: str) -> None:
        pass
    @property
    def name(self) -> str:
        """
        :type: str
        """
    @name.setter
    def name(self, arg0: str) -> None:
        pass
    @property
    def noarch(self) -> str:
        """
        :type: str
        """
    @noarch.setter
    def noarch(self, arg0: str) -> None:
        pass
    @property
    def sha256(self) -> str:
        """
        :type: str
        """
    @sha256.setter
    def sha256(self, arg0: str) -> None:
        pass
    @property
    def signatures(self) -> str:
        """
        :type: str
        """
    @signatures.setter
    def signatures(self, arg0: str) -> None:
        pass
    @property
    def size(self) -> int:
        """
        :type: int
        """
    @size.setter
    def size(self, arg0: int) -> None:
        pass
    @property
    def subdir(self) -> str:
        """
        :type: str
        """
    @subdir.setter
    def subdir(self, arg0: str) -> None:
        pass
    @property
    def timestamp(self) -> int:
        """
        :type: int
        """
    @timestamp.setter
    def timestamp(self, arg0: int) -> None:
        pass
    @property
    def track_features(self) -> str:
        """
        :type: str
        """
    @track_features.setter
    def track_features(self, arg1: str) -> None:
        pass
    @property
    def url(self) -> str:
        """
        :type: str
        """
    @url.setter
    def url(self, arg0: str) -> None:
        pass
    @property
    def version(self) -> str:
        """
        :type: str
        """
    @version.setter
    def version(self, arg0: str) -> None:
        pass
    pass

class Path:
    def __init__(self, arg0: str) -> None: ...
    def __repr__(self) -> str: ...
    def __str__(self) -> str: ...
    pass

class RoleBaseExtension:
    @property
    def timestamp(self) -> str:
        """
        :type: str
        """
    pass

class Pool:
    def __init__(self) -> None: ...
    def create_whatprovides(self) -> None: ...
    def id2pkginfo(self, id: int) -> typing.Optional[PackageInfo]: ...
    @typing.overload
    def matchspec2id(self, ms: MatchSpec) -> int: ...
    @typing.overload
    def matchspec2id(self, ms: str) -> int: ...
    def select_solvables(self, id: int, sorted: bool = False) -> typing.List[int]: ...
    def set_debuglevel(self) -> None: ...
    pass

class PrefixData:
    def __init__(self, arg0: Path) -> None: ...
    def add_packages(self, arg0: typing.List[PackageInfo]) -> None: ...
    @property
    def package_records(self) -> typing.Dict[str, PackageInfo]:
        """
        :type: typing.Dict[str, PackageInfo]
        """
    pass

class ProblemsGraph:
    class ConflictMap:
        pass

    class ConstraintNode(MatchSpec):
        pass

    class PackageNode(PackageInfo):
        pass

    class RootNode:
        pass

    class UnresolvedDependencyNode(MatchSpec):
        pass
    def conflicts(self) -> ProblemsGraph.ConflictMap: ...
    @staticmethod
    def from_solver(arg0: Solver, arg1: Pool) -> ProblemsGraph: ...
    def graph(
        self,
    ) -> typing.Tuple[
        typing.Dict[
            int,
            typing.Union[
                ProblemsGraph.RootNode,
                ProblemsGraph.PackageNode,
                ProblemsGraph.UnresolvedDependencyNode,
                ProblemsGraph.ConstraintNode,
            ],
        ],
        typing.Dict[typing.Tuple[int, int], MatchSpec],
    ]: ...
    def root_node(self) -> int: ...
    pass

class Query:
    def __init__(self, arg0: Pool) -> None: ...
    def depends(self, arg0: str, arg1: QueryFormat) -> str: ...
    def find(self, arg0: str, arg1: QueryFormat) -> str: ...
    def whoneeds(self, arg0: str, arg1: QueryFormat) -> str: ...
    pass

class QueryFormat:
    """
    Members:

      JSON

      TREE

      TABLE

      PRETTY

      RECURSIVETABLE
    """

    def __eq__(self, other: object) -> bool: ...
    def __getstate__(self) -> int: ...
    def __hash__(self) -> int: ...
    def __index__(self) -> int: ...
    def __init__(self, value: int) -> None: ...
    def __int__(self) -> int: ...
    def __ne__(self, other: object) -> bool: ...
    def __repr__(self) -> str: ...
    def __setstate__(self, state: int) -> None: ...
    @property
    def name(self) -> str:
        """
        :type: str
        """
    @property
    def value(self) -> int:
        """
        :type: int
        """
    JSON: libmambapy.bindings.QueryFormat  # value = <QueryFormat.JSON: 0>
    PRETTY: libmambapy.bindings.QueryFormat  # value = <QueryFormat.PRETTY: 3>
    RECURSIVETABLE: libmambapy.bindings.QueryFormat  # value = <QueryFormat.RECURSIVETABLE: 4>
    TABLE: libmambapy.bindings.QueryFormat  # value = <QueryFormat.TABLE: 2>
    TREE: libmambapy.bindings.QueryFormat  # value = <QueryFormat.TREE: 1>
    __members__: dict  # value = {'JSON': <QueryFormat.JSON: 0>, 'TREE': <QueryFormat.TREE: 1>, 'TABLE': <QueryFormat.TABLE: 2>, 'PRETTY': <QueryFormat.PRETTY: 3>, 'RECURSIVETABLE': <QueryFormat.RECURSIVETABLE: 4>}
    pass

class Repo:
    @typing.overload
    def __init__(self, arg0: Pool, arg1: str, arg2: str, arg3: str) -> None: ...
    @typing.overload
    def __init__(self, arg0: Pool, arg1: PrefixData) -> None: ...
    def add_extra_pkg_info(self, arg0: typing.Dict[str, ExtraPkgInfo]) -> None: ...
    def clear(self, arg0: bool) -> bool: ...
    def name(self) -> str: ...
    def priority(self) -> typing.Tuple[int, int]: ...
    def set_installed(self) -> None: ...
    def set_priority(self, arg0: int, arg1: int) -> None: ...
    def size(self) -> int: ...
    pass

class KeyMgr(RoleBase, RoleBaseExtension):
    def __init__(self, arg0: str, arg1: RoleFullKeys, arg2: SpecBase) -> None: ...
    pass

class PkgMgr(RoleBase, RoleBaseExtension):
    def __init__(self, arg0: str, arg1: RoleFullKeys, arg2: SpecBase) -> None: ...
    pass

class RoleFullKeys:
    @typing.overload
    def __init__(self) -> None: ...
    @typing.overload
    def __init__(self, keys: typing.Dict[str, Key], threshold: int) -> None: ...
    @property
    def keys(self) -> typing.Dict[str, Key]:
        """
        :type: typing.Dict[str, Key]
        """
    @keys.setter
    def keys(self, arg0: typing.Dict[str, Key]) -> None:
        pass
    @property
    def threshold(self) -> int:
        """
        :type: int
        """
    @threshold.setter
    def threshold(self, arg0: int) -> None:
        pass
    pass

class RootImpl(RoleBase, RoleBaseExtension):
    def __init__(self, json_str: str) -> None: ...
    def create_key_mgr(self, json_str: str) -> KeyMgr: ...
    def update(self, json_str: str) -> RootRole: ...
    pass

class RootRole:
    pass

class Solver:
    def __init__(
        self, arg0: Pool, arg1: typing.List[typing.Tuple[int, int]]
    ) -> None: ...
    def add_constraint(self, arg0: str) -> None: ...
    def add_global_job(self, arg0: int) -> None: ...
    def add_jobs(self, arg0: typing.List[str], arg1: int) -> None: ...
    def add_pin(self, arg0: str) -> None: ...
    def all_problems_structured(self) -> typing.List[SolverProblem]: ...
    def all_problems_to_str(self) -> str: ...
    def explain_problems(self) -> str: ...
    def is_solved(self) -> bool: ...
    def must_solve(self) -> None: ...
    def problems_to_str(self) -> str: ...
    def set_flags(self, arg0: typing.List[typing.Tuple[int, int]]) -> None: ...
    def set_postsolve_flags(
        self, arg0: typing.List[typing.Tuple[int, int]]
    ) -> None: ...
    def solve(self) -> bool: ...
    def try_solve(self) -> bool: ...
    pass

class SolverProblem:
    def __str__(self) -> str: ...
    @property
    def dep(self) -> typing.Optional[str]:
        """
        :type: typing.Optional[str]
        """
    @dep.setter
    def dep(self, arg0: typing.Optional[str]) -> None:
        pass
    @property
    def dep_id(self) -> int:
        """
        :type: int
        """
    @dep_id.setter
    def dep_id(self, arg0: int) -> None:
        pass
    @property
    def description(self) -> str:
        """
        :type: str
        """
    @description.setter
    def description(self, arg0: str) -> None:
        pass
    @property
    def source(self) -> typing.Optional[PackageInfo]:
        """
        :type: typing.Optional[PackageInfo]
        """
    @source.setter
    def source(self, arg0: typing.Optional[PackageInfo]) -> None:
        pass
    @property
    def source_id(self) -> int:
        """
        :type: int
        """
    @source_id.setter
    def source_id(self, arg0: int) -> None:
        pass
    @property
    def target(self) -> typing.Optional[PackageInfo]:
        """
        :type: typing.Optional[PackageInfo]
        """
    @target.setter
    def target(self, arg0: typing.Optional[PackageInfo]) -> None:
        pass
    @property
    def target_id(self) -> int:
        """
        :type: int
        """
    @target_id.setter
    def target_id(self, arg0: int) -> None:
        pass
    @property
    def type(self) -> SolverRuleinfo:
        """
        :type: SolverRuleinfo
        """
    @type.setter
    def type(self, arg0: SolverRuleinfo) -> None:
        pass
    pass

class SolverRuleinfo:
    """
    Members:

      SOLVER_RULE_UNKNOWN

      SOLVER_RULE_PKG

      SOLVER_RULE_PKG_NOT_INSTALLABLE

      SOLVER_RULE_PKG_NOTHING_PROVIDES_DEP

      SOLVER_RULE_PKG_REQUIRES

      SOLVER_RULE_PKG_SELF_CONFLICT

      SOLVER_RULE_PKG_CONFLICTS

      SOLVER_RULE_PKG_SAME_NAME

      SOLVER_RULE_PKG_OBSOLETES

      SOLVER_RULE_PKG_IMPLICIT_OBSOLETES

      SOLVER_RULE_PKG_INSTALLED_OBSOLETES

      SOLVER_RULE_PKG_RECOMMENDS

      SOLVER_RULE_PKG_CONSTRAINS

      SOLVER_RULE_UPDATE

      SOLVER_RULE_FEATURE

      SOLVER_RULE_JOB

      SOLVER_RULE_JOB_NOTHING_PROVIDES_DEP

      SOLVER_RULE_JOB_PROVIDED_BY_SYSTEM

      SOLVER_RULE_JOB_UNKNOWN_PACKAGE

      SOLVER_RULE_JOB_UNSUPPORTED

      SOLVER_RULE_DISTUPGRADE

      SOLVER_RULE_INFARCH

      SOLVER_RULE_CHOICE

      SOLVER_RULE_LEARNT

      SOLVER_RULE_BEST

      SOLVER_RULE_YUMOBS

      SOLVER_RULE_RECOMMENDS

      SOLVER_RULE_BLACK

      SOLVER_RULE_STRICT_REPO_PRIORITY
    """

    def __eq__(self, other: object) -> bool: ...
    def __getstate__(self) -> int: ...
    def __hash__(self) -> int: ...
    def __index__(self) -> int: ...
    def __init__(self, value: int) -> None: ...
    def __int__(self) -> int: ...
    def __ne__(self, other: object) -> bool: ...
    def __repr__(self) -> str: ...
    def __setstate__(self, state: int) -> None: ...
    @property
    def name(self) -> str:
        """
        :type: str
        """
    @property
    def value(self) -> int:
        """
        :type: int
        """
    SOLVER_RULE_BEST: libmambapy.bindings.SolverRuleinfo  # value = <SolverRuleinfo.SOLVER_RULE_BEST: 2304>
    SOLVER_RULE_BLACK: libmambapy.bindings.SolverRuleinfo  # value = <SolverRuleinfo.SOLVER_RULE_BLACK: 3072>
    SOLVER_RULE_CHOICE: libmambapy.bindings.SolverRuleinfo  # value = <SolverRuleinfo.SOLVER_RULE_CHOICE: 1792>
    SOLVER_RULE_DISTUPGRADE: libmambapy.bindings.SolverRuleinfo  # value = <SolverRuleinfo.SOLVER_RULE_DISTUPGRADE: 1280>
    SOLVER_RULE_FEATURE: libmambapy.bindings.SolverRuleinfo  # value = <SolverRuleinfo.SOLVER_RULE_FEATURE: 768>
    SOLVER_RULE_INFARCH: libmambapy.bindings.SolverRuleinfo  # value = <SolverRuleinfo.SOLVER_RULE_INFARCH: 1536>
    SOLVER_RULE_JOB: libmambapy.bindings.SolverRuleinfo  # value = <SolverRuleinfo.SOLVER_RULE_JOB: 1024>
    SOLVER_RULE_JOB_NOTHING_PROVIDES_DEP: libmambapy.bindings.SolverRuleinfo  # value = <SolverRuleinfo.SOLVER_RULE_JOB_NOTHING_PROVIDES_DEP: 1025>
    SOLVER_RULE_JOB_PROVIDED_BY_SYSTEM: libmambapy.bindings.SolverRuleinfo  # value = <SolverRuleinfo.SOLVER_RULE_JOB_PROVIDED_BY_SYSTEM: 1026>
    SOLVER_RULE_JOB_UNKNOWN_PACKAGE: libmambapy.bindings.SolverRuleinfo  # value = <SolverRuleinfo.SOLVER_RULE_JOB_UNKNOWN_PACKAGE: 1027>
    SOLVER_RULE_JOB_UNSUPPORTED: libmambapy.bindings.SolverRuleinfo  # value = <SolverRuleinfo.SOLVER_RULE_JOB_UNSUPPORTED: 1028>
    SOLVER_RULE_LEARNT: libmambapy.bindings.SolverRuleinfo  # value = <SolverRuleinfo.SOLVER_RULE_LEARNT: 2048>
    SOLVER_RULE_PKG: libmambapy.bindings.SolverRuleinfo  # value = <SolverRuleinfo.SOLVER_RULE_PKG: 256>
    SOLVER_RULE_PKG_CONFLICTS: libmambapy.bindings.SolverRuleinfo  # value = <SolverRuleinfo.SOLVER_RULE_PKG_CONFLICTS: 261>
    SOLVER_RULE_PKG_CONSTRAINS: libmambapy.bindings.SolverRuleinfo  # value = <SolverRuleinfo.SOLVER_RULE_PKG_CONSTRAINS: 267>
    SOLVER_RULE_PKG_IMPLICIT_OBSOLETES: libmambapy.bindings.SolverRuleinfo  # value = <SolverRuleinfo.SOLVER_RULE_PKG_IMPLICIT_OBSOLETES: 264>
    SOLVER_RULE_PKG_INSTALLED_OBSOLETES: libmambapy.bindings.SolverRuleinfo  # value = <SolverRuleinfo.SOLVER_RULE_PKG_INSTALLED_OBSOLETES: 265>
    SOLVER_RULE_PKG_NOTHING_PROVIDES_DEP: libmambapy.bindings.SolverRuleinfo  # value = <SolverRuleinfo.SOLVER_RULE_PKG_NOTHING_PROVIDES_DEP: 258>
    SOLVER_RULE_PKG_NOT_INSTALLABLE: libmambapy.bindings.SolverRuleinfo  # value = <SolverRuleinfo.SOLVER_RULE_PKG_NOT_INSTALLABLE: 257>
    SOLVER_RULE_PKG_OBSOLETES: libmambapy.bindings.SolverRuleinfo  # value = <SolverRuleinfo.SOLVER_RULE_PKG_OBSOLETES: 263>
    SOLVER_RULE_PKG_RECOMMENDS: libmambapy.bindings.SolverRuleinfo  # value = <SolverRuleinfo.SOLVER_RULE_PKG_RECOMMENDS: 266>
    SOLVER_RULE_PKG_REQUIRES: libmambapy.bindings.SolverRuleinfo  # value = <SolverRuleinfo.SOLVER_RULE_PKG_REQUIRES: 259>
    SOLVER_RULE_PKG_SAME_NAME: libmambapy.bindings.SolverRuleinfo  # value = <SolverRuleinfo.SOLVER_RULE_PKG_SAME_NAME: 262>
    SOLVER_RULE_PKG_SELF_CONFLICT: libmambapy.bindings.SolverRuleinfo  # value = <SolverRuleinfo.SOLVER_RULE_PKG_SELF_CONFLICT: 260>
    SOLVER_RULE_RECOMMENDS: libmambapy.bindings.SolverRuleinfo  # value = <SolverRuleinfo.SOLVER_RULE_RECOMMENDS: 2816>
    SOLVER_RULE_STRICT_REPO_PRIORITY: libmambapy.bindings.SolverRuleinfo  # value = <SolverRuleinfo.SOLVER_RULE_STRICT_REPO_PRIORITY: 3328>
    SOLVER_RULE_UNKNOWN: libmambapy.bindings.SolverRuleinfo  # value = <SolverRuleinfo.SOLVER_RULE_UNKNOWN: 0>
    SOLVER_RULE_UPDATE: libmambapy.bindings.SolverRuleinfo  # value = <SolverRuleinfo.SOLVER_RULE_UPDATE: 512>
    SOLVER_RULE_YUMOBS: libmambapy.bindings.SolverRuleinfo  # value = <SolverRuleinfo.SOLVER_RULE_YUMOBS: 2560>
    __members__: dict  # value = {'SOLVER_RULE_UNKNOWN': <SolverRuleinfo.SOLVER_RULE_UNKNOWN: 0>, 'SOLVER_RULE_PKG': <SolverRuleinfo.SOLVER_RULE_PKG: 256>, 'SOLVER_RULE_PKG_NOT_INSTALLABLE': <SolverRuleinfo.SOLVER_RULE_PKG_NOT_INSTALLABLE: 257>, 'SOLVER_RULE_PKG_NOTHING_PROVIDES_DEP': <SolverRuleinfo.SOLVER_RULE_PKG_NOTHING_PROVIDES_DEP: 258>, 'SOLVER_RULE_PKG_REQUIRES': <SolverRuleinfo.SOLVER_RULE_PKG_REQUIRES: 259>, 'SOLVER_RULE_PKG_SELF_CONFLICT': <SolverRuleinfo.SOLVER_RULE_PKG_SELF_CONFLICT: 260>, 'SOLVER_RULE_PKG_CONFLICTS': <SolverRuleinfo.SOLVER_RULE_PKG_CONFLICTS: 261>, 'SOLVER_RULE_PKG_SAME_NAME': <SolverRuleinfo.SOLVER_RULE_PKG_SAME_NAME: 262>, 'SOLVER_RULE_PKG_OBSOLETES': <SolverRuleinfo.SOLVER_RULE_PKG_OBSOLETES: 263>, 'SOLVER_RULE_PKG_IMPLICIT_OBSOLETES': <SolverRuleinfo.SOLVER_RULE_PKG_IMPLICIT_OBSOLETES: 264>, 'SOLVER_RULE_PKG_INSTALLED_OBSOLETES': <SolverRuleinfo.SOLVER_RULE_PKG_INSTALLED_OBSOLETES: 265>, 'SOLVER_RULE_PKG_RECOMMENDS': <SolverRuleinfo.SOLVER_RULE_PKG_RECOMMENDS: 266>, 'SOLVER_RULE_PKG_CONSTRAINS': <SolverRuleinfo.SOLVER_RULE_PKG_CONSTRAINS: 267>, 'SOLVER_RULE_UPDATE': <SolverRuleinfo.SOLVER_RULE_UPDATE: 512>, 'SOLVER_RULE_FEATURE': <SolverRuleinfo.SOLVER_RULE_FEATURE: 768>, 'SOLVER_RULE_JOB': <SolverRuleinfo.SOLVER_RULE_JOB: 1024>, 'SOLVER_RULE_JOB_NOTHING_PROVIDES_DEP': <SolverRuleinfo.SOLVER_RULE_JOB_NOTHING_PROVIDES_DEP: 1025>, 'SOLVER_RULE_JOB_PROVIDED_BY_SYSTEM': <SolverRuleinfo.SOLVER_RULE_JOB_PROVIDED_BY_SYSTEM: 1026>, 'SOLVER_RULE_JOB_UNKNOWN_PACKAGE': <SolverRuleinfo.SOLVER_RULE_JOB_UNKNOWN_PACKAGE: 1027>, 'SOLVER_RULE_JOB_UNSUPPORTED': <SolverRuleinfo.SOLVER_RULE_JOB_UNSUPPORTED: 1028>, 'SOLVER_RULE_DISTUPGRADE': <SolverRuleinfo.SOLVER_RULE_DISTUPGRADE: 1280>, 'SOLVER_RULE_INFARCH': <SolverRuleinfo.SOLVER_RULE_INFARCH: 1536>, 'SOLVER_RULE_CHOICE': <SolverRuleinfo.SOLVER_RULE_CHOICE: 1792>, 'SOLVER_RULE_LEARNT': <SolverRuleinfo.SOLVER_RULE_LEARNT: 2048>, 'SOLVER_RULE_BEST': <SolverRuleinfo.SOLVER_RULE_BEST: 2304>, 'SOLVER_RULE_YUMOBS': <SolverRuleinfo.SOLVER_RULE_YUMOBS: 2560>, 'SOLVER_RULE_RECOMMENDS': <SolverRuleinfo.SOLVER_RULE_RECOMMENDS: 2816>, 'SOLVER_RULE_BLACK': <SolverRuleinfo.SOLVER_RULE_BLACK: 3072>, 'SOLVER_RULE_STRICT_REPO_PRIORITY': <SolverRuleinfo.SOLVER_RULE_STRICT_REPO_PRIORITY: 3328>}
    pass

class SpecBase:
    pass

class SpecImpl(SpecBase):
    def __init__(self) -> None: ...
    pass

class SubdirData:
    def __init__(
        self, arg0: Channel, arg1: str, arg2: str, arg3: MultiPackageCache, arg4: str
    ) -> None: ...
    def cache_path(self) -> str: ...
    def create_repo(self, arg0: Pool) -> Repo: ...
    def download_and_check_targets(self, arg0: DownloadTargetList) -> bool: ...
    def finalize_checks(self) -> None: ...
    def loaded(self) -> bool: ...
    pass

class TimeRef:
    @typing.overload
    def __init__(self) -> None: ...
    @typing.overload
    def __init__(self, arg0: int) -> None: ...
    def set(self, arg0: int) -> None: ...
    def set_now(self) -> None: ...
    def timestamp(self) -> str: ...
    pass

class Transaction:
    @typing.overload
    def __init__(self, arg0: Solver, arg1: MultiPackageCache) -> None: ...
    @typing.overload
    def __init__(self, arg0: Pool, arg1: Solver, arg2: MultiPackageCache) -> None: ...
    def execute(self, arg0: PrefixData) -> bool: ...
    def fetch_extract_packages(self) -> bool: ...
    def find_python_version(self) -> typing.Tuple[str, str]: ...
    def log_json(self) -> None: ...
    def print(self) -> None: ...
    def prompt(self) -> bool: ...
    def to_conda(
        self,
    ) -> typing.Tuple[
        typing.Tuple[typing.List[str], typing.List[str]],
        typing.List[typing.Tuple[str, str, str]],
        typing.List[typing.Tuple[str, str]],
    ]: ...
    pass

class ostream_redirect:
    def __enter__(self) -> None: ...
    def __exit__(self, *args) -> None: ...
    def __init__(self, stdout: bool = True, stderr: bool = True) -> None: ...
    pass

def cache_fn_url(arg0: str) -> str:
    pass

def cancel_json_output() -> None:
    pass

def clean(arg0: int) -> None:
    pass

def create_cache_dir(arg0: Path) -> str:
    pass

def generate_ed25519_keypair() -> typing.Tuple[str, str]:
    pass

def get_channels(arg0: typing.List[str]) -> typing.List[Channel]:
    pass

def get_virtual_packages() -> typing.List[PackageInfo]:
    pass

def init_console() -> None:
    pass

def sign(data: str, secret_key: str) -> str:
    pass

def simplify_conflicts(arg0: ProblemsGraph) -> ProblemsGraph:
    pass

def transmute(
    source_package: Path,
    destination_package: Path,
    compression_level: int,
    compression_threads: int = 1,
) -> bool:
    pass

MAMBA_CLEAN_ALL = 1
MAMBA_CLEAN_INDEX = 2
MAMBA_CLEAN_LOCKS = 16
MAMBA_CLEAN_PKGS = 4
MAMBA_CLEAN_TARBALLS = 8
MAMBA_DOWNLOAD_FAILFAST = 1
MAMBA_DOWNLOAD_SORT = 2
MAMBA_FORCE_REINSTALL = 4
MAMBA_NO_DEPS = 1
MAMBA_ONLY_DEPS = 2
SOLVER_ALLOWUNINSTALL = 2816
SOLVER_CLEANDEPS = 262144
SOLVER_DISFAVOR = 3328
SOLVER_DISTUPGRADE = 1792
SOLVER_DROP_ORPHANED = 2304
SOLVER_ERASE = 512
SOLVER_ESSENTIAL = 131072
SOLVER_FAVOR = 3072
SOLVER_FLAG_ADD_ALREADY_RECOMMENDED = 8
SOLVER_FLAG_ALLOW_ARCHCHANGE = 2
SOLVER_FLAG_ALLOW_DOWNGRADE = 1
SOLVER_FLAG_ALLOW_NAMECHANGE = 10
SOLVER_FLAG_ALLOW_UNINSTALL = 4
SOLVER_FLAG_ALLOW_VENDORCHANGE = 3
SOLVER_FLAG_BEST_OBEY_POLICY = 12
SOLVER_FLAG_BREAK_ORPHANS = 19
SOLVER_FLAG_DUP_ALLOW_ARCHCHANGE = 15
SOLVER_FLAG_DUP_ALLOW_DOWNGRADE = 14
SOLVER_FLAG_DUP_ALLOW_NAMECHANGE = 17
SOLVER_FLAG_DUP_ALLOW_VENDORCHANGE = 16
SOLVER_FLAG_FOCUS_BEST = 24
SOLVER_FLAG_FOCUS_INSTALLED = 20
SOLVER_FLAG_IGNORE_RECOMMENDED = 7
SOLVER_FLAG_INSTALL_ALSO_UPDATES = 26
SOLVER_FLAG_KEEP_EXPLICIT_OBSOLETES = 11
SOLVER_FLAG_KEEP_ORPHANS = 18
SOLVER_FLAG_NEED_UPDATEPROVIDE = 22
SOLVER_FLAG_NO_AUTOTARGET = 13
SOLVER_FLAG_NO_INFARCHCHECK = 9
SOLVER_FLAG_NO_UPDATEPROVIDE = 5
SOLVER_FLAG_ONLY_NAMESPACE_RECOMMENDED = 27
SOLVER_FLAG_SPLITPROVIDES = 6
SOLVER_FLAG_STRICT_REPO_PRIORITY = 28
SOLVER_FLAG_STRONG_RECOMMENDS = 25
SOLVER_FLAG_URPM_REORDER = 23
SOLVER_FLAG_YUM_OBSOLETES = 21
SOLVER_FORCEBEST = 1048576
SOLVER_INSTALL = 256
SOLVER_JOBMASK = 65280
SOLVER_LOCK = 1536
SOLVER_MULTIVERSION = 1280
SOLVER_NOAUTOSET = 536870912
SOLVER_NOOP = 0
SOLVER_NOTBYUSER = 4194304
SOLVER_ORUPDATE = 524288
SOLVER_SELECTMASK = 255
SOLVER_SETARCH = 67108864
SOLVER_SETEV = 16777216
SOLVER_SETEVR = 33554432
SOLVER_SETMASK = 2130706432
SOLVER_SETNAME = 1073741824
SOLVER_SETREPO = 268435456
SOLVER_SETVENDOR = 134217728
SOLVER_SOLVABLE = 1
SOLVER_SOLVABLE_ALL = 6
SOLVER_SOLVABLE_NAME = 2
SOLVER_SOLVABLE_ONE_OF = 4
SOLVER_SOLVABLE_PROVIDES = 3
SOLVER_SOLVABLE_REPO = 5
SOLVER_TARGETED = 2097152
SOLVER_UPDATE = 768
SOLVER_USERINSTALLED = 2560
SOLVER_VERIFY = 2048
SOLVER_WEAK = 65536
SOLVER_WEAKENDEPS = 1024
