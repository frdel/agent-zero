#pragma once

#include <reproc/drain.h>
#include <reproc/reproc.h>

#ifdef __cplusplus
extern "C" {
#endif

/*! Sets `options.redirect.parent = true` unless `discard` is set and calls
`reproc_run_ex` with `REPROC_SINK_NULL` for the `out` and `err` sinks. */
REPROC_EXPORT int reproc_run(const char *const *argv, reproc_options options);

/*!
Wrapper function that starts a process with the given arguments, drain its
output and waits until it exits. Have a look at its (trivial) implementation and
the documentation of the functions it calls to see exactly what it does:
https://github.com/DaanDeMeyer/reproc/blob/master/reproc/src/run.c
*/
REPROC_EXPORT int reproc_run_ex(const char *const *argv,
                                reproc_options options,
                                reproc_sink out,
                                reproc_sink err);

#ifdef __cplusplus
}
#endif
