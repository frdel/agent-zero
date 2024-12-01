# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""
The basic idea to nest logical expressions is instead of trying to denest
things via distribution, we add new variables. So if we have some logical
expression expr, we replace it with x and add expr <-> x to the clauses,
where x is a new variable, and expr <-> x is recursively evaluated in the
same way, so that the final clauses are ORs of atoms.

To use this, create a new Clauses object with the max var, for instance, if you
already have [[1, 2, -3]], you would use C = Clause(3).  All functions return
a new literal, which represents that function, or True or False if the expression
can be resolved fully. They may also add new clauses to C.clauses, which
will then be delivered to the SAT solver.

All functions take atoms as arguments (an atom is an integer, representing a
literal or a negated literal, or boolean constants True or False; that is,
it is the callers' responsibility to do the conversion of expressions
recursively. This is done because we do not have data structures
representing the various logical classes, only atoms.

The polarity argument can be set to True or False if you know that the literal
being used will only be used in the positive or the negative, respectively
(e.g., you will only use x, not -x).  This will generate fewer clauses. It
is probably best if you do not take advantage of this directly, but rather
through the Require and Prevent functions.

"""

from itertools import chain

from ._logic import FALSE, TRUE
from ._logic import Clauses as _Clauses

# TODO: We may want to turn the user-facing {TRUE,FALSE} values into an Enum and
#       hide the _logic.{TRUE,FALSE} values as an implementation detail.
#       We then have to handle the {TRUE,FALSE} -> _logic.{TRUE,FALSE} conversion
#       in Clauses._convert and the inverse _logic.{TRUE,FALSE} -> {TRUE,FALSE}
#       conversion in Clauses._eval.
TRUE = TRUE
FALSE = FALSE

PycoSatSolver = "pycosat"
PyCryptoSatSolver = "pycryptosat"
PySatSolver = "pysat"


class Clauses:
    def __init__(self, m=0, sat_solver=PycoSatSolver):
        self.names = {}
        self.indices = {}
        self._clauses = _Clauses(m=m, sat_solver_str=sat_solver)

    @property
    def m(self):
        return self._clauses.m

    @property
    def unsat(self):
        return self._clauses.unsat

    def get_clause_count(self):
        return self._clauses.get_clause_count()

    def as_list(self):
        return self._clauses.as_list()

    def _check_variable(self, variable):
        if 0 < abs(variable) <= self.m:
            return variable
        raise ValueError(f"SAT variable out of bounds: {variable} (max_var: {self.m})")

    def _check_literal(self, literal):
        if literal in {TRUE, FALSE}:
            return literal
        return self._check_variable(literal)

    def add_clause(self, clause):
        self._clauses.add_clause(map(self._check_variable, self._convert(clause)))

    def add_clauses(self, clauses):
        for clause in clauses:
            self.add_clause(clause)

    def name_var(self, m, name):
        self._check_literal(m)
        nname = "!" + name
        self.names[name] = m
        self.names[nname] = -m
        if m not in {TRUE, FALSE} and m not in self.indices:
            self.indices[m] = name
            self.indices[-m] = nname
        return m

    def new_var(self, name=None):
        m = self._clauses.new_var()
        if name:
            self.name_var(m, name)
        return m

    def from_name(self, name):
        return self.names.get(name)

    def from_index(self, m):
        return self.indices.get(m)

    def _assign(self, vals, name=None):
        x = self._clauses.assign(vals)
        if not name:
            return x
        if vals in {TRUE, FALSE}:
            x = self._clauses.new_var()
            self._clauses.add_clause((x,) if vals else (-x,))
        return self.name_var(x, name)

    def _convert(self, x):
        if isinstance(x, (tuple, list)):
            return type(x)(map(self._convert, x))
        if isinstance(x, int):
            return self._check_literal(x)
        name = x
        try:
            return self.names[name]
        except KeyError:
            raise ValueError(f"Unregistered SAT variable name: {name}")

    def _eval(self, func, args, no_literal_args, polarity, name):
        args = self._convert(args)
        if name is False:
            self._clauses.Eval(func, args + no_literal_args, polarity)
            return None
        vals = func(*(args + no_literal_args), polarity=polarity)
        return self._assign(vals, name)

    def Prevent(self, what, *args):
        return what.__get__(self, Clauses)(*args, polarity=False, name=False)

    def Require(self, what, *args):
        return what.__get__(self, Clauses)(*args, polarity=True, name=False)

    def Not(self, x, polarity=None, name=None):
        return self._eval(self._clauses.Not, (x,), (), polarity, name)

    def And(self, f, g, polarity=None, name=None):
        return self._eval(self._clauses.And, (f, g), (), polarity, name)

    def Or(self, f, g, polarity=None, name=None):
        return self._eval(self._clauses.Or, (f, g), (), polarity, name)

    def Xor(self, f, g, polarity=None, name=None):
        return self._eval(self._clauses.Xor, (f, g), (), polarity, name)

    def ITE(self, c, t, f, polarity=None, name=None):
        """If c Then t Else f.

        In this function, if any of c, t, or f are True and False the resulting
        expression is resolved.
        """
        return self._eval(self._clauses.ITE, (c, t, f), (), polarity, name)

    def All(self, iter, polarity=None, name=None):
        return self._eval(self._clauses.All, (iter,), (), polarity, name)

    def Any(self, vals, polarity=None, name=None):
        return self._eval(self._clauses.Any, (list(vals),), (), polarity, name)

    def AtMostOne_NSQ(self, vals, polarity=None, name=None):
        return self._eval(
            self._clauses.AtMostOne_NSQ, (list(vals),), (), polarity, name
        )

    def AtMostOne_BDD(self, vals, polarity=None, name=None):
        return self._eval(
            self._clauses.AtMostOne_BDD, (list(vals),), (), polarity, name
        )

    def AtMostOne(self, vals, polarity=None, name=None):
        vals = list(vals)
        nv = len(vals)
        if nv < 5 - (polarity is not True):
            what = self.AtMostOne_NSQ
        else:
            what = self.AtMostOne_BDD
        return self._eval(what, (vals,), (), polarity, name)

    def ExactlyOne_NSQ(self, vals, polarity=None, name=None):
        return self._eval(
            self._clauses.ExactlyOne_NSQ, (list(vals),), (), polarity, name
        )

    def ExactlyOne_BDD(self, vals, polarity=None, name=None):
        return self._eval(
            self._clauses.ExactlyOne_BDD, (list(vals),), (), polarity, name
        )

    def ExactlyOne(self, vals, polarity=None, name=None):
        vals = list(vals)
        nv = len(vals)
        if nv < 2:
            what = self.ExactlyOne_NSQ
        else:
            what = self.ExactlyOne_BDD
        return self._eval(what, (vals,), (), polarity, name)

    def LinearBound(self, equation, lo, hi, preprocess=True, polarity=None, name=None):
        if not isinstance(equation, dict):
            # in case of duplicate literal -> coefficient mappings, always take the last one
            equation = {named_lit: coeff for coeff, named_lit in equation}
        named_literals = list(equation.keys())
        coefficients = list(equation.values())
        return self._eval(
            self._clauses.LinearBound,
            (named_literals,),
            (coefficients, lo, hi, preprocess),
            polarity,
            name,
        )

    def sat(self, additional=None, includeIf=False, names=False, limit=0):
        """
        Calculate a SAT solution for the current clause set.

        Returned is the list of those solutions.  When the clauses are
        unsatisfiable, an empty list is returned.

        """
        if self.unsat:
            return None
        if not self.m:
            return set() if names else []
        if additional:
            additional = (tuple(self.names.get(c, c) for c in cc) for cc in additional)
        solution = self._clauses.sat(
            additional=additional, includeIf=includeIf, limit=limit
        )
        if solution is None:
            return None
        if names:
            return {
                nm
                for nm in (self.indices.get(s) for s in solution)
                if nm and nm[0] != "!"
            }
        return solution

    def itersolve(self, constraints=None, m=None):
        exclude = []
        if m is None:
            m = self.m
        while True:
            # We don't use pycosat.itersolve because it is more
            # important to limit the number of terms added to the
            # exclusion list, in our experience. Once we update
            # pycosat to do this, this can use it.
            sol = self.sat(chain(constraints, exclude))
            if sol is None:
                return
            yield sol
            exclude.append([-k for k in sol if -m <= k <= m])

    def minimize(self, objective, bestsol=None, trymax=False):
        if not isinstance(objective, dict):
            # in case of duplicate literal -> coefficient mappings, always take the last one
            objective = {named_lit: coeff for coeff, named_lit in objective}
        literals = self._convert(list(objective.keys()))
        coeffs = list(objective.values())

        return self._clauses.minimize(literals, coeffs, bestsol=bestsol, trymax=trymax)


def minimal_unsatisfiable_subset(clauses, sat, explicit_specs):
    """
    Given a set of clauses, find a minimal unsatisfiable subset (an
    unsatisfiable core)

    A set is a minimal unsatisfiable subset if no proper subset is
    unsatisfiable.  A set of clauses may have many minimal unsatisfiable
    subsets of different sizes.

    sat should be a function that takes a tuple of clauses and returns True if
    the clauses are satisfiable and False if they are not.  The algorithm will
    work with any order-reversing function (reversing the order of subset and
    the order False < True), that is, any function where (A <= B) iff (sat(B)
    <= sat(A)), where A <= B means A is a subset of B and False < True).

    """
    working_set = set()
    found_conflicts = set()

    if sat(explicit_specs, True) is None:
        found_conflicts = set(explicit_specs)
    else:
        # we succeeded, so we'll add the spec to our future constraints
        working_set = set(explicit_specs)

    for spec in set(clauses) - working_set:
        if (
            sat(
                working_set
                | {
                    spec,
                },
                True,
            )
            is None
        ):
            found_conflicts.add(spec)
        else:
            # we succeeded, so we'll add the spec to our future constraints
            working_set.add(spec)

    return found_conflicts
