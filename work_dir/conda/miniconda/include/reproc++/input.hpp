#pragma once

#include <cstddef>
#include <cstdint>

namespace reproc {

class input {
  const uint8_t *data_ = nullptr;
  size_t size_ = 0;

public:
  input() = default;

  input(const uint8_t *data, size_t size) : data_(data), size_(size) {}

  /*! Implicitly convert from string literals. */
  template <size_t N>
  input(const char (&data)[N]) // NOLINT
      : data_(reinterpret_cast<const uint8_t *>(data)), size_(N)
  {}

  input(const input &other) = default;
  input &operator=(const input &) = default;

  const uint8_t *data() const noexcept
  {
    return data_;
  }

  size_t size() const noexcept
  {
    return size_;
  }
};

}
