// Copyright (c) 2023, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.


#ifndef MAMBA_SPECS_PLATFORM_HPP
#define MAMBA_SPECS_PLATFORM_HPP

#include <optional>
#include <string_view>

#include <nlohmann/json_fwd.hpp>

namespace mamba::specs
{
    enum class Platform
    {
        noarch,
        linux_32,
        linux_64,
        linux_armv6l,
        linux_armv7l,
        linux_aarch64,
        linux_ppc64,
        linux_ppc64le,
        linux_s390x,
        linux_riscv32,
        linux_riscv64,
        osx_64,
        osx_arm64,
        win_32,
        win_64,
        win_arm64,
    };

    /**
     * Convert the enumeration to its conda string.
     */
    auto platform_name(Platform p) -> std::string_view;

    /**
     * Return the enum matching the platform name.
     */
    auto platform_parse(std::string_view str) -> std::optional<Platform>;

    /**
     * Detect the platform on which mamba was built.
     */
    auto build_platform() -> Platform;
    auto build_platform_name() -> std::string_view;

    /**
     * Serialize to JSON string.
     */
    void to_json(nlohmann::json& j, const Platform& p);

    /**
     * Deserialize from JSON string.
     */
    void from_json(const nlohmann::json& j, Platform& p);

}
#endif
