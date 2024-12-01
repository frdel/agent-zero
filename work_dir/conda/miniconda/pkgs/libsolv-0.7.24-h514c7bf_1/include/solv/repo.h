/*
 * Copyright (c) 2007, Novell Inc.
 *
 * This program is licensed under the BSD license, read LICENSE.BSD
 * for further information
 */

/*
 * repo.h
 *
 */

#ifndef LIBSOLV_REPO_H
#define LIBSOLV_REPO_H

#include "pooltypes.h"
#include "pool.h"
#include "poolarch.h"
#include "repodata.h"
#include "dataiterator.h"
#include "hash.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct s_Repo {
  const char *name;		/* name pointer */
  Id repoid;			/* our id */
  void *appdata;		/* application private pointer */

  Pool *pool;			/* pool containing this repo */

  int start;			/* start of this repo solvables within pool->solvables */
  int end;			/* last solvable + 1 of this repo */
  int nsolvables;		/* number of solvables repo is contributing to pool */

  int disabled;			/* ignore the solvables? */
  int priority;			/* priority of this repo */
  int subpriority;		/* sub-priority of this repo, used just for sorting, not pruning */

  Id *idarraydata;		/* array of metadata Ids, solvable dependencies are offsets into this array */
  int idarraysize;

  int nrepodata;		/* number of our stores..  */

  Id *rpmdbid;			/* solvable side data: rpm database id */

#ifdef LIBSOLV_INTERNAL
  Repodata *repodata;		/* our stores for non-solvable related data */
  Offset lastoff;		/* start of last array in idarraydata */

  Hashtable lastidhash;		/* hash to speed up repo_addid_dep */
  Hashval lastidhash_mask;
  int lastidhash_idarraysize;
  int lastmarker;
  Offset lastmarkerpos;
#endif /* LIBSOLV_INTERNAL */
} Repo;

extern Repo *repo_create(Pool *pool, const char *name);
extern void repo_free(Repo *repo, int reuseids);
extern void repo_empty(Repo *repo, int reuseids);
extern void repo_freedata(Repo *repo);
extern Id repo_add_solvable(Repo *repo);
extern Id repo_add_solvable_block(Repo *repo, int count);
extern void repo_free_solvable(Repo *repo, Id p, int reuseids);
extern void repo_free_solvable_block(Repo *repo, Id start, int count, int reuseids);
extern void *repo_sidedata_create(Repo *repo, size_t size);
extern void *repo_sidedata_extend(Repo *repo, void *b, size_t size, Id p, int count);
extern Id repo_add_solvable_block_before(Repo *repo, int count, Repo *beforerepo);

extern Offset repo_addid(Repo *repo, Offset olddeps, Id id);
extern Offset repo_addid_dep(Repo *repo, Offset olddeps, Id id, Id marker);
extern Offset repo_reserve_ids(Repo *repo, Offset olddeps, int num);

static inline const char *repo_name(const Repo *repo)
{
  return repo->name;
}

/* those two functions are here because they need the Repo definition */

static inline Repo *pool_id2repo(Pool *pool, Id repoid)
{
  return repoid < pool->nrepos ? pool->repos[repoid] : 0;
}

static inline int pool_disabled_solvable(const Pool *pool, Solvable *s)
{
  if (s->repo && s->repo->disabled)
    return 1;
  if (pool->considered)
    {
      Id id = s - pool->solvables;
      if (!MAPTST(pool->considered, id))
	return 1;
    }
  return 0;
}

static inline int pool_badarch_solvable(const Pool *pool, Solvable *s)
{
  if (pool->id2arch && (!s->arch || pool_arch2score(pool, s->arch) == 0))
    return 1;
  return 0;
}

static inline int pool_installable(const Pool *pool, Solvable *s)
{
  if (s->arch == ARCH_SRC || s->arch == ARCH_NOSRC)
    return 0;
  if (s->repo && s->repo->disabled)
    return 0;
  if (pool->id2arch && (!s->arch || pool_arch2score(pool, s->arch) == 0))
    return 0;
  if (pool->considered)
    {
      Id id = s - pool->solvables;
      if (!MAPTST(pool->considered, id))
	return 0;
    }
  return 1;
}

#ifdef LIBSOLV_INTERNAL
static inline int pool_installable_whatprovides(const Pool *pool, Solvable *s)
{
  /* we always need the installed solvable in the whatprovides data,
     otherwise obsoletes/conflicts on them won't work */
  if (s->repo != pool->installed)
    {
      if (s->arch == ARCH_SRC || s->arch == ARCH_NOSRC || pool_badarch_solvable(pool, s))
	return 0;
      if (pool->considered && !pool->whatprovideswithdisabled)
	{
	  Id id = s - pool->solvables;
	  if (!MAPTST(pool->considered, id))
	    return 0;
	}
    }
  return 1;
}
#endif

