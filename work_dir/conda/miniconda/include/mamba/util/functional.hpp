// Copyright (c) 2023, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_UTIL_FUNCTIONAL_HPP
#define MAMBA_UTIL_FUNCTIONAL_HPP

#include <utility>

#include "mamba/util/deprecation.hpp"

namespace mamba::util
{
    MAMBA_DEPRECATED_CXX20 struct identity
    {
        template <typename T>
        constexpr auto operator()(T&& t) const noexcept -> T&&;
    };

    /********************************
     *  Implementation of identity  *
     ********************************/

    template <typename T>
    constexpr auto identity::operator()(T&& t) const noexcept -> T&&
    {
        return std::forward<T>(t);
    }
}
#endif
