# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Implements the query language for conda packages (a.k.a, MatchSpec).

The MatchSpec is the conda package specification (e.g. `conda==23.3`, `python<3.7`,
`cryptography * *_0`) and is used to communicate the desired packages to install.
"""

import re
import warnings
from abc import ABCMeta, abstractmethod, abstractproperty
from collections.abc import Mapping
from functools import reduce
from itertools import chain
from logging import getLogger
from operator import attrgetter
from os.path import basename

from ..auxlib.decorators import memoizedproperty
from ..base.constants import CONDA_PACKAGE_EXTENSION_V1, CONDA_PACKAGE_EXTENSION_V2
from ..base.context import context
from ..common.compat import isiterable
from ..common.io import dashlist
from ..common.iterators import groupby_to_dict as groupby
from ..common.path import expand, is_package_file, strip_pkg_extension, url_to_path
from ..common.url import is_url, path_to_url, unquote
from ..exceptions import InvalidMatchSpec, InvalidSpec
from .channel import Channel
from .version import BuildNumberMatch, VersionSpec

try:
    from frozendict import frozendict
except ImportError:
    from ..auxlib.collection import frozendict

log = getLogger(__name__)


class MatchSpecType(type):
    def __call__(cls, spec_arg=None, **kwargs):
        try:
            if spec_arg:
                if isinstance(spec_arg, MatchSpec) and not kwargs:
                    return spec_arg
                elif isinstance(spec_arg, MatchSpec):
                    new_kwargs = dict(spec_arg._match_components)
                    new_kwargs.setdefault("optional", spec_arg.optional)
                    new_kwargs.setdefault("target", spec_arg.target)
                    new_kwargs["_original_spec_str"] = spec_arg.original_spec_str
                    new_kwargs.update(**kwargs)
                    return super().__call__(**new_kwargs)
                elif isinstance(spec_arg, str):
                    parsed = _parse_spec_str(spec_arg)
                    if kwargs:
                        parsed = dict(parsed, **kwargs)
                        if set(kwargs) - {"optional", "target"}:
                            # if kwargs has anything but optional and target,
                            # strip out _original_spec_str from parsed
                            parsed.pop("_original_spec_str", None)
                    return super().__call__(**parsed)
                elif isinstance(spec_arg, Mapping):
                    parsed = dict(spec_arg, **kwargs)
                    return super().__call__(**parsed)
                elif hasattr(spec_arg, "to_match_spec"):
                    spec = spec_arg.to_match_spec()
                    if kwargs:
                        return MatchSpec(spec, **kwargs)
                    else:
                        return spec
                else:
                    raise InvalidSpec(
                        f"Invalid MatchSpec:\n  spec_arg={spec_arg}\n  kwargs={kwargs}"
                    )
            else:
                return super().__call__(**kwargs)
        except InvalidSpec as e:
            msg = ""
            if spec_arg:
                msg += f"{spec_arg}"
            if kwargs:
                msg += " " + ", ".join(f"{k}={v}" for k, v in kwargs.items())
            raise InvalidMatchSpec(msg, details=e) from e


class MatchSpec(metaclass=MatchSpecType):
    """The query language for conda packages.

    Any of the fields that comprise a :class:`PackageRecord` can be used to compose a
    :class:`MatchSpec`.

    :class:`MatchSpec` can be composed with keyword arguments, where keys are any of the
    attributes of :class:`PackageRecord`.  Values for keyword arguments are the exact values the
    attribute should match against.  Many fields can also be matched against non-exact values--by
    including wildcard `*` and `>`/`<` ranges--where supported.  Any non-specified field is
    the equivalent of a full wildcard match.

    :class:`MatchSpec` can also be composed using a single positional argument, with optional
    keyword arguments.  Keyword arguments also override any conflicting information provided in
    the positional argument.  The positional argument can be either an existing :class:`MatchSpec`
    instance or a string.  Conda has historically had several string representations for equivalent
    :class:`MatchSpec`s.  This :class:`MatchSpec` should accept any existing valid spec string, and
    correctly compose a :class:`MatchSpec` instance.

    A series of rules are now followed for creating the canonical string representation of a
    :class:`MatchSpec` instance.  The canonical string representation can generically be
    represented by

        (channel(/subdir):(namespace):)name(version(build))[key1=value1,key2=value2]

    where `()` indicate optional fields.  The rules for constructing a canonical string
    representation are:

    1. `name` (i.e. "package name") is required, but its value can be '*'.  Its position is always
       outside the key-value brackets.
    2. If `version` is an exact version, it goes outside the key-value brackets and is prepended
       by `==`. If `version` is a "fuzzy" value (e.g. `1.11.*`), it goes outside the key-value
       brackets with the `.*` left off and is prepended by `=`.  Otherwise `version` is included
       inside key-value brackets.
    3. If `version` is an exact version, and `build` is an exact value, `build` goes outside
       key-value brackets prepended by a `=`.  Otherwise, `build` goes inside key-value brackets.
       `build_string` is an alias for `build`.
    4. The `namespace` position is being held for a future conda feature.
    5. If `channel` is included and is an exact value, a `::` separator is ued between `channel`
       and `name`.  `channel` can either be a canonical channel name or a channel url.  In the
       canonical string representation, the canonical channel name will always be used.
    6. If `channel` is an exact value and `subdir` is an exact value, `subdir` is appended to
       `channel` with a `/` separator.  Otherwise, `subdir` is included in the key-value brackets.
    7. Key-value brackets can be delimited by comma, space, or comma+space.  Value can optionally
       be wrapped in single or double quotes, but must be wrapped if `value` contains a comma,
       space, or equal sign.  The canonical format uses comma delimiters and single quotes.
    8. When constructing a :class:`MatchSpec` instance from a string, any key-value pair given
       inside the key-value brackets overrides any matching parameter given outside the brackets.

    When :class:`MatchSpec` attribute values are simple strings, the are interpreted using the
    following conventions:

      - If the string begins with `^` and ends with `$`, it is converted to a regex.
      - If the string contains an asterisk (`*`), it is transformed from a glob to a regex.
      - Otherwise, an exact match to the string is sought.


    Examples:
        >>> str(MatchSpec(name='foo', build='py2*', channel='conda-forge'))
        'conda-forge::foo[build=py2*]'
        >>> str(MatchSpec('foo 1.0 py27_0'))
        'foo==1.0=py27_0'
        >>> str(MatchSpec('foo=1.0=py27_0'))
        'foo==1.0=py27_0'
        >>> str(MatchSpec('conda-forge::foo[version=1.0.*]'))
        'conda-forge::foo=1.0'
        >>> str(MatchSpec('conda-forge/linux-64::foo>=1.0'))
        "conda-forge/linux-64::foo[version='>=1.0']"
        >>> str(MatchSpec('*/linux-64::foo>=1.0'))
        "foo[subdir=linux-64,version='>=1.0']"

    To fully-specify a package with a full, exact spec, the fields
      - channel
      - subdir
      - name
      - version
      - build
    must be given as exact values.  In the future, the namespace field will be added to this list.
    Alternatively, an exact spec is given by '*[md5=12345678901234567890123456789012]'
    or '*[sha256=f453db4ffe2271ec492a2913af4e61d4a6c118201f07de757df0eff769b65d2e]'.
    """

    FIELD_NAMES = (
        "channel",
        "subdir",
        "name",
        "version",
        "build",
        "build_number",
        "track_features",
        "features",
        "url",
        "md5",
        "sha256",
        "license",
        "license_family",
        "fn",
    )
    FIELD_NAMES_SET = frozenset(FIELD_NAMES)
    _MATCHER_CACHE = {}

    def __init__(self, optional=False, target=None, **kwargs):
        self._optional = optional
        self._target = target
        self._original_spec_str = kwargs.pop("_original_spec_str", None)
        self._match_components = self._build_components(**kwargs)

    @classmethod
    def from_dist_str(cls, dist_str):
        parts = {}
        if dist_str[-len(CONDA_PACKAGE_EXTENSION_V2) :] == CONDA_PACKAGE_EXTENSION_V2:
            dist_str = dist_str[: -len(CONDA_PACKAGE_EXTENSION_V2)]
        elif dist_str[-len(CONDA_PACKAGE_EXTENSION_V1) :] == CONDA_PACKAGE_EXTENSION_V1:
            dist_str = dist_str[: -len(CONDA_PACKAGE_EXTENSION_V1)]
        if "::" in dist_str:
            channel_subdir_str, dist_str = dist_str.split("::", 1)
            if "/" in channel_subdir_str:
                channel_str, subdir = channel_subdir_str.rsplit("/", 1)
                if subdir not in context.known_subdirs:
                    channel_str = channel_subdir_str
                    subdir = None
                parts["channel"] = channel_str
                if subdir:
                    parts["subdir"] = subdir
            else:
                parts["channel"] = channel_subdir_str

        name, version, build = dist_str.rsplit("-", 2)
        parts.update(
            {
                "name": name,
                "version": version,
                "build": build,
            }
        )
        return cls(**parts)

    def get_exact_value(self, field_name):
        v = self._match_components.get(field_name)
        return v and v.exact_value

    def get_raw_value(self, field_name):
        v = self._match_components.get(field_name)
        return v and v.raw_value

    def get(self, field_name, default=None):
        v = self.get_raw_value(field_name)
        return default if v is None else v

    @property
    def is_name_only_spec(self):
        return (
            len(self._match_components) == 1
            and "name" in self._match_components
            and self.name != "*"
        )

    def dist_str(self):
        return self.__str__()

    @property
    def optional(self):
        return self._optional

    @property
    def target(self):
        return self._target

    @property
    def original_spec_str(self):
        return self._original_spec_str

    def match(self, rec):
        """
        Accepts a `PackageRecord` or a dict, and matches can pull from any field
        in that record.  Returns True for a match, and False for no match.
        """
        if isinstance(rec, dict):
            # TODO: consider AttrDict instead of PackageRecord
            from .records import PackageRecord

            rec = PackageRecord.from_objects(rec)
        for field_name, v in self._match_components.items():
            if not self._match_individual(rec, field_name, v):
                return False
        return True

    def _match_individual(self, record, field_name, match_component):
        val = getattr(record, field_name)
        try:
            return match_component.match(val)
        except AttributeError:
            return match_component == val

    def _is_simple(self):
        return (
            len(self._match_components) == 1
            and self.get_exact_value("name") is not None
        )

    def _is_single(self):
        return len(self._match_components) == 1

    def _to_filename_do_not_use(self):
        # WARNING: this is potentially unreliable and use should probably be limited
        #   returns None if a filename can't be constructed
        fn_field = self.get_exact_value("fn")
        if fn_field:
            return fn_field
        vals = tuple(self.get_exact_value(x) for x in ("name", "version", "build"))
        if not any(x is None for x in vals):
            return ("{}-{}-{}".format(*vals)) + CONDA_PACKAGE_EXTENSION_V1
        else:
            return None

    def __repr__(self):
        builder = [f'{self.__class__.__name__}("{self}"']
        if self.target:
            builder.append(f', target="{self.target}"')
        if self.optional:
            builder.append(", optional=True")
        builder.append(")")
        return "".join(builder)

    def __str__(self):
        builder = []
        brackets = []

        channel_matcher = self._match_components.get("channel")
        if channel_matcher and channel_matcher.exact_value:
            builder.append(str(channel_matcher))
        elif channel_matcher and not channel_matcher.matches_all:
            brackets.append(f"channel={str(channel_matcher)}")

        subdir_matcher = self._match_components.get("subdir")
        if subdir_matcher:
            if channel_matcher and channel_matcher.exact_value:
                builder.append(f"/{subdir_matcher}")
            else:
                brackets.append(f"subdir={subdir_matcher}")

        name_matcher = self._match_components.get("name", "*")
        builder.append(("::%s" if builder else "%s") % name_matcher)

        version = self._match_components.get("version")
        build = self._match_components.get("build")
        version_exact = False
        if version:
            version = str(version)
            if any(s in version for s in "><$^|,"):
                brackets.append(f"version='{version}'")
            elif version[:2] in ("!=", "~="):
                if build:
                    brackets.append(f"version='{version}'")
                else:
                    builder.append(version)
            elif version[-2:] == ".*":
                builder.append("=" + version[:-2])
            elif version[-1] == "*":
                builder.append("=" + version[:-1])
            elif version.startswith("=="):
                builder.append(version)
                version_exact = True
            else:
                builder.append("==" + version)
                version_exact = True

        if build:
            build = str(build)
            if any(s in build for s in "><$^|,"):
                brackets.append(f"build='{build}'")
            elif "*" in build:
                brackets.append(f"build={build}")
            elif version_exact:
                builder.append("=" + build)
            else:
                brackets.append(f"build={build}")

        _skip = {"channel", "subdir", "name", "version", "build"}
        if "url" in self._match_components and "fn" in self._match_components:
            _skip.add("fn")
        for key in self.FIELD_NAMES:
            if key not in _skip and key in self._match_components:
                if key == "url" and channel_matcher:
                    # skip url in canonical str if channel already included
                    continue
                value = str(self._match_components[key])
                if any(s in value for s in ", ="):
                    brackets.append(f"{key}='{value}'")
                else:
                    brackets.append(f"{key}={value}")

        if brackets:
            builder.append("[{}]".format(",".join(brackets)))

        return "".join(builder)

    def __json__(self):
        return self.__str__()

    def conda_build_form(self):
        builder = []
        name = self.get_exact_value("name")
        assert name
        builder.append(name)

        build = self.get_raw_value("build")
        version = self.get_raw_value("version")

        if build:
            assert version
            builder += [version, build]
        elif version:
            builder.append(version)

        return " ".join(builder)

    def __eq__(self, other):
        if isinstance(other, MatchSpec):
            return self._hash_key == other._hash_key
        else:
            return False

    def __hash__(self):
        return hash(self._hash_key)

    @memoizedproperty
    def _hash_key(self):
        return self._match_components, self.optional, self.target

    def __contains__(self, field):
        return field in self._match_components

    def _build_components(self, **kwargs):
        not_fields = set(kwargs) - MatchSpec.FIELD_NAMES_SET
        if not_fields:
            raise InvalidMatchSpec(
                self._original_spec_str, f"Cannot match on field(s): {not_fields}"
            )
        _make_component = MatchSpec._make_component
        return frozendict(_make_component(key, value) for key, value in kwargs.items())

    @staticmethod
    def _make_component(field_name, value):
        if hasattr(value, "match"):
            matcher = value
            return field_name, matcher

        _MATCHER_CACHE = MatchSpec._MATCHER_CACHE
        cache_key = (field_name, value)
        cached_matcher = _MATCHER_CACHE.get(cache_key)
        if cached_matcher:
            return field_name, cached_matcher
        if field_name in _implementors:
            matcher = _implementors[field_name](value)
        else:
            matcher = ExactStrMatch(str(value))
        _MATCHER_CACHE[(field_name, value)] = matcher
        return field_name, matcher

    @property
    def name(self):
        return self.get_exact_value("name") or "*"

    #
    # Remaining methods are for back compatibility with conda-build. Do not remove
    # without coordination with the conda-build team.
    #
    @property
    def strictness(self):
        # With the old MatchSpec, strictness==3 if name, version, and
        # build were all specified.
        s = sum(f in self._match_components for f in ("name", "version", "build"))
        if s < len(self._match_components):
            return 3
        elif not self.get_exact_value("name") or "build" in self._match_components:
            return 3
        elif "version" in self._match_components:
            return 2
        else:
            return 1

    @property
    def spec(self):
        return self.conda_build_form()

    @property
    def version(self):
        # in the old MatchSpec object, version was a VersionSpec, not a str
        # so we'll keep that API here
        return self._match_components.get("version")

    @property
    def fn(self):
        val = self.get_raw_value("fn") or self.get_raw_value("url")
        if val:
            val = basename(val)
        assert val
        return val

    @classmethod
    def merge(cls, match_specs, union=False):
        match_specs = sorted(tuple(cls(s) for s in match_specs if s), key=str)
        name_groups = groupby(attrgetter("name"), match_specs)
        unmergeable = name_groups.pop("*", []) + name_groups.pop(None, [])

        merged_specs = []
        mergeable_groups = tuple(
            chain.from_iterable(
                groupby(lambda s: s.optional, group).values()
                for group in name_groups.values()
            )
        )
        for group in mergeable_groups:
            target_groups = groupby(attrgetter("target"), group)
            target_groups.pop(None, None)
            if len(target_groups) > 1:
                raise ValueError(f"Incompatible MatchSpec merge:{dashlist(group)}")
            merged_specs.append(
                reduce(lambda x, y: x._merge(y, union), group)
                if len(group) > 1
                else group[0]
            )
        return (*merged_specs, *unmergeable)

    @classmethod
    def union(cls, match_specs):
        return cls.merge(match_specs, union=True)

    def _merge(self, other, union=False):
        if self.optional != other.optional or self.target != other.target:
            raise ValueError(f"Incompatible MatchSpec merge:  - {self}\n  - {other}")

        final_components = {}
        component_names = set(self._match_components) | set(other._match_components)
        for component_name in component_names:
            this_component = self._match_components.get(component_name)
            that_component = other._match_components.get(component_name)
            if this_component is None and that_component is None:
                continue
            elif this_component is None:
                final_components[component_name] = that_component
            elif that_component is None:
                final_components[component_name] = this_component
            else:
                if union:
                    try:
                        final = this_component.union(that_component)
                    except (AttributeError, ValueError, TypeError):
                        final = f"{this_component}|{that_component}"
                else:
                    final = this_component.merge(that_component)
                final_components[component_name] = final
        return self.__class__(
            optional=self.optional, target=self.target, **final_components
        )


def _parse_version_plus_build(v_plus_b):
    """This should reliably pull the build string out of a version + build string combo.
    Examples:
        >>> _parse_version_plus_build("=1.2.3 0")
        ('=1.2.3', '0')
        >>> _parse_version_plus_build("1.2.3=0")
        ('1.2.3', '0')
        >>> _parse_version_plus_build(">=1.0 , < 2.0 py34_0")
        ('>=1.0,<2.0', 'py34_0')
        >>> _parse_version_plus_build(">=1.0 , < 2.0 =py34_0")
        ('>=1.0,<2.0', 'py34_0')
        >>> _parse_version_plus_build("=1.2.3 ")
        ('=1.2.3', None)
        >>> _parse_version_plus_build(">1.8,<2|==1.7")
        ('>1.8,<2|==1.7', None)
        >>> _parse_version_plus_build("* openblas_0")
        ('*', 'openblas_0')
        >>> _parse_version_plus_build("* *")
        ('*', '*')
    """
    parts = re.search(
        r"((?:.+?)[^><!,|]?)(?:(?<![=!|,<>~])(?:[ =])([^-=,|<>~]+?))?$", v_plus_b
    )
    if parts:
        version, build = parts.groups()
        build = build and build.strip()
    else:
        version, build = v_plus_b, None
    return version and version.replace(" ", ""), build


def _parse_legacy_dist(dist_str):
    """
    Examples:
        >>> _parse_legacy_dist("_license-1.1-py27_1.tar.bz2")
        ('_license', '1.1', 'py27_1')
        >>> _parse_legacy_dist("_license-1.1-py27_1")
        ('_license', '1.1', 'py27_1')
    """
    dist_str, _ = strip_pkg_extension(dist_str)
    name, version, build = dist_str.rsplit("-", 2)
    return name, version, build


def _parse_channel(channel_val):
    if not channel_val:
        return None, None
    chn = Channel(channel_val)
    channel_name = chn.name or chn.base_url
    return channel_name, chn.subdir


_PARSE_CACHE = {}


def _parse_spec_str(spec_str):
    cached_result = _PARSE_CACHE.get(spec_str)
    if cached_result:
        return cached_result

    original_spec_str = spec_str

    # pre-step for ugly backward compat
    if spec_str.endswith("@"):
        feature_name = spec_str[:-1]
        return {
            "name": "*",
            "track_features": (feature_name,),
        }

    # Step 1. strip '#' comment
    if "#" in spec_str:
        ndx = spec_str.index("#")
        spec_str, _ = spec_str[:ndx], spec_str[ndx:]
        spec_str.strip()

    # Step 1.b strip ' if ' anticipating future compatibility issues
    spec_split = spec_str.split(" if ", 1)
    if len(spec_split) > 1:
        log.debug("Ignoring conditional in spec %s", spec_str)
    spec_str = spec_split[0]

    # Step 2. done if spec_str is a tarball
    if is_package_file(spec_str):
        # treat as a normal url
        if not is_url(spec_str):
            spec_str = unquote(path_to_url(expand(spec_str)))

        channel = Channel(spec_str)
        if channel.subdir:
            name, version, build = _parse_legacy_dist(channel.package_filename)
            result = {
                "channel": channel.canonical_name,
                "subdir": channel.subdir,
                "name": name,
                "version": version,
                "build": build,
                "fn": channel.package_filename,
                "url": spec_str,
            }
        else:
            # url is not a channel
            if spec_str.startswith("file://"):
                # We must undo percent-encoding when generating fn.
                path_or_url = url_to_path(spec_str)
            else:
                path_or_url = spec_str

            return {
                "name": "*",
                "fn": basename(path_or_url),
                "url": spec_str,
            }
        return result

    # Step 3. strip off brackets portion
    brackets = {}
    m3 = re.match(r".*(?:(\[.*\]))", spec_str)
    if m3:
        brackets_str = m3.groups()[0]
        spec_str = spec_str.replace(brackets_str, "")
        brackets_str = brackets_str[1:-1]
        m3b = re.finditer(
            r'([a-zA-Z0-9_-]+?)=(["\']?)([^\'"]*?)(\2)(?:[, ]|$)', brackets_str
        )
        for match in m3b:
            key, _, value, _ = match.groups()
            if not key or not value:
                raise InvalidMatchSpec(
                    original_spec_str, "key-value mismatch in brackets"
                )
            brackets[key] = value

    # Step 4. strip off parens portion
    m4 = re.match(r".*(?:(\(.*\)))", spec_str)
    parens = {}
    if m4:
        parens_str = m4.groups()[0]
        spec_str = spec_str.replace(parens_str, "")
        parens_str = parens_str[1:-1]
        m4b = re.finditer(
            r'([a-zA-Z0-9_-]+?)=(["\']?)([^\'"]*?)(\2)(?:[, ]|$)', parens_str
        )
        for match in m4b:
            key, _, value, _ = match.groups()
            parens[key] = value
        if "optional" in parens_str:
            parens["optional"] = True

    # Step 5. strip off '::' channel and namespace
    m5 = spec_str.rsplit(":", 2)
    m5_len = len(m5)
    if m5_len == 3:
        channel_str, namespace, spec_str = m5
    elif m5_len == 2:
        namespace, spec_str = m5
        channel_str = None
    elif m5_len:
        spec_str = m5[0]
        channel_str, namespace = None, None
    else:
        raise NotImplementedError()
    channel, subdir = _parse_channel(channel_str)
    if "channel" in brackets:
        b_channel, b_subdir = _parse_channel(brackets.pop("channel"))
        if b_channel:
            channel = b_channel
        if b_subdir:
            subdir = b_subdir
    if "subdir" in brackets:
        subdir = brackets.pop("subdir")

    # Step 6. strip off package name from remaining version + build
    m3 = re.match(r"([^ =<>!~]+)?([><!=~ ].+)?", spec_str)
    if m3:
        name, spec_str = m3.groups()
        if name is None:
            raise InvalidMatchSpec(
                original_spec_str, f"no package name found in '{spec_str}'"
            )
    else:
        raise InvalidMatchSpec(original_spec_str, "no package name found")

    # Step 7. otherwise sort out version + build
    spec_str = spec_str and spec_str.strip()
    # This was an attempt to make MatchSpec('numpy-1.11.0-py27_0') work like we'd want. It's
    # not possible though because plenty of packages have names with more than one '-'.
    # if spec_str is None and name.count('-') >= 2:
    #     name, version, build = _parse_legacy_dist(name)
    if spec_str:
        if "[" in spec_str:
            raise InvalidMatchSpec(
                original_spec_str, "multiple brackets sections not allowed"
            )

        version, build = _parse_version_plus_build(spec_str)

        # Catch cases where version ends up as "==" and pass it through so existing error
        # handling code can treat it like cases where version ends up being "<=" or ">=".
        # This is necessary because the "Translation" code below mangles "==" into a empty
        # string, which results in an empty version field on "components." The set of fields
        # on components drives future logic which breaks on an empty string but will deal with
        # missing versions like "==", "<=", and ">=" "correctly."
        #
        # All of these "missing version" cases result from match specs like "numpy==",
        # "numpy<=", "numpy>=", "numpy= " (with trailing space). Existing code indicates
        # these should be treated as an error and an exception raised.
        # IMPORTANT: "numpy=" (no trailing space) is treated as valid.
        if version == "==" or version == "=":
            pass
        # Otherwise,
        # translate version '=1.2.3' to '1.2.3*'
        # is it a simple version starting with '='? i.e. '=1.2.3'
        elif version[0] == "=":
            test_str = version[1:]
            if version[:2] == "==" and build is None:
                version = version[2:]
            elif not any(c in test_str for c in "=,|"):
                if build is None and test_str[-1] != "*":
                    version = test_str + "*"
                else:
                    version = test_str
    else:
        version, build = None, None

    # Step 8. now compile components together
    components = {}
    components["name"] = name or "*"

    if channel is not None:
        components["channel"] = channel
    if subdir is not None:
        components["subdir"] = subdir
    if namespace is not None:
        # components['namespace'] = namespace
        pass
    if version is not None:
        components["version"] = version
    if build is not None:
        components["build"] = build

    # anything in brackets will now strictly override key as set in other area of spec str
    # EXCEPT FOR: name
    # If we let name in brackets override a name outside of brackets it is possible to write
    # MatchSpecs that appear to install one package but actually install a completely different one
    # e.g. tensorflow[name=* version=* md5=<hash of pytorch package> ] will APPEAR to install
    # tensorflow but actually install pytorch.
    if "name" in components and "name" in brackets:
        msg = (
            f"'name' specified both inside ({brackets['name']}) and outside "
            f"({components['name']}) of brackets. The value outside of brackets "
            f"({components['name']}) will be used."
        )
        warnings.warn(msg, UserWarning)
        del brackets["name"]
    components.update(brackets)
    components["_original_spec_str"] = original_spec_str
    _PARSE_CACHE[original_spec_str] = components
    return components


class MatchInterface(metaclass=ABCMeta):
    def __init__(self, value):
        self._raw_value = value

    @abstractmethod
    def match(self, other):
        raise NotImplementedError()

    def matches(self, value):
        return self.match(value)

    @property
    def raw_value(self):
        return self._raw_value

    @abstractproperty
    def exact_value(self):
        """If the match value is an exact specification, returns the value.
        Otherwise returns None.
        """
        raise NotImplementedError()

    def merge(self, other):
        if self.raw_value != other.raw_value:
            raise ValueError(
                f"Incompatible component merge:\n  - {self.raw_value!r}\n  - {other.raw_value!r}"
            )
        return self.raw_value

    def union(self, other):
        options = {self.raw_value, other.raw_value}
        return "|".join(options)


class _StrMatchMixin:
    def __str__(self):
        return self._raw_value

    def __repr__(self):
        return f"{self.__class__.__name__}('{self._raw_value}')"

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self._raw_value == other._raw_value

    def __hash__(self):
        return hash(self._raw_value)

    @property
    def exact_value(self):
        return self._raw_value


class ExactStrMatch(_StrMatchMixin, MatchInterface):
    __slots__ = ("_raw_value",)

    def __init__(self, value):
        super().__init__(value)

    def match(self, other):
        try:
            _other_val = other._raw_value
        except AttributeError:
            _other_val = str(other)
        return self._raw_value == _other_val


class ExactLowerStrMatch(ExactStrMatch):
    def __init__(self, value):
        super().__init__(value.lower())

    def match(self, other):
        try:
            _other_val = other._raw_value
        except AttributeError:
            _other_val = str(other)
        return self._raw_value == _other_val.lower()


class GlobStrMatch(_StrMatchMixin, MatchInterface):
    __slots__ = "_raw_value", "_re_match"

    def __init__(self, value):
        super().__init__(value)
        self._re_match = None

        try:
            if value.startswith("^") and value.endswith("$"):
                self._re_match = re.compile(value).match
            elif "*" in value:
                value = re.escape(value).replace("\\*", r".*")
                self._re_match = re.compile(rf"^(?:{value})$").match
        except re.error as e:
            raise InvalidMatchSpec(
                value, f"Contains an invalid regular expression. '{e}'"
            )

    def match(self, other):
        try:
            _other_val = other._raw_value
        except AttributeError:
            _other_val = str(other)

        if self._re_match:
            return self._re_match(_other_val)
        else:
            return self._raw_value == _other_val

    @property
    def exact_value(self):
        return self._raw_value if self._re_match is None else None

    @property
    def matches_all(self):
        return self._raw_value == "*"


class GlobLowerStrMatch(GlobStrMatch):
    def __init__(self, value):
        super().__init__(value.lower())


class SplitStrMatch(MatchInterface):
    __slots__ = ("_raw_value",)

    def __init__(self, value):
        super().__init__(self._convert(value))

    def _convert(self, value):
        try:
            return frozenset(value.replace(" ", ",").split(","))
        except AttributeError:
            if isiterable(value):
                return frozenset(value)
            raise

    def match(self, other):
        try:
            return other and self._raw_value & other._raw_value
        except AttributeError:
            return self._raw_value & self._convert(other)

    def __repr__(self):
        if self._raw_value:
            return "{{{}}}".format(", ".join(f"'{s}'" for s in sorted(self._raw_value)))
        else:
            return "set()"

    def __str__(self):
        # this space delimiting makes me nauseous
        return " ".join(sorted(self._raw_value))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self._raw_value == other._raw_value

    def __hash__(self):
        return hash(self._raw_value)

    @property
    def exact_value(self):
        return self._raw_value


class FeatureMatch(MatchInterface):
    __slots__ = ("_raw_value",)

    def __init__(self, value):
        super().__init__(self._convert(value))

    def _convert(self, value):
        if not value:
            return frozenset()
        elif isinstance(value, str):
            return frozenset(
                f
                for f in (ff.strip() for ff in value.replace(" ", ",").split(","))
                if f
            )
        else:
            return frozenset(f for f in (ff.strip() for ff in value) if f)

    def match(self, other):
        other = self._convert(other)
        return self._raw_value == other

    def __repr__(self):
        return "[{}]".format(", ".join(f"'{k}'" for k in sorted(self._raw_value)))

    def __str__(self):
        return " ".join(sorted(self._raw_value))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self._raw_value == other._raw_value

    def __hash__(self):
        return hash(self._raw_value)

    @property
    def exact_value(self):
        return self._raw_value


class ChannelMatch(GlobStrMatch):
    def __init__(self, value):
        self._re_match = None

        try:
            if isinstance(value, str):
                if value.startswith("^") and value.endswith("$"):
                    self._re_match = re.compile(value).match
                elif "*" in value:
                    self._re_match = re.compile(
                        r"^(?:{})$".format(value.replace("*", r".*"))
                    ).match
                else:
                    value = Channel(value)
        except re.error as e:
            raise InvalidMatchSpec(
                value, f"Contains an invalid regular expression. '{e}'"
            )

        super(GlobStrMatch, self).__init__(value)

    def match(self, other):
        try:
            _other_val = Channel(other._raw_value)
        except AttributeError:
            _other_val = Channel(other)

        if self._re_match:
            return self._re_match(_other_val.canonical_name)
        else:
            # assert ChannelMatch('pkgs/free').match('defaults') is False
            # assert ChannelMatch('defaults').match('pkgs/free') is True
            return self._raw_value.name in (_other_val.name, _other_val.canonical_name)

    def __str__(self):
        try:
            return f"{self._raw_value.name}"
        except AttributeError:
            return f"{self._raw_value}"

    def __repr__(self):
        return f"'{self.__str__()}'"


class CaseInsensitiveStrMatch(GlobLowerStrMatch):
    def match(self, other):
        try:
            _other_val = other._raw_value
        except AttributeError:
            _other_val = str(other)

        _other_val = _other_val.lower()
        if self._re_match:
            return self._re_match(_other_val)
        else:
            return self._raw_value == _other_val


_implementors = {
    "channel": ChannelMatch,
    "name": GlobLowerStrMatch,
    "version": VersionSpec,
    "build": GlobStrMatch,
    "build_number": BuildNumberMatch,
    "track_features": FeatureMatch,
    "features": FeatureMatch,
    "license": CaseInsensitiveStrMatch,
    "license_family": CaseInsensitiveStrMatch,
}
