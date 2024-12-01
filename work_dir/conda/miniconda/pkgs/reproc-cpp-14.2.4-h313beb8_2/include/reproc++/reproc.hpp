#pragma once

#include <chrono>
#include <cstdint>
#include <cstdio>
#include <memory>
#include <system_error>
#include <utility>

#include <reproc++/arguments.hpp>
#include <reproc++/env.hpp>
#include <reproc++/export.hpp>
#include <reproc++/input.hpp>

// Forward declare `reproc_t` so we don't have to include reproc.h in the
// header.
struct reproc_t;

/*! The `reproc` namespace wraps all reproc++ declarations. `process` wraps
reproc's API inside a C++ class. To avoid exposing reproc's API when using
reproc++ all structs, enums and constants of reproc have a replacement in
reproc++. Only differences in behaviour compared to reproc are documented. Refer
to reproc.h and the examples for general information on how to use reproc. */
namespace reproc {

/*! Conversion from reproc `errno` constants to `std::errc` constants:
https://en.cppreference.com/w/cpp/error/errc */
using error = std::errc;

namespace signal {

REPROCXX_EXPORT extern const int kill;
REPROCXX_EXPORT extern const int terminate;

}

/*! Timeout values are passed as `reproc::milliseconds` instead of `int` in
reproc++. */
using milliseconds = std::chrono::duration<int, std::milli>;

REPROCXX_EXPORT extern const milliseconds infinite;
REPROCXX_EXPORT extern const milliseconds deadline;

enum class stop {
  noop,
  wait,
  terminate,
  kill,
};

struct stop_action {
  stop action;
  milliseconds timeout;
};

struct stop_actions {
  stop_action first;
  stop_action second;
  stop_action third;
};

#if defined(_WIN32)
using handle = void *;
#else
using handle = int;
#endif

struct redirect {
  enum type {
    default_, // Unfortunately, both `default` and `auto` are keywords.
    pipe,
    parent,
    discard,
    // stdout would conflict with a macro on Windows.
    stdout_,
    // Unfortunately, class members and nested enum members can't have the same
    // name.
    handle_,
    file_,
    path_,
  };

  enum type type;
  reproc::handle handle;
  FILE *file;
  const char *path;
};

struct options {
  struct {
    env::type behavior;
    /*! Implicitly converts from any STL container of string pairs to the
    environment format expected by `reproc_start`. */
    class env extra;
  } env = {};

  const char *working_directory = nullptr;

  struct {
    redirect in;
    redirect out;
    redirect err;
    bool parent;
    bool discard;
    FILE *file;
    const char *path;
  } redirect = {};

  struct stop_actions stop = {};
  reproc::milliseconds timeout = reproc::milliseconds(0);
  reproc::milliseconds deadline = reproc::milliseconds(0);
  /*! Implicitly converts from string literals to the pointer size pair expected
  by `reproc_start`. */
  class input input;
  bool nonblocking = false;

  /*! Make a shallow copy of `options`. */
  static options clone(const options &other)
  {
    struct options clone;
    clone.env.behavior = other.env.behavior;
    // Make sure we make a shallow copy of `environment`.
    clone.env.extra = other.env.extra.data();
    clone.working_directory = other.working_directory;
    clone.redirect = other.redirect;
    clone.stop = other.stop;
    clone.timeout = other.timeout;
    clone.deadline = other.deadline;
    clone.input = other.input;

    return clone;
  }
};

enum class stream {
  in,
  out,
  err,
};

class process;

namespace event {

enum {
  in = 1 << 0,
  out = 1 << 1,
  err = 1 << 2,
  exit = 1 << 3,
  deadline = 1 << 4,
};

struct source {
  class process &process;
  int interests;
  int events;
};

}

REPROCXX_EXPORT std::error_code poll(event::source *sources,
                                     size_t num_sources,
                                     milliseconds timeout = infinite);

/*! Improves on reproc's API by adding RAII and changing the API of some
functions to be more idiomatic C++. */
class process {

public:
  REPROCXX_EXPORT process();
  REPROCXX_EXPORT ~process() noexcept;

  // Enforce unique ownership of child processes.
  REPROCXX_EXPORT process(process &&other) noexcept;
  REPROCXX_EXPORT process &operator=(process &&other) noexcept;

  /*! `reproc_start` but implicitly converts from STL containers to the
  arguments format expected by `reproc_start`. */
  REPROCXX_EXPORT std::error_code start(const arguments &arguments,
                                        const options &options = {}) noexcept;

  REPROCXX_EXPORT std::pair<int, std::error_code> pid() noexcept;

  /*! Sets the `fork` option in `reproc_options` and calls `start`. Returns
  `true` in the child process and `false` in the parent process. */
  REPROCXX_EXPORT std::pair<bool, std::error_code>
  fork(const options &options = {}) noexcept;

  /*! Shorthand for `reproc::poll` that only polls this process. Returns a pair
  of (events, error). */
  REPROCXX_EXPORT std::pair<int, std::error_code>
  poll(int interests, milliseconds timeout = infinite);

  /*! `reproc_read` but returns a pair of (bytes read, error). */
  REPROCXX_EXPORT std::pair<size_t, std::error_code>
  read(stream stream, uint8_t *buffer, size_t size) noexcept;

  /*! reproc_write` but returns a pair of (bytes_written, error). */
  REPROCXX_EXPORT std::pair<size_t, std::error_code>
  write(const uint8_t *buffer, size_t size) noexcept;

  REPROCXX_EXPORT std::error_code close(stream stream) noexcept;

  /*! `reproc_wait` but returns a pair of (status, error). */
  REPROCXX_EXPORT std::pair<int, std::error_code>
  wait(milliseconds timeout) noexcept;

  REPROCXX_EXPORT std::error_code terminate() noexcept;

  REPROCXX_EXPORT std::error_code kill() noexcept;

  /*! `reproc_stop` but returns a pair of (status, error). */
  REPROCXX_EXPORT std::pair<int, std::error_code>
  stop(stop_actions stop) noexcept;

private:
  REPROCXX_EXPORT friend std::error_code
  poll(event::source *sources, size_t num_sources, milliseconds timeout);

  std::unique_ptr<reproc_t, reproc_t *(*) (reproc_t *)> impl_;
};

}
