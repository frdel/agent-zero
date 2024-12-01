/*
 * Copyright (c) 2007, Novell Inc.
 *
 * This program is licensed under the BSD license, read LICENSE.BSD
 * for further information
 */
#ifndef LIBSOLV_DIRPOOL_H
#define LIBSOLV_DIRPOOL_H


#include "pooltypes.h"
#include "util.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct s_Dirpool {
  Id *dirs;
  int ndirs;
  Id *dirtraverse;
} Dirpool;

void dirpool_init(Dirpool *dp);
void dirpool_free(Dirpool *dp);

void dirpool_make_dirtraverse(Dirpool *dp);
Id dirpool_add_dir(Dirpool *dp, Id parent, Id comp, int create);

/* return the parent directory of child did */
static inline Id dirpool_parent(Dirpool *dp, Id did)
{
  if (!did)
    return 0;
  while (dp->dirs[--did] > 0)
    ;
  return -dp->dirs[did];
}

/* return the next child entry of child did */
static inline Id
dirpool_sibling(Dirpool *dp, Id did)
{
  /* if this block contains another entry, simply return it */
  if (did + 1 < dp->ndirs && dp->dirs[did + 1] > 0)
    return did + 1;
  /* end of block reached, rewind to get to the block's
   * dirtraverse entry */
  while (dp->dirs[--did] > 0)
    ;
  /* need to special case did == 0 to prevent looping */
  if (!did)
    return 0;
  if (!dp->dirtraverse)
    dirpool_make_dirtraverse(dp);
  return dp->dirtraverse[did];
}

/* return the first child entry of directory did */
static inline Id
dirpool_child(Dirpool *dp, Id did)
{
  if (!dp->dirtraverse)
    dirpool_make_dirtraverse(dp);
  return dp->dirtraverse[did];
}

static inline void
dirpool_free_dirtraverse(Dirpool *dp)
{
  solv_free(dp->dirtraverse);
  dp->dirtraverse = 0;
}

static inline Id
dirpool_compid(Dirpool *dp, Id did)
{
  return dp->dirs[did];
}

#ifdef __cplusplus
}
#endif

#endif /* LIBSOLV_DIRPOOL_H */
