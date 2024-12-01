// Copyright (c) 2023, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_UTIL_BUILD_HPP
#define MAMBA_UTIL_BUILD_HPP

namespace mamba::util
{
#if __APPLE__ || __MACH__
    inline static constexpr bool on_win = false;
    inline static constexpr bool on_linux = false;
    inline static constexpr bool on_mac = true;
#elif __linux__
    inline static constexpr bool on_win = false;
    inline static constexpr bool on_linux = true;
    inline static constexpr bool on_mac = false;
#elif _WIN32
    inline static constexpr bool on_win = true;
    inline static constexpr bool on_linux = false;
    inline static constexpr bool on_mac = false;
#else
#error "no supported OS detected"
#endif
}
#endif
