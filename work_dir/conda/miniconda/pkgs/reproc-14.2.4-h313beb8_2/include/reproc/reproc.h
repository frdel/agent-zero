#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

#include <reproc/export.h>

#ifdef __cplusplus
extern "C" {
#endif

/*! Used to store information about a child process. `reproc_t` is an opaque
type and can be allocated and released via `reproc_new` and `reproc_destroy`
respectively. */
typedef struct reproc_t reproc_t;

/*! reproc error naming follows POSIX errno naming prefixed with `REPROC`. */

/*! An invalid argument was passed to an API function */
REPROC_EXPORT extern const int REPROC_EINVAL;
/*! A timeout value passed to an API function expired. */
REPROC_EXPORT extern const int REPROC_ETIMEDOUT;
/*! The child process closed one of its streams (and in the case of
stdout/stderr all of the data remaining in that stream has been read). */
REPROC_EXPORT extern const int REPROC_EPIPE;
/*! A memory allocation failed. */
REPROC_EXPORT extern const int REPROC_ENOMEM;
/*! A call to `reproc_read` or `reproc_write` would have blocked. */
REPROC_EXPORT extern const int REPROC_EWOULDBLOCK;

/*! Signal exit status constants. */

REPROC_EXPORT extern const int REPROC_SIGKILL;
REPROC_EXPORT extern const int REPROC_SIGTERM;

/*! Tells a function that takes a timeout value to wait indefinitely. */
REPROC_EXPORT extern const int REPROC_INFINITE;
/*! Tells `reproc_wait` to wait until the deadline passed to `reproc_start`
expires. */
REPROC_EXPORT extern const int REPROC_DEADLINE;

/*! Stream identifiers used to indicate which stream to act on. */
typedef enum {
  /*! stdin */
  REPROC_STREAM_IN,
  /*! stdout */
  REPROC_STREAM_OUT,
  /*! stderr */
  REPROC_STREAM_ERR,
} REPROC_STREAM;

/*! Used to tell reproc where to redirect the streams of the child process. */
typedef enum {
  /*! Use the default redirect behavior, see the documentation for `redirect` in
  `reproc_options`. */
  REPROC_REDIRECT_DEFAULT,
  /*! Redirect to a pipe. */
  REPROC_REDIRECT_PIPE,
  /*! Redirect to the corresponding stream from the parent process. */
  REPROC_REDIRECT_PARENT,
  /*! Redirect to /dev/null (or NUL on Windows). */
  REPROC_REDIRECT_DISCARD,
  /*! Redirect to child process stdout. Only valid for stderr. */
  REPROC_REDIRECT_STDOUT,
  /*! Redirect to a handle (fd on Linux, HANDLE/SOCKET on Windows). */
  REPROC_REDIRECT_HANDLE,
  /*! Redirect to a `FILE *`. */
  REPROC_REDIRECT_FILE,
  /*! Redirect to a specific path. */
  REPROC_REDIRECT_PATH,
} REPROC_REDIRECT;

/*! Used to tell `reproc_stop` how to stop a child process. */
typedef enum {
  /*! noop (no operation) */
  REPROC_STOP_NOOP,
  /*! `reproc_wait` */
  REPROC_STOP_WAIT,
  /*! `reproc_terminate` */
  REPROC_STOP_TERMINATE,
  /*! `reproc_kill` */
  REPROC_STOP_KILL,
} REPROC_STOP;

typedef struct reproc_stop_action {
  REPROC_STOP action;
  int timeout;
} reproc_stop_action;

typedef struct reproc_stop_actions {
  reproc_stop_action first;
  reproc_stop_action second;
  reproc_stop_action third;
} reproc_stop_actions;

// clang-format off

#define REPROC_STOP_ACTIONS_NULL (reproc_stop_actions) {                       \
  { REPROC_STOP_NOOP, 0 },                                                     \
  { REPROC_STOP_NOOP, 0 },                                                     \
  { REPROC_STOP_NOOP, 0 },                                                     \
}

// clang-format on

#if defined(_WIN32)
typedef void *reproc_handle; // `HANDLE`
#else
typedef int reproc_handle; // fd
#endif

