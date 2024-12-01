# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
import sys
from array import array
from itertools import combinations
from logging import DEBUG, getLogger

from .constants import TRACE

log = getLogger(__name__)


TRUE = sys.maxsize
FALSE = -TRUE


class _ClauseList:
    """Storage for the CNF clauses, represented as a list of tuples of ints."""

    def __init__(self):
        self._clause_list = []
        # Methods append and extend are directly bound for performance reasons,
        # to avoid call overhead and lookups.
        self.append = self._clause_list.append
        self.extend = self._clause_list.extend

    def get_clause_count(self):
        """Return number of stored clauses."""
        return len(self._clause_list)

    def save_state(self):
        """
        Get state information to be able to revert temporary additions of
        supplementary clauses.  _ClauseList: state is simply the number of clauses.
        """
        return len(self._clause_list)

    def restore_state(self, saved_state):
        """
        Restore state saved via `save_state`.
        Removes clauses that were added after the state has been saved.
        """
        len_clauses = saved_state
        self._clause_list[len_clauses:] = []

    def as_list(self):
        """Return clauses as a list of tuples of ints."""
        return self._clause_list

    def as_array(self):
        """Return clauses as a flat int array, each clause being terminated by 0."""
        clause_array = array("i")
        for c in self._clause_list:
            clause_array.extend(c)
            clause_array.append(0)
        return clause_array


class _ClauseArray:
    """
    Storage for the CNF clauses, represented as a flat int array.
    Each clause is terminated by int(0).
    """

    def __init__(self):
        self._clause_array = array("i")
        # Methods append and extend are directly bound for performance reasons,
        # to avoid call overhead and lookups.
        self._array_append = self._clause_array.append
        self._array_extend = self._clause_array.extend

    def extend(self, clauses):
        for clause in clauses:
            self.append(clause)

    def append(self, clause):
        self._array_extend(clause)
        self._array_append(0)

    def get_clause_count(self):
        """
        Return number of stored clauses.
        This is an O(n) operation since we don't store the number of clauses
        explicitly due to performance reasons (Python interpreter overhead in
        self.append).
        """
        return self._clause_array.count(0)

    def save_state(self):
        """
        Get state information to be able to revert temporary additions of
        supplementary clauses. _ClauseArray: state is the length of the int
        array, NOT number of clauses.
        """
        return len(self._clause_array)

    def restore_state(self, saved_state):
        """
        Restore state saved via `save_state`.
        Removes clauses that were added after the state has been saved.
        """
        len_clause_array = saved_state
        self._clause_array[len_clause_array:] = array("i")

    def as_list(self):
        """Return clauses as a list of tuples of ints."""
        clause = []
        for v in self._clause_array:
            if v == 0:
                yield tuple(clause)
                clause.clear()
            else:
                clause.append(v)

    def as_array(self):
        """Return clauses as a flat int array, each clause being terminated by 0."""
        return self._clause_array


class _SatSolver:
    """Simple wrapper to call a SAT solver given a _ClauseList/_ClauseArray instance."""

    def __init__(self, **run_kwargs):
        self._run_kwargs = run_kwargs or {}
        self._clauses = _ClauseList()
        # Bind some methods of _clauses to reduce lookups and call overhead.
        self.add_clause = self._clauses.append
        self.add_clauses = self._clauses.extend

    def get_clause_count(self):
        return self._clauses.get_clause_count()

    def as_list(self):
        return self._clauses.as_list()

    def save_state(self):
        return self._clauses.save_state()

    def restore_state(self, saved_state):
        return self._clauses.restore_state(saved_state)

    def run(self, m, **kwargs):
        run_kwargs = self._run_kwargs.copy()
        run_kwargs.update(kwargs)
        solver = self.setup(m, **run_kwargs)
        sat_solution = self.invoke(solver)
        solution = self.process_solution(sat_solution)
        return solution

    def setup(self, m, **kwargs):
        """Create a solver instance, add the clauses to it, and return it."""
        raise NotImplementedError()

    def invoke(self, solver):
        """Start the actual SAT solving and return the calculated solution."""
        raise NotImplementedError()

    def process_solution(self, sat_solution):
        """
        Process the solution returned by self.invoke.
        Returns a list of satisfied variables or None if no solution is found.
        """
        raise NotImplementedError()


