// Copyright (c) 2019, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_CORE_FS_UTIL
#define MAMBA_CORE_FS_UTIL

#include <system_error>

namespace fs
{
    class u8path;
}

namespace mamba
{
    namespace path
    {
        bool starts_with_home(const fs::u8path& p);

        void create_directories_sudo_safe(const fs::u8path& path);
        bool touch(const fs::u8path& path, bool mkdir = false, bool sudo_safe = false);

        /**
         * Returns `true` only if the provided path is either:
         * - a file we are able to open for writing;
         * - a directory we are able to create a file in for writing;
         * - a file name that does not exist but the parent directory in the path exists and we
         *   are able to create a file with that name in that directory for writing.
         * Returns `false` otherwise.
         */
        bool is_writable(const fs::u8path& path) noexcept;
    }

    namespace mamba_fs
    {
        /** Like std::rename, but works across file systems by moving the file instead
         * if the rename fails.
         * if both rename and move fail, the error code is set to the error code of the
         * copy_file operation and the `to` file is removed. You will have to handle removal
         * of the `from` file yourself.
         */
        void rename_or_move(const fs::u8path& from, const fs::u8path& to, std::error_code& ec);

    }
}
#endif
