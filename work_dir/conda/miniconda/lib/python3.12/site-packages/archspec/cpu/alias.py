# Copyright 2019-2020 Lawrence Livermore National Security, LLC and other
# Archspec Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)
"""Aliases for microarchitecture features."""
from .schema import TARGETS_JSON, LazyDictionary

_FEATURE_ALIAS_PREDICATE = {}


class FeatureAliasTest:
    """A test that must be passed for a feature alias to succeed.

    Args:
        rules (dict): dictionary of rules to be met. Each key must be a
            valid alias predicate
    """

    # pylint: disable=too-few-public-methods
    def __init__(self, rules):
        self.rules = rules
        self.predicates = []
        for name, args in rules.items():
            self.predicates.append(_FEATURE_ALIAS_PREDICATE[name](args))

    def __call__(self, microarchitecture):
        return all(feature_test(microarchitecture) for feature_test in self.predicates)


def _feature_aliases():
    """Returns the dictionary of all defined feature aliases."""
    json_data = TARGETS_JSON["feature_aliases"]
    aliases = {}
    for alias, rules in json_data.items():
        aliases[alias] = FeatureAliasTest(rules)
    return aliases


FEATURE_ALIASES = LazyDictionary(_feature_aliases)


def alias_predicate(func):
    """Decorator to register a predicate that can be used to evaluate
    feature aliases.
    """
    name = func.__name__

    # Check we didn't register anything else with the same name
    if name in _FEATURE_ALIAS_PREDICATE:
        msg = f'the alias predicate "{name}" already exists'
        raise KeyError(msg)

    _FEATURE_ALIAS_PREDICATE[name] = func

    return func


@alias_predicate
def reason(_):
    """This predicate returns always True and it's there to allow writing
    a documentation string in the JSON file to explain why an alias is needed.
    """
    return lambda x: True


@alias_predicate
def any_of(list_of_features):
    """Returns a predicate that is True if any of the feature in the
    list is in the microarchitecture being tested, False otherwise.
    """

    def _impl(microarchitecture):
        return any(x in microarchitecture for x in list_of_features)

    return _impl


@alias_predicate
def families(list_of_families):
    """Returns a predicate that is True if the architecture family of
    the microarchitecture being tested is in the list, False otherwise.
    """

    def _impl(microarchitecture):
        return str(microarchitecture.family) in list_of_families

    return _impl
