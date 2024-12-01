# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""YAML and JSON serialization and deserialization functions."""

import functools
import json
from io import StringIO
from logging import getLogger

import ruamel.yaml as yaml

from ..auxlib.entity import EntityEncoder

log = getLogger(__name__)


# FUTURE: Python 3.9+, replace with functools.cache
@functools.lru_cache(maxsize=None)
def _yaml_round_trip():
    parser = yaml.YAML(typ="rt")
    parser.indent(mapping=2, offset=2, sequence=4)
    return parser


# FUTURE: Python 3.9+, replace with functools.cache
@functools.lru_cache(maxsize=None)
def _yaml_safe():
    parser = yaml.YAML(typ="safe", pure=True)
    parser.indent(mapping=2, offset=2, sequence=4)
    parser.default_flow_style = False
    parser.sort_base_mapping_type_on_output = False
    return parser


def yaml_round_trip_load(string):
    return _yaml_round_trip().load(string)


def yaml_safe_load(string):
    """
    Examples:
        >>> yaml_safe_load("key: value")
        {'key': 'value'}

    """
    return _yaml_safe().load(string)


def yaml_round_trip_dump(object, stream=None):
    """Dump object to string or stream."""
    ostream = stream or StringIO()
    _yaml_round_trip().dump(object, ostream)
    if not stream:
        return ostream.getvalue()


def yaml_safe_dump(object, stream=None):
    """Dump object to string or stream."""
    ostream = stream or StringIO()
    _yaml_safe().dump(object, ostream)
    if not stream:
        return ostream.getvalue()


def json_load(string):
    return json.loads(string)


def json_dump(object):
    return json.dumps(
        object, indent=2, sort_keys=True, separators=(",", ": "), cls=EntityEncoder
    )