typedef struct reproc_redirect {
  /*! Type of redirection. */
  REPROC_REDIRECT type;
  /*!
  Redirect a stream to an operating system handle. The given handle must be in
  blocking mode ( `O_NONBLOCK` and `OVERLAPPED` handles are not supported).

  Note that reproc does not take ownership of the handle. The user is
  responsible for closing the handle after passing it to `reproc_start`. Since
  the operating system will copy the handle to the child process, the handle
  can be closed immediately after calling `reproc_start` if the handle is not
  needed in the parent process anymore.

  If `handle` is set, `type` must be unset or set to `REPROC_REDIRECT_HANDLE`
  and `file`, `path` must be unset.
  */
  reproc_handle handle;
  /*!
  Redirect a stream to a file stream.

  Note that reproc does not take ownership of the file. The user is
  responsible for closing the file after passing it to `reproc_start`. Just
  like with `handles`, the operating system will copy the file handle to the
  child process so the file can be closed immediately after calling
  `reproc_start` if it isn't needed anymore by the parent process.

  Any file passed to `file.in` must have been opened in read mode. Likewise,
  any files passed to `file.out` or `file.err` must have been opened in write
  mode.

  If `file` is set, `type` must be unset or set to `REPROC_REDIRECT_FILE` and
  `handle`, `path` must be unset.
  */
  FILE *file;
  /*!
  Redirect a stream to a given path.

  reproc will create or open the file at the given path. Depending on the
  stream, the file is opened in read or write mode.

  If `path` is set, `type` must be unset or set to `REPROC_REDIRECT_PATH` and
  `handle`, `file` must be unset.
  */
  const char *path;
} reproc_redirect;

typedef enum {
  REPROC_ENV_EXTEND,
  REPROC_ENV_EMPTY,
} REPROC_ENV;

typedef struct reproc_options {
  /*!
  `working_directory` specifies the working directory for the child process. If
  `working_directory` is `NULL`, the child process runs in the working directory
  of the parent process.
  */
  const char *working_directory;

  struct {
    /*!
    `behavior` specifies whether the child process should start with a copy of
    the parent process environment variables or an empty environment. By
    default, the child process starts with a copy of the parent's environment
    variables (`REPROC_ENV_EXTEND`). If `behavior` is set to `REPROC_ENV_EMPTY`,
    the child process starts with an empty environment.
    */
    REPROC_ENV behavior;
    /*!
    `extra` is an array of UTF-8 encoded, NUL-terminated strings that specifies
    extra environment variables for the child process. It has the following
    layout:

    - All elements except the final element must be of the format `NAME=VALUE`.
    - The final element must be `NULL`.

    Example: ["IP=127.0.0.1", "PORT=8080", `NULL`]

    If `env` is `NULL`, no extra environment variables are added to the
    environment of the child process.
    */
    const char *const *extra;
  } env;
  /*!
  `redirect` specifies where to redirect the streams from the child process.

  By default each stream is redirected to a pipe which can be written to (stdin)
  or read from (stdout/stderr) using `reproc_write` and `reproc_read`
  respectively.
  */
  struct {
    /*!
    `in`, `out` and `err` specify where to redirect the standard I/O streams of
    the child process. When not set, `in` and `out` default to
    `REPROC_REDIRECT_PIPE` while `err` defaults to `REPROC_REDIRECT_PARENT`.
    */
    reproc_redirect in;
    reproc_redirect out;
    reproc_redirect err;
    /*!
    Use `REPROC_REDIRECT_PARENT` instead of `REPROC_REDIRECT_PIPE` when `type`
    is unset.

    When this option is set, `discard`, `file` and `path` must be unset.
    */
    bool parent;
    /*!
    Use `REPROC_REDIRECT_DISCARD` instead of `REPROC_REDIRECT_PIPE` when `type`
    is unset.

    When this option is set, `parent`, `file` and `path` must be unset.
    */
    bool discard;
    /*!
    Shorthand for redirecting stdout and stderr to the same file.

    If this option is set, `out`, `err`, `parent`, `discard` and `path` must be
    unset.
    */
    FILE *file;
    /*!
    Shorthand for redirecting stdout and stderr to the same path.

    If this option is set, `out`, `err`, `parent`, `discard` and `file` must be
    unset.
    */
    const char *path;
  } redirect;
  /*!
  Stop actions that are passed to `reproc_stop` in `reproc_destroy` to stop the
  child process. See `reproc_stop` for more information on how `stop` is
  interpreted.
  */
  reproc_stop_actions stop;
  /*!
  Maximum allowed duration in milliseconds the process is allowed to run in
  milliseconds. If the deadline is exceeded, Any ongoing and future calls to
  `reproc_poll` return `REPROC_ETIMEDOUT`.

  Note that only `reproc_poll` takes the deadline into account. More
  specifically, if the `nonblocking` option is not enabled, `reproc_read` and
  `reproc_write` can deadlock waiting on the child process to perform I/O. If
  this is a problem, enable the `nonblocking` option and use `reproc_poll`
  together with a deadline/timeout to avoid any deadlocks.

  If `REPROC_DEADLINE` is passed as the timeout to `reproc_wait`, it waits until
  the deadline expires.

  When `deadline` is zero, no deadline is set for the process.
  */
  int deadline;
  /*!
  `input` is written to the stdin pipe before the child process is started.

  Because `input` is written to the stdin pipe before the process starts,
  `input.size` must be smaller than the system's default pipe size (64KB).

  If `input` is set, the stdin pipe is closed after `input` is written to it.

  If `redirect.in` is set, this option may not be set.
  */
  struct {
    const uint8_t *data;
    size_t size;
  } input;
  /*!
  This option can only be used on POSIX systems. If enabled on Windows, an error
  will be returned.

  If `fork` is enabled, `reproc_start` forks a child process and returns 0 in
  the child process and > 0 in the parent process. In the child process, only
  `reproc_destroy` may be called on the `reproc_t` instance to free its
  associated memory.

  When `fork` is enabled. `argv` must be `NULL` when calling `reproc_start`.
  */
  bool fork;
  /*!
  Put pipes created by reproc in nonblocking mode. This makes `reproc_read` and
  `reproc_write` nonblocking operations. If needed, use `reproc_poll` to wait
  until streams becomes readable/writable.
  */
  bool nonblocking;
} reproc_options;