class _PycoSatSolver(_SatSolver):
    def setup(self, m, limit=0, **kwargs):
        from pycosat import itersolve

        # NOTE: The iterative solving isn't actually used here, we just call
        #       itersolve to separate setup from the actual run.
        return itersolve(self._clauses.as_list(), vars=m, prop_limit=limit)
        # If we add support for passing the clauses as an integer stream to the
        # solvers, we could also use self._clauses.as_array like this:
        # return itersolve(self._clauses.as_array(), vars=m, prop_limit=limit)

    def invoke(self, iter_sol):
        try:
            sat_solution = next(iter_sol)
        except StopIteration:
            sat_solution = "UNSAT"
        del iter_sol
        return sat_solution

    def process_solution(self, sat_solution):
        if sat_solution in ("UNSAT", "UNKNOWN"):
            return None
        return sat_solution


class _PyCryptoSatSolver(_SatSolver):
    def setup(self, m, threads=1, **kwargs):
        from pycryptosat import Solver

        solver = Solver(threads=threads)
        solver.add_clauses(self._clauses.as_list())
        return solver

    def invoke(self, solver):
        sat, sat_solution = solver.solve()
        if not sat:
            sat_solution = None
        return sat_solution

    def process_solution(self, solution):
        if not solution:
            return None
        # The first element of the solution is always None.
        solution = [i for i, b in enumerate(solution) if b]
        return solution


class _PySatSolver(_SatSolver):
    def setup(self, m, **kwargs):
        from pysat.solvers import Glucose4

        solver = Glucose4()
        solver.append_formula(self._clauses.as_list())
        return solver

    def invoke(self, solver):
        if not solver.solve():
            sat_solution = None
        else:
            sat_solution = solver.get_model()
        solver.delete()
        return sat_solution

    def process_solution(self, sat_solution):
        if sat_solution is None:
            solution = None
        else:
            solution = sat_solution
        return solution


_sat_solver_str_to_cls = {
    "pycosat": _PycoSatSolver,
    "pycryptosat": _PyCryptoSatSolver,
    "pysat": _PySatSolver,
}

_sat_solver_cls_to_str = {cls: string for string, cls in _sat_solver_str_to_cls.items()}


