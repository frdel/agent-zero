#pragma once

#include <reproc++/detail/array.hpp>
#include <reproc++/detail/type_traits.hpp>

namespace reproc {

class env : public detail::array {
public:
  enum type {
    extend,
    empty,
  };

  env(const char *const *envp = nullptr) // NOLINT
      : detail::array(envp, false)
  {}

  /*!
  `Env` must be iterable as a sequence of string pairs. Examples of
  types that satisfy this requirement are `std::vector<std::pair<std::string,
  std::string>>` and `std::map<std::string, std::string>`.

  The pairs in `env` represent the extra environment variables of the child
  process and are converted to the right format before being passed as the
  environment to `reproc_start` via the `env.extra` field of `reproc_options`.
  */
  template <typename Env,
            typename = detail::enable_if_not_char_array<Env>>
  env(const Env &env) // NOLINT
      : detail::array(from(env), true)
  {}

private:
  template <typename Env>
  static const char *const *from(const Env &env);
};

template <typename Env>
const char *const *env::from(const Env &env)
{
  using name_size_type = typename Env::value_type::first_type::size_type;
  using value_size_type = typename Env::value_type::second_type::size_type;

  const char **envp = new const char *[env.size() + 1];
  std::size_t current = 0;

  for (const auto &entry : env) {
    const auto &name = entry.first;
    const auto &value = entry.second;

    // We add 2 to the size to reserve space for the '=' sign and the NUL
    // terminator at the end of the string.
    char *string = new char[name.size() + value.size() + 2];

    envp[current++] = string;

    for (name_size_type i = 0; i < name.size(); i++) {
      *string++ = name[i];
    }

    *string++ = '=';

    for (value_size_type i = 0; i < value.size(); i++) {
      *string++ = value[i];
    }

    *string = '\0';
  }

  envp[current] = nullptr;

  return envp;
}

}
