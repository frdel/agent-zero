// Copyright (c) 2019, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_CORE_SHELL_INIT
#define MAMBA_CORE_SHELL_INIT

#include <string>
#include <vector>

#include "mamba_fs.hpp"

extern const char data_micromamba_sh[];
extern const char data_micromamba_csh[];
extern const char data_micromamba_bat[];
extern const char data_activate_bat[];
extern const char data__mamba_activate_bat[];
extern const char data_mamba_hook_bat[];
extern const char data_mamba_hook_ps1[];
extern const char data_Mamba_psm1[];
extern const char data_mamba_xsh[];
extern const char data_mamba_fish[];
extern const char data_mamba_completion_posix[];

namespace mamba
{
    std::string guess_shell();

#ifdef _WIN32
    void init_cmd_exe_registry(const std::wstring& reg_path, const fs::u8path& conda_prefix);
#endif

    fs::u8path get_self_exe_path();
    std::string get_hook_contents(const std::string& shell);

    // this function calls cygpath to convert win path to unix
    std::string native_path_to_unix(const std::string& path, bool is_a_path_env = false);

    std::string
    rcfile_content(const fs::u8path& env_prefix, const std::string& shell, const fs::u8path& mamba_exe);

    std::string
    xonsh_content(const fs::u8path& env_prefix, const std::string& shell, const fs::u8path& mamba_exe);

    void modify_rc_file(
        const fs::u8path& file_path,
        const fs::u8path& conda_prefix,
        const std::string& shell,
        const fs::u8path& mamba_exe
    );

    void
    reset_rc_file(const fs::u8path& file_path, const std::string& shell, const fs::u8path& mamba_exe);

    // we need this function during linking...
    void init_root_prefix_cmdexe(const fs::u8path& root_prefix);
    void deinit_root_prefix_cmdexe(const fs::u8path& root_prefix);
    void init_root_prefix(const std::string& shell, const fs::u8path& root_prefix);
    void deinit_root_prefix(const std::string& shell, const fs::u8path& root_prefix);

    std::string powershell_contents(const fs::u8path& conda_prefix);
    void init_powershell(const fs::u8path& profile_path, const fs::u8path& conda_prefix);
    void deinit_powershell(const fs::u8path& profile_path, const fs::u8path& conda_prefix);

    void init_shell(const std::string& shell, const fs::u8path& conda_prefix);
    void deinit_shell(const std::string& shell, const fs::u8path& conda_prefix);
    std::vector<std::string> find_initialized_shells();

}

#endif
