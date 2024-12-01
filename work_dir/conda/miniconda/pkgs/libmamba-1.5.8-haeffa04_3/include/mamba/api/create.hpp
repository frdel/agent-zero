// Copyright (c) 2019, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_API_CREATE_HPP
#define MAMBA_API_CREATE_HPP

#include <string>

#include "mamba/core/mamba_fs.hpp"

namespace mamba
{
    class Configuration;

    void create(Configuration& config);

    namespace detail
    {
        void store_platform_config(
            const fs::u8path& prefix,
            const std::string& platform,
            bool& remove_prefix_on_failure
        );
    }
}

#endif
