# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""
A generalized application configuration utility.

Features include:
  - lazy eval
  - merges configuration files
  - parameter type validation, with custom validation
  - parameter aliases

Easily extensible to other source formats, e.g. json and ini

"""

from __future__ import annotations

import copy
import sys
from abc import ABCMeta, abstractmethod
from collections import defaultdict
from collections.abc import Mapping
from enum import Enum, EnumMeta
from functools import wraps
from itertools import chain
from logging import getLogger
from os import environ
from os.path import expandvars
from pathlib import Path
from re import IGNORECASE, VERBOSE, compile
from string import Template
from typing import TYPE_CHECKING

from boltons.setutils import IndexedSet
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.reader import ReaderError
from ruamel.yaml.scanner import ScannerError

from .. import CondaError, CondaMultiError
from ..auxlib.collection import AttrDict, first, last
from ..auxlib.exceptions import ThisShouldNeverHappenError
from ..auxlib.type_coercion import TypeCoercionError, typify, typify_data_structure
from ..common.iterators import unique
from .compat import isiterable, primitive_types
from .constants import NULL
from .serialize import yaml_round_trip_load

try:
    from frozendict import deepfreeze, frozendict
    from frozendict import getFreezeConversionMap as _getFreezeConversionMap
    from frozendict import register as _register

    if Enum not in _getFreezeConversionMap():
        # leave enums as is, deepfreeze will flatten it into a dict
        # see https://github.com/Marco-Sulla/python-frozendict/issues/98
        _register(Enum, lambda x: x)

    del _getFreezeConversionMap
    del _register
except ImportError:
    from .._vendor.frozendict import frozendict
    from ..auxlib.collection import make_immutable as deepfreeze

if TYPE_CHECKING:
    from re import Match
    from typing import Any, Hashable, Iterable, Sequence

log = getLogger(__name__)

EMPTY_MAP = frozendict()


def pretty_list(iterable, padding="  "):  # TODO: move elsewhere in conda.common
    if not isiterable(iterable):
        iterable = [iterable]
    try:
        return "\n".join(f"{padding}- {item}" for item in iterable)
    except TypeError:
        return pretty_list([iterable], padding)


def pretty_map(dictionary, padding="  "):
    return "\n".join(f"{padding}{key}: {value}" for key, value in dictionary.items())


def expand_environment_variables(unexpanded):
    if isinstance(unexpanded, (str, bytes)):
        return expandvars(unexpanded)
    else:
        return unexpanded


class ConfigurationError(CondaError):
    pass


class ConfigurationLoadError(ConfigurationError):
    def __init__(self, path, message_addition="", **kwargs):
        message = "Unable to load configuration file.\n  path: %(path)s\n"
        super().__init__(message + message_addition, path=path, **kwargs)


class ValidationError(ConfigurationError):
    def __init__(self, parameter_name, parameter_value, source, msg=None, **kwargs):
        self.parameter_name = parameter_name
        self.parameter_value = parameter_value
        self.source = source
        super().__init__(msg, **kwargs)


class MultipleKeysError(ValidationError):
    def __init__(self, source, keys, preferred_key):
        self.source = source
        self.keys = keys
        msg = (
            f"Multiple aliased keys in file {source}:\n"
            f"{pretty_list(keys)}\n"
            f"Must declare only one. Prefer '{preferred_key}'"
        )
        super().__init__(preferred_key, None, source, msg=msg)


class InvalidTypeError(ValidationError):
    def __init__(
        self, parameter_name, parameter_value, source, wrong_type, valid_types, msg=None
    ):
        self.wrong_type = wrong_type
        self.valid_types = valid_types
        if msg is None:
            msg = (
                f"Parameter {parameter_name} = {parameter_value!r} declared in {source} has type {wrong_type}.\n"
                f"Valid types:\n{pretty_list(valid_types)}"
            )
        super().__init__(parameter_name, parameter_value, source, msg=msg)


class CustomValidationError(ValidationError):
    def __init__(self, parameter_name, parameter_value, source, custom_message):
        super().__init__(
            parameter_name,
            parameter_value,
            source,
            msg=(
                f"Parameter {parameter_name} = {parameter_value!r} declared in "
                f"{source} is invalid.\n{custom_message}"
            ),
        )


class MultiValidationError(CondaMultiError, ConfigurationError):
    def __init__(self, errors, *args, **kwargs):
        super().__init__(errors, *args, **kwargs)


def raise_errors(errors):
    if not errors:
        return True
    elif len(errors) == 1:
        raise errors[0]
    else:
        raise MultiValidationError(errors)


class ParameterFlag(Enum):
    final = "final"
    top = "top"
    bottom = "bottom"

    def __str__(self):
        return f"{self.value}"

    @classmethod
    def from_name(cls, name):
        return cls[name]

    @classmethod
    def from_value(cls, value):
        return cls(value)

    @classmethod
    def from_string(cls, string):
        try:
            string = string.strip("!#")
            return cls.from_value(string)
        except (ValueError, AttributeError):
            return None


class RawParameter(metaclass=ABCMeta):
    def __init__(self, source, key, raw_value):
        self.source = source
        self.key = key
        try:
            self._raw_value = raw_value.decode("utf-8")
        except AttributeError:
            # AttributeError: raw_value is not encoded
            self._raw_value = raw_value

    def __repr__(self):
        return str(vars(self))

    @abstractmethod
    def value(self, parameter_obj):
        raise NotImplementedError()

    @abstractmethod
    def keyflag(self):
        raise NotImplementedError()

    @abstractmethod
    def valueflags(self, parameter_obj):
        raise NotImplementedError()

    @classmethod
    def make_raw_parameters(cls, source, from_map):
        if from_map:
            return {key: cls(source, key, from_map[key]) for key in from_map}
        return EMPTY_MAP


class EnvRawParameter(RawParameter):
    source = "envvars"

    def value(self, parameter_obj):
        # note: this assumes that EnvRawParameters will only have flat configuration of either
        # primitive or sequential type
        if hasattr(parameter_obj, "string_delimiter"):
            assert isinstance(self._raw_value, str)
            string_delimiter = getattr(parameter_obj, "string_delimiter")
            # TODO: add stripping of !important, !top, and !bottom
            return tuple(
                EnvRawParameter(EnvRawParameter.source, self.key, v)
                for v in (vv.strip() for vv in self._raw_value.split(string_delimiter))
                if v
            )
        else:
            return self.__important_split_value[0].strip()

    def keyflag(self):
        return ParameterFlag.final if len(self.__important_split_value) >= 2 else None

    def valueflags(self, parameter_obj):
        if hasattr(parameter_obj, "string_delimiter"):
            string_delimiter = getattr(parameter_obj, "string_delimiter")
            # TODO: add stripping of !important, !top, and !bottom
            return tuple("" for _ in self._raw_value.split(string_delimiter))
        else:
            return self.__important_split_value[0].strip()

    @property
    def __important_split_value(self):
        return self._raw_value.split("!important")

    @classmethod
    def make_raw_parameters(cls, appname):
        keystart = f"{appname.upper()}_"
        raw_env = {
            k.replace(keystart, "", 1).lower(): v
            for k, v in environ.items()
            if k.startswith(keystart)
        }
        return super().make_raw_parameters(EnvRawParameter.source, raw_env)


class ArgParseRawParameter(RawParameter):
    source = "cmd_line"

    def value(self, parameter_obj):
        # note: this assumes ArgParseRawParameter will only have flat configuration of either
        # primitive or sequential type
        if isiterable(self._raw_value):
            children_values = []
            for i in range(len(self._raw_value)):
                children_values.append(
                    ArgParseRawParameter(self.source, self.key, self._raw_value[i])
                )
            return tuple(children_values)
        else:
            return deepfreeze(self._raw_value)

    def keyflag(self):
        return None

    def valueflags(self, parameter_obj):
        return None if isinstance(parameter_obj, PrimitiveLoadedParameter) else ()

    @classmethod
    def make_raw_parameters(cls, args_from_argparse):
        return super().make_raw_parameters(
            ArgParseRawParameter.source, args_from_argparse
        )


class YamlRawParameter(RawParameter):
    # this class should encapsulate all direct use of ruamel.yaml in this module

    def __init__(self, source, key, raw_value, key_comment):
        self._key_comment = key_comment
        super().__init__(source, key, raw_value)

        if isinstance(self._raw_value, CommentedSeq):
            value_comments = self._get_yaml_list_comments(self._raw_value)
            self._value_flags = tuple(
                ParameterFlag.from_string(s) for s in value_comments
            )
            children_values = []
            for i in range(len(self._raw_value)):
                children_values.append(
                    YamlRawParameter(
                        self.source, self.key, self._raw_value[i], value_comments[i]
                    )
                )
            self._value = tuple(children_values)
        elif isinstance(self._raw_value, CommentedMap):
            value_comments = self._get_yaml_map_comments(self._raw_value)
            self._value_flags = {
                k: ParameterFlag.from_string(v)
                for k, v in value_comments.items()
                if v is not None
            }
            children_values = {}
            for k, v in self._raw_value.items():
                children_values[k] = YamlRawParameter(
                    self.source, self.key, v, value_comments[k]
                )
            self._value = frozendict(children_values)
        elif isinstance(self._raw_value, primitive_types):
            self._value_flags = None
            self._value = self._raw_value
        else:
            print(type(self._raw_value), self._raw_value, file=sys.stderr)
            raise ThisShouldNeverHappenError()  # pragma: no cover

    def value(self, parameter_obj):
        return self._value

    def keyflag(self):
        return ParameterFlag.from_string(self._key_comment)

    def valueflags(self, parameter_obj):
        return self._value_flags

    @staticmethod
    def _get_yaml_key_comment(commented_dict, key):
        try:
            return commented_dict.ca.items[key][2].value.strip()
        except (AttributeError, KeyError):
            return None

    @classmethod
    def _get_yaml_list_comments(cls, value):
        # value is a ruamel.yaml CommentedSeq, len(value) is the number of lines in the sequence,
        # value.ca is the comment object for the sequence and the comments themselves are stored as
        # a sparse dict
        list_comments = []
        for i in range(len(value)):
            try:
                list_comments.append(cls._get_yaml_list_comment_item(value.ca.items[i]))
            except (AttributeError, IndexError, KeyError, TypeError):
                list_comments.append(None)
        return tuple(list_comments)

    @staticmethod
    def _get_yaml_list_comment_item(item):
        # take the pre_item comment if available
        # if not, take the first post_item comment if available
        if item[0]:
            return item[0].value.strip() or None
        else:
            return item[1][0].value.strip() or None

    @staticmethod
    def _get_yaml_map_comments(value):
        map_comments = {}
        for key in value:
            try:
                map_comments[key] = value.ca.items[key][2].value.strip() or None
            except (AttributeError, KeyError):
                map_comments[key] = None
        return map_comments

    @classmethod
    def make_raw_parameters(cls, source, from_map):
        if from_map:
            return {
                key: cls(
                    source, key, from_map[key], cls._get_yaml_key_comment(from_map, key)
                )
                for key in from_map
            }
        return EMPTY_MAP

    @classmethod
    def make_raw_parameters_from_file(cls, filepath):
        with open(filepath) as fh:
            try:
                yaml_obj = yaml_round_trip_load(fh)
            except ScannerError as err:
                mark = err.problem_mark
                raise ConfigurationLoadError(
                    filepath,
                    "  reason: invalid yaml at line %(line)s, column %(column)s",
                    line=mark.line,
                    column=mark.column,
                )
            except ReaderError as err:
                raise ConfigurationLoadError(
                    filepath,
                    "  reason: invalid yaml at position %(position)s",
                    position=err.position,
                )
            return cls.make_raw_parameters(filepath, yaml_obj) or EMPTY_MAP


class DefaultValueRawParameter(RawParameter):
    """Wraps a default value as a RawParameter, for usage in ParameterLoader."""

    def __init__(self, source, key, raw_value):
        super().__init__(source, key, raw_value)

        if isinstance(self._raw_value, Mapping):
            children_values = {}
            for k, v in self._raw_value.items():
                children_values[k] = DefaultValueRawParameter(self.source, self.key, v)
            self._value = frozendict(children_values)
        elif isiterable(self._raw_value):
            children_values = []
            for i in range(len(self._raw_value)):
                children_values.append(
                    DefaultValueRawParameter(self.source, self.key, self._raw_value[i])
                )
            self._value = tuple(children_values)
        elif isinstance(self._raw_value, ConfigurationObject):
            self._value = self._raw_value
            for attr_name, attr_value in vars(self._raw_value).items():
                self._value.__setattr__(
                    attr_name,
                    DefaultValueRawParameter(self.source, self.key, attr_value),
                )
        elif isinstance(self._raw_value, Enum):
            self._value = self._raw_value
        elif isinstance(self._raw_value, primitive_types):
            self._value = self._raw_value
        else:
            raise ThisShouldNeverHappenError()  # pragma: no cover

    def value(self, parameter_obj):
        return self._value

    def keyflag(self):
        return None

    def valueflags(self, parameter_obj):
        if isinstance(self._raw_value, Mapping):
            return frozendict()
        elif isiterable(self._raw_value):
            return ()
        elif isinstance(self._raw_value, ConfigurationObject):
            return None
        elif isinstance(self._raw_value, Enum):
            return None
        elif isinstance(self._raw_value, primitive_types):
            return None
        else:
            raise ThisShouldNeverHappenError()  # pragma: no cover


class LoadedParameter(metaclass=ABCMeta):
    # (type) describes the type of parameter
    _type = None
    # (Parameter or type) if the LoadedParameter holds a collection, describes the element held in
    # the collection. if not, describes the primitive type held by the LoadedParameter.
    _element_type = None

    def __init__(self, name, value, key_flag, value_flags, validation=None):
        """
        Represents a Parameter that has been loaded with configuration value.

        Args:
            name (str): name of the loaded parameter
            value (LoadedParameter or primitive): the value of the loaded parameter
            key_flag (ParameterFlag or None): priority flag for the parameter itself
            value_flags (Any or None): priority flags for the parameter values
            validation (callable): Given a parameter value as input, return a boolean indicating
                validity, or alternately return a string describing an invalid value.
        """
        self._name = name
        self.value = value
        self.key_flag = key_flag
        self.value_flags = value_flags
        self._validation = validation

    def __eq__(self, other):
        if type(other) is type(self):
            return self.value == other.value
        return False

    def __hash__(self):
        return hash(self.value)

    def collect_errors(self, instance, typed_value, source="<<merged>>"):
        """
        Validate a LoadedParameter typed value.

        Args:
            instance (Configuration): the instance object used to create the LoadedParameter.
            typed_value (Any): typed value to validate.
            source (str): string description for the source of the typed_value.
        """
        errors = []
        if not isinstance(typed_value, self._type):
            errors.append(
                InvalidTypeError(
                    self._name, typed_value, source, type(self.value), self._type
                )
            )
        elif self._validation is not None:
            result = self._validation(typed_value)
            if result is False:
                errors.append(ValidationError(self._name, typed_value, source))
            elif isinstance(result, str):
                errors.append(
                    CustomValidationError(self._name, typed_value, source, result)
                )
        return errors

    def expand(self):
        """
        Recursively expands any environment values in the Loaded Parameter.

        Returns: LoadedParameter
        """
        # This is similar to conda.auxlib.type_coercion.typify_data_structure
        # It could be DRY-er but that would break SRP.
        if isinstance(self.value, Mapping):
            new_value = type(self.value)((k, v.expand()) for k, v in self.value.items())
        elif isiterable(self.value):
            new_value = type(self.value)(v.expand() for v in self.value)
        elif isinstance(self.value, ConfigurationObject):
            for attr_name, attr_value in vars(self.value).items():
                if isinstance(attr_value, LoadedParameter):
                    self.value.__setattr__(attr_name, attr_value.expand())
            return self.value
        else:
            new_value = expand_environment_variables(self.value)
        self.value = new_value
        return self

    @abstractmethod
    def merge(self, matches):
        """
        Recursively merges matches into one LoadedParameter.

        Args:
            matches (List<LoadedParameter>): list of matches of this parameter.

        Returns: LoadedParameter
        """
        raise NotImplementedError()

    def typify(self, source):
        """
        Recursively types a LoadedParameter.

        Args:
            source (str): string describing the source of the LoadedParameter.

        Returns: a primitive, sequence, or map representing the typed value.
        """
        element_type = self._element_type
        try:
            return LoadedParameter._typify_data_structure(
                self.value, source, element_type
            )
        except TypeCoercionError as e:
            msg = str(e)
            if issubclass(element_type, Enum):
                choices = ", ".join(
                    map("'{}'".format, element_type.__members__.values())
                )
                msg += f"\nValid choices for {self._name}: {choices}"
            raise CustomValidationError(self._name, e.value, source, msg)

    @staticmethod
    def _typify_data_structure(value, source, type_hint=None):
        if isinstance(value, Mapping):
            return type(value)((k, v.typify(source)) for k, v in value.items())
        elif isiterable(value):
            return type(value)(v.typify(source) for v in value)
        elif isinstance(value, ConfigurationObject):
            for attr_name, attr_value in vars(value).items():
                if isinstance(attr_value, LoadedParameter):
                    value.__setattr__(attr_name, attr_value.typify(source))
            return value
        elif (
            isinstance(value, str)
            and isinstance(type_hint, type)
            and issubclass(type_hint, str)
        ):
            # This block is necessary because if we fall through to typify(), we end up calling
            # .strip() on the str, when sometimes we want to preserve preceding and trailing
            # whitespace.
            return type_hint(value)
        else:
            return typify(value, type_hint)

    @staticmethod
    def _match_key_is_important(loaded_parameter):
        return loaded_parameter.key_flag is ParameterFlag.final

    @staticmethod
    def _first_important_matches(matches):
        idx = first(
            enumerate(matches),
            lambda x: LoadedParameter._match_key_is_important(x[1]),
            apply=lambda x: x[0],
        )
        return matches if idx is None else matches[: idx + 1]


class PrimitiveLoadedParameter(LoadedParameter):
    """
    LoadedParameter type that holds a single python primitive value.

    The python primitive types are str, int, float, complex, bool, and NoneType. In addition,
    python 2 has long and unicode types.
    """

    def __init__(
        self, name, element_type, value, key_flag, value_flags, validation=None
    ):
        """
        Args:
            element_type (type or tuple[type]): Type-validation of parameter's value.
            value (primitive value): primitive python value.
        """
        self._type = element_type
        self._element_type = element_type
        super().__init__(name, value, key_flag, value_flags, validation)

    def __eq__(self, other):
        if type(other) is type(self):
            return self.value == other.value
        return False

    def __hash__(self):
        return hash(self.value)

    def merge(self, matches):
        important_match = first(
            matches, LoadedParameter._match_key_is_important, default=None
        )
        if important_match is not None:
            return important_match

        last_match = last(matches, lambda x: x is not None, default=None)
        if last_match is not None:
            return last_match
        raise ThisShouldNeverHappenError()  # pragma: no cover


class MapLoadedParameter(LoadedParameter):
    """LoadedParameter type that holds a map (i.e. dict) of LoadedParameters."""

    _type = frozendict

    def __init__(
        self, name, value, element_type, key_flag, value_flags, validation=None
    ):
        """
        Args:
            value (Mapping): Map of string keys to LoadedParameter values.
            element_type (Parameter): The Parameter type that is held in value.
            value_flags (Mapping): Map of priority value flags.
        """
        self._element_type = element_type
        super().__init__(name, value, key_flag, value_flags, validation)

    def collect_errors(self, instance, typed_value, source="<<merged>>"):
        errors = super().collect_errors(instance, typed_value, self.value)

        # recursively validate the values in the map
        if isinstance(self.value, Mapping):
            for key, value in self.value.items():
                errors.extend(value.collect_errors(instance, typed_value[key], source))
        return errors

    def merge(self, parameters: Sequence[MapLoadedParameter]) -> MapLoadedParameter:
        # get all values up to and including first important_match
        # but if no important_match, then all matches are important_matches
        parameters = LoadedParameter._first_important_matches(parameters)

        # ensure all parameter values are Mappings
        for parameter in parameters:
            if not isinstance(parameter.value, Mapping):
                raise InvalidTypeError(
                    self.name,
                    parameter.value,
                    parameter.source,
                    parameter.value.__class__.__name__,
                    self._type.__name__,
                )

        # map keys with final values,
        # first key has higher precedence than later ones
        final_map = {
            key: value
            for parameter in reversed(parameters)
            for key, value in parameter.value.items()
            if parameter.value_flags.get(key) == ParameterFlag.final
        }

        # map each value by recursively calling merge on any entries with the same key,
        # last key has higher precedence than earlier ones
        grouped_map = {}
        for parameter in parameters:
            for key, value in parameter.value.items():
                grouped_map.setdefault(key, []).append(value)
        merged_map = {
            key: values[0].merge(values) for key, values in grouped_map.items()
        }

        # update merged_map with final_map values
        merged_value = frozendict({**merged_map, **final_map})

        # create new parameter for the merged values
        return MapLoadedParameter(
            self._name,
            merged_value,
            self._element_type,
            self.key_flag,
            self.value_flags,
            validation=self._validation,
        )


class SequenceLoadedParameter(LoadedParameter):
    """LoadedParameter type that holds a sequence (i.e. list) of LoadedParameters."""

    _type = tuple

    def __init__(
        self, name, value, element_type, key_flag, value_flags, validation=None
    ):
        """
        Args:
            value (Sequence): Sequence of LoadedParameter values.
            element_type (Parameter): The Parameter type that is held in the sequence.
            value_flags (Sequence): Sequence of priority value_flags.
        """
        self._element_type = element_type
        super().__init__(name, value, key_flag, value_flags, validation)

    def collect_errors(self, instance, typed_value, source="<<merged>>"):
        errors = super().collect_errors(instance, typed_value, self.value)
        # recursively collect errors on the elements in the sequence
        for idx, element in enumerate(self.value):
            errors.extend(element.collect_errors(instance, typed_value[idx], source))
        return errors

    def merge(self, matches):
        # get matches up to and including first important_match
        # but if no important_match, then all matches are important_matches
        relevant_matches_and_values = tuple(
            (match, match.value)
            for match in LoadedParameter._first_important_matches(matches)
        )
        for match, value in relevant_matches_and_values:
            if not isinstance(value, tuple):
                raise InvalidTypeError(
                    self.name,
                    value,
                    match.source,
                    value.__class__.__name__,
                    self._type.__name__,
                )

        # get individual lines from important_matches that were marked important
        # these will be prepended to the final result
        def get_marked_lines(match, marker):
            return (
                tuple(
                    line
                    for line, flag in zip(match.value, match.value_flags)
                    if flag is marker
                )
                if match
                else ()
            )

        top_lines = chain.from_iterable(
            get_marked_lines(m, ParameterFlag.top)
            for m, _ in relevant_matches_and_values
        )

        # also get lines that were marked as bottom, but reverse the match order so that lines
        # coming earlier will ultimately be last
        bottom_lines = tuple(
            chain.from_iterable(
                get_marked_lines(match, ParameterFlag.bottom)
                for match, _ in reversed(relevant_matches_and_values)
            )
        )

        # now, concat all lines, while reversing the matches
        #   reverse because elements closer to the end of search path take precedence
        all_lines = chain.from_iterable(
            v for _, v in reversed(relevant_matches_and_values)
        )

        # stack top_lines + all_lines, then de-dupe
        top_deduped = tuple(unique((*top_lines, *all_lines)))

        # take the top-deduped lines, reverse them, and concat with reversed bottom_lines
        # this gives us the reverse of the order we want, but almost there
        # NOTE: for a line value marked both top and bottom, the bottom marker will win out
        #       for the top marker to win out, we'd need one additional de-dupe step
        bottom_deduped = tuple(
            unique((*reversed(bottom_lines), *reversed(top_deduped)))
        )
        # just reverse, and we're good to go
        merged_values = tuple(reversed(bottom_deduped))

        return SequenceLoadedParameter(
            self._name,
            merged_values,
            self._element_type,
            self.key_flag,
            self.value_flags,
            validation=self._validation,
        )


class ObjectLoadedParameter(LoadedParameter):
    """LoadedParameter type that holds a mapping (i.e. object) of LoadedParameters."""

    _type = object

    def __init__(
        self, name, value, element_type, key_flag, value_flags, validation=None
    ):
        """
        Args:
            value (Sequence): Object with LoadedParameter fields.
            element_type (object): The Parameter type that is held in the sequence.
            value_flags (Sequence): Sequence of priority value_flags.
        """
        self._element_type = element_type
        super().__init__(name, value, key_flag, value_flags, validation)

    def collect_errors(self, instance, typed_value, source="<<merged>>"):
        errors = super().collect_errors(instance, typed_value, self.value)

        # recursively validate the values in the object fields
        if isinstance(self.value, ConfigurationObject):
            for key, value in vars(self.value).items():
                if isinstance(value, LoadedParameter):
                    errors.extend(
                        value.collect_errors(instance, typed_value[key], source)
                    )
        return errors

    def merge(
        self, parameters: Sequence[ObjectLoadedParameter]
    ) -> ObjectLoadedParameter:
        # get all parameters up to and including first important_match
        # but if no important_match, then all parameters are important_matches
        parameters = LoadedParameter._first_important_matches(parameters)

        # map keys with final values,
        # first key has higher precedence than later ones
        final_map = {
            key: value
            for parameter in reversed(parameters)
            for key, value in vars(parameter.value).items()
            if (
                isinstance(value, LoadedParameter)
                and parameter.value_flags.get(key) == ParameterFlag.final
            )
        }

        # map each value by recursively calling merge on any entries with the same key,
        # last key has higher precedence than earlier ones
        grouped_map = {}
        for parameter in parameters:
            for key, value in vars(parameter.value).items():
                grouped_map.setdefault(key, []).append(value)
        merged_map = {
            key: values[0].merge(values) for key, values in grouped_map.items()
        }

        # update merged_map with final_map values
        merged_value = copy.deepcopy(self._element_type)
        for key, value in {**merged_map, **final_map}.items():
            merged_value.__setattr__(key, value)

        # create new parameter for the merged values
        return ObjectLoadedParameter(
            self._name,
            merged_value,
            self._element_type,
            self.key_flag,
            self.value_flags,
            validation=self._validation,
        )


class ConfigurationObject:
    """Dummy class to mark whether a Python object has config parameters within."""


class Parameter(metaclass=ABCMeta):
    # (type) describes the type of parameter
    _type = None
    # (Parameter or type) if the Parameter is holds a collection, describes the element held in
    # the collection. if not, describes the primitive type held by the Parameter.
    _element_type = None

    def __init__(self, default, validation=None):
        """
        The Parameter class represents an unloaded configuration parameter, holding type, default
        and validation information until the parameter is loaded with a configuration.

        Args:
            default (Any): the typed, python representation default value given if the Parameter
                is not found in a Configuration.
            validation (callable): Given a parameter value as input, return a boolean indicating
                validity, or alternately return a string describing an invalid value.
        """
        self._default = default
        self._validation = validation

    @property
    def default(self):
        """Returns a DefaultValueRawParameter that wraps the actual default value."""
        wrapped_default = DefaultValueRawParameter("default", "default", self._default)
        return self.load("default", wrapped_default)

    def get_all_matches(self, name, names, instance):
        """
        Finds all matches of a Parameter in a Configuration instance

        Args:
            name (str): canonical name of the parameter to search for
            names (tuple(str)): alternative aliases of the parameter
            instance (Configuration): instance of the configuration to search within

        Returns (List(RawParameter)): matches of the parameter found in the configuration.
        """
        matches = []
        multikey_exceptions = []
        for filepath, raw_parameters in instance.raw_data.items():
            match, error = ParameterLoader.raw_parameters_from_single_source(
                name, names, raw_parameters
            )
            if match is not None:
                matches.append(match)
            if error:
                multikey_exceptions.append(error)
        return matches, multikey_exceptions

    @abstractmethod
    def load(self, name, match):
        """
        Loads a Parameter with the value in a RawParameter.

        Args:
            name (str): name of the parameter to pass through
            match (RawParameter): the value of the RawParameter match

        Returns a LoadedParameter
        """
        raise NotImplementedError()

    def typify(self, name, source, value):
        element_type = self._element_type
        try:
            return typify_data_structure(value, element_type)
        except TypeCoercionError as e:
            msg = str(e)
            if issubclass(element_type, Enum):
                choices = ", ".join(
                    map("'{}'".format, element_type.__members__.values())
                )
                msg += f"\nValid choices for {name}: {choices}"
            raise CustomValidationError(name, e.value, source, msg)


class PrimitiveParameter(Parameter):
    """
    Parameter type for a Configuration class that holds a single python primitive value.

    The python primitive types are str, int, float, complex, bool, and NoneType. In addition,
    python 2 has long and unicode types.
    """

    def __init__(self, default, element_type=None, validation=None):
        """
        Args:
            default (primitive value): default value if the Parameter is not found.
            element_type (type or tuple[type]): Type-validation of parameter's value. If None,
                type(default) is used.
        """
        self._type = type(default) if element_type is None else element_type
        self._element_type = self._type
        super().__init__(default, validation)

    def load(self, name, match):
        return PrimitiveLoadedParameter(
            name,
            self._type,
            match.value(self._element_type),
            match.keyflag(),
            match.valueflags(self._element_type),
            validation=self._validation,
        )


class MapParameter(Parameter):
    """Parameter type for a Configuration class that holds a map (i.e. dict) of Parameters."""

    _type = frozendict

    def __init__(self, element_type, default=frozendict(), validation=None):
        """
        Args:
            element_type (Parameter): The Parameter type held in the MapParameter.
            default (Mapping):  The parameter's default value. If None, will be an empty dict.
        """
        self._element_type = element_type
        default = default and frozendict(default) or frozendict()
        super().__init__(default, validation=validation)

    def get_all_matches(self, name, names, instance):
        # it also config settings like `proxy_servers: ~`
        matches, exceptions = super().get_all_matches(name, names, instance)
        matches = tuple(m for m in matches if m._raw_value is not None)
        return matches, exceptions

    def load(self, name, match):
        value = match.value(self._element_type)
        if value is None:
            return MapLoadedParameter(
                name,
                frozendict(),
                self._element_type,
                match.keyflag(),
                frozendict(),
                validation=self._validation,
            )

        if not isinstance(value, Mapping):
            raise InvalidTypeError(
                name, value, match.source, value.__class__.__name__, self._type.__name__
            )

        loaded_map = {}
        for key, child_value in match.value(self._element_type).items():
            loaded_child_value = self._element_type.load(name, child_value)
            loaded_map[key] = loaded_child_value

        return MapLoadedParameter(
            name,
            frozendict(loaded_map),
            self._element_type,
            match.keyflag(),
            match.valueflags(self._element_type),
            validation=self._validation,
        )


class SequenceParameter(Parameter):
    """Parameter type for a Configuration class that holds a sequence (i.e. list) of Parameters."""

    _type = tuple

    def __init__(self, element_type, default=(), validation=None, string_delimiter=","):
        """
        Args:
            element_type (Parameter): The Parameter type that is held in the sequence.
            default (Sequence): default value, empty tuple if not given.
            string_delimiter (str): separation string used to parse string into sequence.
        """
        self._element_type = element_type
        self.string_delimiter = string_delimiter
        super().__init__(default, validation)

    def get_all_matches(self, name, names, instance):
        # this is necessary to handle argparse `action="append"`, which can't be set to a
        #   default value of NULL
        # it also config settings like `channels: ~`
        matches, exceptions = super().get_all_matches(name, names, instance)
        matches = tuple(m for m in matches if m._raw_value is not None)
        return matches, exceptions

    def load(self, name, match):
        value = match.value(self)
        if value is None:
            return SequenceLoadedParameter(
                name,
                (),
                self._element_type,
                match.keyflag(),
                (),
                validation=self._validation,
            )

        if not isiterable(value):
            raise InvalidTypeError(
                name, value, match.source, value.__class__.__name__, self._type.__name__
            )

        loaded_sequence = []
        for child_value in value:
            loaded_child_value = self._element_type.load(name, child_value)
            loaded_sequence.append(loaded_child_value)

        return SequenceLoadedParameter(
            name,
            tuple(loaded_sequence),
            self._element_type,
            match.keyflag(),
            match.valueflags(self._element_type),
            validation=self._validation,
        )


class ObjectParameter(Parameter):
    """Parameter type for a Configuration class that holds an object with Parameter fields."""

    _type = object

    def __init__(self, element_type, default=ConfigurationObject(), validation=None):
        """
        Args:
            element_type (object): The object type with parameter fields held in ObjectParameter.
            default (Sequence): default value, empty tuple if not given.
        """
        self._element_type = element_type
        super().__init__(default, validation)

    def get_all_matches(self, name, names, instance):
        # it also config settings like `proxy_servers: ~`
        matches, exceptions = super().get_all_matches(name, names, instance)
        matches = tuple(m for m in matches if m._raw_value is not None)
        return matches, exceptions

    def load(self, name, match):
        value = match.value(self._element_type)
        if value is None:
            return ObjectLoadedParameter(
                name,
                None,
                self._element_type,
                match.keyflag(),
                None,
                validation=self._validation,
            )

        if not isinstance(value, (Mapping, ConfigurationObject)):
            raise InvalidTypeError(
                name, value, match.source, value.__class__.__name__, self._type.__name__
            )

        # for a default object, extract out the instance variables
        if isinstance(value, ConfigurationObject):
            value = vars(value)

        object_parameter_attrs = {
            attr_name: parameter_type
            for attr_name, parameter_type in vars(self._element_type).items()
            if isinstance(parameter_type, Parameter)
        }

        # recursively load object fields
        loaded_attrs = {}
        for attr_name, parameter_type in object_parameter_attrs.items():
            if raw_child_value := value.get(attr_name):
                loaded_child_value = parameter_type.load(name, raw_child_value)
            else:
                loaded_child_value = parameter_type.default
            loaded_attrs[attr_name] = loaded_child_value

        # copy object and replace Parameter with LoadedParameter fields
        object_copy = copy.deepcopy(self._element_type)
        for attr_name, loaded_child_parameter in loaded_attrs.items():
            object_copy.__setattr__(attr_name, loaded_child_parameter)

        return ObjectLoadedParameter(
            name,
            object_copy,
            self._element_type,
            match.keyflag(),
            match.valueflags(self._element_type),
            validation=self._validation,
        )


class ParameterLoader:
    """
    ParameterLoader class contains the top level logic needed to load a parameter from start to
    finish.
    """

    def __init__(self, parameter_type, aliases=(), expandvars=False):
        """
        Args:
            parameter_type (Parameter): the type of Parameter that is stored in the loader.
            aliases (tuple(str)): alternative aliases for the Parameter
            expandvars (bool): whether or not to recursively expand environmental variables.
        """
        self._name = None
        self._names = None
        self.type = parameter_type
        self.aliases = aliases
        self._expandvars = expandvars

    def _set_name(self, name):
        # this is an explicit method, and not a descriptor/setter
        # it's meant to be called by the Configuration metaclass
        self._name = name
        _names = frozenset(x for x in chain(self.aliases, (name,)))
        self._names = _names
        return name

    @property
    def name(self):
        if self._name is None:
            # The Configuration metaclass should call the `_set_name` method.
            raise ThisShouldNeverHappenError()  # pragma: no cover
        return self._name

    @property
    def names(self):
        if self._names is None:
            # The Configuration metaclass should call the `_set_name` method.
            raise ThisShouldNeverHappenError()  # pragma: no cover
        return self._names

    def __get__(self, instance, instance_type):
        # strategy is "extract and merge," which is actually just map and reduce
        # extract matches from each source in SEARCH_PATH
        # then merge matches together
        if self.name in instance._cache_:
            return instance._cache_[self.name]

        # step 1/2: load config and find top level matches
        raw_matches, errors = self.type.get_all_matches(self.name, self.names, instance)

        # step 3: parse RawParameters into LoadedParameters
        matches = [self.type.load(self.name, match) for match in raw_matches]

        # step 4: merge matches
        merged = matches[0].merge(matches) if matches else self.type.default

        # step 5: typify
        # We need to expand any environment variables before type casting.
        # Otherwise e.g. `my_bool_var: $BOOL` with BOOL=True would raise a TypeCoercionError.
        expanded = merged.expand() if self._expandvars else merged
        try:
            result = expanded.typify("<<merged>>")
        except CustomValidationError as e:
            errors.append(e)
        else:
            errors.extend(expanded.collect_errors(instance, result, "<<merged>>"))
        raise_errors(errors)
        instance._cache_[self.name] = result
        return result

    def _raw_parameters_from_single_source(self, raw_parameters):
        return ParameterLoader.raw_parameters_from_single_source(
            self.name, self.names, raw_parameters
        )

    @staticmethod
    def raw_parameters_from_single_source(name, names, raw_parameters):
        # while supporting parameter name aliases, we enforce that only one definition is given
        # per data source
        keys = names & frozenset(raw_parameters.keys())
        matches = {key: raw_parameters[key] for key in keys}
        numkeys = len(keys)
        if numkeys == 0:
            return None, None
        elif numkeys == 1:
            return next(iter(matches.values())), None
        elif name in keys:
            return matches[name], MultipleKeysError(
                raw_parameters[next(iter(keys))].source, keys, name
            )
        else:
            return None, MultipleKeysError(
                raw_parameters[next(iter(keys))].source, keys, name
            )


class ConfigurationType(type):
    """metaclass for Configuration"""

    def __init__(cls, name, bases, attr):
        super().__init__(name, bases, attr)

        # call _set_name for each parameter
        cls.parameter_names = tuple(
            p._set_name(name)
            for name, p in cls.__dict__.items()
            if isinstance(p, ParameterLoader)
        )


CONDARC_FILENAMES = (".condarc", "condarc")
YAML_EXTENSIONS = (".yml", ".yaml")
_RE_CUSTOM_EXPANDVARS = compile(
    rf"""
    # delimiter and a Python identifier
    \$(?P<named>{Template.idpattern}) |

    # delimiter and a braced identifier
    \${{(?P<braced>{Template.idpattern})}} |

    # delimiter padded identifier
    %(?P<padded>{Template.idpattern})%
    """,
    flags=IGNORECASE | VERBOSE,
)


def custom_expandvars(
    template: str, mapping: Mapping[str, Any] = {}, /, **kwargs
) -> str:
    """Expand variables in a string.

    Inspired by `string.Template` and modified to mirror `os.path.expandvars` functionality
    allowing custom variables without mutating `os.environ`.

    Expands POSIX and Windows CMD environment variables as follows:

    - $VARIABLE → value of VARIABLE
    - ${VARIABLE} → value of VARIABLE
    - %VARIABLE% → value of VARIABLE

    Invalid substitutions are left as-is:

    - $MISSING → $MISSING
    - ${MISSING} → ${MISSING}
    - %MISSING% → %MISSING%
    - $$ → $$
    - %% → %%
    - $ → $
    - % → %
    """
    mapping = {**mapping, **kwargs}

    def convert(match: Match):
        return str(
            mapping.get(
                match.group("named") or match.group("braced") or match.group("padded"),
                match.group(),  # fallback to the original string
            )
        )

    return _RE_CUSTOM_EXPANDVARS.sub(convert, template)


class Configuration(metaclass=ConfigurationType):
    def __init__(self, search_path=(), app_name=None, argparse_args=None, **kwargs):
        # Currently, __init__ does a **full** disk reload of all files.
        # A future improvement would be to cache files that are already loaded.
        self.raw_data = {}
        self._cache_ = {}
        self._reset_callbacks = IndexedSet()
        self._validation_errors = defaultdict(list)

        self._set_search_path(search_path, **kwargs)
        self._set_env_vars(app_name)
        self._set_argparse_args(argparse_args)

    @staticmethod
    def _expand_search_path(
        search_path: Iterable[Path | str],
        **kwargs,
    ) -> Iterable[Path]:
        for search in search_path:
            # use custom_expandvars instead of os.path.expandvars so additional variables can be
            # passed in without mutating os.environ
            if isinstance(search, Path):
                path = search
            else:
                template = custom_expandvars(search, environ, **kwargs)
                path = Path(template).expanduser()

            if path.is_file() and (
                path.name in CONDARC_FILENAMES or path.suffix in YAML_EXTENSIONS
            ):
                yield path
            elif path.is_dir():
                yield from (
                    subpath
                    for subpath in sorted(path.iterdir())
                    if subpath.is_file() and subpath.suffix in YAML_EXTENSIONS
                )

    @classmethod
    def _load_search_path(
        cls,
        search_path: Iterable[Path],
    ) -> Iterable[tuple[Path, dict]]:
        for path in search_path:
            try:
                yield path, YamlRawParameter.make_raw_parameters_from_file(path)
            except ConfigurationLoadError as err:
                log.warning(
                    "Ignoring configuration file (%s) due to error:\n%s",
                    path,
                    err,
                )

    def _set_search_path(self, search_path: Iterable[Path | str], **kwargs):
        self._search_path = IndexedSet(self._expand_search_path(search_path, **kwargs))

        self._set_raw_data(dict(self._load_search_path(self._search_path)))

        self._reset_cache()
        return self

    def _set_env_vars(self, app_name=None):
        self._app_name = app_name

        # remove existing source so "insert" order is correct
        source = EnvRawParameter.source
        if source in self.raw_data:
            del self.raw_data[source]

        if app_name:
            self.raw_data[source] = EnvRawParameter.make_raw_parameters(app_name)

        self._reset_cache()
        return self

    def _set_argparse_args(self, argparse_args):
        # the argparse_args we store internally in this class as self._argparse_args
        #   will be a mapping type, not a non-`dict` object like argparse_args is natively
        if hasattr(argparse_args, "__dict__"):
            # the argparse_args from argparse will be an object with a __dict__ attribute
            #   and not a mapping type like this method will turn it into
            items = vars(argparse_args).items()
        elif not argparse_args:
            # argparse_args can be initialized as `None`
            items = ()
        else:
            # we're calling this method with argparse_args that are a mapping type, likely
            #   already having been processed by this method before
            items = argparse_args.items()

        self._argparse_args = argparse_args = AttrDict(
            {k: v for k, v in items if v is not NULL}
        )

        # remove existing source so "insert" order is correct
        source = ArgParseRawParameter.source
        if source in self.raw_data:
            del self.raw_data[source]

        self.raw_data[source] = ArgParseRawParameter.make_raw_parameters(argparse_args)

        self._reset_cache()
        return self

    def _set_raw_data(self, raw_data: Mapping[Hashable, dict]):
        self.raw_data.update(raw_data)
        self._reset_cache()
        return self

    def _reset_cache(self):
        self._cache_ = {}
        for callback in self._reset_callbacks:
            callback()
        return self

    def register_reset_callaback(self, callback):
        self._reset_callbacks.add(callback)

    def check_source(self, source):
        # this method ends up duplicating much of the logic of Parameter.__get__
        # I haven't yet found a way to make it more DRY though
        typed_values = {}
        validation_errors = []
        raw_parameters = self.raw_data[source]
        for key in self.parameter_names:
            parameter = self.__class__.__dict__[key]
            match, multikey_error = parameter._raw_parameters_from_single_source(
                raw_parameters
            )
            if multikey_error:
                validation_errors.append(multikey_error)

            if match is not None:
                loaded_parameter = parameter.type.load(key, match)
                # untyped_value = loaded_parameter.value
                # if untyped_value is None:
                #     if isinstance(parameter, SequenceLoadedParameter):
                #         untyped_value = ()
                #     elif isinstance(parameter, MapLoadedParameter):
                #         untyped_value = {}
                try:
                    typed_value = loaded_parameter.typify(match.source)
                except CustomValidationError as e:
                    validation_errors.append(e)
                else:
                    collected_errors = loaded_parameter.collect_errors(
                        self, typed_value, match.source
                    )
                    if collected_errors:
                        validation_errors.extend(collected_errors)
                    else:
                        typed_values[match.key] = typed_value
            else:
                # this situation will happen if there is a multikey_error and none of the
                # matched keys is the primary key
                pass
        return typed_values, validation_errors

    def validate_all(self):
        validation_errors = list(
            chain.from_iterable(
                self.check_source(source)[1] for source in self.raw_data
            )
        )
        raise_errors(validation_errors)
        self.validate_configuration()

    @staticmethod
    def _collect_validation_error(func, *args, **kwargs):
        try:
            func(*args, **kwargs)
        except ConfigurationError as e:
            return (e.errors if hasattr(e, "errors") else e,)
        return ()

    def validate_configuration(self):
        errors = chain.from_iterable(
            Configuration._collect_validation_error(getattr, self, name)
            for name in self.parameter_names
        )
        post_errors = self.post_build_validation()
        raise_errors(tuple(chain.from_iterable((errors, post_errors))))

    def post_build_validation(self):
        return ()

    def collect_all(self):
        typed_values = {}
        validation_errors = {}
        for source in self.raw_data:
            typed_values[source], validation_errors[source] = self.check_source(source)
        raise_errors(tuple(chain.from_iterable(validation_errors.values())))
        return {k: v for k, v in typed_values.items() if v}

    def describe_parameter(self, parameter_name):
        # TODO, in Parameter base class, rename element_type to value_type
        if parameter_name not in self.parameter_names:
            parameter_name = "_" + parameter_name
        parameter_loader = self.__class__.__dict__[parameter_name]
        parameter = parameter_loader.type
        assert isinstance(parameter, Parameter)

        # dedupe leading underscore from name
        name = parameter_loader.name.lstrip("_")
        aliases = tuple(alias for alias in parameter_loader.aliases if alias != name)

        description = self.get_descriptions().get(name, "")
        et = parameter._element_type
        if type(et) == EnumMeta:  # noqa: E721
            et = [et]
        if not isiterable(et):
            et = [et]

        if isinstance(parameter._element_type, Parameter):
            element_types = tuple(
                _et.__class__.__name__.lower().replace("parameter", "") for _et in et
            )
        else:
            element_types = tuple(_et.__name__ for _et in et)

        details = {
            "parameter_type": parameter.__class__.__name__.lower().replace(
                "parameter", ""
            ),
            "name": name,
            "aliases": aliases,
            "element_types": element_types,
            "default_value": parameter.default.typify("<<describe>>"),
            "description": description.replace("\n", " ").strip(),
        }
        if isinstance(parameter, SequenceParameter):
            details["string_delimiter"] = parameter.string_delimiter
        return details

    def list_parameters(self):
        return tuple(sorted(name.lstrip("_") for name in self.parameter_names))

    def typify_parameter(self, parameter_name, value, source):
        # return a tuple with correct parameter name and typed-value
        if parameter_name not in self.parameter_names:
            parameter_name = "_" + parameter_name
        parameter_loader = self.__class__.__dict__[parameter_name]
        parameter = parameter_loader.type
        assert isinstance(parameter, Parameter)

        return parameter.typify(parameter_name, source, value)

    def get_descriptions(self):
        raise NotImplementedError()


def unique_sequence_map(*, unique_key: str):
    """
    Used to validate properties on :class:`Configuration` subclasses defined as a
    ``SequenceParameter(MapParameter())`` where the map contains a single key that
    should be regarded as unique. This decorator will handle removing duplicates and
    merging to a single sequence.
    """

    def inner_wrap(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            sequence_map = func(*args, **kwargs)
            new_sequence_mapping = {}

            for mapping in sequence_map:
                unique_key_value = mapping.get(unique_key)

                if unique_key_value is None:
                    log.error(
                        f'Configuration: skipping {mapping} for "{func.__name__}"; unique key '
                        f'"{unique_key}" not present on mapping'
                    )
                    continue

                if unique_key_value in new_sequence_mapping:
                    log.error(
                        f'Configuration: skipping {mapping} for "{func.__name__}"; value '
                        f'"{unique_key_value}" already present'
                    )
                    continue

                new_sequence_mapping[unique_key_value] = mapping

            return tuple(new_sequence_mapping.values())

        return wrapper

    return inner_wrap
