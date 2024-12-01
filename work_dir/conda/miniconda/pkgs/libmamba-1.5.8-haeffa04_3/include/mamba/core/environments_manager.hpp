// Copyright (c) 2019, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_CORE_ENVIRONMENT_MANAGER
#define MAMBA_CORE_ENVIRONMENT_MANAGER

#include <set>
#include <string>

#include "fsutil.hpp"

namespace mamba
{
    const char PREFIX_MAGIC_FILE[] = "conda-meta/history";

    bool is_conda_environment(const fs::u8path& prefix);

    class EnvironmentsManager
    {
    public:

        void register_env(const fs::u8path& location);
        void unregister_env(const fs::u8path& location);
        std::set<fs::u8path> list_all_known_prefixes();

    private:

        std::set<std::string>
        clean_environments_txt(const fs::u8path& env_txt_file, const fs::u8path& location);
        std::string remove_trailing_slash(std::string p);
        fs::u8path get_environments_txt_file(const fs::u8path& home) const;
    };
}  // namespace mamba

#endif