# Code that uses special cases (generates no clauses) is in ADTs/FEnv.h in
# minisatp. Code that generates clauses is in Hardware_clausify.cc (and are
# also described in the paper, "Translating Pseudo-Boolean Constraints into
# SAT," Eén and Sörensson).
class Clauses:
    def __init__(self, m=0, sat_solver_str=_sat_solver_cls_to_str[_PycoSatSolver]):
        self.unsat = False
        self.m = m

        try:
            sat_solver_cls = _sat_solver_str_to_cls[sat_solver_str]
        except KeyError:
            raise NotImplementedError(f"Unknown SAT solver: {sat_solver_str}")
        self._sat_solver = sat_solver_cls()

        # Bind some methods of _sat_solver to reduce lookups and call overhead.
        self.add_clause = self._sat_solver.add_clause
        self.add_clauses = self._sat_solver.add_clauses

    def get_clause_count(self):
        return self._sat_solver.get_clause_count()

    def as_list(self):
        return self._sat_solver.as_list()

    def new_var(self):
        m = self.m + 1
        self.m = m
        return m

    def assign(self, vals):
        if isinstance(vals, tuple):
            x = self.new_var()
            self.add_clauses((-x,) + y for y in vals[0])
            self.add_clauses((x,) + y for y in vals[1])
            return x
        return vals

    def Combine(self, args, polarity):
        if any(v == FALSE for v in args):
            return FALSE
        args = [v for v in args if v != TRUE]
        nv = len(args)
        if nv == 0:
            return TRUE
        if nv == 1:
            return args[0]
        if all(isinstance(v, tuple) for v in args):
            return (sum((v[0] for v in args), []), sum((v[1] for v in args), []))
        else:
            return self.All(map(self.assign, args), polarity)

    def Eval(self, func, args, polarity):
        saved_state = self._sat_solver.save_state()
        vals = func(*args, polarity=polarity)
        # eval without assignment:
        if isinstance(vals, tuple):
            self.add_clauses(vals[0])
            self.add_clauses(vals[1])
        elif vals not in {TRUE, FALSE}:
            self.add_clause((vals if polarity else -vals,))
        else:
            self._sat_solver.restore_state(saved_state)
            self.unsat = self.unsat or (vals == TRUE) != polarity

    def Prevent(self, func, *args):
        self.Eval(func, args, polarity=False)

    def Require(self, func, *args):
        self.Eval(func, args, polarity=True)

    def Not(self, x, polarity=None, add_new_clauses=False):
        return -x

    def And(self, f, g, polarity, add_new_clauses=False):
        if f == FALSE or g == FALSE:
            return FALSE
        if f == TRUE:
            return g
        if g == TRUE:
            return f
        if f == g:
            return f
        if f == -g:
            return FALSE
        if g < f:
            f, g = g, f
        if add_new_clauses:
            # This is equivalent to running self.assign(pval, nval) on
            # the (pval, nval) tuple we return below. Duplicating the code here
            # is an important performance tweak to avoid the costly generator
            # expressions and tuple additions in self.assign.
            x = self.new_var()
            if polarity in (True, None):
                self.add_clauses(
                    [
                        (
                            -x,
                            f,
                        ),
                        (
                            -x,
                            g,
                        ),
                    ]
                )
            if polarity in (False, None):
                self.add_clauses([(x, -f, -g)])
            return x
        pval = [(f,), (g,)] if polarity in (True, None) else []
        nval = [(-f, -g)] if polarity in (False, None) else []
        return pval, nval

    def Or(self, f, g, polarity, add_new_clauses=False):
        if f == TRUE or g == TRUE:
            return TRUE
        if f == FALSE:
            return g
        if g == FALSE:
            return f
        if f == g:
            return f
        if f == -g:
            return TRUE
        if g < f:
            f, g = g, f
        if add_new_clauses:
            x = self.new_var()
            if polarity in (True, None):
                self.add_clauses([(-x, f, g)])
            if polarity in (False, None):
                self.add_clauses(
                    [
                        (
                            x,
                            -f,
                        ),
                        (
                            x,
                            -g,
                        ),
                    ]
                )
            return x
        pval = [(f, g)] if polarity in (True, None) else []
        nval = [(-f,), (-g,)] if polarity in (False, None) else []
        return pval, nval

    def Xor(self, f, g, polarity, add_new_clauses=False):
        if f == FALSE:
            return g
        if f == TRUE:
            return self.Not(g, polarity, add_new_clauses=add_new_clauses)
        if g == FALSE:
            return f
        if g == TRUE:
            return -f
        if f == g:
            return FALSE
        if f == -g:
            return TRUE
        if g < f:
            f, g = g, f
        if add_new_clauses:
            x = self.new_var()
            if polarity in (True, None):
                self.add_clauses([(-x, f, g), (-x, -f, -g)])
            if polarity in (False, None):
                self.add_clauses([(x, -f, g), (x, f, -g)])
            return x
        pval = [(f, g), (-f, -g)] if polarity in (True, None) else []
        nval = [(-f, g), (f, -g)] if polarity in (False, None) else []
        return pval, nval

    def ITE(self, c, t, f, polarity, add_new_clauses=False):
        if c == TRUE:
            return t
        if c == FALSE:
            return f
        if t == TRUE:
            return self.Or(c, f, polarity, add_new_clauses=add_new_clauses)
        if t == FALSE:
            return self.And(-c, f, polarity, add_new_clauses=add_new_clauses)
        if f == FALSE:
            return self.And(c, t, polarity, add_new_clauses=add_new_clauses)
        if f == TRUE:
            return self.Or(t, -c, polarity, add_new_clauses=add_new_clauses)
        if t == c:
            return self.Or(c, f, polarity, add_new_clauses=add_new_clauses)
        if t == -c:
            return self.And(-c, f, polarity, add_new_clauses=add_new_clauses)
        if f == c:
            return self.And(c, t, polarity, add_new_clauses=add_new_clauses)
        if f == -c:
            return self.Or(t, -c, polarity, add_new_clauses=add_new_clauses)
        if t == f:
            return t
        if t == -f:
            return self.Xor(c, f, polarity, add_new_clauses=add_new_clauses)
        if t < f:
            t, f, c = f, t, -c
        # Basically, c ? t : f is equivalent to (c AND t) OR (NOT c AND f)
        # The third clause in each group is redundant but assists the unit
        # propagation in the SAT solver.
        if add_new_clauses:
            x = self.new_var()
            if polarity in (True, None):
                self.add_clauses([(-x, -c, t), (-x, c, f), (-x, t, f)])
            if polarity in (False, None):
                self.add_clauses([(x, -c, -t), (x, c, -f), (x, -t, -f)])
            return x
        pval = [(-c, t), (c, f), (t, f)] if polarity in (True, None) else []
        nval = [(-c, -t), (c, -f), (-t, -f)] if polarity in (False, None) else []
        return pval, nval

    def All(self, iter, polarity=None):
        vals = set()
        for v in iter:
            if v == TRUE:
                continue
            if v == FALSE or -v in vals:
                return FALSE
            vals.add(v)
        nv = len(vals)
        if nv == 0:
            return TRUE
        elif nv == 1:
            return next(v for v in vals)
        pval = [(v,) for v in vals] if polarity in (True, None) else []
        nval = [tuple(-v for v in vals)] if polarity in (False, None) else []
        return pval, nval

    def Any(self, iter, polarity):
        vals = set()
        for v in iter:
            if v == FALSE:
                continue
            elif v == TRUE or -v in vals:
                return TRUE
            vals.add(v)
        nv = len(vals)
        if nv == 0:
            return FALSE
        elif nv == 1:
            return next(v for v in vals)
        pval = [tuple(vals)] if polarity in (True, None) else []
        nval = [(-v,) for v in vals] if polarity in (False, None) else []
        return pval, nval

    def AtMostOne_NSQ(self, vals, polarity):
        combos = []
        for v1, v2 in combinations(map(self.Not, vals), 2):
            combos.append(self.Or(v1, v2, polarity))
        return self.Combine(combos, polarity)

    def AtMostOne_BDD(self, vals, polarity=None):
        lits = list(vals)
        coeffs = [1] * len(lits)
        return self.LinearBound(lits, coeffs, 0, 1, True, polarity)

    def ExactlyOne_NSQ(self, vals, polarity):
        vals = list(vals)
        v1 = self.AtMostOne_NSQ(vals, polarity)
        v2 = self.Any(vals, polarity)
        return self.Combine((v1, v2), polarity)

    def ExactlyOne_BDD(self, vals, polarity):
        lits = list(vals)
        coeffs = [1] * len(lits)
        return self.LinearBound(lits, coeffs, 1, 1, True, polarity)

    def LB_Preprocess(self, lits, coeffs):
        equation = []
        offset = 0
        for coeff, lit in zip(coeffs, lits):
            if lit == TRUE:
                offset += coeff
                continue
            if lit == FALSE or coeff == 0:
                continue
            if coeff < 0:
                offset += coeff
                coeff, lit = -coeff, -lit
            equation.append((coeff, lit))
        coeffs, lits = tuple(zip(*sorted(equation))) or ((), ())
        return lits, coeffs, offset

    def BDD(self, lits, coeffs, nterms, lo, hi, polarity):
        # The equation (coeffs x lits) is sorted in
        # order of increasing coefficients.
        # Then we take advantage of the following recurrence:
        #                l      <= S + cN xN <= u
        #  => IF xN THEN l - cN <= S         <= u - cN
        #           ELSE l      <= S         <= u
        # we use memoization to prune common subexpressions
        total = sum(c for c in coeffs[:nterms])
        target = (nterms - 1, 0, total)
        call_stack = [target]
        ret = {}
        call_stack_append = call_stack.append
        call_stack_pop = call_stack.pop
        ret_get = ret.get
        ITE = self.ITE

        csum = 0
        while call_stack:
            ndx, csum, total = call_stack[-1]
            lower_limit = lo - csum
            upper_limit = hi - csum
            if lower_limit <= 0 and upper_limit >= total:
                ret[call_stack_pop()] = TRUE
                continue
            if lower_limit > total or upper_limit < 0:
                ret[call_stack_pop()] = FALSE
                continue
            LA = lits[ndx]
            LC = coeffs[ndx]
            ndx -= 1
            total -= LC
            hi_key = (ndx, csum if LA < 0 else csum + LC, total)
            thi = ret_get(hi_key)
            if thi is None:
                call_stack_append(hi_key)
                continue
            lo_key = (ndx, csum + LC if LA < 0 else csum, total)
            tlo = ret_get(lo_key)
            if tlo is None:
                call_stack_append(lo_key)
                continue
            # NOTE: The following ITE call is _the_ hotspot of the Python-side
            # computations for the overall minimization run. For performance we
            # avoid calling self.assign here via add_new_clauses=True.
            # If we want to translate parts of the code to a compiled language,
            # self.BDD (+ its downward call stack) is the prime candidate!
            ret[call_stack_pop()] = ITE(
                abs(LA), thi, tlo, polarity, add_new_clauses=True
            )
        return ret[target]

    def LinearBound(self, lits, coeffs, lo, hi, preprocess, polarity):
        if preprocess:
            lits, coeffs, offset = self.LB_Preprocess(lits, coeffs)
            lo -= offset
            hi -= offset
        nterms = len(coeffs)
        if nterms and coeffs[-1] > hi:
            nprune = sum(c > hi for c in coeffs)
            log.log(
                TRACE, "Eliminating %d/%d terms for bound violation", nprune, nterms
            )
            nterms -= nprune
        else:
            nprune = 0
        # Tighten bounds
        total = sum(c for c in coeffs[:nterms])
        if preprocess:
            lo = max([lo, 0])
            hi = min([hi, total])
        if lo > hi:
            return FALSE
        if nterms == 0:
            res = TRUE if lo == 0 else FALSE
        else:
            res = self.BDD(lits, coeffs, nterms, lo, hi, polarity)
        if nprune:
            prune = self.All([-a for a in lits[nterms:]], polarity)
            res = self.Combine((res, prune), polarity)
        return res

    def _run_sat(self, m, limit=0):
        if log.isEnabledFor(DEBUG):
            log.debug("Invoking SAT with clause count: %s", self.get_clause_count())
        solution = self._sat_solver.run(m, limit=limit)
        return solution

    def sat(self, additional=None, includeIf=False, limit=0):
        """
        Calculate a SAT solution for the current clause set.

        Returned is the list of those solutions.  When the clauses are
        unsatisfiable, an empty list is returned.

        """
        if self.unsat:
            return None
        if not self.m:
            return []
        saved_state = self._sat_solver.save_state()
        if additional:

            def preproc(eqs):
                def preproc_(cc):
                    for c in cc:
                        if c == FALSE:
                            continue
                        yield c
                        if c == TRUE:
                            break

                for cc in eqs:
                    cc = tuple(preproc_(cc))
                    if not cc:
                        yield cc
                        break
                    if cc[-1] != TRUE:
                        yield cc

            additional = list(preproc(additional))
            if additional:
                if not additional[-1]:
                    return None
                self.add_clauses(additional)
        solution = self._run_sat(self.m, limit=limit)
        if additional and (solution is None or not includeIf):
            self._sat_solver.restore_state(saved_state)
        return solution

    def minimize(self, lits, coeffs, bestsol=None, trymax=False):
        """
        Minimize the objective function given by (coeff, integer) pairs in
        zip(coeffs, lits).
        The actual minimization is multiobjective: first, we minimize the
        largest active coefficient value, then we minimize the sum.
        """
        if bestsol is None or len(bestsol) < self.m:
            log.debug("Clauses added, recomputing solution")
            bestsol = self.sat()
        if bestsol is None or self.unsat:
            log.debug("Constraints are unsatisfiable")
            return bestsol, sum(abs(c) for c in coeffs) + 1 if coeffs else 1
        if not coeffs:
            log.debug("Empty objective, trivial solution")
            return bestsol, 0

        lits, coeffs, offset = self.LB_Preprocess(lits, coeffs)
        maxval = max(coeffs)

        def peak_val(sol, objective_dict):
            return max(objective_dict.get(s, 0) for s in sol)

        def sum_val(sol, objective_dict):
            return sum(objective_dict.get(s, 0) for s in sol)

        lo = 0
        try0 = 0
        for peak in (True, False) if maxval > 1 else (False,):
            if peak:
                log.log(TRACE, "Beginning peak minimization")
                objval = peak_val
            else:
                log.log(TRACE, "Beginning sum minimization")
                objval = sum_val

            objective_dict = {a: c for c, a in zip(coeffs, lits)}
            bestval = objval(bestsol, objective_dict)

            # If we got lucky and the initial solution is optimal, we still
            # need to generate the constraints at least once
            hi = bestval
            m_orig = self.m
            if log.isEnabledFor(DEBUG):
                # This is only used for the log message below.
                nz = self.get_clause_count()
            saved_state = self._sat_solver.save_state()
            if trymax and not peak:
                try0 = hi - 1

            log.log(TRACE, "Initial range (%d,%d)", lo, hi)
            while True:
                if try0 is None:
                    mid = (lo + hi) // 2
                else:
                    mid = try0
                if peak:
                    prevent = tuple(a for c, a in zip(coeffs, lits) if c > mid)
                    require = tuple(a for c, a in zip(coeffs, lits) if lo <= c <= mid)
                    self.Prevent(self.Any, prevent)
                    if require:
                        self.Require(self.Any, require)
                else:
                    self.Require(self.LinearBound, lits, coeffs, lo, mid, False)

                if log.isEnabledFor(DEBUG):
                    log.log(
                        TRACE,
                        "Bisection attempt: (%d,%d), (%d+%d) clauses",
                        lo,
                        mid,
                        nz,
                        self.get_clause_count() - nz,
                    )
                newsol = self.sat()
                if newsol is None:
                    lo = mid + 1
                    log.log(TRACE, "Bisection failure, new range=(%d,%d)", lo, hi)
                    if lo > hi:
                        # FIXME: This is not supposed to happen!
                        # TODO: Investigate and fix the cause.
                        break
                    # If this was a failure of the first test after peak minimization,
                    # then it means that the peak minimizer is "tight" and we don't need
                    # any further constraints.
                else:
                    done = lo == mid
                    bestsol = newsol
                    bestval = objval(newsol, objective_dict)
                    hi = bestval
                    log.log(TRACE, "Bisection success, new range=(%d,%d)", lo, hi)
                    if done:
                        break
                self.m = m_orig
                # Since we only ever _add_ clauses and only remove then via
                # restore_state, it's fine to test on equality only.
                if self._sat_solver.save_state() != saved_state:
                    self._sat_solver.restore_state(saved_state)
                self.unsat = False
                try0 = None

            log.debug("Final %s objective: %d" % ("peak" if peak else "sum", bestval))
            if bestval == 0:
                break
            elif peak:
                # Now that we've minimized the peak value, we can drop any terms
                # with coefficients larger than this. Furthermore, since we know
                # at least one peak will be active, our lower bound for the sum
                # equals the peak.
                lits = [a for c, a in zip(coeffs, lits) if c <= bestval]
                coeffs = [c for c in coeffs if c <= bestval]
                try0 = sum_val(bestsol, objective_dict)
                lo = bestval
            else:
                log.debug("New peak objective: %d" % peak_val(bestsol, objective_dict))

        return bestsol, bestval
