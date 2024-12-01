// Copyright (c) 2019, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_CORE_TRANSACTION_HPP
#define MAMBA_CORE_TRANSACTION_HPP

#include <string>
#include <tuple>
#include <vector>

#include "mamba/api/install.hpp"

#include "mamba_fs.hpp"
#include "match_spec.hpp"
#include "package_cache.hpp"
#include "package_info.hpp"
#include "pool.hpp"
#include "prefix_data.hpp"
#include "solution.hpp"
#include "transaction_context.hpp"

namespace mamba
{
    class ChannelContext;
    class MSolver;

    class MTransaction
    {
    public:

        MTransaction(
            MPool& pool,
            const std::vector<MatchSpec>& specs_to_remove,
            const std::vector<MatchSpec>& specs_to_install,
            MultiPackageCache& caches
        );
        MTransaction(MPool& pool, MSolver& solver, MultiPackageCache& caches);

        // Only use if the packages have been solved previously already.
        MTransaction(MPool& pool, const std::vector<PackageInfo>& packages, MultiPackageCache& caches);

        MTransaction(const MTransaction&) = delete;
        MTransaction(MTransaction&&) = delete;
        MTransaction& operator=(const MTransaction&) = delete;
        MTransaction& operator=(MTransaction&&) = delete;

        using to_install_type = std::vector<std::tuple<std::string, std::string, std::string>>;
        using to_remove_type = std::vector<std::tuple<std::string, std::string>>;
        using to_specs_type = std::tuple<std::vector<std::string>, std::vector<std::string>>;
        using to_conda_type = std::tuple<to_specs_type, to_install_type, to_remove_type>;

        to_conda_type to_conda();
        void log_json();
        bool fetch_extract_packages();
        bool empty();
        bool prompt();
        void print();
        bool execute(PrefixData& prefix);

        [[deprecated]] std::pair<std::string, std::string> py_find_python_version() const;

    private:

        MPool m_pool;
        TransactionContext m_transaction_context;
        MultiPackageCache m_multi_cache;
        const fs::u8path m_cache_path;
        Solution m_solution;

        History::UserRequest m_history_entry = History::UserRequest::prefilled();

        std::vector<MatchSpec> m_requested_specs;
    };

    MTransaction create_explicit_transaction_from_urls(
        MPool& pool,
        const std::vector<std::string>& urls,
        MultiPackageCache& package_caches,
        std::vector<detail::other_pkg_mgr_spec>& other_specs
    );

    MTransaction create_explicit_transaction_from_lockfile(
        MPool& pool,
        const fs::u8path& env_lockfile_path,
        const std::vector<std::string>& categories,
        MultiPackageCache& package_caches,
        std::vector<detail::other_pkg_mgr_spec>& other_specs
    );
}  // namespace mamba

#endif  // MAMBA_TRANSACTION_HPP
