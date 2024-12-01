"""Collection of functions to coerce conversion of types with an intelligent guess."""
from collections.abc import Mapping
from itertools import chain
from re import IGNORECASE, compile

from enum import Enum

from ..deprecations import deprecated
from .compat import isiterable
from .decorators import memoizedproperty
from .exceptions import AuxlibError

__all__ = ["boolify", "typify", "maybecall", "numberify"]

BOOLISH_TRUE = ("true", "yes", "on", "y")
BOOLISH_FALSE = ("false", "off", "n", "no", "non", "none", "")
NULL_STRINGS = ("none", "~", "null", "\0")
BOOL_COERCEABLE_TYPES = (int, bool, float, complex, list, set, dict, tuple)
NUMBER_TYPES = (int, float, complex)
NUMBER_TYPES_SET = {*NUMBER_TYPES}
STRING_TYPES_SET = {str}

NO_MATCH = object()


class TypeCoercionError(AuxlibError, ValueError):

    def __init__(self, value, msg, *args, **kwargs):
        self.value = value
        super().__init__(msg, *args, **kwargs)


class _Regex:

    @memoizedproperty
    def BOOLEAN_TRUE(self):
        return compile(r'^true$|^yes$|^on$', IGNORECASE), True

    @memoizedproperty
    def BOOLEAN_FALSE(self):
        return compile(r'^false$|^no$|^off$', IGNORECASE), False

    @memoizedproperty
    def NONE(self):
        return compile(r'^none$|^null$', IGNORECASE), None

    @memoizedproperty
    def INT(self):
        return compile(r'^[-+]?\d+$'), int

    @memoizedproperty
    def BIN(self):
        return compile(r'^[-+]?0[bB][01]+$'), bin

    @memoizedproperty
    def OCT(self):
        return compile(r'^[-+]?0[oO][0-7]+$'), oct

    @memoizedproperty
    def HEX(self):
        return compile(r'^[-+]?0[xX][0-9a-fA-F]+$'), hex

    @memoizedproperty
    def FLOAT(self):
        return compile(r'^[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?$'), float

    @memoizedproperty
    def COMPLEX(self):
        return (compile(r'^(?:[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?)?'  # maybe first float
                        r'[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?j$'),     # second float with j
                complex)

    @property
    def numbers(self):
        yield self.INT
        yield self.FLOAT
        yield self.BIN
        yield self.OCT
        yield self.HEX
        yield self.COMPLEX

    @property
    def boolean(self):
        yield self.BOOLEAN_TRUE
        yield self.BOOLEAN_FALSE

    @property
    def none(self):
        yield self.NONE

    def convert_number(self, value_string):
        return self._convert(value_string, (self.numbers, ))

    def convert(self, value_string):
        return self._convert(value_string, (self.boolean, self.none, self.numbers, ))

    def _convert(self, value_string, type_list):
        return next((typish(value_string) if callable(typish) else typish
                     for regex, typish in chain.from_iterable(type_list)
                     if regex.match(value_string)),
                    NO_MATCH)


_REGEX = _Regex()


def numberify(value):
    """

    Examples:
        >>> [numberify(x) for x in ('1234', 1234, '0755', 0o0755, False, 0, '0', True, 1, '1')]
          [1234, 1234, 755, 493, 0, 0, 0, 1, 1, 1]
        >>> [numberify(x) for x in ('12.34', 12.34, 1.2+3.5j, '1.2+3.5j')]
        [12.34, 12.34, (1.2+3.5j), (1.2+3.5j)]

    """
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, NUMBER_TYPES):
        return value
    candidate = _REGEX.convert_number(value)
    if candidate is not NO_MATCH:
        return candidate
    raise TypeCoercionError(value, f"Cannot convert {value} to a number.")


