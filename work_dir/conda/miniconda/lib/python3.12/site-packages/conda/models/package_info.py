# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""(Legacy) Low-level implementation of a PackageRecord."""

from logging import getLogger

from ..auxlib.entity import (
    ComposableField,
    Entity,
    EnumField,
    ImmutableEntity,
    IntegerField,
    ListField,
    StringField,
)
from .channel import Channel
from .enums import NoarchType
from .records import PackageRecord, PathsData

log = getLogger(__name__)


class NoarchField(EnumField):
    def box(self, instance, instance_type, val):
        return super().box(instance, instance_type, NoarchType.coerce(val))


class Noarch(Entity):
    type = NoarchField(NoarchType)
    entry_points = ListField(
        str, required=False, nullable=True, default=None, default_in_dump=False
    )


class PreferredEnv(Entity):
    name = StringField()
    executable_paths = ListField(str, required=False, nullable=True)
    softlink_paths = ListField(str, required=False, nullable=True)


class PackageMetadata(Entity):
    # from info/package_metadata.json
    package_metadata_version = IntegerField()
    noarch = ComposableField(Noarch, required=False, nullable=True)
    preferred_env = ComposableField(
        PreferredEnv, required=False, nullable=True, default=None, default_in_dump=False
    )


class PackageInfo(ImmutableEntity):
    # attributes external to the package tarball
    extracted_package_dir = StringField()
    package_tarball_full_path = StringField()
    channel = ComposableField(Channel)
    repodata_record = ComposableField(PackageRecord)
    url = StringField()

    # attributes within the package tarball
    icondata = StringField(required=False, nullable=True)
    package_metadata = ComposableField(PackageMetadata, required=False, nullable=True)
    paths_data = ComposableField(PathsData)

    def dist_str(self):
        return f"{self.channel.canonical_name}::{self.name}-{self.version}-{self.build}"

    @property
    def name(self):
        return self.repodata_record.name

    @property
    def version(self):
        return self.repodata_record.version

    @property
    def build(self):
        return self.repodata_record.build

    @property
    def build_number(self):
        return self.repodata_record.build_number
