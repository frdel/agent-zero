#pragma once

#include <mutex>
#include <ostream>
#include <string>

#include <reproc++/reproc.hpp>

namespace reproc {

/*!
`reproc_drain` but takes lambdas as sinks. Return an error code from a sink to
break out of `drain` early. `out` and `err` expect the following signature:

```c++
std::error_code sink(stream stream, const uint8_t *buffer, size_t size);
```
*/
template <typename Out, typename Err>
std::error_code drain(process &process, Out &&out, Err &&err)
{
  static constexpr uint8_t initial = 0;
  std::error_code ec;

  // A single call to `read` might contain multiple messages. By always calling
  // both sinks once with no data before reading, we give them the chance to
  // process all previous output before reading from the child process again.

  ec = out(stream::in, &initial, 0);
  if (ec) {
    return ec;
  }

  ec = err(stream::in, &initial, 0);
  if (ec) {
    return ec;
  }

  static constexpr size_t BUFFER_SIZE = 4096;
  uint8_t buffer[BUFFER_SIZE] = {};

  for (;;) {
    int events = 0;
    std::tie(events, ec) = process.poll(event::out | event::err, infinite);
    if (ec) {
      ec = ec == error::broken_pipe ? std::error_code() : ec;
      break;
    }

    if (events & event::deadline) {
      ec = std::make_error_code(std::errc::timed_out);
      break;
    }

    stream stream = events & event::out ? stream::out : stream::err;

    size_t bytes_read = 0;
    std::tie(bytes_read, ec) = process.read(stream, buffer, BUFFER_SIZE);
    if (ec && ec != error::broken_pipe) {
      break;
    }

    bytes_read = ec == error::broken_pipe ? 0 : bytes_read;

    // This used to be `auto &sink = stream == stream::out ? out : err;` but
    // that doesn't actually work if `out` and `err` are not the same type.
    if (stream == stream::out) {
      ec = out(stream, buffer, bytes_read);
    } else {
      ec = err(stream, buffer, bytes_read);
    }

    if (ec) {
      break;
    }
  }

  return ec;
}

namespace sink {

/*! Reads all output into `string`. */
class string {
  std::string &string_;

public:
  explicit string(std::string &string) noexcept : string_(string) {}

  std::error_code operator()(stream stream, const uint8_t *buffer, size_t size)
  {
    (void) stream;
    string_.append(reinterpret_cast<const char *>(buffer), size);
    return {};
  }
};

/*! Forwards all output to `ostream`. */
class ostream {
  std::ostream &ostream_;

public:
  explicit ostream(std::ostream &ostream) noexcept : ostream_(ostream) {}

  std::error_code operator()(stream stream, const uint8_t *buffer, size_t size)
  {
    (void) stream;
    ostream_.write(reinterpret_cast<const char *>(buffer),
                   static_cast<std::streamsize>(size));
    return {};
  }
};

/*! Discards all output. */
class discard {
public:
  std::error_code
  operator()(stream stream, const uint8_t *buffer, size_t size) const noexcept
  {
    (void) stream;
    (void) buffer;
    (void) size;

    return {};
  }
};

constexpr discard null = discard();

namespace thread_safe {

/*! `sink::string` but locks the given mutex before invoking the sink. */
class string {
  sink::string sink_;
  std::mutex &mutex_;

public:
  string(std::string &string, std::mutex &mutex) noexcept
      : sink_(string), mutex_(mutex)
  {}

  std::error_code operator()(stream stream, const uint8_t *buffer, size_t size)
  {
    std::lock_guard<std::mutex> lock(mutex_);
    return sink_(stream, buffer, size);
  }
};

}

}
}
