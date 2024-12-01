/*
 * Copyright (c) 2007, Novell Inc.
 *
 * This program is licensed under the BSD license, read LICENSE.BSD
 * for further information
 */

/*
 * poolid.h
 *
 */

#ifndef LIBSOLV_POOLID_H
#define LIBSOLV_POOLID_H

#include "pooltypes.h"
#include "hash.h"

#ifdef __cplusplus
extern "C" {
#endif

/*-----------------------------------------------
 * Ids with relation
 */

typedef struct s_Reldep {
  Id name;		/* "package" */
  Id evr;		/* "0:42-3" */
  int flags;		/* operation/relation, see REL_x in pool.h */
} Reldep;

extern Id pool_str2id(Pool *pool, const char *, int);
extern Id pool_strn2id(Pool *pool, const char *, unsigned int, int);
extern Id pool_rel2id(Pool *pool, Id, Id, int, int);
extern const char *pool_id2str(const Pool *pool, Id);
extern const char *pool_id2rel(const Pool *pool, Id);
extern const char *pool_id2evr(const Pool *pool, Id);
extern const char *pool_dep2str(Pool *pool, Id); /* might alloc tmpspace */

extern void pool_shrink_strings(Pool *pool);
extern void pool_shrink_rels(Pool *pool);
extern void pool_freeidhashes(Pool *pool);
extern void pool_resize_rels_hash(Pool *pool, int numnew);

#ifdef __cplusplus
}
#endif

#endif /* LIBSOLV_POOLID_H */
