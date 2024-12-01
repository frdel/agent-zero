/*
 * Copyright (c) 2007-2012, Novell Inc.
 *
 * This program is licensed under the BSD license, read LICENSE.BSD
 * for further information
 */

/*
 * dataiterator.h
 *
 */

#ifndef LIBSOLV_DATAITERATOR_H
#define LIBSOLV_DATAITERATOR_H

#include "pooltypes.h"
#include "pool.h"

#ifdef __cplusplus
extern "C" {
#endif

struct s_Repo;

typedef struct s_KeyValue {
  Id id;
  const char *str;
  unsigned int num;
  unsigned int num2;

  int entry;	/* array entry, starts with 0 */
  int eof;	/* last entry reached */

  struct s_KeyValue *parent;
} KeyValue;

#define SOLV_KV_NUM64(kv) (((unsigned long long)((kv)->num2)) << 32 | (kv)->num)

/* search matcher flags */
#define SEARCH_STRINGMASK		15
#define SEARCH_STRING			1
#define SEARCH_STRINGSTART		2
#define SEARCH_STRINGEND		3
#define SEARCH_SUBSTRING		4
#define SEARCH_GLOB 			5
#define SEARCH_REGEX 			6
#define SEARCH_ERROR 			15
#define	SEARCH_NOCASE			(1<<7)

/* iterator control */
#define	SEARCH_NO_STORAGE_SOLVABLE	(1<<8)
#define SEARCH_SUB			(1<<9)
#define SEARCH_ARRAYSENTINEL		(1<<10)
#define SEARCH_DISABLED_REPOS		(1<<11)
#define SEARCH_KEEP_TYPE_DELETED	(1<<12)		/* only has effect if no keyname is given */

/* stringification flags */
#define SEARCH_SKIP_KIND		(1<<16)
/* By default we stringify just to the basename of a file because
   the construction of the full filename is costly.  Specify this
   flag if you want to match full filenames */
#define SEARCH_FILES			(1<<17)
#define SEARCH_CHECKSUMS		(1<<18)

/* internal */
#define SEARCH_SUBSCHEMA		(1<<30)
#define SEARCH_THISSOLVID		(1<<31)

/* obsolete */
#define SEARCH_COMPLETE_FILELIST	0		/* ignored, this is the default */

/*
 * Datamatcher: match a string against a query
 */
typedef struct s_Datamatcher {
  int flags;		/* see matcher flags above */
  const char *match;	/* the query string */
  void *matchdata;	/* e.g. compiled regexp */
  int error;
} Datamatcher;

int  datamatcher_init(Datamatcher *ma, const char *match, int flags);
void datamatcher_free(Datamatcher *ma);
int  datamatcher_match(Datamatcher *ma, const char *str);
int  datamatcher_checkbasename(Datamatcher *ma, const char *str);


/*
 * Dataiterator
 *
 * Iterator like interface to 'search' functionality
 *
 * Dataiterator is per-pool, additional filters can be applied
 * to limit the search domain. See dataiterator_init below.
 *
 * Use these like:
 *    Dataiterator di;
 *    dataiterator_init(&di, repo->pool, repo, 0, 0, "bla", SEARCH_SUBSTRING);
 *    while (dataiterator_step(&di))
 *      dosomething(di.solvid, di.key, di.kv);
 *    dataiterator_free(&di);
 */
typedef struct s_Dataiterator
{
  int state;
  int flags;

  Pool *pool;
  struct s_Repo *repo;
  struct s_Repodata *data;

  /* data pointers */
  unsigned char *dp;
  unsigned char *ddp;
  Id *idp;
  Id *keyp;

  /* the result */
  struct s_Repokey *key;
  KeyValue kv;

  /* our matcher */
  Datamatcher matcher;

  /* iterators/filters */
  Id keyname;
  Id repodataid;
  Id solvid;
  Id repoid;

  Id keynames[3 + 1];
  int nkeynames;
  int rootlevel;

  /* recursion data */
  struct di_parent {
    KeyValue kv;
    unsigned char *dp;
    Id *keyp;
  } parents[3];
  int nparents;

  /* vertical data */
  unsigned char *vert_ddp;
  Id vert_off;
  Id vert_len;
  Id vert_storestate;

  /* strdup data */
  char *dupstr;
  int dupstrn;

  Id *keyskip;
  Id *oldkeyskip;
} Dataiterator;


/*
 * Initialize dataiterator
 *
 * di:      Pointer to Dataiterator to be initialized
 * pool:    Search domain for the iterator
 * repo:    if non-null, limit search to this repo
 * solvid:  if non-null, limit search to this solvable
 * keyname: if non-null, limit search to this keyname
 * match:   if non-null, limit search to this match
 */
int  dataiterator_init(Dataiterator *di, Pool *pool, struct s_Repo *repo, Id p, Id keyname, const char *match, int flags);
void dataiterator_init_clone(Dataiterator *di, Dataiterator *from);
void dataiterator_set_search(Dataiterator *di, struct s_Repo *repo, Id p);
void dataiterator_set_keyname(Dataiterator *di, Id keyname);
int  dataiterator_set_match(Dataiterator *di, const char *match, int flags);

void dataiterator_prepend_keyname(Dataiterator *di, Id keyname);
void dataiterator_free(Dataiterator *di);
int  dataiterator_step(Dataiterator *di);
void dataiterator_setpos(Dataiterator *di);
void dataiterator_setpos_parent(Dataiterator *di);
int  dataiterator_match(Dataiterator *di, Datamatcher *ma);
void dataiterator_skip_attribute(Dataiterator *di);
void dataiterator_skip_solvable(Dataiterator *di);
void dataiterator_skip_repo(Dataiterator *di);
void dataiterator_jump_to_solvid(Dataiterator *di, Id solvid);
void dataiterator_jump_to_repo(Dataiterator *di, struct s_Repo *repo);
void dataiterator_entersub(Dataiterator *di);
void dataiterator_clonepos(Dataiterator *di, Dataiterator *from);
void dataiterator_seek(Dataiterator *di, int whence);
void dataiterator_strdup(Dataiterator *di);

#define DI_SEEK_STAY    (1 << 16)
#define DI_SEEK_CHILD   1
#define DI_SEEK_PARENT  2
#define DI_SEEK_REWIND  3

#ifdef __cplusplus
}
#endif

#endif /* LIBSOLV_DATAITERATOR_H */
