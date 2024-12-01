// Copyright (c) 2019, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_CORE_UTIL_RANDOM_HPP
#define MAMBA_CORE_UTIL_RANDOM_HPP

#include <algorithm>
#include <array>
#include <cstring>
#include <limits>
#include <random>
#include <string>

namespace mamba
{
    template <typename T = std::mt19937>
    inline auto random_generator() -> T
    {
        using std::begin;
        using std::end;
        constexpr auto seed_bits = sizeof(typename T::result_type) * T::state_size;
        constexpr auto seed_len = seed_bits / std::numeric_limits<std::seed_seq::result_type>::digits;
        auto seed = std::array<std::seed_seq::result_type, seed_len>{};
        auto dev = std::random_device{};
        std::generate_n(begin(seed), seed_len, std::ref(dev));
        auto seed_seq = std::seed_seq(begin(seed), end(seed));
        return T{ seed_seq };
    }

    template <typename T = std::mt19937>
    inline auto local_random_generator() -> T&
    {
        thread_local auto rng = random_generator<T>();
        return rng;
    }

    template <typename T = int, typename G = std::mt19937>
    inline T random_int(T min, T max, G& generator = local_random_generator())
    {
        return std::uniform_int_distribution<T>{ min, max }(generator);
    }

    inline std::string generate_random_alphanumeric_string(std::size_t len)
    {
        static constexpr auto chars = "0123456789"
                                      "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                                      "abcdefghijklmnopqrstuvwxyz";
        auto& rng = local_random_generator<std::mt19937>();

        auto dist = std::uniform_int_distribution{ {}, std::strlen(chars) - 1 };
        auto result = std::string(len, '\0');
        std::generate_n(begin(result), len, [&]() { return chars[dist(rng)]; });
        return result;
    }
}

#endif
