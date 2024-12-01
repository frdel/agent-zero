# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Implements the version spec with parsing and comparison logic.

Object inheritance:

.. autoapi-inheritance-diagram:: BaseSpec VersionSpec BuildNumberMatch
   :top-classes: conda.models.version.BaseSpec
   :parts: 1
"""

from __future__ import annotations

import operator as op
import re
from itertools import zip_longest
from logging import getLogger

from ..exceptions import InvalidVersionSpec

log = getLogger(__name__)


def normalized_version(version: str) -> VersionOrder:
    """Parse a version string and return VersionOrder object."""
    return VersionOrder(version)


def ver_eval(vtest, spec):
    return VersionSpec(spec).match(vtest)


version_check_re = re.compile(r"^[\*\.\+!_0-9a-z]+$")
version_split_re = re.compile("([0-9]+|[*]+|[^0-9*]+)")
version_cache = {}


class SingleStrArgCachingType(type):
    def __call__(cls, arg):
        if isinstance(arg, cls):
            return arg
        elif isinstance(arg, str):
            try:
                return cls._cache_[arg]
            except KeyError:
                val = cls._cache_[arg] = super().__call__(arg)
                return val
        else:
            return super().__call__(arg)


class VersionOrder(metaclass=SingleStrArgCachingType):
    """Implement an order relation between version strings.

    Version strings can contain the usual alphanumeric characters
    (A-Za-z0-9), separated into components by dots and underscores. Empty
    segments (i.e. two consecutive dots, a leading/trailing underscore)
    are not permitted. An optional epoch number - an integer
    followed by '!' - can proceed the actual version string
    (this is useful to indicate a change in the versioning
    scheme itself). Version comparison is case-insensitive.

    Conda supports six types of version strings:
    * Release versions contain only integers, e.g. '1.0', '2.3.5'.
    * Pre-release versions use additional letters such as 'a' or 'rc',
      for example '1.0a1', '1.2.beta3', '2.3.5rc3'.
    * Development versions are indicated by the string 'dev',
      for example '1.0dev42', '2.3.5.dev12'.
    * Post-release versions are indicated by the string 'post',
      for example '1.0post1', '2.3.5.post2'.
    * Tagged versions have a suffix that specifies a particular
      property of interest, e.g. '1.1.parallel'. Tags can be added
      to any of the preceding four types. As far as sorting is concerned,
      tags are treated like strings in pre-release versions.
    * An optional local version string separated by '+' can be appended
      to the main (upstream) version string. It is only considered
      in comparisons when the main versions are equal, but otherwise
      handled in exactly the same manner.

    To obtain a predictable version ordering, it is crucial to keep the
    version number scheme of a given package consistent over time.
    Specifically,
    * version strings should always have the same number of components
      (except for an optional tag suffix or local version string),
    * letters/strings indicating non-release versions should always
      occur at the same position.

    Before comparison, version strings are parsed as follows:
    * They are first split into epoch, version number, and local version
      number at '!' and '+' respectively. If there is no '!', the epoch is
      set to 0. If there is no '+', the local version is empty.
    * The version part is then split into components at '.' and '_'.
    * Each component is split again into runs of numerals and non-numerals
    * Subcomponents containing only numerals are converted to integers.
    * Strings are converted to lower case, with special treatment for 'dev'
      and 'post'.
    * When a component starts with a letter, the fillvalue 0 is inserted
      to keep numbers and strings in phase, resulting in '1.1.a1' == 1.1.0a1'.
    * The same is repeated for the local version part.

    Examples:
        1.2g.beta15.rc  =>  [[0], [1], [2, 'g'], [0, 'beta', 15], [0, 'rc']]
        1!2.15.1_ALPHA  =>  [[1], [2], [15], [1, '_alpha']]

    The resulting lists are compared lexicographically, where the following
    rules are applied to each pair of corresponding subcomponents:
    * integers are compared numerically
    * strings are compared lexicographically, case-insensitive
    * strings are smaller than integers, except
    * 'dev' versions are smaller than all corresponding versions of other types
    * 'post' versions are greater than all corresponding versions of other types
    * if a subcomponent has no correspondent, the missing correspondent is
      treated as integer 0 to ensure '1.1' == '1.1.0'.

    The resulting order is:
           0.4
         < 0.4.0
         < 0.4.1.rc
        == 0.4.1.RC   # case-insensitive comparison
         < 0.4.1
         < 0.5a1
         < 0.5b3
         < 0.5C1      # case-insensitive comparison
         < 0.5
         < 0.9.6
         < 0.960923
         < 1.0
         < 1.1dev1    # special case 'dev'
         < 1.1_       # appended underscore is special case for openssl-like versions
         < 1.1a1
         < 1.1.0dev1  # special case 'dev'
        == 1.1.dev1   # 0 is inserted before string
         < 1.1.a1
         < 1.1.0rc1
         < 1.1.0
        == 1.1
         < 1.1.0post1 # special case 'post'
        == 1.1.post1  # 0 is inserted before string
         < 1.1post1   # special case 'post'
         < 1996.07.12
         < 1!0.4.1    # epoch increased
         < 1!3.1.1.6
         < 2!0.4.1    # epoch increased again

    Some packages (most notably openssl) have incompatible version conventions.
    In particular, openssl interprets letters as version counters rather than
    pre-release identifiers. For openssl, the relation

      1.0.1 < 1.0.1a  =>  False  # should be true for openssl

    holds, whereas conda packages use the opposite ordering. You can work-around
    this problem by appending an underscore to plain version numbers:

      1.0.1_ < 1.0.1a =>  True   # ensure correct ordering for openssl
    """

    _cache_ = {}

    def __init__(self, vstr: str):
        # version comparison is case-insensitive
        version = vstr.strip().rstrip().lower()
        # basic validity checks
        if version == "":
            raise InvalidVersionSpec(vstr, "empty version string")
        invalid = not version_check_re.match(version)
        if invalid and "-" in version and "_" not in version:
            # Allow for dashes as long as there are no underscores
            # as well, by converting the former to the latter.
            version = version.replace("-", "_")
            invalid = not version_check_re.match(version)
        if invalid:
            raise InvalidVersionSpec(vstr, "invalid character(s)")

        # when fillvalue ==  0  =>  1.1 == 1.1.0
        # when fillvalue == -1  =>  1.1  < 1.1.0
        self.norm_version = version
        self.fillvalue = 0

        # find epoch
        version = version.split("!")
        if len(version) == 1:
            # epoch not given => set it to '0'
            epoch = ["0"]
        elif len(version) == 2:
            # epoch given, must be an integer
            if not version[0].isdigit():
                raise InvalidVersionSpec(vstr, "epoch must be an integer")
            epoch = [version[0]]
        else:
            raise InvalidVersionSpec(vstr, "duplicated epoch separator '!'")

        # find local version string
        version = version[-1].split("+")
        if len(version) == 1:
            # no local version
            self.local = []
        # Case 2: We have a local version component in version[1]
        elif len(version) == 2:
            # local version given
            self.local = version[1].replace("_", ".").split(".")
        else:
            raise InvalidVersionSpec(vstr, "duplicated local version separator '+'")

        # Error Case: Version is empty because the version string started with +.
        # e.g. "+", "1.2", "+a", "+1".
        # This is an error because specifying only a local version is invalid.
        # version[0] is empty because vstr.split("+") returns something like ['', '1.2']
        if version[0] == "":
            raise InvalidVersionSpec(
                vstr, "Missing version before local version separator '+'"
            )

        if version[0][-1] == "_":
            # If the last character of version is "-" or "_", don't split that out
            # individually. Implements the instructions for openssl-like versions
            #   > You can work-around this problem by appending a dash to plain version numbers
            split_version = version[0][:-1].replace("_", ".").split(".")
            split_version[-1] += "_"
        else:
            split_version = version[0].replace("_", ".").split(".")
        self.version = epoch + split_version

        # split components into runs of numerals and non-numerals,
        # convert numerals to int, handle special strings
        for v in (self.version, self.local):
            for k in range(len(v)):
                c = version_split_re.findall(v[k])
                if not c:
                    raise InvalidVersionSpec(vstr, "empty version component")
                for j in range(len(c)):
                    if c[j].isdigit():
                        c[j] = int(c[j])
                    elif c[j] == "post":
                        # ensure number < 'post' == infinity
                        c[j] = float("inf")
                    elif c[j] == "dev":
                        # ensure '*' < 'DEV' < '_' < 'a' < number
                        # by upper-casing (all other strings are lower case)
                        c[j] = "DEV"
                if v[k][0].isdigit():
                    v[k] = c
                else:
                    # components shall start with a number to keep numbers and
                    # strings in phase => prepend fillvalue
                    v[k] = [self.fillvalue] + c

    def __str__(self) -> str:
        return self.norm_version

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}("{self}")'

    def _eq(self, t1: list[str], t2: list[str]) -> bool:
        for v1, v2 in zip_longest(t1, t2, fillvalue=[]):
            for c1, c2 in zip_longest(v1, v2, fillvalue=self.fillvalue):
                if c1 != c2:
                    return False
        return True

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, VersionOrder):
            return False
        return self._eq(self.version, other.version) and self._eq(
            self.local, other.local
        )

    def startswith(self, other: object) -> bool:
        if not isinstance(other, VersionOrder):
            return False
        # Tests if the version lists match up to the last element in "other".
        if other.local:
            if not self._eq(self.version, other.version):
                return False
            t1 = self.local
            t2 = other.local
        else:
            t1 = self.version
            t2 = other.version
        nt = len(t2) - 1
        if not self._eq(t1[:nt], t2[:nt]):
            return False
        v1 = [] if len(t1) <= nt else t1[nt]
        v2 = t2[nt]
        nt = len(v2) - 1
        if not self._eq([v1[:nt]], [v2[:nt]]):
            return False
        c1 = self.fillvalue if len(v1) <= nt else v1[nt]
        c2 = v2[nt]
        if isinstance(c2, str):
            return isinstance(c1, str) and c1.startswith(c2)
        return c1 == c2

    def __ne__(self, other: object) -> bool:
        return not (self == other)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, VersionOrder):
            return False
        for t1, t2 in zip([self.version, self.local], [other.version, other.local]):
            for v1, v2 in zip_longest(t1, t2, fillvalue=[]):
                for c1, c2 in zip_longest(v1, v2, fillvalue=self.fillvalue):
                    if c1 == c2:
                        continue
                    elif isinstance(c1, str):
                        if not isinstance(c2, str):
                            # str < int
                            return True
                    elif isinstance(c2, str):
                        # not (int < str)
                        return False
                    # c1 and c2 have the same type
                    return c1 < c2
        # self == other
        return False

    def __gt__(self, other: object) -> bool:
        return other < self

    def __le__(self, other: object) -> bool:
        return not (other < self)

    def __ge__(self, other: object) -> bool:
        return not (self < other)


# each token slurps up leading whitespace, which we strip out.
VSPEC_TOKENS = (
    r"\s*\^[^$]*[$]|"  # regexes
    r"\s*[()|,]|"  # parentheses, logical and, logical or
    r"[^()|,]+"
)  # everything else


def treeify(spec_str):
    """
    Examples:
        >>> treeify("1.2.3")
        '1.2.3'
        >>> treeify("1.2.3,>4.5.6")
        (',', '1.2.3', '>4.5.6')
        >>> treeify("1.2.3,4.5.6|<=7.8.9")
        ('|', (',', '1.2.3', '4.5.6'), '<=7.8.9')
        >>> treeify("(1.2.3|4.5.6),<=7.8.9")
        (',', ('|', '1.2.3', '4.5.6'), '<=7.8.9')
        >>> treeify("((1.5|((1.6|1.7), 1.8), 1.9 |2.0))|2.1")
        ('|', '1.5', (',', ('|', '1.6', '1.7'), '1.8', '1.9'), '2.0', '2.1')
        >>> treeify("1.5|(1.6|1.7),1.8,1.9|2.0|2.1")
        ('|', '1.5', (',', ('|', '1.6', '1.7'), '1.8', '1.9'), '2.0', '2.1')
    """
    # Converts a VersionSpec expression string into a tuple-based
    # expression tree.
    assert isinstance(spec_str, str)
    tokens = re.findall(VSPEC_TOKENS, f"({spec_str})")
    output = []
    stack = []

    def apply_ops(cstop):
        # cstop: operators with lower precedence
        while stack and stack[-1] not in cstop:
            if len(output) < 2:
                raise InvalidVersionSpec(spec_str, "cannot join single expression")
            c = stack.pop()
            r = output.pop()
            # Fuse expressions with the same operator; e.g.,
            #   ('|', ('|', a, b), ('|', c, d))becomes
            #   ('|', a, b, c d)
            # We're playing a bit of a trick here. Instead of checking
            # if the left or right entries are tuples, we're counting
            # on the fact that if we _do_ see a string instead, its
            # first character cannot possibly be equal to the operator.
            r = r[1:] if r[0] == c else (r,)
            left = output.pop()
            left = left[1:] if left[0] == c else (left,)
            output.append((c,) + left + r)

    for item in tokens:
        item = item.strip()
        if item == "|":
            apply_ops("(")
            stack.append("|")
        elif item == ",":
            apply_ops("|(")
            stack.append(",")
        elif item == "(":
            stack.append("(")
        elif item == ")":
            apply_ops("(")
            if not stack or stack[-1] != "(":
                raise InvalidVersionSpec(spec_str, "expression must start with '('")
            stack.pop()
        else:
            output.append(item)
    if stack:
        raise InvalidVersionSpec(
            spec_str, f"unable to convert to expression tree: {stack}"
        )
    if not output:
        raise InvalidVersionSpec(spec_str, "unable to determine version from spec")
    return output[0]


def untreeify(spec, _inand=False, depth=0):
    """
    Examples:
        >>> untreeify('1.2.3')
        '1.2.3'
        >>> untreeify((',', '1.2.3', '>4.5.6'))
        '1.2.3,>4.5.6'
        >>> untreeify(('|', (',', '1.2.3', '4.5.6'), '<=7.8.9'))
        '(1.2.3,4.5.6)|<=7.8.9'
        >>> untreeify((',', ('|', '1.2.3', '4.5.6'), '<=7.8.9'))
        '(1.2.3|4.5.6),<=7.8.9'
        >>> untreeify(('|', '1.5', (',', ('|', '1.6', '1.7'), '1.8', '1.9'), '2.0', '2.1'))
        '1.5|((1.6|1.7),1.8,1.9)|2.0|2.1'
    """
    if isinstance(spec, tuple):
        if spec[0] == "|":
            res = "|".join(map(lambda x: untreeify(x, depth=depth + 1), spec[1:]))
            if _inand or depth > 0:
                res = f"({res})"
        else:
            res = ",".join(
                map(lambda x: untreeify(x, _inand=True, depth=depth + 1), spec[1:])
            )
            if depth > 0:
                res = f"({res})"
        return res
    return spec


def compatible_release_operator(x, y):
    return op.__ge__(x, y) and x.startswith(
        VersionOrder(".".join(str(y).split(".")[:-1]))
    )


# This RE matches the operators '==', '!=', '<=', '>=', '<', '>'
# followed by a version string. It rejects expressions like
# '<= 1.2' (space after operator), '<>1.2' (unknown operator),
# and '<=!1.2' (nonsensical operator).
version_relation_re = re.compile(r"^(=|==|!=|<=|>=|<|>|~=)(?![=<>!~])(\S+)$")
regex_split_re = re.compile(r".*[()|,^$]")
OPERATOR_MAP = {
    "==": op.__eq__,
    "!=": op.__ne__,
    "<=": op.__le__,
    ">=": op.__ge__,
    "<": op.__lt__,
    ">": op.__gt__,
    "=": lambda x, y: x.startswith(y),
    "!=startswith": lambda x, y: not x.startswith(y),
    "~=": compatible_release_operator,
}
OPERATOR_START = frozenset(("=", "<", ">", "!", "~"))


class BaseSpec:
    def __init__(self, spec_str, matcher, is_exact):
        self.spec_str = spec_str
        self._is_exact = is_exact
        self.match = matcher

    @property
    def spec(self):
        return self.spec_str

    def is_exact(self):
        return self._is_exact

    def __eq__(self, other):
        try:
            other_spec = other.spec
        except AttributeError:
            other_spec = self.__class__(other).spec
        return self.spec == other_spec

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.spec)

    def __str__(self):
        return self.spec

    def __repr__(self):
        return f"{self.__class__.__name__}('{self.spec}')"

    @property
    def raw_value(self):
        return self.spec

    @property
    def exact_value(self):
        return self.is_exact() and self.spec or None

    def merge(self, other):
        raise NotImplementedError()

    def regex_match(self, spec_str):
        return bool(self.regex.match(spec_str))

    def operator_match(self, spec_str):
        return self.operator_func(VersionOrder(str(spec_str)), self.matcher_vo)

    def any_match(self, spec_str):
        return any(s.match(spec_str) for s in self.tup)

    def all_match(self, spec_str):
        return all(s.match(spec_str) for s in self.tup)

    def exact_match(self, spec_str):
        return self.spec == spec_str

    def always_true_match(self, spec_str):
        return True


class VersionSpec(BaseSpec, metaclass=SingleStrArgCachingType):
    _cache_ = {}

    def __init__(self, vspec):
        vspec_str, matcher, is_exact = self.get_matcher(vspec)
        super().__init__(vspec_str, matcher, is_exact)

    def get_matcher(self, vspec):
        if isinstance(vspec, str) and regex_split_re.match(vspec):
            vspec = treeify(vspec)

        if isinstance(vspec, tuple):
            vspec_tree = vspec
            _matcher = self.any_match if vspec_tree[0] == "|" else self.all_match
            tup = tuple(VersionSpec(s) for s in vspec_tree[1:])
            vspec_str = untreeify((vspec_tree[0],) + tuple(t.spec for t in tup))
            self.tup = tup
            matcher = _matcher
            is_exact = False
            return vspec_str, matcher, is_exact

        vspec_str = str(vspec).strip()
        if vspec_str[0] == "^" or vspec_str[-1] == "$":
            if vspec_str[0] != "^" or vspec_str[-1] != "$":
                raise InvalidVersionSpec(
                    vspec_str, "regex specs must start with '^' and end with '$'"
                )
            self.regex = re.compile(vspec_str)
            matcher = self.regex_match
            is_exact = False
        elif vspec_str[0] in OPERATOR_START:
            m = version_relation_re.match(vspec_str)
            if m is None:
                raise InvalidVersionSpec(vspec_str, "invalid operator")
            operator_str, vo_str = m.groups()
            if vo_str[-2:] == ".*":
                if operator_str in ("=", ">="):
                    vo_str = vo_str[:-2]
                elif operator_str == "!=":
                    vo_str = vo_str[:-2]
                    operator_str = "!=startswith"
                elif operator_str == "~=":
                    raise InvalidVersionSpec(vspec_str, "invalid operator with '.*'")
                else:
                    log.warning(
                        "Using .* with relational operator is superfluous and deprecated "
                        "and will be removed in a future version of conda. Your spec was "
                        f"{vo_str}, but conda is ignoring the .* and treating it as {vo_str[:-2]}"
                    )
                    vo_str = vo_str[:-2]
            try:
                self.operator_func = OPERATOR_MAP[operator_str]
            except KeyError:
                raise InvalidVersionSpec(vspec_str, f"invalid operator: {operator_str}")
            self.matcher_vo = VersionOrder(vo_str)
            matcher = self.operator_match
            is_exact = operator_str == "=="
        elif vspec_str == "*":
            matcher = self.always_true_match
            is_exact = False
        elif "*" in vspec_str.rstrip("*"):
            rx = vspec_str.replace(".", r"\.").replace("+", r"\+").replace("*", r".*")
            rx = rf"^(?:{rx})$"

            self.regex = re.compile(rx)
            matcher = self.regex_match
            is_exact = False
        elif vspec_str[-1] == "*":
            if vspec_str[-2:] != ".*":
                vspec_str = vspec_str[:-1] + ".*"

            # if vspec_str[-1] in OPERATOR_START:
            #     m = version_relation_re.match(vspec_str)
            #     if m is None:
            #         raise InvalidVersionSpecError(vspec_str)
            #     operator_str, vo_str = m.groups()
            #
            #
            # else:
            #     pass

            vo_str = vspec_str.rstrip("*").rstrip(".")
            self.operator_func = VersionOrder.startswith
            self.matcher_vo = VersionOrder(vo_str)
            matcher = self.operator_match
            is_exact = False
        elif "@" not in vspec_str:
            self.operator_func = OPERATOR_MAP["=="]
            self.matcher_vo = VersionOrder(vspec_str)
            matcher = self.operator_match
            is_exact = True
        else:
            matcher = self.exact_match
            is_exact = True
        return vspec_str, matcher, is_exact

    def merge(self, other):
        assert isinstance(other, self.__class__)
        return self.__class__(",".join(sorted((self.raw_value, other.raw_value))))

    def union(self, other):
        assert isinstance(other, self.__class__)
        options = {self.raw_value, other.raw_value}
        # important: we only return a string here because the parens get gobbled otherwise
        #    this info is for visual display only, not for feeding into actual matches
        return "|".join(sorted(options))


# TODO: someday switch out these class names for consistency
VersionMatch = VersionSpec


class BuildNumberMatch(BaseSpec, metaclass=SingleStrArgCachingType):
    _cache_ = {}

    def __init__(self, vspec):
        vspec_str, matcher, is_exact = self.get_matcher(vspec)
        super().__init__(vspec_str, matcher, is_exact)

    def get_matcher(self, vspec):
        try:
            vspec = int(vspec)
        except ValueError:
            pass
        else:
            matcher = self.exact_match
            is_exact = True
            return vspec, matcher, is_exact

        vspec_str = str(vspec).strip()
        if vspec_str == "*":
            matcher = self.always_true_match
            is_exact = False
        elif vspec_str.startswith(("=", "<", ">", "!")):
            m = version_relation_re.match(vspec_str)
            if m is None:
                raise InvalidVersionSpec(vspec_str, "invalid operator")
            operator_str, vo_str = m.groups()
            try:
                self.operator_func = OPERATOR_MAP[operator_str]
            except KeyError:
                raise InvalidVersionSpec(vspec_str, f"invalid operator: {operator_str}")
            self.matcher_vo = VersionOrder(vo_str)
            matcher = self.operator_match

            is_exact = operator_str == "=="
        elif vspec_str[0] == "^" or vspec_str[-1] == "$":
            if vspec_str[0] != "^" or vspec_str[-1] != "$":
                raise InvalidVersionSpec(
                    vspec_str, "regex specs must start with '^' and end with '$'"
                )
            self.regex = re.compile(vspec_str)

            matcher = self.regex_match
            is_exact = False
        # if hasattr(spec, 'match'):
        #     self.spec = _spec
        #     self.match = spec.match
        else:
            matcher = self.exact_match
            is_exact = True
        return vspec_str, matcher, is_exact

    def merge(self, other):
        if self.raw_value != other.raw_value:
            raise ValueError(
                f"Incompatible component merge:\n  - {self.raw_value!r}\n  - {other.raw_value!r}"
            )
        return self.raw_value

    def union(self, other):
        options = {self.raw_value, other.raw_value}
        return "|".join(options)

    @property
    def exact_value(self) -> int | None:
        try:
            return int(self.raw_value)
        except ValueError:
            return None

    def __str__(self):
        return str(self.spec)

    def __repr__(self):
        return str(self.spec)
