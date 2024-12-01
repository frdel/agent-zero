#pragma once

#include <reproc/reproc.h>

#ifdef __cplusplus
extern "C" {
#endif

/*! Used by `reproc_drain` to provide data to the caller. Each time data is
read, `function` is called with `context`. If a sink returns a non-zero value,
`reproc_drain` will return immediately with the same value. */
typedef struct reproc_sink {
  int (*function)(REPROC_STREAM stream,
                  const uint8_t *buffer,
                  size_t size,
                  void *context);
  void *context;
} reproc_sink;

/*! Pass `REPROC_SINK_NULL` as the sink for output streams that have not been
redirected to a pipe. */
REPROC_EXPORT extern const reproc_sink REPROC_SINK_NULL;

/*!
Reads from the child process stdout and stderr until an error occurs or both
streams are closed. The `out` and `err` sinks receive the output from stdout and
stderr respectively. The same sink may be passed to both `out` and `err`.

`reproc_drain` always starts by calling both sinks once with an empty buffer and
`stream` set to `REPROC_STREAM_IN` to give each sink the chance to process all
output from the previous call to `reproc_drain` one by one.

When a stream is closed, its corresponding `sink` is called once with `size` set
to zero.

Note that his function returns 0 instead of `REPROC_EPIPE` when both output
streams of the child process are closed.

Actionable errors:
- `REPROC_ETIMEDOUT`
*/
REPROC_EXPORT int
reproc_drain(reproc_t *process, reproc_sink out, reproc_sink err);

/*!
Appends the output of a process (stdout and stderr) to the value of `output`.
`output` must point to either `NULL` or a NUL-terminated string.

Calls `realloc` as necessary to make space in `output` to store the output of
the child process. Make sure to always call `reproc_free` on the value of
`output` after calling `reproc_drain` (even if it fails).

Because the resulting sink does not store the output size, `strlen` is called
each time data is read to calculate the current size of the output. This might
cause performance problems when draining processes that produce a lot of output.

Similarly, this sink will not work on processes that have NUL terminators in
their output because `strlen` is used to calculate the current output size.

Returns `REPROC_ENOMEM` if a call to `realloc` fails. `output` will contain any
output read from the child process, preceeded by whatever was stored in it at
the moment its corresponding sink was passed to `reproc_drain`.

The `drain` example shows how to use `reproc_sink_string`.
```
*/
REPROC_EXPORT reproc_sink reproc_sink_string(char **output);

/*! Discards the output of a process. */
REPROC_EXPORT reproc_sink reproc_sink_discard(void);

/*! Calls `free` on `ptr` and returns `NULL`. Use this function to free memory
allocated by `reproc_sink_string`. This avoids issues with allocating across
module (DLL) boundaries on Windows. */
REPROC_EXPORT void *reproc_free(void *ptr);

#ifdef __cplusplus
}
#endif
