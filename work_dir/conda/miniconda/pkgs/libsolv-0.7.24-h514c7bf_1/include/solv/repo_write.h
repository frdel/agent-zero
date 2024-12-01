/*
 * Copyright (c) 2007, Novell Inc.
 *
 * This program is licensed under the BSD license, read LICENSE.BSD
 * for further information
 */

/*
 * repo_write.h
 *
 */

#ifndef REPO_WRITE_H
#define REPO_WRITE_H

#include <stdio.h>

#include "repo.h"
#include "queue.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct s_Repowriter {
  Repo *repo;
  int flags;
  int repodatastart;
  int repodataend;
  int solvablestart;
  int solvableend;
  int (*keyfilter)(Repo *repo, Repokey *key, void *kfdata);
  void *kfdata;
  Queue *keyq;
  void *userdata;
  int userdatalen;
} Repowriter;

/* repowriter flags */
#define REPOWRITER_NO_STORAGE_SOLVABLE	(1 << 0)
#define REPOWRITER_KEEP_TYPE_DELETED	(1 << 1)
#define REPOWRITER_LEGACY		(1 << 30)

Repowriter *repowriter_create(Repo *repo);
Repowriter *repowriter_free(Repowriter *writer);
void repowriter_set_flags(Repowriter *writer, int flags);
void repowriter_set_keyfilter(Repowriter *writer, int (*keyfilter)(Repo *repo, Repokey *key, void *kfdata), void *kfdata);
void repowriter_set_keyqueue(Repowriter *writer, Queue *keyq);
void repowriter_set_repodatarange(Repowriter *writer, int repodatastart, int repodataend);
void repowriter_set_solvablerange(Repowriter *writer, int solvablestart, int solvableend);
void repowriter_set_userdata(Repowriter *writer, const void *data, int len);
int repowriter_write(Repowriter *writer, FILE *fp);

/* convenience functions */
extern int repo_write(Repo *repo, FILE *fp);
extern int repodata_write(Repodata *data , FILE *fp);

extern int repo_write_stdkeyfilter(Repo *repo, Repokey *key, void *kfdata);

/* deprecated functions, do not use in new code! */
extern int repo_write_filtered(Repo *repo, FILE *fp, int (*keyfilter)(Repo *repo, Repokey *key, void *kfdata), void *kfdata, Queue *keyq);
extern int repodata_write_filtered(Repodata *data , FILE *fp, int (*keyfilter)(Repo *repo, Repokey *key, void *kfdata), void *kfdata, Queue *keyq);

#ifdef __cplusplus
}
#endif

#endif
