// Copyright (c) 2019, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_CORE_LINK
#define MAMBA_CORE_LINK

#include <stack>
#include <string>
#include <tuple>
#include <vector>

#include "mamba/util/build.hpp"

#include "mamba_fs.hpp"
#include "match_spec.hpp"
#include "package_paths.hpp"
#include "transaction.hpp"
#include "transaction_context.hpp"

namespace mamba
{
    std::string replace_long_shebang(const std::string& shebang);
    std::string python_shebang(const std::string& python_exe);

    static const std::regex shebang_regex("^(#!"      // pretty much the whole match string
                                          "(?:[ ]*)"  // allow spaces between #! and beginning of
                                                      // the executable path
                                          "(/(?:\\\\ |[^ \n\r\t])*)"  // the executable is the next
                                                                      // text block without an
                                                                      // escaped space or non-space
                                                                      // whitespace character
                                          "(.*))$");  // the rest of the line can contain option
                                                      // flags and end whole_shebang group

    constexpr std::size_t MAX_SHEBANG_LENGTH = util::on_linux ? 127 : 512;

    struct python_entry_point_parsed
    {
        std::string command, module, func;
    };

    class UnlinkPackage
    {
    public:

        UnlinkPackage(const PackageInfo& pkg_info, const fs::u8path& cache_path, TransactionContext* context);

        bool execute();
        bool undo();

    private:

        bool unlink_path(const nlohmann::json& path_data);

        PackageInfo m_pkg_info;
        fs::u8path m_cache_path;
        std::string m_specifier;
        TransactionContext* m_context;
    };

    class LinkPackage
    {
    public:

        LinkPackage(const PackageInfo& pkg_info, const fs::u8path& cache_path, TransactionContext* context);

        bool execute();
        bool undo();

    private:

        std::tuple<std::string, std::string> link_path(const PathData& path_data, bool noarch_python);
        std::vector<fs::u8path> compile_pyc_files(const std::vector<fs::u8path>& py_files);
        auto
        create_python_entry_point(const fs::u8path& path, const python_entry_point_parsed& entry_point);
        void create_application_entry_point(
            const fs::u8path& source_full_path,
            const fs::u8path& target_full_path,
            const fs::u8path& python_full_path
        );

        PackageInfo m_pkg_info;
        fs::u8path m_cache_path;
        fs::u8path m_source;
        std::vector<std::string> m_clobber_warnings;
        TransactionContext* m_context;
    };

}  // namespace mamba

#endif