def boolify(value, nullable=False, return_string=False):
    """Convert a number, string, or sequence type into a pure boolean.

    Args:
        value (number, string, sequence): pretty much anything

    Returns:
        bool: boolean representation of the given value

    Examples:
        >>> [boolify(x) for x in ('yes', 'no')]
        [True, False]
        >>> [boolify(x) for x in (0.1, 0+0j, True, '0', '0.0', '0.1', '2')]
        [True, False, True, False, False, True, True]
        >>> [boolify(x) for x in ("true", "yes", "on", "y")]
        [True, True, True, True]
        >>> [boolify(x) for x in ("no", "non", "none", "off", "")]
        [False, False, False, False, False]
        >>> [boolify(x) for x in ([], set(), dict(), tuple())]
        [False, False, False, False]
        >>> [boolify(x) for x in ([1], set([False]), dict({'a': 1}), tuple([2]))]
        [True, True, True, True]

    """
    # cast number types naturally
    if isinstance(value, BOOL_COERCEABLE_TYPES):
        return bool(value)
    # try to coerce string into number
    val = str(value).strip().lower().replace(".", "", 1)
    if val.isnumeric():
        return bool(float(val))
    elif val in BOOLISH_TRUE:
        return True
    elif nullable and val in NULL_STRINGS:
        return None
    elif val in BOOLISH_FALSE:
        return False
    else:  # must be False
        try:
            return bool(complex(val))
        except ValueError:
            if isinstance(value, str) and return_string:
                return value
            raise TypeCoercionError(value, "The value %r cannot be boolified." % value)


def typify_str_no_hint(value):
    candidate = _REGEX.convert(value)
    return candidate if candidate is not NO_MATCH else value


def typify(value, type_hint=None):
    """Take a primitive value, usually a string, and try to make a more relevant type out of it.
    An optional type_hint will try to coerce the value to that type.

    Args:
        value (Any): Usually a string, not a sequence
        type_hint (type or tuple[type]):

    Examples:
        >>> typify('32')
        32
        >>> typify('32', float)
        32.0
        >>> typify('32.0')
        32.0
        >>> typify('32.0.0')
        '32.0.0'
        >>> [typify(x) for x in ('true', 'yes', 'on')]
        [True, True, True]
        >>> [typify(x) for x in ('no', 'FALSe', 'off')]
        [False, False, False]
        >>> [typify(x) for x in ('none', 'None', None)]
        [None, None, None]

    """
    # value must be a string, or there at least needs to be a type hint
    if isinstance(value, str):
        value = value.strip()
    elif type_hint is None:
        # can't do anything because value isn't a string and there's no type hint
        return value

    # now we either have a stripped string, a type hint, or both
    # use the hint if it exists
    if isiterable(type_hint):
        if isinstance(type_hint, type) and issubclass(type_hint, Enum):
            try:
                return type_hint(value)
            except ValueError as e:
                try:
                    return type_hint[value]
                except KeyError:
                    raise TypeCoercionError(value, str(e))
        type_hint = set(type_hint)
        if not (type_hint - NUMBER_TYPES_SET):
            return numberify(value)
        elif not (type_hint - STRING_TYPES_SET):
            return str(value)
        elif not (type_hint - {bool, type(None)}):
            return boolify(value, nullable=True)
        elif not (type_hint - (STRING_TYPES_SET | {bool})):
            return boolify(value, return_string=True)
        elif not (type_hint - (STRING_TYPES_SET | {type(None)})):
            value = str(value)
            return None if value.lower() == 'none' else value
        elif not (type_hint - {bool, int}):
            return typify_str_no_hint(str(value))
        else:
            raise NotImplementedError()
    elif type_hint is not None:
        # coerce using the type hint, or use boolify for bool
        try:
            return boolify(value) if type_hint == bool else type_hint(value)
        except ValueError as e:
            # ValueError: invalid literal for int() with base 10: 'nope'
            raise TypeCoercionError(value, str(e))
    else:
        # no type hint, but we know value is a string, so try to match with the regex patterns
        #   if there's still no match, `typify_str_no_hint` will return `value`
        return typify_str_no_hint(value)


def typify_data_structure(value, type_hint=None):
    if isinstance(value, Mapping):
        return type(value)((k, typify(v, type_hint)) for k, v in value.items())
    elif isiterable(value):
        return type(value)(typify(v, type_hint) for v in value)
    elif isinstance(value, str) and isinstance(type_hint, type) and issubclass(type_hint, str):
        # This block is necessary because if we fall through to typify(), we end up calling
        # .strip() on the str, when sometimes we want to preserve preceding and trailing
        # whitespace.
        return type_hint(value)
    else:
        return typify(value, type_hint)


def maybecall(value):
    return value() if callable(value) else value
