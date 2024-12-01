// Copyright (c) 2019, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_CORE_PACKAGE_HANDLING_HPP
#define MAMBA_CORE_PACKAGE_HANDLING_HPP

#include <string>
#include <system_error>
#include <vector>

#include "mamba_fs.hpp"

namespace mamba
{
    enum compression_algorithm
    {
        none,
        bzip2,
        zip,
        zstd
    };

    void create_archive(
        const fs::u8path& directory,
        const fs::u8path& destination,
        compression_algorithm,
        int compression_level,
        int compression_threads,
        bool (*filter)(const fs::u8path&)
    );
    void create_package(
        const fs::u8path& directory,
        const fs::u8path& out_file,
        int compression_threads,
        int compression_level
    );

    void extract_archive(const fs::u8path& file, const fs::u8path& destination);
    void extract_conda(
        const fs::u8path& file,
        const fs::u8path& dest_dir,
        const std::vector<std::string>& parts = { "info", "pkg" }
    );
    void extract(const fs::u8path& file, const fs::u8path& destination);
    fs::u8path extract(const fs::u8path& file);
    void extract_subproc(const fs::u8path& file, const fs::u8path& dest);
    bool transmute(
        const fs::u8path& pkg_file,
        const fs::u8path& target,
        int compression_level,
        int compression_threads
    );
    bool validate(const fs::u8path& pkg_folder);
}  // namespace mamba

#endif  // MAMBA_PACKAGE_HANDLING_HPP
