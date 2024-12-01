// Copyright (c) 2019, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_CORE_VIRTUAL_PACKAGES_HPP
#define MAMBA_CORE_VIRTUAL_PACKAGES_HPP

#include <string>
#include <vector>

#include "mamba/core/package_info.hpp"

namespace mamba
{
    std::vector<PackageInfo> get_virtual_packages();

    namespace detail
    {
        std::string cuda_version();
        std::string get_arch();

        PackageInfo make_virtual_package(
            const std::string& name,
            const std::string& version = "",
            const std::string& build_string = ""
        );

        std::vector<PackageInfo> dist_packages();
    }
}

#endif
