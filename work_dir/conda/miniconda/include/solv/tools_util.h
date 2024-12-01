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

#ifndef LIBSOLV_TOOLS_UTIL_H
#define LIBSOLV_TOOLS_UTIL_H

static inline Id
makeevr(Pool *pool, const char *s)
{
  if (!strncmp(s, "0:", 2) && s[2])
    s += 2;
  return pool_str2id(pool, s, 1);
}

/**
 * split a string
 */
#ifndef DISABLE_SPLIT
static int
split(char *l, char **sp, int m)
{
  int i;
  for (i = 0; i < m;)
    {
      while (*l == ' ')
        l++;
      if (!*l)
        break;
      sp[i++] = l;
      while (*l && *l != ' ')
        l++;
      if (!*l)
        break;
      *l++ = 0;
    }
  return i;
}
#endif

#ifndef DISABLE_JOIN2

struct joindata {
  char *tmp;
  int tmpl;
};

/* this join does not depend on parsedata */
static char *
join2(struct joindata *jd, const char *s1, const char *s2, const char *s3)
{
  int l = 1;
  char *p;

  if (s1)
    l += strlen(s1);
  if (s2)
    l += strlen(s2);
  if (s3)
    l += strlen(s3);
  if (l > jd->tmpl)
    {
      jd->tmpl = l + 256;
      jd->tmp = solv_realloc(jd->tmp, jd->tmpl);
    }
  p = jd->tmp;
  if (s1)
    {
      strcpy(p, s1);
      p += strlen(s1);
    }
  if (s2)
    {
      strcpy(p, s2);
      p += strlen(s2);
    }
  if (s3)
    {
      strcpy(p, s3);
      p += strlen(s3);
    }
  *p = 0;
  return jd->tmp;
}

static inline char *
join_dup(struct joindata *jd, const char *s)
{
  return s ? join2(jd, s, 0, 0) : 0;
}

static inline void
join_freemem(struct joindata *jd)
{
  if (jd->tmp)
    free(jd->tmp);
  jd->tmp = 0;
  jd->tmpl = 0;
}

#endif

#endif /* LIBSOLV_TOOLS_UTIL_H */
