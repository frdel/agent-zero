/*
 * Copyright (c) 2012, Novell Inc.
 *
 * This program is licensed under the BSD license, read LICENSE.BSD
 * for further information
 */

#include "pool.h"
#include "repo.h"
#include "solver.h"

#define TESTCASE_RESULT_TRANSACTION	(1 << 0)
#define TESTCASE_RESULT_PROBLEMS	(1 << 1)
#define TESTCASE_RESULT_ORPHANED	(1 << 2)
#define TESTCASE_RESULT_RECOMMENDED	(1 << 3)
#define TESTCASE_RESULT_UNNEEDED	(1 << 4)
#define TESTCASE_RESULT_ALTERNATIVES	(1 << 5)
#define TESTCASE_RESULT_RULES		(1 << 6)
#define TESTCASE_RESULT_GENID		(1 << 7)
#define TESTCASE_RESULT_REASON		(1 << 8)
#define TESTCASE_RESULT_CLEANDEPS	(1 << 9)
#define TESTCASE_RESULT_JOBS		(1 << 10)
#define TESTCASE_RESULT_USERINSTALLED	(1 << 11)
#define TESTCASE_RESULT_ORDER		(1 << 12)
#define TESTCASE_RESULT_ORDEREDGES	(1 << 13)
#define TESTCASE_RESULT_PROOF		(1 << 14)

/* reuse solver hack, testsolv use only */
#define TESTCASE_RESULT_REUSE_SOLVER	(1 << 31)

extern Id testcase_str2dep(Pool *pool, const char *s);
extern const char *testcase_dep2str(Pool *pool, Id id);
extern const char *testcase_repoid2str(Pool *pool, Id repoid);
extern const char *testcase_solvid2str(Pool *pool, Id p);
extern Repo *testcase_str2repo(Pool *pool, const char *str);
extern Id testcase_str2solvid(Pool *pool, const char *str);
extern const char *testcase_job2str(Pool *pool, Id how, Id what);
extern Id testcase_str2job(Pool *pool, const char *str, Id *whatp);
extern int testcase_write_testtags(Repo *repo, FILE *fp);
extern int testcase_add_testtags(Repo *repo, FILE *fp, int flags);
extern const char *testcase_getsolverflags(Solver *solv);
extern int testcase_setsolverflags(Solver *solv, const char *str);
extern void testcase_resetsolverflags(Solver *solv);
extern char *testcase_solverresult(Solver *solv, int flags);
extern int testcase_write(Solver *solv, const char *dir, int resultflags, const char *testcasename, const char *resultname);
extern Solver *testcase_read(Pool *pool, FILE *fp, const char *testcase, Queue *job, char **resultp, int *resultflagsp);
extern char *testcase_resultdiff(const char *result1, const char *result2);
extern const char **testcase_mangle_repo_names(Pool *pool);

