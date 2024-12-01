/*
 * Copyright (c) 2007, Novell Inc.
 *
 * This program is licensed under the BSD license, read LICENSE.BSD
 * for further information
 */

#ifndef LIBSOLV_POOLARCH_H
#define LIBSOLV_POOLARCH_H

#include "pool.h"

#ifdef __cplusplus
extern "C" {
#endif

extern void pool_setarch(Pool *, const char *);
extern void pool_setarchpolicy(Pool *, const char *);
extern unsigned char pool_arch2color_slow(Pool *pool, Id arch);

#define ARCHCOLOR_32    1
#define ARCHCOLOR_64    2
#define ARCHCOLOR_ALL   255

static inline unsigned char pool_arch2color(Pool *pool, Id arch)
{
  if ((unsigned int)arch >= (unsigned int)pool->lastarch)
    return ARCHCOLOR_ALL;
  if (pool->id2color && pool->id2color[arch])
    return pool->id2color[arch];
  return pool_arch2color_slow(pool, arch);
}

static inline int pool_colormatch(Pool *pool, Solvable *s1, Solvable *s2)
{
  if (s1->arch == s2->arch)
    return 1;
  if ((pool_arch2color(pool, s1->arch) & pool_arch2color(pool, s2->arch)) != 0)
    return 1;
  return 0;
}

static inline unsigned int pool_arch2score(const Pool *pool, Id arch) {
  return (unsigned int)arch < (unsigned int)pool->lastarch ? (unsigned int)pool->id2arch[arch] : 0;
}

#ifdef __cplusplus
}
#endif

#endif /* LIBSOLV_POOLARCH_H */
