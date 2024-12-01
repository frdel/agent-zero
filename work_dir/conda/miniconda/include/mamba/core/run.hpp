// Copyright (c) 2019, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#include <string>
#include <string_view>

#include <nlohmann/json.hpp>

#include "mamba/core/mamba_fs.hpp"
#include "mamba/core/util.hpp"

namespace mamba
{
    bool is_process_name_running(const std::string& name);
    std::string generate_unique_process_name(std::string_view program_name);
    const fs::u8path& proc_dir();
    LockFile lock_proc_dir();

    void daemonize();
    class ScopedProcFile
    {
        const fs::u8path location;

    public:

        ScopedProcFile(
            const std::string& name,
            const std::vector<std::string>& command,
            LockFile proc_dir_lock = lock_proc_dir()
        );
        ~ScopedProcFile();
    };

    enum class STREAM_OPTIONS : int
    {
        ALL_STREAMS = 0,
        SINKOUT = 1,
        SINKERR = 1 << 1,
        SINKIN = 1 << 2,
    };

    int run_in_environment(
        const fs::u8path& prefix,
        std::vector<std::string> command,
        const std::string& cwd,
        int stream_options,
        bool clean_env,
        bool detach,
        const std::vector<std::string>& env_vars,
        const std::string& specific_process_name
    );

    nlohmann::json get_all_running_processes_info(
        const std::function<bool(const nlohmann::json&)>& filter = std::function<
            bool(const nlohmann::json&)>()
    );
    bool is_process_name_running(const std::string& name);
}
