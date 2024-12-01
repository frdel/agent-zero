#pragma once

#include <type_traits>

namespace reproc {
namespace detail {

template <bool B, typename T = void>
using enable_if = typename std::enable_if<B, T>::type;

template <typename T>
using is_char_array = std::is_convertible<T, const char *const *>;

template <typename T>
using enable_if_not_char_array = enable_if<!is_char_array<T>::value>;

}
}
