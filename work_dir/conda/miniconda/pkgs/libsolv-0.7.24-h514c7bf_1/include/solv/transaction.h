/*
 * Copyright (c) 2007-2009, Novell Inc.
 *
 * This program is licensed under the BSD license, read LICENSE.BSD
 * for further information
 */

/*
 * transaction.h
 *
 */

#ifndef LIBSOLV_TRANSACTION_H
#define LIBSOLV_TRANSACTION_H

#include "pooltypes.h"
#include "queue.h"
#include "bitmap.h"

#ifdef __cplusplus
extern "C" {
#endif

struct s_Pool;
struct s_DUChanges;
struct s_TransactionOrderdata;

typedef struct s_Transaction {
  struct s_Pool *pool;		/* back pointer to pool */

  Queue steps;			/* the transaction steps */

#ifdef LIBSOLV_INTERNAL
  Queue transaction_info;
  Id *transaction_installed;
  Map transactsmap;
  Map multiversionmap;

  struct s_TransactionOrderdata *orderdata;
#endif

} Transaction;


/* step types */
#define SOLVER_TRANSACTION_IGNORE		0x00

#define SOLVER_TRANSACTION_ERASE		0x10
#define SOLVER_TRANSACTION_REINSTALLED		0x11
#define SOLVER_TRANSACTION_DOWNGRADED		0x12
#define SOLVER_TRANSACTION_CHANGED		0x13
#define SOLVER_TRANSACTION_UPGRADED		0x14
#define SOLVER_TRANSACTION_OBSOLETED		0x15

#define SOLVER_TRANSACTION_INSTALL		0x20
#define SOLVER_TRANSACTION_REINSTALL		0x21
#define SOLVER_TRANSACTION_DOWNGRADE		0x22
#define SOLVER_TRANSACTION_CHANGE		0x23
#define SOLVER_TRANSACTION_UPGRADE		0x24
#define SOLVER_TRANSACTION_OBSOLETES		0x25

#define SOLVER_TRANSACTION_MULTIINSTALL		0x30
#define SOLVER_TRANSACTION_MULTIREINSTALL	0x31

#define SOLVER_TRANSACTION_MAXTYPE		0x3f

/* modes */
#define SOLVER_TRANSACTION_SHOW_ACTIVE		(1 << 0)
#define SOLVER_TRANSACTION_SHOW_ALL		(1 << 1)
#define SOLVER_TRANSACTION_SHOW_OBSOLETES	(1 << 2)
#define SOLVER_TRANSACTION_SHOW_MULTIINSTALL	(1 << 3)
#define SOLVER_TRANSACTION_CHANGE_IS_REINSTALL	(1 << 4)
#define SOLVER_TRANSACTION_MERGE_VENDORCHANGES	(1 << 5)
#define SOLVER_TRANSACTION_MERGE_ARCHCHANGES	(1 << 6)

#define SOLVER_TRANSACTION_RPM_ONLY		(1 << 7)

#define SOLVER_TRANSACTION_KEEP_PSEUDO		(1 << 8)

#define SOLVER_TRANSACTION_OBSOLETE_IS_UPGRADE  (1 << 9)

/* extra classifications */
#define SOLVER_TRANSACTION_ARCHCHANGE		0x100
#define SOLVER_TRANSACTION_VENDORCHANGE		0x101

/* order flags */
#define SOLVER_TRANSACTION_KEEP_ORDERDATA	(1 << 0)
#define SOLVER_TRANSACTION_KEEP_ORDERCYCLES	(1 << 1)
#define SOLVER_TRANSACTION_KEEP_ORDEREDGES	(1 << 2)

/* cycle severities */
#define SOLVER_ORDERCYCLE_HARMLESS		0
#define SOLVER_ORDERCYCLE_NORMAL		1
#define SOLVER_ORDERCYCLE_CRITICAL		2

extern Transaction *transaction_create(struct s_Pool *pool);
extern Transaction *transaction_create_decisionq(struct s_Pool *pool, Queue *decisionq, Map *multiversionmap);
extern Transaction *transaction_create_clone(Transaction *srctrans);
extern void transaction_free(Transaction *trans);

/* if p is installed, returns with pkg(s) obsolete p */
/* if p is not installed, returns with pkg(s) we obsolete */
extern Id   transaction_obs_pkg(Transaction *trans, Id p);
extern void transaction_all_obs_pkgs(Transaction *trans, Id p, Queue *pkgs);

/* return step type of a transaction element */
extern Id   transaction_type(Transaction *trans, Id p, int mode);

/* return sorted collection of all step types */
/* classify_pkgs can be used to return all packages of a type */
extern void transaction_classify(Transaction *trans, int mode, Queue *classes);
extern void transaction_classify_pkgs(Transaction *trans, int mode, Id type, Id from, Id to, Queue *pkgs);

/* return all packages that will be installed after the transaction is run*/
/* The new packages are put at the head of the queue, the number of new
   packages is returned */
extern int transaction_installedresult(Transaction *trans, Queue *installedq);

long long transaction_calc_installsizechange(Transaction *trans);
void transaction_calc_duchanges(Transaction *trans, struct s_DUChanges *mps, int nmps);



/* order a transaction */
extern void transaction_order(Transaction *trans, int flags);

/* roll your own order funcion:
 * add pkgs free for installation to queue choices after chosen was
 * installed. start with chosen = 0
 * needs an ordered transaction created with SOLVER_TRANSACTION_KEEP_ORDERDATA */
extern int  transaction_order_add_choices(Transaction *trans, Id chosen, Queue *choices);
/* add obsoleted packages into transaction steps */
extern void transaction_add_obsoleted(Transaction *trans);

/* debug function, report problems found in the order */
extern void transaction_check_order(Transaction *trans);

/* order cycle introspection */
extern void transaction_order_get_cycleids(Transaction *trans, Queue *q, int minseverity);
extern int transaction_order_get_cycle(Transaction *trans, Id cid, Queue *q);
extern void transaction_order_get_edges(Transaction *trans, Id p, Queue *q, int unbroken);

extern void transaction_free_orderdata(Transaction *trans);
extern void transaction_clone_orderdata(Transaction *trans, Transaction *srctrans);

#ifdef __cplusplus
}
#endif

#endif
