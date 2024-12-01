# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Defines Channel and MultiChannel objects and other channel-related functions.

Object inheritance:

.. autoapi-inheritance-diagram:: Channel MultiChannel
   :top-classes: conda.models.channel.Channel
   :parts: 1
"""

from __future__ import annotations

from copy import copy
from itertools import chain
from logging import getLogger
from typing import TYPE_CHECKING

from boltons.setutils import IndexedSet

from ..base.constants import (
    DEFAULTS_CHANNEL_NAME,
    MAX_CHANNEL_PRIORITY,
    UNKNOWN_CHANNEL,
)
from ..base.context import context
from ..common.compat import ensure_text_type, isiterable
from ..common.path import is_package_file, is_path, win_path_backout
from ..common.url import (
    Url,
    has_scheme,
    is_url,
    join_url,
    path_to_url,
    split_conda_url_easy_parts,
    split_platform,
    split_scheme_auth_token,
    urlparse,
)

if TYPE_CHECKING:
    from typing import Self

    from ..base.context import Context


log = getLogger(__name__)


class ChannelType(type):
    """
    This metaclass does basic caching and enables static constructor method usage with a
    single arg.
    """

    def __call__(cls, *args, **kwargs):
        if len(args) == 1 and not kwargs:
            value = args[0]
            if isinstance(value, Channel):
                return value
            elif value in Channel._cache_:
                return Channel._cache_[value]
            else:
                c = Channel._cache_[value] = Channel.from_value(value)
                return c
        elif "channels" in kwargs:
            # presence of 'channels' kwarg indicates MultiChannel
            channels = tuple(cls(**_kwargs) for _kwargs in kwargs["channels"])
            return MultiChannel(kwargs["name"], channels)
        else:
            return super().__call__(*args, **kwargs)


class Channel(metaclass=ChannelType):
    """
    Channel:
    scheme <> auth <> location <> token <> channel <> subchannel <> platform <> package_filename

    Package Spec:
    channel <> subchannel <> namespace <> package_name

    """

    _cache_ = {}

    @staticmethod
    def _reset_state():
        Channel._cache_ = {}

    def __init__(
        self,
        scheme=None,
        auth=None,
        location=None,
        token=None,
        name=None,
        platform=None,
        package_filename=None,
    ):
        self.scheme = scheme
        self.auth = auth
        self.location = location
        self.token = token
        self.name = name or ""
        self.platform = platform
        self.package_filename = package_filename

    @property
    def channel_location(self):
        return self.location

    @property
    def channel_name(self):
        return self.name

    @property
    def subdir(self):
        return self.platform

    @staticmethod
    def from_url(url):
        return parse_conda_channel_url(url)

    @staticmethod
    def from_channel_name(channel_name):
        return _get_channel_for_name(channel_name)

    @staticmethod
    def from_value(value: str | None) -> Self:
        """Construct a new :class:`Channel` from a single value.

        Args:
          value: Anyone of the following forms:

            `None`, or one of the special strings "<unknown>", "None:///<unknown>", or "None":
                represents the unknown channel, used for packages with unknown origin.

            A URL including a scheme like ``file://`` or ``https://``:
                represents a channel URL.

            A local directory path:
                represents a local channel; relative paths must start with ``./``.

            A package file (i.e. the path to a file ending in ``.conda`` or ``.tar.bz2``):
                represents a channel for a single package

            A known channel name:
                represents a known channel, e.g. from the users ``.condarc`` file or
                the global configuration.

        Returns:
          A channel object.
        """
        if value in (None, "<unknown>", "None:///<unknown>", "None"):
            return Channel(name=UNKNOWN_CHANNEL)
        value = ensure_text_type(value)
        if has_scheme(value):
            if value.startswith("file:"):
                value = win_path_backout(value)
            return Channel.from_url(value)
        elif is_path(value):
            return Channel.from_url(path_to_url(value))
        elif is_package_file(value):
            if value.startswith("file:"):
                value = win_path_backout(value)
            return Channel.from_url(value)
        else:
            # at this point assume we don't have a bare (non-scheme) url
            #   e.g. this would be bad:  repo.anaconda.com/pkgs/free
            _stripped, platform = split_platform(context.known_subdirs, value)
            if _stripped in context.custom_multichannels:
                return MultiChannel(
                    _stripped, context.custom_multichannels[_stripped], platform
                )
            else:
                return Channel.from_channel_name(value)

    @staticmethod
    def make_simple_channel(channel_alias, channel_url, name=None):
        ca = channel_alias
        test_url, scheme, auth, token = split_scheme_auth_token(channel_url)
        if name and scheme:
            return Channel(
                scheme=scheme,
                auth=auth,
                location=test_url,
                token=token,
                name=name.strip("/"),
            )
        if scheme:
            if ca.location and test_url.startswith(ca.location):
                location, name = ca.location, test_url.replace(ca.location, "", 1)
            else:
                url_parts = urlparse(test_url)
                location = str(Url(hostname=url_parts.hostname, port=url_parts.port))
                name = url_parts.path or ""
            return Channel(
                scheme=scheme,
                auth=auth,
                location=location,
                token=token,
                name=name.strip("/"),
            )
        else:
            return Channel(
                scheme=ca.scheme,
                auth=ca.auth,
                location=ca.location,
                token=ca.token,
                name=name and name.strip("/") or channel_url.strip("/"),
            )

    @property
    def canonical_name(self):
        try:
            return self.__canonical_name
        except AttributeError:
            pass

        for multiname, channels in context.custom_multichannels.items():
            for channel in channels:
                if self.name == channel.name:
                    cn = self.__canonical_name = multiname
                    return cn

        for that_name in context.custom_channels:
            if self.name and tokenized_startswith(
                self.name.split("/"), that_name.split("/")
            ):
                cn = self.__canonical_name = self.name
                return cn

        if any(
            alias.location == self.location
            for alias in (
                context.channel_alias,
                *context.migrated_channel_aliases,
            )
        ):
            cn = self.__canonical_name = self.name
            return cn

        # fall back to the equivalent of self.base_url
        # re-defining here because base_url for MultiChannel is None
        if self.scheme:
            cn = self.__canonical_name = (
                f"{self.scheme}://{join_url(self.location, self.name)}"
            )
            return cn
        else:
            cn = self.__canonical_name = join_url(self.location, self.name).lstrip("/")
            return cn

    def urls(self, with_credentials=False, subdirs=None):
        if subdirs is None:
            subdirs = context.subdirs

        assert isiterable(subdirs), subdirs  # subdirs must be a non-string iterable

        if self.canonical_name == UNKNOWN_CHANNEL:
            return Channel(DEFAULTS_CHANNEL_NAME).urls(with_credentials, subdirs)

        base = [self.location]
        if with_credentials and self.token:
            base.extend(["t", self.token])
        base.append(self.name)
        base = join_url(*base)

        def _platforms():
            if self.platform:
                yield self.platform
                if self.platform != "noarch":
                    yield "noarch"
            else:
                yield from subdirs

        bases = (join_url(base, p) for p in _platforms())
        if with_credentials and self.auth:
            return [f"{self.scheme}://{self.auth}@{b}" for b in bases]
        else:
            return [f"{self.scheme}://{b}" for b in bases]

    def url(self, with_credentials=False):
        if self.canonical_name == UNKNOWN_CHANNEL:
            return None

        base = [self.location]
        if with_credentials and self.token:
            base.extend(["t", self.token])
        base.append(self.name)
        if self.platform:
            base.append(self.platform)
            if self.package_filename:
                base.append(self.package_filename)
        else:
            first_non_noarch = next(
                (s for s in context.subdirs if s != "noarch"), "noarch"
            )
            base.append(first_non_noarch)

        base = join_url(*base)

        if with_credentials and self.auth:
            return f"{self.scheme}://{self.auth}@{base}"
        else:
            return f"{self.scheme}://{base}"

    @property
    def base_url(self):
        if self.canonical_name == UNKNOWN_CHANNEL:
            return None
        return f"{self.scheme}://{join_url(self.location, self.name)}"

    @property
    def base_urls(self):
        return (self.base_url,)

    @property
    def subdir_url(self):
        url = self.url(True)
        if self.package_filename and url:
            url = url.rsplit("/", 1)[0]
        return url

    def __str__(self):
        base = self.base_url or self.name
        if self.subdir:
            return join_url(base, self.subdir)
        else:
            return base

    def __repr__(self):
        return 'Channel("%s")' % (
            join_url(self.name, self.subdir) if self.subdir else self.name
        )

    def __eq__(self, other):
        if isinstance(other, Channel):
            return self.location == other.location and self.name == other.name
        else:
            try:
                _other = Channel(other)
                return self.location == _other.location and self.name == _other.name
            except Exception as e:
                log.debug("%r", e)
                return False

    def __hash__(self):
        return hash((self.location, self.name))

    def __nonzero__(self):
        return any((self.location, self.name))

    def __bool__(self):
        return self.__nonzero__()

    def __json__(self):
        return self.__dict__

    @property
    def url_channel_wtf(self):
        return self.base_url, self.canonical_name

    def dump(self):
        return {
            "scheme": self.scheme,
            "auth": self.auth,
            "location": self.location,
            "token": self.token,
            "name": self.name,
            "platform": self.platform,
            "package_filename": self.package_filename,
        }


class MultiChannel(Channel):
    def __init__(self, name, channels, platform=None):
        self.name = name
        self.location = None

        if platform:
            self._channels = tuple(
                Channel(**{**channel.dump(), "platform": platform})
                for channel in channels
            )
        else:
            self._channels = channels

        self.scheme = None
        self.auth = None
        self.token = None
        self.platform = platform
        self.package_filename = None

    @property
    def channel_location(self):
        return self.location

    @property
    def canonical_name(self):
        return self.name

    def urls(self, with_credentials=False, subdirs=None):
        _channels = self._channels
        return list(
            chain.from_iterable(c.urls(with_credentials, subdirs) for c in _channels)
        )

    @property
    def base_url(self):
        return None

    @property
    def base_urls(self):
        return tuple(c.base_url for c in self._channels)

    def url(self, with_credentials=False):
        return None

    def dump(self):
        return {"name": self.name, "channels": tuple(c.dump() for c in self._channels)}


def tokenized_startswith(test_iterable, startswith_iterable):
    return all(t == sw for t, sw in zip(test_iterable, startswith_iterable))


def tokenized_conda_url_startswith(test_url, startswith_url):
    test_url, startswith_url = urlparse(test_url), urlparse(startswith_url)
    if (
        test_url.hostname != startswith_url.hostname
        or test_url.port != startswith_url.port
    ):
        return False
    norm_url_path = lambda url: url.path.strip("/") or "/"
    return tokenized_startswith(
        norm_url_path(test_url).split("/"), norm_url_path(startswith_url).split("/")
    )


def _get_channel_for_name(channel_name):
    def _get_channel_for_name_helper(name):
        if name in context.custom_channels:
            return context.custom_channels[name]
        else:
            test_name = name.rsplit("/", 1)[0]  # progressively strip off path segments
            if test_name == name:
                return None
            return _get_channel_for_name_helper(test_name)

    _stripped, platform = split_platform(context.known_subdirs, channel_name)
    channel = _get_channel_for_name_helper(_stripped)

    if channel is not None:
        # stripping off path threw information away from channel_name (i.e. any potential subname)
        # channel.name *should still be* channel_name
        channel = copy(channel)
        channel.name = _stripped
        if platform:
            channel.platform = platform
        return channel
    else:
        ca = context.channel_alias
        return Channel(
            scheme=ca.scheme,
            auth=ca.auth,
            location=ca.location,
            token=ca.token,
            name=_stripped,
            platform=platform,
        )


def _read_channel_configuration(scheme, host, port, path):
    # return location, name, scheme, auth, token

    path = path and path.rstrip("/")
    test_url = str(Url(hostname=host, port=port, path=path))

    # Step 1. No path given; channel name is None
    if not path:
        return (
            str(Url(hostname=host, port=port)).rstrip("/"),
            None,
            scheme or None,
            None,
            None,
        )

    # Step 2. migrated_custom_channels matches
    for name, location in sorted(
        context.migrated_custom_channels.items(), reverse=True, key=lambda x: len(x[0])
    ):
        location, _scheme, _auth, _token = split_scheme_auth_token(location)
        if tokenized_conda_url_startswith(test_url, join_url(location, name)):
            # translate location to new location, with new credentials
            subname = test_url.replace(join_url(location, name), "", 1).strip("/")
            channel_name = join_url(name, subname)
            channel = _get_channel_for_name(channel_name)
            return (
                channel.location,
                channel_name,
                channel.scheme,
                channel.auth,
                channel.token,
            )

    # Step 3. migrated_channel_aliases matches
    for migrated_alias in context.migrated_channel_aliases:
        if test_url.startswith(migrated_alias.location):
            name = test_url.replace(migrated_alias.location, "", 1).strip("/")
            ca = context.channel_alias
            return ca.location, name, ca.scheme, ca.auth, ca.token

    # Step 4. custom_channels matches
    for name, channel in sorted(
        context.custom_channels.items(), reverse=True, key=lambda x: len(x[0])
    ):
        that_test_url = join_url(channel.location, channel.name)
        if tokenized_startswith(test_url.split("/"), that_test_url.split("/")):
            subname = test_url.replace(that_test_url, "", 1).strip("/")
            return (
                channel.location,
                join_url(channel.name, subname),
                scheme,
                channel.auth,
                channel.token,
            )

    # Step 5. channel_alias match
    ca = context.channel_alias
    if ca.location and tokenized_startswith(
        test_url.split("/"), ca.location.split("/")
    ):
        name = test_url.replace(ca.location, "", 1).strip("/") or None
        return ca.location, name, scheme, ca.auth, ca.token

    # Step 6. not-otherwise-specified file://-type urls
    if host is None:
        # this should probably only happen with a file:// type url
        assert port is None
        location, name = test_url.rsplit("/", 1)
        if not location:
            location = "/"
        _scheme, _auth, _token = "file", None, None
        return location, name, _scheme, _auth, _token

    # Step 7. fall through to host:port as channel_location and path as channel_name
    #  but bump the first token of paths starting with /conda for compatibility with
    #  Anaconda Enterprise Repository software.
    bump = None
    path_parts = path.strip("/").split("/")
    if path_parts and path_parts[0] == "conda":
        bump, path = "conda", "/".join(path_parts[1:])
    return (
        str(Url(hostname=host, port=port, path=bump)).rstrip("/"),
        path.strip("/") or None,
        scheme or None,
        None,
        None,
    )


def parse_conda_channel_url(url):
    (
        scheme,
        auth,
        token,
        platform,
        package_filename,
        host,
        port,
        path,
        query,
    ) = split_conda_url_easy_parts(context.known_subdirs, url)

    # recombine host, port, path to get a channel_name and channel_location
    (
        channel_location,
        channel_name,
        configured_scheme,
        configured_auth,
        configured_token,
    ) = _read_channel_configuration(scheme, host, port, path)

    # if we came out with no channel_location or channel_name, we need to figure it out
    # from host, port, path
    assert channel_location is not None or channel_name is not None

    return Channel(
        configured_scheme or "https",
        auth or configured_auth,
        channel_location,
        token or configured_token,
        channel_name,
        platform,
        package_filename,
    )


# backward compatibility for conda-build
def get_conda_build_local_url():
    return (context.local_build_root,)


def prioritize_channels(channels, with_credentials=True, subdirs=None):
    # prioritize_channels returns a dict with platform-specific channel
    #   urls as the key, and a tuple of canonical channel name and channel priority
    #   number as the value
    # ('https://conda.anaconda.org/conda-forge/osx-64/', ('conda-forge', 1))
    channels = chain.from_iterable(
        (Channel(cc) for cc in c._channels) if isinstance(c, MultiChannel) else (c,)
        for c in (Channel(c) for c in channels)
    )
    result = {}
    for priority_counter, chn in enumerate(channels):
        channel = Channel(chn)
        for url in channel.urls(with_credentials, subdirs):
            if url in result:
                continue
            result[url] = (
                channel.canonical_name,
                min(priority_counter, MAX_CHANNEL_PRIORITY - 1),
            )
    return result


def all_channel_urls(channels, subdirs=None, with_credentials=True):
    result = IndexedSet()
    for chn in channels:
        channel = Channel(chn)
        result.update(channel.urls(with_credentials, subdirs))
    return result


def offline_keep(url):
    return not context.offline or not is_url(url) or url.startswith("file:/")


def get_channel_objs(ctx: Context):
    """Return current channels as Channel objects"""
    return tuple(Channel(chn) for chn in ctx.channels)


context.register_reset_callaback(Channel._reset_state)
