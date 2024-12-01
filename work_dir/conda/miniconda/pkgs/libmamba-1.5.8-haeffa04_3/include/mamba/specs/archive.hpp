// Copyright (c) 2023, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_SPECS_ARCHIVE_HPP
#define MAMBA_SPECS_ARCHIVE_HPP

#include <array>
#include <string_view>
#include <type_traits>

#include "mamba/core/mamba_fs.hpp"

namespace mamba::specs
{
    inline static constexpr auto ARCHIVE_EXTENSIONS = std::array{
        std::string_view(".tar.bz2"),
        std::string_view(".conda"),
    };

    /** Detect if the package path has one of the known archive extension. */
    template <typename Str, std::enable_if_t<std::is_convertible_v<Str, std::string_view>, bool> = true>
    [[nodiscard]] auto has_archive_extension(const Str& path) -> bool;
    [[nodiscard]] auto has_archive_extension(std::string_view path) -> bool;
    [[nodiscard]] auto has_archive_extension(const fs::u8path& path) -> bool;

    /** Remove the known archive extension from the package path if present. */
    template <typename Str, std::enable_if_t<std::is_convertible_v<Str, std::string_view>, bool> = true>
    [[nodiscard]] auto strip_archive_extension(const Str& path) -> std::string_view;
    [[nodiscard]] auto strip_archive_extension(std::string_view path) -> std::string_view;
    [[nodiscard]] auto strip_archive_extension(fs::u8path path) -> fs::u8path;

    /********************
     *  Implementation  *
     ********************/

    template <typename Str, std::enable_if_t<std::is_convertible_v<Str, std::string_view>, bool>>
    [[nodiscard]] auto has_archive_extension(const Str& path) -> bool
    {
        return has_archive_extension(std::string_view(path));
    }

    template <typename Str, std::enable_if_t<std::is_convertible_v<Str, std::string_view>, bool>>
    [[nodiscard]] auto strip_archive_extension(const Str& path) -> std::string_view
    {
        return strip_archive_extension(std::string_view(path));
    }

}
#endif
