/*
 * Copyright (c) 2007, Novell Inc.
 *
 * This program is licensed under the BSD license, read LICENSE.BSD
 * for further information
 */

/*
 * util.h
 *
 */

#ifndef LIBSOLV_UTIL_H
#define LIBSOLV_UTIL_H

#include <stddef.h>
#include <string.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * malloc
 * exits with error message on error
 */
extern void *solv_malloc(size_t);
extern void *solv_malloc2(size_t, size_t);
extern void *solv_calloc(size_t, size_t);
extern void *solv_realloc(void *, size_t);
extern void *solv_realloc2(void *, size_t, size_t);
extern void *solv_extend_realloc(void *, size_t, size_t, size_t);
extern void *solv_free(void *);
extern char *solv_strdup(const char *);
extern void solv_oom(size_t, size_t);
extern unsigned int solv_timems(unsigned int subtract);
extern int solv_setcloexec(int fd, int state);
extern void solv_sort(void *base, size_t nmemb, size_t size, int (*compar)(const void *, const void *, void *), void *compard);
extern char *solv_dupjoin(const char *str1, const char *str2, const char *str3);
extern char *solv_dupappend(const char *str1, const char *str2, const char *str3);
extern int solv_hex2bin(const char **strp, unsigned char *buf, int bufl);
extern char *solv_bin2hex(const unsigned char *buf, int l, char *str);
extern size_t solv_validutf8(const char *buf);
extern char *solv_latin1toutf8(const char *buf);
extern char *solv_replacebadutf8(const char *buf, int replchar);


static inline void *solv_extend(void *buf, size_t len, size_t nmemb, size_t size, size_t block)
{
  if (nmemb == 1)
    {
      if ((len & block) == 0)
	buf = solv_extend_realloc(buf, len + 1, size, block);
    }
  else
    {
      if (((len - 1) | block) != ((len + nmemb - 1) | block))
	buf = solv_extend_realloc(buf, len + nmemb, size, block);
    }
  return buf;
}

/**
 * extend an array by reallocation and zero's the new section
 * buf old pointer
 * len current size
 * nmbemb number of elements to add
 * size size of each element
 * block block size used to allocate the elements
 */
static inline void *solv_zextend(void *buf, size_t len, size_t nmemb, size_t size, size_t block)
{
  buf = solv_extend(buf, len, nmemb, size, block);
  memset((char *)buf + len * size, 0, nmemb * size);
  return buf;
}

static inline void *solv_extend_resize(void *buf, size_t len, size_t size, size_t block)
{
  if (len)
    buf = solv_extend_realloc(buf, len, size, block);
  return buf;
}

static inline void *solv_calloc_block(size_t len, size_t size, size_t block)
{
  void *buf;
  if (!len)
    return 0;
  buf = solv_extend_realloc((void *)0, len, size, block);
  memset(buf, 0, ((len + block) & ~block) * size);
  return buf;
}

static inline void *solv_memdup(const void *buf, size_t len)
{
  void *newbuf;
  if (!buf)
    return 0;
  newbuf = solv_malloc(len);
  if (len)
    memcpy(newbuf, buf, len);
  return newbuf;
}

static inline void *solv_memdup2(const void *buf, size_t num, size_t len)
{
  void *newbuf;
  if (!buf)
    return 0;
  newbuf = solv_malloc2(num, len);
  if (num)
    memcpy(newbuf, buf, num * len);
  return newbuf;
}

#ifdef __cplusplus
}
#endif

#endif /* LIBSOLV_UTIL_H */