/* not in solvable.h because we need the repo definition */
static inline Solvable *solvable_free(Solvable *s, int reuseids)
{
  if (s && s->repo)
    repo_free_solvable(s->repo, s - s->repo->pool->solvables, reuseids);
  return 0;
}

/* search callback values */
#define SEARCH_NEXT_KEY         1
#define SEARCH_NEXT_SOLVABLE    2
#define SEARCH_STOP             3
#define SEARCH_ENTERSUB		-1

/* standard flags used in the repo_add functions */
#define REPO_REUSE_REPODATA		(1 << 0)
#define REPO_NO_INTERNALIZE		(1 << 1)
#define REPO_LOCALPOOL			(1 << 2)
#define REPO_USE_LOADING		(1 << 3)
#define REPO_EXTEND_SOLVABLES		(1 << 4)
#define REPO_USE_ROOTDIR		(1 << 5)
#define REPO_NO_LOCATION		(1 << 6)

Repodata *repo_add_repodata(Repo *repo, int flags);
Repodata *repo_id2repodata(Repo *repo, Id id);
Repodata *repo_last_repodata(Repo *repo);

void repo_search(Repo *repo, Id p, Id key, const char *match, int flags, int (*callback)(void *cbdata, Solvable *s, Repodata *data, Repokey *key, KeyValue *kv), void *cbdata);

/* returns the last repodata that contains the key */
Repodata *repo_lookup_repodata(Repo *repo, Id entry, Id keyname);
Repodata *repo_lookup_repodata_opt(Repo *repo, Id entry, Id keyname);
Repodata *repo_lookup_filelist_repodata(Repo *repo, Id entry, Datamatcher *matcher);

/* returns the string value of the attribute, or NULL if not found */
Id repo_lookup_type(Repo *repo, Id entry, Id keyname);
const char *repo_lookup_str(Repo *repo, Id entry, Id keyname);
/* returns the integer value of the attribute, or notfound if not found */
unsigned long long repo_lookup_num(Repo *repo, Id entry, Id keyname, unsigned long long notfound);
Id repo_lookup_id(Repo *repo, Id entry, Id keyname);
int repo_lookup_idarray(Repo *repo, Id entry, Id keyname, Queue *q);
int repo_lookup_deparray(Repo *repo, Id entry, Id keyname, Queue *q, Id marker);
int repo_lookup_void(Repo *repo, Id entry, Id keyname);
const char *repo_lookup_checksum(Repo *repo, Id entry, Id keyname, Id *typep);
const unsigned char *repo_lookup_bin_checksum(Repo *repo, Id entry, Id keyname, Id *typep);
const void *repo_lookup_binary(Repo *repo, Id entry, Id keyname, int *lenp);
unsigned int repo_lookup_count(Repo *repo, Id entry, Id keyname);	/* internal */
Id solv_depmarker(Id keyname, Id marker);

void repo_set_id(Repo *repo, Id p, Id keyname, Id id);
void repo_set_num(Repo *repo, Id p, Id keyname, unsigned long long num);
void repo_set_str(Repo *repo, Id p, Id keyname, const char *str);
void repo_set_poolstr(Repo *repo, Id p, Id keyname, const char *str);
void repo_add_poolstr_array(Repo *repo, Id p, Id keyname, const char *str);
void repo_add_idarray(Repo *repo, Id p, Id keyname, Id id);
void repo_add_deparray(Repo *repo, Id p, Id keyname, Id dep, Id marker);
void repo_set_idarray(Repo *repo, Id p, Id keyname, Queue *q);
void repo_set_deparray(Repo *repo, Id p, Id keyname, Queue *q, Id marker);
void repo_unset(Repo *repo, Id p, Id keyname);

void repo_internalize(Repo *repo);
void repo_disable_paging(Repo *repo);
Id *repo_create_keyskip(Repo *repo, Id entry, Id **oldkeyskip);


/* iterator macros */
#define FOR_REPO_SOLVABLES(r, p, s)						\
  for (p = (r)->start, s = (r)->pool->solvables + p; p < (r)->end; p++, s = (r)->pool->solvables + p)	\
    if (s->repo != (r))								\
      continue;									\
    else

#ifdef LIBSOLV_INTERNAL
#define FOR_REPODATAS(repo, rdid, data)	\
	for (rdid = 1, data = repo->repodata + rdid; rdid < repo->nrepodata; rdid++, data++)
#else
#define FOR_REPODATAS(repo, rdid, data)	\
	for (rdid = 1; rdid < repo->nrepodata && (data = repo_id2repodata(repo, rdid)); rdid++)
#endif

/* weird suse stuff, do not use */
extern Offset repo_fix_supplements(Repo *repo, Offset provides, Offset supplements, Offset freshens);
extern Offset repo_fix_conflicts(Repo *repo, Offset conflicts);
extern void repo_rewrite_suse_deps(Solvable *s, Offset freshens);

#ifdef __cplusplus
}
#endif

#endif /* LIBSOLV_REPO_H */
