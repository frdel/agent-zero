/*
 * Copyright (c) 2007, Novell Inc.
 *
 * This program is licensed under the BSD license, read LICENSE.BSD
 * for further information
 */

/*
 * pool.h
 *
 */

#ifndef LIBSOLV_POOL_H
#define LIBSOLV_POOL_H

#include <stdio.h>

#include "solvversion.h"
#include "pooltypes.h"
#include "poolid.h"
#include "solvable.h"
#include "bitmap.h"
#include "queue.h"
#include "strpool.h"

/* well known ids */
#include "knownid.h"

#ifdef __cplusplus
extern "C" {
#endif

/* well known solvable */
#define SYSTEMSOLVABLE		1


/*----------------------------------------------- */

struct s_Repo;
struct s_Repodata;
struct s_Repokey;
struct s_KeyValue;

typedef struct s_Datapos {
  struct s_Repo *repo;
  Id solvid;
  Id repodataid;
  Id schema;
  Id dp;
} Datapos;


#ifdef LIBSOLV_INTERNAL

/* how many strings to maintain (round robin) */
#define POOL_TMPSPACEBUF 16

struct s_Pool_tmpspace {
  char *buf[POOL_TMPSPACEBUF];
  int   len[POOL_TMPSPACEBUF];
  int   n;
};

#endif

struct s_Pool {
  void *appdata;		/* application private pointer */

  struct s_Stringpool ss;

  Reldep *rels;			/* table of rels: Id -> Reldep */
  int nrels;			/* number of unique rels */

  struct s_Repo **repos;
  int nrepos;			/* repos allocated */
  int urepos;			/* repos in use */

  struct s_Repo *installed; 	/* packages considered installed */

  Solvable *solvables;
  int nsolvables;		/* solvables allocated */

  const char **languages;
  int nlanguages;

  /* package manager type, deb/rpm */
  int disttype;

  Id *id2arch;			/* map arch ids to scores */
  unsigned char *id2color;	/* map arch ids to colors */
  Id lastarch;			/* size of the id2arch/id2color arrays */

  Queue vendormap;		/* map vendor to vendorclasses mask */
  const char **vendorclasses;	/* vendor equivalence classes */

  /* providers data, as two-step indirect list
   * whatprovides[Id] -> Offset into whatprovidesdata for name
   * whatprovidesdata[Offset] -> 0-terminated list of solvables providing Id
   */
  Offset *whatprovides;		/* Offset to providers of a specific name, Id -> Offset  */
  Offset *whatprovides_rel;	/* Offset to providers of a specific relation, Id -> Offset  */

  Id *whatprovidesdata;		/* Ids of solvable providing Id */
  Offset whatprovidesdataoff;	/* next free slot within whatprovidesdata */
  int whatprovidesdataleft;	/* number of 'free slots' within whatprovidesdata */

  /* If nonzero, then consider only the solvables with Ids set in this
     bitmap for solving.  If zero, consider all solvables.  */
  Map *considered;

  /* callback for REL_NAMESPACE dependencies handled by the application  */
  Id (*nscallback)(struct s_Pool *, void *data, Id name, Id evr);
  void *nscallbackdata;

  /* debug mask and callback */
  int  debugmask;
  void (*debugcallback)(struct s_Pool *, void *data, int type, const char *str);
  void *debugcallbackdata;

  /* load callback */
  int (*loadcallback)(struct s_Pool *, struct s_Repodata *, void *);
  void *loadcallbackdata;

  /* search position */
  Datapos pos;

  Queue pooljobs;		/* fixed jobs, like USERINSTALLED/MULTIVERSION */

#ifdef LIBSOLV_INTERNAL
  /* flags to tell the library how the installed package manager works */
  int promoteepoch;		/* true: missing epoch is replaced by epoch of dependency   */
  int havedistepoch;		/* true: thr release part in the evr may contain a distepoch suffix */
  int obsoleteusesprovides;	/* true: obsoletes are matched against provides, not names */
  int implicitobsoleteusesprovides;	/* true: implicit obsoletes due to same name are matched against provides, not names */
  int obsoleteusescolors;	/* true: obsoletes check arch color */
  int implicitobsoleteusescolors;	/* true: implicit obsoletes check arch color */
  int noinstalledobsoletes;	/* true: ignore obsoletes of installed packages */
  int forbidselfconflicts;	/* true: packages which conflict with itself are not installable */
  int noobsoletesmultiversion;	/* true: obsoletes are ignored for multiversion installs */

  Id noarchid;			/* ARCH_NOARCH, ARCH_ALL, ARCH_ANY, ... */

  /* hash for rel unification */
  Hashtable relhashtbl;		/* hashtable: (name,evr,op)Hash -> Id */
  Hashval relhashmask;

  Id *languagecache;
  int languagecacheother;

  /* our tmp space string space */
  struct s_Pool_tmpspace tmpspace;

  char *errstr;			/* last error string */
  int errstra;			/* allocated space for errstr */

  char *rootdir;

  int (*custom_vendorcheck)(struct s_Pool *, Solvable *, Solvable *);

  int addfileprovidesfiltered;	/* 1: only use filtered file list for addfileprovides */
  int addedfileprovides;	/* true: application called addfileprovides */
  Queue lazywhatprovidesq;	/* queue to store old whatprovides offsets */
  int nowhatprovidesaux;	/* don't allocate and use the whatprovides aux helper */
  Offset *whatprovidesaux;
  Offset whatprovidesauxoff;
  Id *whatprovidesauxdata;
  Offset whatprovidesauxdataoff;

  int whatprovideswithdisabled;
#endif
};

#define DISTTYPE_RPM	0
#define DISTTYPE_DEB	1
#define DISTTYPE_ARCH   2
#define DISTTYPE_HAIKU  3
#define DISTTYPE_CONDA  4

#define SOLV_FATAL			(1<<0)
#define SOLV_ERROR			(1<<1)
#define SOLV_WARN			(1<<2)
#define SOLV_DEBUG_STATS		(1<<3)
#define SOLV_DEBUG_RULE_CREATION	(1<<4)
#define SOLV_DEBUG_PROPAGATE		(1<<5)
#define SOLV_DEBUG_ANALYZE		(1<<6)
#define SOLV_DEBUG_UNSOLVABLE		(1<<7)
#define SOLV_DEBUG_SOLUTIONS		(1<<8)
#define SOLV_DEBUG_POLICY		(1<<9)
#define SOLV_DEBUG_RESULT		(1<<10)
#define SOLV_DEBUG_JOB			(1<<11)
#define SOLV_DEBUG_SOLVER		(1<<12)
#define SOLV_DEBUG_TRANSACTION		(1<<13)
#define SOLV_DEBUG_WATCHES		(1<<14)

#define SOLV_DEBUG_TO_STDERR		(1<<30)

#define POOL_FLAG_PROMOTEEPOCH				1
#define POOL_FLAG_FORBIDSELFCONFLICTS			2
#define POOL_FLAG_OBSOLETEUSESPROVIDES			3
#define POOL_FLAG_IMPLICITOBSOLETEUSESPROVIDES		4
#define POOL_FLAG_OBSOLETEUSESCOLORS			5
#define POOL_FLAG_NOINSTALLEDOBSOLETES			6
#define POOL_FLAG_HAVEDISTEPOCH				7
#define POOL_FLAG_NOOBSOLETESMULTIVERSION		8
#define POOL_FLAG_ADDFILEPROVIDESFILTERED		9
#define POOL_FLAG_IMPLICITOBSOLETEUSESCOLORS		10
#define POOL_FLAG_NOWHATPROVIDESAUX			11
#define POOL_FLAG_WHATPROVIDESWITHDISABLED		12

/* ----------------------------------------------- */


/* mark dependencies with relation by setting bit31 */

#define MAKERELDEP(id) ((id) | 0x80000000)
#define ISRELDEP(id) (((id) & 0x80000000) != 0)
#define GETRELID(id) ((id) ^ 0x80000000)				/* returns Id */
#define GETRELDEP(pool, id) ((pool)->rels + ((id) ^ 0x80000000))	/* returns Reldep* */

#define REL_GT		1
#define REL_EQ		2
#define REL_LT		4

#define REL_AND		16
#define REL_OR		17
#define REL_WITH	18
#define REL_NAMESPACE	19
#define REL_ARCH	20
#define REL_FILECONFLICT	21
#define REL_COND	22	/* OR_NOT */
#define REL_COMPAT	23
#define REL_KIND	24	/* for filters only */
#define REL_MULTIARCH	25	/* debian multiarch annotation */
#define REL_ELSE	26	/* only as evr part of REL_COND/REL_UNLESS */
#define REL_ERROR	27	/* parse errors and the like */
#define REL_WITHOUT	28
#define REL_UNLESS	29	/* AND_NOT */
#define REL_CONDA	30

#if !defined(__GNUC__) && !defined(__attribute__)
# define __attribute__(x)
#endif

extern Pool *pool_create(void);
extern void pool_free(Pool *pool);
extern void pool_freeallrepos(Pool *pool, int reuseids);

extern void pool_setdebuglevel(Pool *pool, int level);
extern int  pool_setdisttype(Pool *pool, int disttype);
extern int  pool_set_flag(Pool *pool, int flag, int value);
extern int  pool_get_flag(Pool *pool, int flag);

extern void pool_debug(Pool *pool, int type, const char *format, ...) __attribute__((format(printf, 3, 4)));
extern void pool_setdebugcallback(Pool *pool, void (*debugcallback)(struct s_Pool *, void *data, int type, const char *str), void *debugcallbackdata);
extern void pool_setdebugmask(Pool *pool, int mask);
extern void pool_setloadcallback(Pool *pool, int (*cb)(struct s_Pool *, struct s_Repodata *, void *), void *loadcbdata);
extern void pool_setnamespacecallback(Pool *pool, Id (*cb)(struct s_Pool *, void *, Id, Id), void *nscbdata);
extern void pool_flush_namespaceproviders(Pool *pool, Id ns, Id evr);

extern void pool_set_custom_vendorcheck(Pool *pool, int (*vendorcheck)(struct s_Pool *, Solvable *, Solvable *));
extern int (*pool_get_custom_vendorcheck(Pool *pool))(struct s_Pool *, Solvable *, Solvable *);

extern char *pool_alloctmpspace(Pool *pool, int len);
extern void  pool_freetmpspace(Pool *pool, const char *space);
extern char *pool_tmpjoin(Pool *pool, const char *str1, const char *str2, const char *str3);
extern char *pool_tmpappend(Pool *pool, const char *str1, const char *str2, const char *str3);
extern const char *pool_bin2hex(Pool *pool, const unsigned char *buf, int len);

extern void pool_set_installed(Pool *pool, struct s_Repo *repo);

extern int  pool_error(Pool *pool, int ret, const char *format, ...) __attribute__((format(printf, 3, 4)));
extern char *pool_errstr(Pool *pool);

extern void pool_set_rootdir(Pool *pool, const char *rootdir);
extern const char *pool_get_rootdir(Pool *pool);
extern char *pool_prepend_rootdir(Pool *pool, const char *dir);
extern const char *pool_prepend_rootdir_tmp(Pool *pool, const char *dir);

/**
 * Solvable management
 */
extern Id pool_add_solvable(Pool *pool);
extern Id pool_add_solvable_block(Pool *pool, int count);

extern void pool_free_solvable_block(Pool *pool, Id start, int count, int reuseids);
static inline Solvable *pool_id2solvable(const Pool *pool, Id p)
{
  return pool->solvables + p;
}
static inline Id pool_solvable2id(const Pool *pool, Solvable *s)
{
  return s - pool->solvables;
}

extern const char *pool_solvable2str(Pool *pool, Solvable *s);
static inline const char *pool_solvid2str(Pool *pool, Id p)
{
  return pool_solvable2str(pool, pool->solvables + p);
}
extern const char *pool_solvidset2str(Pool *pool, Queue *q);

void pool_set_languages(Pool *pool, const char **languages, int nlanguages);
Id pool_id2langid(Pool *pool, Id id, const char *lang, int create);

int pool_intersect_evrs(Pool *pool, int pflags, Id pevr, int flags, Id evr);
int pool_match_dep(Pool *pool, Id d1, Id d2);

/* semi private, used in pool_match_nevr */
int pool_match_nevr_rel(Pool *pool, Solvable *s, Id d);

static inline int pool_match_nevr(Pool *pool, Solvable *s, Id d)
{
  if (!ISRELDEP(d))
    return d == s->name;
  else
    return pool_match_nevr_rel(pool, s, d);
}


/**
 * Prepares a pool for solving
 */
extern void pool_createwhatprovides(Pool *pool);
extern void pool_addfileprovides(Pool *pool);
extern void pool_addfileprovides_queue(Pool *pool, Queue *idq, Queue *idqinst);
extern void pool_freewhatprovides(Pool *pool);
extern Id pool_queuetowhatprovides(Pool *pool, Queue *q);
extern Id pool_ids2whatprovides(Pool *pool, Id *ids, int count);
extern Id pool_searchlazywhatprovidesq(Pool *pool, Id d);

extern Id pool_addrelproviders(Pool *pool, Id d);

static inline Id pool_whatprovides(Pool *pool, Id d)
{
  if (!ISRELDEP(d))
    {
      if (pool->whatprovides[d])
	return pool->whatprovides[d];
    }
  else
    {
      Id v = GETRELID(d);
      if (pool->whatprovides_rel[v])
	return pool->whatprovides_rel[v];
    }
  return pool_addrelproviders(pool, d);
}

static inline Id *pool_whatprovides_ptr(Pool *pool, Id d)
{
  Id off = pool_whatprovides(pool, d);
  return pool->whatprovidesdata + off;
}

void pool_whatmatchesdep(Pool *pool, Id keyname, Id dep, Queue *q, int marker);
void pool_whatcontainsdep(Pool *pool, Id keyname, Id dep, Queue *q, int marker);
void pool_whatmatchessolvable(Pool *pool, Id keyname, Id solvid, Queue *q, int marker);
void pool_set_whatprovides(Pool *pool, Id id, Id providers);


/* search the pool. the following filters are available:
 *   p     - search just this solvable
 *   key   - search only this key
 *   match - key must match this string
 */
void pool_search(Pool *pool, Id p, Id key, const char *match, int flags, int (*callback)(void *cbdata, Solvable *s, struct s_Repodata *data, struct s_Repokey *key, struct s_KeyValue *kv), void *cbdata);

void pool_clear_pos(Pool *pool);

/* lookup functions */
const char *pool_lookup_str(Pool *pool, Id entry, Id keyname);
Id pool_lookup_id(Pool *pool, Id entry, Id keyname);
unsigned long long pool_lookup_num(Pool *pool, Id entry, Id keyname, unsigned long long notfound);
int pool_lookup_void(Pool *pool, Id entry, Id keyname);
const unsigned char *pool_lookup_bin_checksum(Pool *pool, Id entry, Id keyname, Id *typep);
int pool_lookup_idarray(Pool *pool, Id entry, Id keyname, Queue *q);
const char *pool_lookup_checksum(Pool *pool, Id entry, Id keyname, Id *typep);
const char *pool_lookup_deltalocation(Pool *pool, Id entry, unsigned int *medianrp);


#define DUCHANGES_ONLYADD	1

typedef struct s_DUChanges {
  const char *path;
  long long kbytes;
  long long files;
  int flags;
} DUChanges;


void pool_create_state_maps(Pool *pool, Queue *installed, Map *installedmap, Map *conflictsmap);
void pool_calc_duchanges(Pool *pool, Map *installedmap, DUChanges *mps, int nmps);
long long pool_calc_installsizechange(Pool *pool, Map *installedmap);

void pool_add_fileconflicts_deps(Pool *pool, Queue *conflicts);



/* loop over all providers of d */
#define FOR_PROVIDES(v, vp, d) 						\
  for (vp = pool_whatprovides(pool, d) ; (v = pool->whatprovidesdata[vp++]) != 0; )

/* loop over all repositories */
#define FOR_REPOS(repoid, r)						\
  for (repoid = 1; repoid < pool->nrepos; repoid++)			\
    if ((r = pool->repos[repoid]) == 0)					\
      continue;								\
    else

#define FOR_POOL_SOLVABLES(p)						\
  for (p = 2; p < pool->nsolvables; p++)				\
    if (pool->solvables[p].repo == 0)					\
      continue;								\
    else

#define POOL_DEBUG(type, ...) do {if ((pool->debugmask & (type)) != 0) pool_debug(pool, (type), __VA_ARGS__);} while (0)
#define IF_POOLDEBUG(type) if ((pool->debugmask & (type)) != 0)

/* weird suse stuff */
void pool_trivial_installable_multiversionmap(Pool *pool, Map *installedmap, Queue *pkgs, Queue *res, Map *multiversionmap);
void pool_trivial_installable(Pool *pool, Map *installedmap, Queue *pkgs, Queue *res);

#ifdef __cplusplus
}
#endif


#endif /* LIBSOLV_POOL_H */
