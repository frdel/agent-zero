/*
 * Copyright (c) 2007, Novell Inc.
 *
 * This program is licensed under the BSD license, read LICENSE.BSD
 * for further information
 */
#ifndef LIBSOLV_STRINGPOOL_H
#define LIBSOLV_STRINGPOOL_H

#include "pooltypes.h"
#include "hash.h"

#ifdef __cplusplus
extern "C" {
#endif

#define STRID_NULL  0
#define STRID_EMPTY 1

struct s_Stringpool
{
  Offset *strings;            /* table of offsets into stringspace, indexed by Id: Id -> Offset */
  int nstrings;               /* number of ids in strings table */
  char *stringspace;          /* space for all unique strings: stringspace + Offset = string */
  Offset sstrings;            /* size of used stringspace */

  Hashtable stringhashtbl;    /* hash table: (string ->) Hash -> Id */
  Hashval stringhashmask;     /* modulo value for hash table (size of table - 1) */
};

void stringpool_init(Stringpool *ss, const char *strs[]);
void stringpool_init_empty(Stringpool *ss);
void stringpool_clone(Stringpool *ss, Stringpool *from);
void stringpool_free(Stringpool *ss);
void stringpool_freehash(Stringpool *ss);
void stringpool_resize_hash(Stringpool *ss, int numnew);

Id stringpool_str2id(Stringpool *ss, const char *str, int create);
Id stringpool_strn2id(Stringpool *ss, const char *str, unsigned int len, int create);

void stringpool_shrink(Stringpool *ss);


static inline const char *
stringpool_id2str(Stringpool *ss, Id id)
{
  return ss->stringspace + ss->strings[id];
}

#ifdef __cplusplus
}
#endif

#endif
