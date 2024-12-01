#pragma once

#include <reproc++/detail/array.hpp>
#include <reproc++/detail/type_traits.hpp>

namespace reproc {

class arguments : public detail::array {
public:
  arguments(const char *const *argv) // NOLINT
      : detail::array(argv, false)
  {}

  /*!
  `Arguments` must be iterable as a sequence of strings. Examples of types that
  satisfy this requirement are `std::vector<std::string>` and
  `std::array<std::string>`.

  `arguments` has the same restrictions as `argv` in `reproc_start` except
  that it should not end with `NULL` (`start` allocates a new array which
  includes the missing `NULL` value).
  */
  template <typename Arguments,
            typename = detail::enable_if_not_char_array<Arguments>>
  arguments(const Arguments &arguments) // NOLINT
      : detail::array(from(arguments), true)
  {}

private:
  template <typename Arguments>
  static const char *const *from(const Arguments &arguments);
};

template <typename Arguments>
const char *const *arguments::from(const Arguments &arguments)
{
  using size_type = typename Arguments::value_type::size_type;

  const char **argv = new const char *[arguments.size() + 1];
  std::size_t current = 0;

  for (const auto &argument : arguments) {
    char *string = new char[argument.size() + 1];

    argv[current++] = string;

    for (size_type i = 0; i < argument.size(); i++) {
      *string++ = argument[i];
    }

    *string = '\0';
  }

  argv[current] = nullptr;

  return argv;
}

}
