/*
 * Copyright (c) 2007-2011, Novell Inc.
 *
 * This program is licensed under the BSD license, read LICENSE.BSD
 * for further information
 */

/*
 * bitmap.h
 *
 */

#ifndef LIBSOLV_BITMAP_H
#define LIBSOLV_BITMAP_H

#include <string.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct s_Map {
  unsigned char *map;
  int size;
} Map;

#define MAPZERO(m) (memset((m)->map, 0, (m)->size))
/* set all bits */
#define MAPSETALL(m) (memset((m)->map, 0xff, (m)->size))
/* set bit */
#define MAPSET(m, n) ((m)->map[(n) >> 3] |= 1 << ((n) & 7))
/* clear bit */
#define MAPCLR(m, n) ((m)->map[(n) >> 3] &= ~(1 << ((n) & 7)))
/* test bit */
#define MAPTST(m, n) ((m)->map[(n) >> 3] & (1 << ((n) & 7)))
/* clear some bits at a position */
#define MAPCLR_AT(m, n) ((m)->map[(n) >> 3] = 0)

extern void map_init(Map *m, int n);
extern void map_init_clone(Map *target, const Map *source);
extern void map_grow(Map *m, int n);
extern void map_free(Map *m);
extern void map_and(Map *t, const Map *s);
extern void map_or(Map *t, const Map *s);
extern void map_subtract(Map *t, const Map *s);
extern void map_invertall(Map *m);

static inline void map_empty(Map *m)
{
  MAPZERO(m);
}
static inline void map_set(Map *m, int n)
{
  MAPSET(m, n);
}
static inline void map_setall(Map *m)
{
  MAPSETALL(m);
}
static inline void map_clr(Map *m, int n)
{
  MAPCLR(m, n);
}
static inline int map_tst(Map *m, int n)
{
  return MAPTST(m, n);
}
static inline void map_clr_at(Map *m, int n)
{
  MAPCLR_AT(m, n);
}

#ifdef __cplusplus
}
#endif

#endif /* LIBSOLV_BITMAP_H */
