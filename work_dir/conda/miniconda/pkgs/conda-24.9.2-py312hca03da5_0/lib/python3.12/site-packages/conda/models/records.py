# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Implements the data model for conda packages.

A PackageRecord is the record of a package present in a channel. A PackageCache is the record of a
downloaded and cached package. A PrefixRecord is the record of a package installed into a conda
environment.

Object inheritance:

.. autoapi-inheritance-diagram:: PackageRecord PackageCacheRecord PrefixRecord
   :top-classes: conda.models.records.PackageRecord
   :parts: 1
"""

from __future__ import annotations

from os.path import basename, join

from boltons.timeutils import dt_to_timestamp, isoparse

from ..auxlib.entity import (
    BooleanField,
    ComposableField,
    DictSafeMixin,
    Entity,
    EnumField,
    IntegerField,
    ListField,
    NumberField,
    StringField,
)
from ..base.context import context
from ..common.compat import isiterable
from ..exceptions import PathNotFoundError
from .channel import Channel
from .enums import FileMode, LinkType, NoarchType, PackageType, PathType, Platform
from .match_spec import MatchSpec


class LinkTypeField(EnumField):
    def box(self, instance, instance_type, val):
        if isinstance(val, str):
            val = val.replace("-", "").replace("_", "").lower()
            if val == "hard":
                val = LinkType.hardlink
            elif val == "soft":
                val = LinkType.softlink
        return super().box(instance, instance_type, val)


class NoarchField(EnumField):
    def box(self, instance, instance_type, val):
        return super().box(instance, instance_type, NoarchType.coerce(val))


class TimestampField(NumberField):
    def __init__(self):
        super().__init__(default=0, required=False, default_in_dump=False)

    @staticmethod
    def _make_seconds(val):
        if val:
            val = val
            if val > 253402300799:  # 9999-12-31
                val /= (
                    1000  # convert milliseconds to seconds; see conda/conda-build#1988
                )
        return val

    @staticmethod
    def _make_milliseconds(val):
        if val:
            if val < 253402300799:  # 9999-12-31
                val *= 1000  # convert seconds to milliseconds
            val = val
        return val

    def box(self, instance, instance_type, val):
        return self._make_seconds(super().box(instance, instance_type, val))

    def dump(self, instance, instance_type, val):
        return int(
            self._make_milliseconds(super().dump(instance, instance_type, val))
        )  # whether in seconds or milliseconds, type must be int (not float) for backward compat

    def __get__(self, instance, instance_type):
        try:
            return super().__get__(instance, instance_type)
        except AttributeError:
            try:
                return int(dt_to_timestamp(isoparse(instance.date)))
            except (AttributeError, ValueError):
                return 0


class Link(DictSafeMixin, Entity):
    source = StringField()
    type = LinkTypeField(LinkType, required=False)


EMPTY_LINK = Link(source="")


class _FeaturesField(ListField):
    def __init__(self, **kwargs):
        super().__init__(str, **kwargs)

    def box(self, instance, instance_type, val):
        if isinstance(val, str):
            val = val.replace(" ", ",").split(",")
        val = tuple(f for f in (ff.strip() for ff in val) if f)
        return super().box(instance, instance_type, val)

    def dump(self, instance, instance_type, val):
        if isiterable(val):
            return " ".join(val)
        else:
            return val or ()  # default value is (), and default_in_dump=False


class ChannelField(ComposableField):
    def __init__(self, aliases=()):
        super().__init__(Channel, required=False, aliases=aliases)

    def dump(self, instance, instance_type, val):
        if val:
            return str(val)
        else:
            val = instance.channel  # call __get__
            return str(val)

    def __get__(self, instance, instance_type):
        try:
            return super().__get__(instance, instance_type)
        except AttributeError:
            url = instance.url
            return self.unbox(instance, instance_type, Channel(url))


class SubdirField(StringField):
    def __init__(self):
        super().__init__(required=False)

    def __get__(self, instance, instance_type):
        try:
            return super().__get__(instance, instance_type)
        except AttributeError:
            try:
                url = instance.url
            except AttributeError:
                url = None
            if url:
                return self.unbox(instance, instance_type, Channel(url).subdir)

            try:
                platform, arch = instance.platform.name, instance.arch
            except AttributeError:
                platform, arch = None, None
            if platform and not arch:
                return self.unbox(instance, instance_type, "noarch")
            elif platform:
                if "x86" in arch:
                    arch = "64" if "64" in arch else "32"
                return self.unbox(instance, instance_type, f"{platform}-{arch}")
            else:
                return self.unbox(instance, instance_type, context.subdir)


class FilenameField(StringField):
    def __init__(self, aliases=()):
        super().__init__(required=False, aliases=aliases)

    def __get__(self, instance, instance_type):
        try:
            return super().__get__(instance, instance_type)
        except AttributeError:
            try:
                url = instance.url
                fn = Channel(url).package_filename
                if not fn:
                    raise AttributeError()
            except AttributeError:
                fn = f"{instance.name}-{instance.version}-{instance.build}"
            assert fn
            return self.unbox(instance, instance_type, fn)


class PackageTypeField(EnumField):
    def __init__(self):
        super().__init__(
            PackageType,
            required=False,
            nullable=True,
            default=None,
            default_in_dump=False,
        )

    def __get__(self, instance, instance_type):
        val = super().__get__(instance, instance_type)
        if val is None:
            # look in noarch field
            noarch_val = instance.noarch
            if noarch_val:
                type_map = {
                    NoarchType.generic: PackageType.NOARCH_GENERIC,
                    NoarchType.python: PackageType.NOARCH_PYTHON,
                }
                val = type_map[NoarchType.coerce(noarch_val)]
                val = self.unbox(instance, instance_type, val)
        return val


class PathData(Entity):
    _path = StringField()
    prefix_placeholder = StringField(
        required=False, nullable=True, default=None, default_in_dump=False
    )
    file_mode = EnumField(FileMode, required=False, nullable=True)
    no_link = BooleanField(
        required=False, nullable=True, default=None, default_in_dump=False
    )
    path_type = EnumField(PathType)

    @property
    def path(self):
        # because I don't have aliases as an option for entity fields yet
        return self._path


class PathDataV1(PathData):
    # TODO: sha256 and size_in_bytes should be required for all PathType.hardlink, but not for softlink and directory  # NOQA
    sha256 = StringField(required=False, nullable=True)
    size_in_bytes = IntegerField(required=False, nullable=True)
    inode_paths = ListField(str, required=False, nullable=True)

    sha256_in_prefix = StringField(required=False, nullable=True)


class PathsData(Entity):
    # from info/paths.json
    paths_version = IntegerField()
    paths = ListField(PathData)


class PackageRecord(DictSafeMixin, Entity):
    """Representation of a concrete package archive (tarball or .conda file).

    It captures all the relevant information about a given package archive, including its source,
    in the following attributes.

    Note that there are two subclasses, :class:`PrefixRecord` and
    :class:`PackageCacheRecord`. These capture the same information, but are augmented with
    additional information relevant for these two sources of packages.

    Further note that :class:`PackageRecord` makes use of its :attr:`_pkey`
    for comparison and hash generation.
    This means that for common operations, like comparisons between :class:`PackageRecord` s
    and reference of :class:`PackageRecord` s in mappings, _different_ objects appear identical.
    The fields taken into account are marked in the following list of attributes.
    The subclasses do not add further attributes to the :attr:`_pkey`.
    """

    #: str: The name of the package.
    #:
    #: Part of the :attr:`_pkey`.
    name = StringField()

    #: str: The version of the package.
    #:
    #: Part of the :attr:`_pkey`.
    version = StringField()

    #: str: The build string of the package.
    #:
    #: Part of the :attr:`_pkey`.
    build = StringField(aliases=("build_string",))

    #: int: The build number of the package.
    #:
    #: Part of the :attr:`_pkey`.
    build_number = IntegerField()

    # the canonical code abbreviation for PackageRef is `pref`
    # fields required to uniquely identifying a package

    #: :class:`conda.models.channel.Channel`: The channel where the package can be found.
    channel = ChannelField(aliases=("schannel",))

    #: str: The subdir, i.e. ``noarch`` or a platform (``linux-64`` or similar).
    #:
    #: Part of the :attr:`_pkey`.
    subdir = SubdirField()

    #: str: The filename of the package.
    #:
    #: Only part of the :attr:`_pkey` if :ref:`separate_format_cache <auto-config-reference>` is ``true`` (default: ``false``).
    fn = FilenameField(aliases=("filename",))

    #: str: The md5 checksum of the package.
    md5 = StringField(
        default=None, required=False, nullable=True, default_in_dump=False
    )

    #: str: If this is a ``.conda`` package and a corresponding ``.tar.bz2`` package exists, this may contain the md5 checksum of that package.
    legacy_bz2_md5 = StringField(
        default=None, required=False, nullable=True, default_in_dump=False
    )

    #: str: If this is a ``.conda`` package and a corresponding ``.tar.bz2`` package exists, this may contain the size of that package.
    legacy_bz2_size = IntegerField(required=False, nullable=True, default_in_dump=False)

    #: str: The download url of the package.
    url = StringField(
        default=None, required=False, nullable=True, default_in_dump=False
    )

    #: str: The sha256 checksum of the package.
    sha256 = StringField(
        default=None, required=False, nullable=True, default_in_dump=False
    )

    @property
    def schannel(self):
        """str: The canonical name of the channel of this package.

        Part of the :attr:`_pkey`.
        """
        return self.channel.canonical_name

    @property
    def _pkey(self):
        """tuple: The components of the PackageRecord that are used for comparison and hashing.

        The :attr:`_pkey` is a tuple made up of the following fields of the :class:`PackageRecord`.
        Two :class:`PackageRecord` s test equal if their respective :attr:`_pkey` s are equal.
        The hash of the :class:`PackageRecord` (important for dictionary access) is the hash of the :attr:`_pkey`.

        The included fields are:

        * :attr:`schannel`
        * :attr:`subdir`
        * :attr:`name`
        * :attr:`version`
        * :attr:`build_number`
        * :attr:`build`
        * :attr:`fn` only if :ref:`separate_format_cache <auto-config-reference>` is set to true (default: false)
        """
        try:
            return self.__pkey
        except AttributeError:
            __pkey = self.__pkey = [
                self.channel.canonical_name,
                self.subdir,
                self.name,
                self.version,
                self.build_number,
                self.build,
            ]
            # NOTE: fn is included to distinguish between .conda and .tar.bz2 packages
            if context.separate_format_cache:
                __pkey.append(self.fn)
            self.__pkey = tuple(__pkey)
            return self.__pkey

    def __hash__(self):
        try:
            return self._hash
        except AttributeError:
            self._hash = hash(self._pkey)
        return self._hash

    def __eq__(self, other):
        return self._pkey == other._pkey

    def dist_str(self):
        return "{}{}::{}-{}-{}".format(
            self.channel.canonical_name,
            ("/" + self.subdir) if self.subdir else "",
            self.name,
            self.version,
            self.build,
        )

    def dist_fields_dump(self):
        return {
            "base_url": self.channel.base_url,
            "build_number": self.build_number,
            "build_string": self.build,
            "channel": self.channel.name,
            "dist_name": self.dist_str().split(":")[-1],
            "name": self.name,
            "platform": self.subdir,
            "version": self.version,
        }

    arch = StringField(required=False, nullable=True)  # so legacy
    platform = EnumField(Platform, required=False, nullable=True)  # so legacy

    depends = ListField(str, default=())
    constrains = ListField(str, default=())

    track_features = _FeaturesField(required=False, default=(), default_in_dump=False)
    features = _FeaturesField(required=False, default=(), default_in_dump=False)

    noarch = NoarchField(
        NoarchType, required=False, nullable=True, default=None, default_in_dump=False
    )  # TODO: rename to package_type
    preferred_env = StringField(
        required=False, nullable=True, default=None, default_in_dump=False
    )

    license = StringField(
        required=False, nullable=True, default=None, default_in_dump=False
    )
    license_family = StringField(
        required=False, nullable=True, default=None, default_in_dump=False
    )
    package_type = PackageTypeField()

    @property
    def is_unmanageable(self):
        return self.package_type in PackageType.unmanageable_package_types()

    timestamp = TimestampField()

    @property
    def combined_depends(self):
        from .match_spec import MatchSpec

        result = {ms.name: ms for ms in MatchSpec.merge(self.depends)}
        for spec in self.constrains or ():
            ms = MatchSpec(spec)
            result[ms.name] = MatchSpec(ms, optional=(ms.name not in result))
        return tuple(result.values())

    # the canonical code abbreviation for PackageRecord is `prec`, not to be confused with
    # PackageCacheRecord (`pcrec`) or PrefixRecord (`prefix_rec`)
    #
    # important for "choosing" a package (i.e. the solver), listing packages
    # (like search), and for verifying downloads
    #
    # this is the highest level of the record inheritance model that MatchSpec is designed to
    # work with

    date = StringField(required=False)
    size = IntegerField(required=False)

    def __str__(self):
        return f"{self.channel.canonical_name}/{self.subdir}::{self.name}=={self.version}={self.build}"

    def to_match_spec(self):
        return MatchSpec(
            channel=self.channel,
            subdir=self.subdir,
            name=self.name,
            version=self.version,
            build=self.build,
        )

    def to_simple_match_spec(self):
        return MatchSpec(
            name=self.name,
            version=self.version,
        )

    @property
    def namekey(self):
        return "global:" + self.name

    def record_id(self):
        # WARNING: This is right now only used in link.py _change_report_str(). It is not
        #          the official record_id / uid until it gets namespace.  Even then, we might
        #          make the format different.  Probably something like
        #              channel_name/subdir:namespace:name-version-build_number-build_string
        return f"{self.channel.name}/{self.subdir}::{self.name}-{self.version}-{self.build}"

    metadata: set[str]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.metadata = set()

    @classmethod
    def feature(cls, feature_name) -> PackageRecord:
        # necessary for the SAT solver to do the right thing with features
        pkg_name = f"{feature_name}@"
        return cls(
            name=pkg_name,
            version="0",
            build="0",
            channel="@",
            subdir=context.subdir,
            md5="12345678901234567890123456789012",
            track_features=(feature_name,),
            build_number=0,
            fn=pkg_name,
        )

    @classmethod
    def virtual_package(
        cls, name: str, version: str | None = None, build_string: str | None = None
    ) -> PackageRecord:
        """
        Create a virtual package record.

        :param name: The name of the virtual package.
        :param version: The version of the virtual package, defaults to "0".
        :param build_string: The build string of the virtual package, defaults to "0".
        :return: A PackageRecord representing the virtual package.
        """
        return cls(
            package_type=PackageType.VIRTUAL_SYSTEM,
            name=name,
            version=version or "0",
            build_string=build_string or "0",
            channel="@",
            subdir=context.subdir,
            md5="12345678901234567890123456789012",
            build_number=0,
            fn=name,
        )


class Md5Field(StringField):
    def __init__(self):
        super().__init__(required=False, nullable=True)

    def __get__(self, instance, instance_type):
        try:
            return super().__get__(instance, instance_type)
        except AttributeError as e:
            try:
                return instance._calculate_md5sum()
            except PathNotFoundError:
                raise e


class PackageCacheRecord(PackageRecord):
    """Representation of a package that has been downloaded or unpacked in the local package cache.

    Specialization of :class:`PackageRecord` that adds information for packages that exist in the
    local package cache, either as the downloaded package file, or unpacked in its own package dir,
    or both.

    Note that this class does not add new fields to the :attr:`PackageRecord._pkey` so that a pure
    :class:`PackageRecord` object that has the same ``_pkey`` fields as a different
    :class:`PackageCacheRecord` object (or, indeed, a :class:`PrefixRecord` object) will be considered
    equal and will produce the same hash.
    """

    #: str: Full path to the local package file.
    package_tarball_full_path = StringField()

    #: str: Full path to the local extracted package.
    extracted_package_dir = StringField()

    #: str: The md5 checksum of the package.
    #:
    #: If the package file exists locally, this class can calculate a missing checksum on-the-fly.
    md5 = Md5Field()

    @property
    def is_fetched(self):
        """bool: Whether the package file exists locally."""
        from ..gateways.disk.read import isfile

        return isfile(self.package_tarball_full_path)

    @property
    def is_extracted(self):
        """bool: Whether the package has been extracted locally."""
        from ..gateways.disk.read import isdir, isfile

        epd = self.extracted_package_dir
        return isdir(epd) and isfile(join(epd, "info", "index.json"))

    @property
    def tarball_basename(self):
        """str: The basename of the local package file."""
        return basename(self.package_tarball_full_path)

    def _calculate_md5sum(self):
        memoized_md5 = getattr(self, "_memoized_md5", None)
        if memoized_md5:
            return memoized_md5

        from os.path import isfile

        if isfile(self.package_tarball_full_path):
            from ..gateways.disk.read import compute_sum

            md5sum = compute_sum(self.package_tarball_full_path, "md5")
            setattr(self, "_memoized_md5", md5sum)
            return md5sum


class PrefixRecord(PackageRecord):
    """Representation of a package that is installed in a local conda environmnet.

    Specialization of :class:`PackageRecord` that adds information for packages that are installed
    in a local conda environment or prefix.

    Note that this class does not add new fields to the :attr:`PackageRecord._pkey` so that a pure
    :class:`PackageRecord` object that has the same ``_pkey`` fields as a different
    :class:`PrefixRecord` object (or, indeed, a :class:`PackageCacheRecord` object) will be considered
    equal and will produce the same hash.

    Objects of this class are generally constructed from metadata in json files inside `$prefix/conda-meta`.
    """

    #: str: The path to the originating package file, usually in the local cache.
    package_tarball_full_path = StringField(required=False)

    #: str: The path to the extracted package directory, usually in the local cache.
    extracted_package_dir = StringField(required=False)

    #: list(str): The list of all files comprising the package as relative paths from the prefix root.
    files = ListField(str, default=(), required=False)

    #: list(str): List with additional information about the files, e.g. checksums and link type.
    paths_data = ComposableField(
        PathsData, required=False, nullable=True, default_in_dump=False
    )

    #: :class:`Link`: Information about how the package was linked into the prefix.
    link = ComposableField(Link, required=False)

    # app = ComposableField(App, required=False)

    #: str: The :class:`MatchSpec` that the user requested or ``None`` if dependency it was installed as a dependency.
    requested_spec = StringField(required=False)

    # There have been requests in the past to save remote server auth
    # information with the package.  Open to rethinking that though.
    #: str: Authentication information.
    auth = StringField(required=False, nullable=True)

    # @classmethod
    # def load(cls, conda_meta_json_path):
    #     return cls()
