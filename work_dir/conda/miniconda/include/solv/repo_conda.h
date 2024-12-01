/*
 * Copyright (c) 2019, SUSE LLC
 *
 * This program is licensed under the BSD license, read LICENSE.BSD
 * for further information
 */

#ifndef LIBSOLV_REPO_CONDA_H
#define LIBSOLV_REPO_CONDA_H

#include <stdio.h>

#include "repo.h"

#ifdef __cplusplus
extern "C" {
#endif

#define CONDA_ADD_USE_ONLY_TAR_BZ2	(1 << 8)
#define CONDA_ADD_WITH_SIGNATUREDATA	(1 << 9)

extern int repo_add_conda(Repo *repo, FILE *fp, int flags);

#ifdef __cplusplus
}
#endif

#endif /* LIBSOLV_REPO_CONDA_H */
