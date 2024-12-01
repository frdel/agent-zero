// Copyright (c) 2019-2023, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_CORE_ENVIRONMENT_HPP
#define MAMBA_CORE_ENVIRONMENT_HPP

#include <cassert>
#include <cstdlib>
#include <map>
#include <optional>
#include <vector>

#include "mamba_fs.hpp"

#ifdef _WIN32
#include <Shlobj.h>
#endif

#ifndef _WIN32
#include <pwd.h>
#include <sys/types.h>
#include <sys/utsname.h>
#include <unistd.h>
#include <wordexp.h>

extern "C"
{
    extern char** environ;
}
#endif

namespace mamba
{
    namespace env
    {
        inline constexpr const char* pathsep()
        {
#ifdef _WIN32
            return ";";
#else
            return ":";
#endif
        }

        std::optional<std::string> get(const std::string& key);
        bool set(const std::string& key, const std::string& value);
        void unset(const std::string& key);

        fs::u8path which(const std::string& exe, const std::string& override_path = "");
        fs::u8path which(const std::string& exe, const std::vector<fs::u8path>& search_paths);
        std::map<std::string, std::string> copy();
        std::string platform();
        fs::u8path home_directory();
        fs::u8path user_config_dir();
        fs::u8path user_data_dir();
        fs::u8path user_cache_dir();

        fs::u8path expand_user(const fs::u8path& path);
        fs::u8path shrink_user(const fs::u8path& path);
    }
}

#endif
