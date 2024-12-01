/*
 * Copyright (c) 2008, Novell Inc.
 *
 * This program is licensed under the BSD license, read LICENSE.BSD
 * for further information
 */

/*
 * solverdebug.h
 *
 */

#ifndef LIBSOLV_SOLVERDEBUG_H
#define LIBSOLV_SOLVERDEBUG_H

#include "pooltypes.h"
#include "pool.h"
#include "solver.h"

#ifdef __cplusplus
extern "C" {
#endif

extern void solver_printruleelement(Solver *solv, int type, Rule *r, Id v);
extern void solver_printrule(Solver *solv, int type, Rule *r);
extern void solver_printruleclass(Solver *solv, int type, Rule *r);
extern void solver_printproblem(Solver *solv, Id v);
extern void solver_printwatches(Solver *solv, int type);
extern void solver_printdecisionq(Solver *solv, int type);
extern void solver_printdecisions(Solver *solv);
extern void solver_printproblemruleinfo(Solver *solv, Id rule);
extern void solver_printprobleminfo(Solver *solv, Id problem);
extern void solver_printcompleteprobleminfo(Solver *solv, Id problem);
extern void solver_printsolution(Solver *solv, Id problem, Id solution);
extern void solver_printallsolutions(Solver *solv);

extern void transaction_print(Transaction *trans);

/* weird suse stuff */
extern void solver_printtrivial(Solver *solv);

#ifdef __cplusplus
}
#endif

#endif /* LIBSOLV_SOLVERDEBUG_H */

