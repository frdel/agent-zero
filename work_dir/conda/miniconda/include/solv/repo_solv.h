/*
 * Copyright (c) 2007, Novell Inc.
 *
 * This program is licensed under the BSD license, read LICENSE.BSD
 * for further information
 */

/*
 * repo_solv.h
 *
 */

#ifndef LIBSOLV_REPO_SOLVE_H
#define LIBSOLV_REPO_SOLVE_H

#include <stdio.h>

#include "pool.h"
#include "repo.h"

#ifdef __cplusplus
extern "C" {
#endif

extern int repo_add_solv(Repo *repo, FILE *fp, int flags);
extern int solv_read_userdata(FILE *fp, unsigned char **datap, int *lenp);

#define SOLV_ADD_NO_STUBS	(1 << 8)

#ifdef __cplusplus
}
#endif

#endif /* LIBSOLV_REPO_SOLVE_H */