enum {
  /*! Data can be written to stdin. */
  REPROC_EVENT_IN = 1 << 0,
  /*! Data can be read from stdout. */
  REPROC_EVENT_OUT = 1 << 1,
  /*! Data can be read from stderr. */
  REPROC_EVENT_ERR = 1 << 2,
  /*! The process finished running. */
  REPROC_EVENT_EXIT = 1 << 3,
  /*! The deadline of the process expired. This event is added by default to the
  list of interested events. */
  REPROC_EVENT_DEADLINE = 1 << 4,
};

typedef struct reproc_event_source {
  /*! Process to poll for events. */
  reproc_t *process;
  /*! Events of the process that we're interested in. Takes a combo of
  `REPROC_EVENT` flags. */
  int interests;
  /*! Combo of `REPROC_EVENT` flags that indicate the events that occurred. This
  field is filled in by `reproc_poll`. */
  int events;
} reproc_event_source;

/*! Allocate a new `reproc_t` instance on the heap. */
REPROC_EXPORT reproc_t *reproc_new(void);

/*!
Starts the process specified by `argv` in the given working directory and
redirects its input, output and error streams.

If this function does not return an error the child process will have started
running and can be inspected using the operating system's tools for process
inspection (e.g. ps on Linux).

Every successful call to this function should be followed by a successful call
to `reproc_wait` or `reproc_stop` and a call to `reproc_destroy`. If an error
occurs during `reproc_start` all allocated resources are cleaned up before
`reproc_start` returns and no further action is required.

`argv` is an array of UTF-8 encoded, NUL-terminated strings that specifies the
program to execute along with its arguments. It has the following layout:

- The first element indicates the executable to run as a child process. This can
be an absolute path, a path relative to the working directory of the parent
process or the name of an executable located in the PATH. It cannot be `NULL`.
- The following elements indicate the whitespace delimited arguments passed to
the executable. None of these elements can be `NULL`.
- The final element must be `NULL`.

Example: ["cmake", "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release", `NULL`]
*/
REPROC_EXPORT int reproc_start(reproc_t *process,
                               const char *const *argv,
                               reproc_options options);

/*!
Returns the process ID of the child or `REPROC_EINVAL` on error.

Note that if `reproc_wait` has been called successfully on this process already,
the returned pid will be that of the just ended child process. The operating
system will have cleaned up the resources allocated to the process
and the operating system is free to reuse the same pid for another process.

Generally, only pass the result of this function to system calls that need a
valid pid if `reproc_wait` hasn't been called successfully on the process yet.
*/
REPROC_EXPORT int reproc_pid(reproc_t *process);

/*!
Polls each process in `sources` for its corresponding events in `interests` and
stores events that occurred for each process in `events`. If an event source
process member is `NULL`, the event source is ignored.

Pass `REPROC_INFINITE` to `timeout` to have `reproc_poll` wait forever for an
event to occur.

If one or more events occur, returns the number of processes with events. If the
timeout expires, returns zero. Returns `REPROC_EPIPE` if none of the sources
have valid pipes remaining that can be polled.

Actionable errors:
- `REPROC_EPIPE`
*/
REPROC_EXPORT int
reproc_poll(reproc_event_source *sources, size_t num_sources, int timeout);

/*!
Reads up to `size` bytes into `buffer` from the child process output stream
indicated by `stream`.

Actionable errors:
- `REPROC_EPIPE`
- `REPROC_EWOULDBLOCK`
*/
REPROC_EXPORT int reproc_read(reproc_t *process,
                              REPROC_STREAM stream,
                              uint8_t *buffer,
                              size_t size);

