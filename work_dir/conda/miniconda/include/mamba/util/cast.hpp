// Copyright (c) 2023, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_CORE_UTIL_CAST_HPP
#define MAMBA_CORE_UTIL_CAST_HPP

#include <limits>
#include <stdexcept>
#include <type_traits>

#include <fmt/format.h>

#include "mamba/util/compare.hpp"

namespace mamba::util
{
    /**
     * A safe cast between arithmetic types.
     *
     * If the conversion leads to an overflow, the cast will throw an ``std::overflow_error``.
     * If the conversion to a floating point type loses precision, the cast will throw a
     * ``std::runtime_error``.
     */
    template <typename To, typename From>
    constexpr auto safe_num_cast(const From& val) -> To;

    /********************
     *  Implementation  *
     ********************/

    namespace detail
    {
        template <typename To, typename From>
        constexpr auto make_overflow_error(const From& val)
        {
            return std::overflow_error{ fmt::format(
                "Value to cast ({}) is out of destination range ([{}, {}])",
                val,
                std::numeric_limits<To>::lowest(),
                std::numeric_limits<To>::max()
            ) };
        };
    }

    template <typename To, typename From>
    constexpr auto safe_num_cast(const From& val) -> To
    {
        static_assert(std::is_arithmetic_v<From>);
        static_assert(std::is_arithmetic_v<To>);

        constexpr auto to_lowest = std::numeric_limits<To>::lowest();
        constexpr auto to_max = std::numeric_limits<To>::max();
        constexpr auto from_lowest = std::numeric_limits<From>::lowest();
        constexpr auto from_max = std::numeric_limits<From>::max();

        if constexpr (std::is_same_v<From, To>)
        {
            return val;
        }
        else if constexpr (std::is_integral_v<From> && std::is_integral_v<To>)
        {
            if constexpr (cmp_less(from_lowest, to_lowest))
            {
                if (cmp_less(val, to_lowest))
                {
                    throw detail::make_overflow_error<To>(val);
                }
            }

            if constexpr (cmp_greater(from_max, to_max))
            {
                if (cmp_greater(val, to_max))
                {
                    throw detail::make_overflow_error<To>(val);
                }
            }

            return static_cast<To>(val);
        }
        else
        {
            using float_type = std::common_type_t<From, To>;
            constexpr auto float_cast = [](const auto& x) { return static_cast<float_type>(x); };

            if constexpr (float_cast(from_lowest) < float_cast(to_lowest))
            {
                if (float_cast(val) < float_cast(to_lowest))
                {
                    throw detail::make_overflow_error<To>(val);
                }
            }

            if constexpr (float_cast(from_max) > float_cast(to_max))
            {
                if (float_cast(val) > float_cast(to_max))
                {
                    throw detail::make_overflow_error<To>(val);
                }
            }

            To cast = static_cast<To>(val);
            From cast_back = static_cast<From>(cast);
            if (cast_back != val)
            {
                throw std::runtime_error{
                    fmt::format("Casting from {} to {} loses precision", val, cast)
                };
            }
            return cast;
        }
    }
}

#endif
