// Copyright (c) 2019-2023, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_CORE_UTIL_OS_HPP
#define MAMBA_CORE_UTIL_OS_HPP

#include <iosfwd>
#include <string>

#include "mamba/core/fsutil.hpp"

namespace mamba
{
#ifdef _WIN32
    // Intention is to avoid including `Windows.h`, while still using the basic Windows API types.
    using DWORD = unsigned long;
#endif

    bool is_admin();
    fs::u8path get_self_exe_path();

    using PID =
#ifdef _WIN32
        DWORD
#else
        int
#endif
        ;

    std::string get_process_name_by_pid(const PID pid);
#ifdef _WIN32
    PID getppid();
#endif

    void run_as_admin(const std::string& args);
    bool enable_long_paths_support(bool force);
    std::string windows_version();
    std::string macos_version();
    std::string linux_version();

    void init_console();
    void reset_console();

#ifdef _WIN32
    std::string to_utf8(const wchar_t* windows_unicode_text, size_t size);
    std::string to_utf8(const wchar_t* windows_unicode_text);
    std::string to_utf8(const std::wstring& windows_unicode_text);
    std::wstring to_windows_unicode(const std::string_view utf8_text);
#endif

    /* Test whether a given `std::ostream` object refers to a terminal. */
    bool is_atty(const std::ostream& stream);

    struct ConsoleFeatures
    {
        bool virtual_terminal_processing, true_colors;
    };

    ConsoleFeatures get_console_features();
    int get_console_width();
    int get_console_height();

    void codesign(const fs::u8path& path, bool verbose = false);

    std::string fix_win_path(const std::string& path);
}

#endif