/*!
Writes up to `size` bytes from `buffer` to the standard input (stdin) of the
child process.

(POSIX) By default, writing to a closed stdin pipe terminates the parent process
with the `SIGPIPE` signal. `reproc_write` will only return `REPROC_EPIPE` if
this signal is ignored by the parent process.

Returns the amount of bytes written. If `buffer` is `NULL` and `size` is zero,
this function returns 0.

If the standard input of the child process wasn't opened with
`REPROC_REDIRECT_PIPE`, this function returns `REPROC_EPIPE` unless `buffer` is
`NULL` and `size` is zero.

Actionable errors:
- `REPROC_EPIPE`
- `REPROC_EWOULDBLOCK`
*/
REPROC_EXPORT int
reproc_write(reproc_t *process, const uint8_t *buffer, size_t size);

/*!
Closes the child process standard stream indicated by `stream`.

This function is necessary when a child process reads from stdin until it is
closed. After writing all the input to the child process using `reproc_write`,
the standard input stream can be closed using this function.
*/
REPROC_EXPORT int reproc_close(reproc_t *process, REPROC_STREAM stream);

/*!
Waits `timeout` milliseconds for the child process to exit. If the child process
has already exited or exits within the given timeout, its exit status is
returned.

If `timeout` is 0, the function will only check if the child process is still
running without waiting. If `timeout` is `REPROC_INFINITE`, this function will
wait indefinitely for the child process to exit. If `timeout` is
`REPROC_DEADLINE`, this function waits until the deadline passed to
`reproc_start` expires.

Actionable errors:
- `REPROC_ETIMEDOUT`
*/
REPROC_EXPORT int reproc_wait(reproc_t *process, int timeout);

/*!
Sends the `SIGTERM` signal (POSIX) or the `CTRL-BREAK` signal (Windows) to the
child process. Remember that successful calls to `reproc_wait` and
`reproc_destroy` are required to make sure the child process is completely
cleaned up.
*/
REPROC_EXPORT int reproc_terminate(reproc_t *process);

/*!
Sends the `SIGKILL` signal to the child process (POSIX) or calls
`TerminateProcess` (Windows) on the child process. Remember that successful
calls to `reproc_wait` and `reproc_destroy` are required to make sure the child
process is completely cleaned up.
*/
REPROC_EXPORT int reproc_kill(reproc_t *process);

/*!
Simplifies calling combinations of `reproc_wait`, `reproc_terminate` and
`reproc_kill`. The function executes each specified step and waits (using
`reproc_wait`) until the corresponding timeout expires before continuing with
the next step.

Example:

Wait 10 seconds for the child process to exit on its own before sending
`SIGTERM` (POSIX) or `CTRL-BREAK` (Windows) and waiting five more seconds for
the child process to exit.

```c
REPROC_ERROR error = reproc_stop(process,
                                 REPROC_STOP_WAIT, 10000,
                                 REPROC_STOP_TERMINATE, 5000,
                                 REPROC_STOP_NOOP, 0);
```

Call `reproc_wait`, `reproc_terminate` and `reproc_kill` directly if you need
extra logic such as logging between calls.

`stop` can contain up to three stop actions that instruct this function how the
child process should be stopped. The first element of each stop action specifies
which action should be called on the child process. The second element of each
stop actions specifies how long to wait after executing the operation indicated
by the first element.

When `stop` is 3x `REPROC_STOP_NOOP`, `reproc_destroy` will wait until the
deadline expires (or forever if there is no deadline). If the process is still
running after the deadline expires, `reproc_stop` then calls `reproc_terminate`
and waits forever for the process to exit.

Note that when a stop action specifies `REPROC_STOP_WAIT`, the function will
just wait for the specified timeout instead of performing an action to stop the
child process.

If the child process has already exited or exits during the execution of this
function, its exit status is returned.

Actionable errors:
- `REPROC_ETIMEDOUT`
*/
REPROC_EXPORT int reproc_stop(reproc_t *process, reproc_stop_actions stop);

/*!
Release all resources associated with `process` including the memory allocated
by `reproc_new`. Calling this function before a succesfull call to `reproc_wait`
can result in resource leaks.

Does nothing if `process` is an invalid `reproc_t` instance and always returns
an invalid `reproc_t` instance (`NULL`). By assigning the result of
`reproc_destroy` to the instance being destroyed, it can be safely called
multiple times on the same instance.

Example: `process = reproc_destroy(process)`.
*/
REPROC_EXPORT reproc_t *reproc_destroy(reproc_t *process);

/*!
Returns a string describing `error`. This string must not be modified by the
caller.
*/
REPROC_EXPORT const char *reproc_strerror(int error);

#ifdef __cplusplus
}
#endif
