# Copyright 2019-2020 Lawrence Livermore National Security, LLC and other
# Archspec Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)
"""Global objects with the content of the microarchitecture
JSON file and its schema
"""
import collections.abc
import json
import os
import pathlib
from typing import Tuple


class LazyDictionary(collections.abc.MutableMapping):
    """Lazy dictionary that gets constructed on first access to any object key

    Args:
        factory (callable): factory function to construct the dictionary
    """

    def __init__(self, factory, *args, **kwargs):
        self.factory = factory
        self.args = args
        self.kwargs = kwargs
        self._data = None

    @property
    def data(self):
        """Returns the lazily constructed dictionary"""
        if self._data is None:
            self._data = self.factory(*self.args, **self.kwargs)
        return self._data

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value

    def __delitem__(self, key):
        del self.data[key]

    def __iter__(self):
        return iter(self.data)

    def __len__(self):
        return len(self.data)


#: Environment variable that might point to a directory with a user defined JSON file
DIR_FROM_ENVIRONMENT = "ARCHSPEC_CPU_DIR"

#: Environment variable that might point to a directory with extensions to JSON files
EXTENSION_DIR_FROM_ENVIRONMENT = "ARCHSPEC_EXTENSION_CPU_DIR"


def _json_file(filename: str, allow_custom: bool = False) -> Tuple[pathlib.Path, pathlib.Path]:
    """Given a filename, returns the absolute path for the main JSON file, and an
    optional absolute path for an extension JSON file.

    Args:
        filename: filename for the JSON file
        allow_custom: if True, allows overriding the location  where the file resides
    """
    json_dir = pathlib.Path(__file__).parent / ".." / "json" / "cpu"
    if allow_custom and DIR_FROM_ENVIRONMENT in os.environ:
        json_dir = pathlib.Path(os.environ[DIR_FROM_ENVIRONMENT])
    json_dir = json_dir.absolute()
    json_file = json_dir / filename

    extension_file = None
    if allow_custom and EXTENSION_DIR_FROM_ENVIRONMENT in os.environ:
        extension_dir = pathlib.Path(os.environ[EXTENSION_DIR_FROM_ENVIRONMENT])
        extension_dir.absolute()
        extension_file = extension_dir / filename

    return json_file, extension_file


def _load(json_file: pathlib.Path, extension_file: pathlib.Path):
    with open(json_file, "r", encoding="utf-8") as file:
        data = json.load(file)

    if not extension_file or not extension_file.exists():
        return data

    with open(extension_file, "r", encoding="utf-8") as file:
        extension_data = json.load(file)

    top_level_sections = list(data.keys())
    for key in top_level_sections:
        if key not in extension_data:
            continue

        data[key].update(extension_data[key])

    return data


#: In memory representation of the data in microarchitectures.json,
#: loaded on first access
TARGETS_JSON = LazyDictionary(_load, *_json_file("microarchitectures.json", allow_custom=True))

#: JSON schema for microarchitectures.json, loaded on first access
TARGETS_JSON_SCHEMA = LazyDictionary(_load, *_json_file("microarchitectures_schema.json"))

#: Information on how to call 'cpuid' to get information on the HOST CPU
CPUID_JSON = LazyDictionary(_load, *_json_file("cpuid.json", allow_custom=True))

#: JSON schema for cpuid.json, loaded on first access
CPUID_JSON_SCHEMA = LazyDictionary(_load, *_json_file("cpuid_schema.json"))
