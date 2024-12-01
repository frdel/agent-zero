// Copyright (c) 2023, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.


#ifndef MAMBA_UTIL_TYPE_TRAITS_HPP
#define MAMBA_UTIL_TYPE_TRAITS_HPP

#include <iosfwd>
#include <type_traits>

namespace mamba::util
{
    namespace detail
    {
        /**
         * Simple detection idiom from N4502 proposal.
         *
         * Primary template handles all types not supporting the operation.
         *
         * @see https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2015/n4502.pdf
         */
        template <typename, template <typename> typename, typename = std::void_t<>>
        struct detect : std::false_type
        {
        };

        /**
         * Specialization recognizes/validates only types supporting the archetype.
         */
        template <typename T, template <typename> typename Op>
        struct detect<T, Op, std::void_t<Op<T>>> : std::true_type
        {
        };

        template <typename L, typename R>
        using left_shift_operator_t = decltype(std::declval<L>() << std::declval<R>());

        template <typename T>
        using ostreamable_t = left_shift_operator_t<std::ostream&, T>;
    }

    template <typename T>
    using is_ostreamable = detail::detect<std::add_const_t<T>, detail::ostreamable_t>;
    template <typename T>
    inline constexpr bool is_ostreamable_v = is_ostreamable<T>::value;

}
#endif
