/*
 * Copyright (c) 2012, Novell Inc.
 *
 * This program is licensed under the BSD license, read LICENSE.BSD
 * for further information
 */

/*
 * selection.h
 *
 */

#ifndef LIBSOLV_SELECTION_H
#define LIBSOLV_SELECTION_H

#include "pool.h"

#ifdef __cplusplus
extern "C" {
#endif

/* what to match */
#define SELECTION_NAME			(1 << 0)
#define SELECTION_PROVIDES		(1 << 1)
#define SELECTION_FILELIST		(1 << 2)
#define SELECTION_CANON			(1 << 3)

/* match extensions */
#define SELECTION_DOTARCH		(1 << 4)	/* allow ".arch" suffix */
#define SELECTION_REL			(1 << 5)	/* allow "<=> rel" suffix */

/* string comparison modifiers */
#define SELECTION_GLOB			(1 << 9)
#define SELECTION_NOCASE		(1 << 11)

/* extra flags */
#define SELECTION_FLAT			(1 << 10)	/* flatten the resulting selection */
#define SELECTION_SKIP_KIND		(1 << 14)	/* remove kind: name prefix in SELECTION_NAME matches */
#define SELECTION_MATCH_DEPSTR		(1 << 15)	/* match dep2str result */

/* package selection */
#define SELECTION_INSTALLED_ONLY	(1 << 8)
#define SELECTION_SOURCE_ONLY		(1 << 12)
#define SELECTION_WITH_SOURCE		(1 << 13)
#define SELECTION_WITH_DISABLED		(1 << 16)
#define SELECTION_WITH_BADARCH		(1 << 17)
#define SELECTION_WITH_ALL		(SELECTION_WITH_SOURCE | SELECTION_WITH_DISABLED | SELECTION_WITH_BADARCH)

/* result operator */
#define SELECTION_REPLACE		(0 << 28)
#define SELECTION_ADD			(1 << 28)
#define SELECTION_SUBTRACT		(2 << 28)
#define SELECTION_FILTER		(3 << 28)


/* extra SELECTION_FILTER bits */
#define SELECTION_FILTER_KEEP_IFEMPTY	(1 << 30)
#define SELECTION_FILTER_SWAPPED	(1 << 31)

/* internal */
#define SELECTION_MODEBITS		(3 << 28)

extern int  selection_make(Pool *pool, Queue *selection, const char *name, int flags);
extern int  selection_make_matchdeps(Pool *pool, Queue *selection, const char *name, int flags, int keyname, int marker);
extern int  selection_make_matchdepid(Pool *pool, Queue *selection, Id dep, int flags, int keyname, int marker);
extern int selection_make_matchsolvable(Pool *pool, Queue *selection, Id solvid, int flags, int keyname, int marker);
extern int selection_make_matchsolvablelist(Pool *pool, Queue *selection, Queue *solvidq, int flags, int keyname, int marker);

extern void selection_filter(Pool *pool, Queue *sel1, Queue *sel2);
extern void selection_add(Pool *pool, Queue *sel1, Queue *sel2);
extern void selection_subtract(Pool *pool, Queue *sel1, Queue *sel2);

extern void selection_solvables(Pool *pool, Queue *selection, Queue *pkgs);

extern const char *pool_selection2str(Pool *pool, Queue *selection, Id flagmask);

#ifdef __cplusplus
}
#endif

#endif
