/*
 * Copyright (c) 2007, Novell Inc.
 *
 * This program is licensed under the BSD license, read LICENSE.BSD
 * for further information
 */

/*
 * repodata.h
 *
 */

#ifndef LIBSOLV_REPODATA_H
#define LIBSOLV_REPODATA_H

#include <stdio.h>

#include "pooltypes.h"
#include "pool.h"
#include "dirpool.h"

#ifdef LIBSOLV_INTERNAL
#include "repopage.h"
#endif

#ifdef __cplusplus
extern "C" {
#endif

#define SIZEOF_MD5	16
#define SIZEOF_SHA1	20
#define SIZEOF_SHA224	28
#define SIZEOF_SHA256	32
#define SIZEOF_SHA384	48
#define SIZEOF_SHA512	64

struct s_Repo;
struct s_KeyValue;

typedef struct s_Repokey {
  Id name;
  Id type;			/* REPOKEY_TYPE_xxx */
  unsigned int size;
  unsigned int storage;		/* KEY_STORAGE_xxx */
} Repokey;

#define KEY_STORAGE_DROPPED             0
#define KEY_STORAGE_SOLVABLE            1
#define KEY_STORAGE_INCORE              2
#define KEY_STORAGE_VERTICAL_OFFSET     3
#define KEY_STORAGE_IDARRAYBLOCK	4

#ifdef LIBSOLV_INTERNAL
struct dircache;
#endif

/* repodata states */
#define REPODATA_AVAILABLE	0
#define REPODATA_STUB		1
#define REPODATA_ERROR		2
#define REPODATA_STORE		3
#define REPODATA_LOADING	4

/* repodata filelist types */
/* note that FILELIST_FILTERED means that the data contains a filtered
 * filelist *AND* that it is authoritative for all included solvables. */
#define REPODATA_FILELIST_FILTERED	1
#define REPODATA_FILELIST_EXTENSION	2

typedef struct s_Repodata {
  Id repodataid;		/* our id */
  struct s_Repo *repo;		/* back pointer to repo */

  int state;			/* available, stub or error */

  void (*loadcallback)(struct s_Repodata *);

  int start;			/* start of solvables this repodata is valid for */
  int end;			/* last solvable + 1 of this repodata */

  Repokey *keys;		/* keys, first entry is always zero */
  int nkeys;			/* length of keys array */
  unsigned char keybits[32];	/* keyname hash */

  Id *schemata;			/* schema -> offset into schemadata */
  int nschemata;		/* number of schemata */
  Id *schemadata;		/* schema storage */

  Stringpool spool;		/* local string pool */
  int localpool;		/* is local string pool used */

  Dirpool dirpool;		/* local dir pool */

#ifdef LIBSOLV_INTERNAL
  FILE *fp;			/* file pointer of solv file */
  int error;			/* corrupt solv file */

  int filelisttype;		/* type of filelist */
  Id *filelistfilter;		/* filelist filter used */
  char *filelistfilterdata;	/* filelist filter string space */

  unsigned int schemadatalen;   /* schema storage size */
  Id *schematahash;		/* unification helper */

  unsigned char *incoredata;	/* in-core data */
  unsigned int incoredatalen;	/* in-core data used */
  unsigned int incoredatafree;	/* free data len */

  Id mainschema;		/* SOLVID_META schema */
  Id *mainschemaoffsets;	/* SOLVID_META offsets into incoredata */

  Id *incoreoffset;		/* offset for all entries */

  Id *verticaloffset;		/* offset for all verticals, nkeys elements */
  Id lastverticaloffset;	/* end of verticals */

  Repopagestore store;		/* our page store */
  Id storestate;		/* incremented every time the store might change */

  unsigned char *vincore;	/* internal vertical data */
  unsigned int vincorelen;	/* data size */

  Id **attrs;			/* un-internalized attributes */
  Id **xattrs;			/* anonymous handles */
  int nxattrs;			/* number of handles */

  unsigned char *attrdata;	/* their string data space */
  unsigned int attrdatalen;	/* its len */
  Id *attriddata;		/* their id space */
  unsigned int attriddatalen;	/* its len */
  unsigned long long *attrnum64data;	/* their 64bit num data space */
  unsigned int attrnum64datalen;	/* its len */

  /* array cache to speed up repodata_add functions*/
  Id lasthandle;
  Id lastkey;
  Id lastdatalen;

  /* directory cache to speed up repodata_str2dir */
  struct dircache *dircache;
#endif

} Repodata;

#define SOLVID_META		-1
#define SOLVID_POS		-2


/*-----
 * management functions
 */
void repodata_initdata(Repodata *data, struct s_Repo *repo, int localpool);
void repodata_freedata(Repodata *data);

void repodata_free(Repodata *data);
void repodata_empty(Repodata *data, int localpool);

void repodata_load(Repodata *data);

/*
 * key management functions
 */
Id repodata_key2id(Repodata *data, Repokey *key, int create);

static inline Repokey *
repodata_id2key(Repodata *data, Id keyid)
{
  return data->keys + keyid;
}

/*
 * schema management functions
 */
Id repodata_schema2id(Repodata *data, Id *schema, int create);
void repodata_free_schemahash(Repodata *data);

static inline Id *
repodata_id2schema(Repodata *data, Id schemaid)
{
  return data->schemadata + data->schemata[schemaid];
}

/*
 * data search and access
 */

/* check if there is a chance that the repodata contains data for
 * the specified keyname */
static inline int
repodata_precheck_keyname(Repodata *data, Id keyname)
{
  unsigned char x = data->keybits[(keyname >> 3) & (sizeof(data->keybits) - 1)];
  return x && (x & (1 << (keyname & 7))) ? 1 : 0;
}

/* check if the repodata contains data for the specified keyname */
static inline int
repodata_has_keyname(Repodata *data, Id keyname)
{
  int i;
  if (!repodata_precheck_keyname(data, keyname))
    return 0;
  for (i = 1; i < data->nkeys; i++)
    if (data->keys[i].name == keyname)
      return 1;
  return 0;
}

/* search key <keyname> (all keys, if keyname == 0) for Id <solvid>
 * Call <callback> for each match */
void repodata_search(Repodata *data, Id solvid, Id keyname, int flags, int (*callback)(void *cbdata, Solvable *s, Repodata *data, Repokey *key, struct s_KeyValue *kv), void *cbdata);
void repodata_search_keyskip(Repodata *data, Id solvid, Id keyname, int flags, Id *keyskip, int (*callback)(void *cbdata, Solvable *s, Repodata *data, Repokey *key, struct s_KeyValue *kv), void *cbdata);
void repodata_search_arrayelement(Repodata *data, Id solvid, Id keyname, int flags, struct s_KeyValue *kv, int (*callback)(void *cbdata, Solvable *s, Repodata *data, Repokey *key, struct s_KeyValue *kv), void *cbdata);

/* Make sure the found KeyValue has the "str" field set. Return "str"
 * if valid, NULL if not possible */
const char *repodata_stringify(Pool *pool, Repodata *data, Repokey *key, struct s_KeyValue *kv, int flags);

/* filelist filter support */
void repodata_set_filelisttype(Repodata *data, int filelisttype);
int repodata_filelistfilter_matches(Repodata *data, const char *str);
void repodata_free_filelistfilter(Repodata *data);

/* lookup functions */
Id repodata_lookup_type(Repodata *data, Id solvid, Id keyname);
Id repodata_lookup_id(Repodata *data, Id solvid, Id keyname);
const char *repodata_lookup_str(Repodata *data, Id solvid, Id keyname);
unsigned long long repodata_lookup_num(Repodata *data, Id solvid, Id keyname, unsigned long long notfound);
int repodata_lookup_void(Repodata *data, Id solvid, Id keyname);
const unsigned char *repodata_lookup_bin_checksum(Repodata *data, Id solvid, Id keyname, Id *typep);
int repodata_lookup_idarray(Repodata *data, Id solvid, Id keyname, Queue *q);
const void *repodata_lookup_binary(Repodata *data, Id solvid, Id keyname, int *lenp);
unsigned int repodata_lookup_count(Repodata *data, Id solvid, Id keyname);	/* internal */

/* internal, used in fileprovides code */
const unsigned char *repodata_lookup_packed_dirstrarray(Repodata *data, Id solvid, Id keyname);

/* internal, fill keyskip array with data */
Id *repodata_fill_keyskip(Repodata *data, Id solvid, Id *keyskip);

/*-----
 * data assignment functions
 */

/*
 * extend the data so that it contains the specified solvables
 * (no longer needed, as the repodata_set functions autoextend)
 */
void repodata_extend(Repodata *data, Id p);
void repodata_extend_block(Repodata *data, Id p, int num);
void repodata_shrink(Repodata *data, int end);

/* internalize freshly set data, so that it is found by the search
 * functions and written out */
void repodata_internalize(Repodata *data);

/* create an anonymous handle. useful for substructures like
 * fixarray/flexarray  */
Id repodata_new_handle(Repodata *data);

/* basic types: void, num, string, Id */
void repodata_set_void(Repodata *data, Id solvid, Id keyname);
void repodata_set_num(Repodata *data, Id solvid, Id keyname, unsigned long long num);
void repodata_set_id(Repodata *data, Id solvid, Id keyname, Id id);
void repodata_set_str(Repodata *data, Id solvid, Id keyname, const char *str);
void repodata_set_binary(Repodata *data, Id solvid, Id keyname, void *buf, int len);
/* create id from string, then set_id */
void repodata_set_poolstr(Repodata *data, Id solvid, Id keyname, const char *str);

/* set numeric constant */
void repodata_set_constant(Repodata *data, Id solvid, Id keyname, unsigned int constant);

/* set Id constant */
void repodata_set_constantid(Repodata *data, Id solvid, Id keyname, Id id);

/* checksum */
void repodata_set_bin_checksum(Repodata *data, Id solvid, Id keyname, Id type,
			       const unsigned char *buf);
void repodata_set_checksum(Repodata *data, Id solvid, Id keyname, Id type,
			   const char *str);
void repodata_set_idarray(Repodata *data, Id solvid, Id keyname, Queue *q);

/* directory (for package file list) */
void repodata_add_dirnumnum(Repodata *data, Id solvid, Id keyname, Id dir, Id num, Id num2);
void repodata_add_dirstr(Repodata *data, Id solvid, Id keyname, Id dir, const char *str);
void repodata_free_dircache(Repodata *data);


/* arrays */
void repodata_add_idarray(Repodata *data, Id solvid, Id keyname, Id id);
void repodata_add_poolstr_array(Repodata *data, Id solvid, Id keyname, const char *str);
void repodata_add_fixarray(Repodata *data, Id solvid, Id keyname, Id ghandle);
void repodata_add_flexarray(Repodata *data, Id solvid, Id keyname, Id ghandle);

/* generic */
void repodata_set_kv(Repodata *data, Id solvid, Id keyname, Id keytype, struct s_KeyValue *kv);
void repodata_unset(Repodata *data, Id solvid, Id keyname);
void repodata_unset_uninternalized(Repodata *data, Id solvid, Id keyname);

/*
 merge/swap attributes from one solvable to another
 works only if the data is not yet internalized
*/
void repodata_merge_attrs(Repodata *data, Id dest, Id src);
void repodata_merge_some_attrs(Repodata *data, Id dest, Id src, Map *keyidmap, int overwrite);
void repodata_swap_attrs(Repodata *data, Id dest, Id src);

Repodata *repodata_create_stubs(Repodata *data);

/*
 * load all paged data, used to speed up copying in repo_rpmdb
 */
void repodata_disable_paging(Repodata *data);

/* helper functions */
Id repodata_globalize_id(Repodata *data, Id id, int create);
Id repodata_localize_id(Repodata *data, Id id, int create);
Id repodata_translate_id(Repodata *data, Repodata *fromdata, Id id, int create);
Id repodata_translate_dir_slow(Repodata *data, Repodata *fromdata, Id dir, int create, Id *cache);

Id repodata_str2dir(Repodata *data, const char *dir, int create);
const char *repodata_dir2str(Repodata *data, Id did, const char *suf);
const char *repodata_chk2str(Repodata *data, Id type, const unsigned char *buf);
void repodata_set_location(Repodata *data, Id solvid, int medianr, const char *dir, const char *file);
void repodata_set_deltalocation(Repodata *data, Id handle, int medianr, const char *dir, const char *file);
void repodata_set_sourcepkg(Repodata *data, Id solvid, const char *sourcepkg);

/* uninternalized data lookup / search */
Repokey *repodata_lookup_kv_uninternalized(Repodata *data, Id solvid, Id keyname, struct s_KeyValue *kv);
void repodata_search_uninternalized(Repodata *data, Id solvid, Id keyname, int flags, int (*callback)(void *cbdata, Solvable *s, Repodata *data, Repokey *key, struct s_KeyValue *kv), void *cbdata);

/* stats */
unsigned int repodata_memused(Repodata *data);

static inline Id
repodata_translate_dir(Repodata *data, Repodata *fromdata, Id dir, int create, Id *cache)
{
  if (cache && dir && cache[(dir & 255) * 2] == dir)
    return cache[(dir & 255) * 2 + 1];
  return repodata_translate_dir_slow(data, fromdata, dir, create, cache);
}

static inline Id *
repodata_create_dirtranscache(Repodata *data)
{
  return (Id *)solv_calloc(256, sizeof(Id) * 2);
}

static inline Id *
repodata_free_dirtranscache(Id *cache)
{
  return (Id *)solv_free(cache);
}


#ifdef __cplusplus
}
#endif

#endif /* LIBSOLV_REPODATA_H */
