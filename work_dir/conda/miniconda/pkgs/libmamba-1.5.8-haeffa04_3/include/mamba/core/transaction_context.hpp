// Copyright (c) 2019, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_CORE_TRANSACTION_CONTEXT
#define MAMBA_CORE_TRANSACTION_CONTEXT

#include <string>

#include <reproc++/reproc.hpp>

#include "context.hpp"
#include "mamba_fs.hpp"
#include "match_spec.hpp"
#include "util.hpp"

namespace mamba
{
    std::string compute_short_python_version(const std::string& long_version);
    // supply short python version, e.g. 2.7, 3.5...
    fs::u8path get_python_short_path(const std::string& python_version);
    fs::u8path get_python_site_packages_short_path(const std::string& python_version);
    fs::u8path get_bin_directory_short_path();
    fs::u8path get_python_noarch_target_path(
        const std::string& source_short_path,
        const fs::u8path& target_site_packages_short_path
    );

    class TransactionContext
    {
    public:

        TransactionContext();
        TransactionContext& operator=(const TransactionContext&);
        TransactionContext(
            const fs::u8path& target_prefix,
            const std::pair<std::string, std::string>& py_versions,
            const std::vector<MatchSpec>& requested_specs
        );

        TransactionContext(
            const fs::u8path& target_prefix,
            const fs::u8path& relocate_prefix,
            const std::pair<std::string, std::string>& py_versions,
            const std::vector<MatchSpec>& requested_specs
        );
        ~TransactionContext();
        bool try_pyc_compilation(const std::vector<fs::u8path>& py_files);
        void wait_for_pyc_compilation();

        bool has_python;
        fs::u8path target_prefix;
        fs::u8path relocate_prefix;
        fs::u8path site_packages_path;
        fs::u8path python_path;
        std::string python_version;
        std::string old_python_version;
        std::string short_python_version;
        bool allow_softlinks = false;
        bool always_copy = false;
        bool always_softlink = false;
        bool compile_pyc = true;
        // this needs to be done when python version changes
        bool relink_noarch = false;
        std::vector<MatchSpec> requested_specs;

    private:

        bool start_pyc_compilation_process();

        std::unique_ptr<reproc::process> m_pyc_process = nullptr;
        std::unique_ptr<TemporaryFile> m_pyc_script_file = nullptr;
        std::unique_ptr<TemporaryFile> m_pyc_compileall = nullptr;
    };
}  // namespace mamba

#endif
