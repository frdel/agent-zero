// Copyright (c) 2022, Cppreference.com
//
// Distributed under the terms of the Copyright/CC-BY-SA License.
//
// The full license can be found at the address
// https://en.cppreference.com/w/Cppreference:Copyright/CC-BY-SA

/**
 * Backport of C++20 ``std::cmp_*`` functions for signed comparison.
 */

#ifndef MAMBA_CORE_UTIL_COMPARE_HPP
#define MAMBA_CORE_UTIL_COMPARE_HPP

#include <type_traits>

#include "mamba/util/deprecation.hpp"

namespace mamba::util
{
    template <class T, class U>
    MAMBA_DEPRECATED_CXX20 constexpr bool cmp_equal(T t, U u) noexcept
    {
        using UT = std::make_unsigned_t<T>;
        using UU = std::make_unsigned_t<U>;
        if constexpr (std::is_signed_v<T> == std::is_signed_v<U>)
        {
            return t == u;
        }
        else if constexpr (std::is_signed_v<T>)
        {
            return t < 0 ? false : UT(t) == u;
        }
        else
        {
            return u < 0 ? false : t == UU(u);
        }
    }

    template <class T, class U>
    MAMBA_DEPRECATED_CXX20 constexpr bool cmp_not_equal(T t, U u) noexcept
    {
        return !cmp_equal(t, u);
    }

    template <class T, class U>
    MAMBA_DEPRECATED_CXX20 constexpr bool cmp_less(T t, U u) noexcept
    {
        using UT = std::make_unsigned_t<T>;
        using UU = std::make_unsigned_t<U>;
        if constexpr (std::is_signed_v<T> == std::is_signed_v<U>)
        {
            return t < u;
        }
        else if constexpr (std::is_signed_v<T>)
        {
            return t < 0 ? true : UT(t) < u;
        }
        else
        {
            return u < 0 ? false : t < UU(u);
        }
    }

    template <class T, class U>
    MAMBA_DEPRECATED_CXX20 constexpr bool cmp_greater(T t, U u) noexcept
    {
        return cmp_less(u, t);
    }

    template <class T, class U>
    MAMBA_DEPRECATED_CXX20 constexpr bool cmp_less_equal(T t, U u) noexcept
    {
        return !cmp_greater(t, u);
    }

    template <class T, class U>
    MAMBA_DEPRECATED_CXX20 constexpr bool cmp_greater_equal(T t, U u) noexcept
    {
        return !cmp_less(t, u);
    }
}
#endif
