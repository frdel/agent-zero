// Copyright (c) 2019, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_CORE_READ_PATHS_HPP
#define MAMBA_CORE_READ_PATHS_HPP

#include <map>
#include <set>
#include <string>
#include <vector>

#include "util.hpp"

const char PREFIX_PLACEHOLDER_1[] = "/opt/anaconda1anaconda2";
// this is intentionally split into parts, such that running
// this program on itself will leave it unchanged
const char PREFIX_PLACEHOLDER_2[] = "anaconda3";

namespace mamba
{
    struct PrefixFileParse
    {
        std::string placeholder;
        std::string file_mode;
        std::string file_path;
    };

    enum class PathType
    {
        UNDEFINED,
        HARDLINK,
        SOFTLINK,
        DIRECTORY,

        // These should not occur in a package, only after installation
        LINKED_PACKAGE_RECORD,
        PYC_FILE,
        UNIX_PYTHON_ENTRY_POINT,
        WINDOWS_PYTHON_ENTRY_POINT_SCRIPT,
        WINDOWS_PYTHON_ENTRY_POINT_EXE
    };

    enum class FileMode
    {
        UNDEFINED,
        BINARY,
        TEXT
    };

    struct PathData
    {
        std::string path;
        PathType path_type = PathType::UNDEFINED;
        std::string sha256;
        std::size_t size_in_bytes = 0;

        std::string prefix_placeholder;
        FileMode file_mode = FileMode::TEXT;
        bool no_link = false;
    };

    std::map<std::string, PrefixFileParse> read_has_prefix(const fs::u8path& path);
    std::set<std::string> read_no_link(const fs::u8path& info_dir);
    std::vector<PathData> read_paths(const fs::u8path& directory);
}  // namespace mamba

#endif
