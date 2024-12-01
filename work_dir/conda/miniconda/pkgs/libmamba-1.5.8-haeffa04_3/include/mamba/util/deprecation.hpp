// Copyright (c) 2023, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_UTIL_DEPRECATION_HPP
#define MAMBA_UTIL_DEPRECATION_HPP

#if __cplusplus >= 202002L
#define MAMBA_UTIL_COMPARE_DEPRECATED [[deprecated("Use C++20 functions with the same name")]]
#else
#define MAMBA_DEPRECATED_CXX20
#endif

#if __cplusplus >= 202302L
#define MAMBA_UTIL_COMPARE_DEPRECATED [[deprecated("Use C++23 functions with the same name")]]
#else
#define MAMBA_DEPRECATED_CXX23
#endif

#endif
