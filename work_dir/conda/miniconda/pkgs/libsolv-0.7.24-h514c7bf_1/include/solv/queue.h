/*
 * Copyright (c) 2007, Novell Inc.
 *
 * This program is licensed under the BSD license, read LICENSE.BSD
 * for further information
 */

/*
 * queue.h
 *
 */

#ifndef LIBSOLV_QUEUE_H
#define LIBSOLV_QUEUE_H

#include "pooltypes.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct s_Queue {
  Id *elements;		/* pointer to elements */
  int count;		/* current number of elements in queue */
  Id *alloc;		/* this is whats actually allocated, elements > alloc if shifted */
  int left;		/* space left in alloc *after* elements+count */
} Queue;


extern void queue_alloc_one(Queue *q);		/* internal */
extern void queue_alloc_one_head(Queue *q);	/* internal */

/* clear queue */
static inline void
queue_empty(Queue *q)
{
  if (q->alloc)
    {
      q->left += (q->elements - q->alloc) + q->count;
      q->elements = q->alloc;
    }
  else
    q->left += q->count;
  q->count = 0;
}

static inline Id
queue_shift(Queue *q)
{
  if (!q->count)
    return 0;
  q->count--;
  return *q->elements++;
}

static inline Id
queue_pop(Queue *q)
{
  if (!q->count)
    return 0;
  q->left++;
  return q->elements[--q->count];
}

static inline void
queue_unshift(Queue *q, Id id)
{
  if (!q->alloc || q->alloc == q->elements)
    queue_alloc_one_head(q);
  *--q->elements = id;
  q->count++;
}

static inline void
queue_push(Queue *q, Id id)
{
  if (!q->left)
    queue_alloc_one(q);
  q->elements[q->count++] = id;
  q->left--;
}

static inline void
queue_pushunique(Queue *q, Id id)
{
  int i;
  for (i = q->count; i > 0; )
    if (q->elements[--i] == id)
      return;
  queue_push(q, id);
}

static inline void
queue_push2(Queue *q, Id id1, Id id2)
{
  queue_push(q, id1);
  queue_push(q, id2);
}

static inline void
queue_truncate(Queue *q, int n)
{
  if (q->count > n)
    {
      q->left += q->count - n;
      q->count = n;
    }
}

extern void queue_init(Queue *q);
extern void queue_init_buffer(Queue *q, Id *buf, int size);
extern void queue_init_clone(Queue *target, const Queue *source);
extern void queue_free(Queue *q);

extern void queue_insert(Queue *q, int pos, Id id);
extern void queue_insert2(Queue *q, int pos, Id id1, Id id2);
extern void queue_insertn(Queue *q, int pos, int n, const Id *elements);
extern void queue_delete(Queue *q, int pos);
extern void queue_delete2(Queue *q, int pos);
extern void queue_deleten(Queue *q, int pos, int n);
extern void queue_prealloc(Queue *q, int n);

#ifdef __cplusplus
}
#endif

#endif /* LIBSOLV_QUEUE_H */
