// Copyright (c) 2019, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_API_INSTALL_HPP
#define MAMBA_API_INSTALL_HPP

#include <string>
#include <vector>

#include <nlohmann/json.hpp>
#include <solv/solver.h>
#include <yaml-cpp/yaml.h>

#include "mamba/core/context.hpp"
#include "mamba/core/mamba_fs.hpp"
#include "mamba/core/package_cache.hpp"
#include "mamba/core/package_info.hpp"
#include "mamba/core/pool.hpp"
#include "mamba/core/repo.hpp"
#include "mamba/core/solver.hpp"

namespace mamba
{
    class ChannelContext;
    class Configuration;

    void install(Configuration& config);

    void install_specs(
        ChannelContext& channel_context,
        const Configuration& config,
        const std::vector<std::string>& specs,
        bool create_env = false,
        bool remove_prefix_on_failure = false,
        int solver_flag = SOLVER_INSTALL,
        int is_retry = 0
    );

    void install_explicit_specs(
        ChannelContext& channel_context,
        const std::vector<std::string>& specs,
        bool create_env = false,
        bool remove_prefix_on_failure = false
    );
    void install_lockfile_specs(
        ChannelContext& channel_context,
        const std::string& lockfile_specs,
        const std::vector<std::string>& categories,
        bool create_env = false,
        bool remove_prefix_on_failure = false
    );

    namespace detail
    {
        void create_target_directory(const fs::u8path prefix);

        void create_empty_target(const fs::u8path& prefix);

        void file_specs_hook(Configuration& config, std::vector<std::string>& file_specs);

        void channels_hook(Configuration& config, std::vector<std::string>& channels);

        bool download_explicit(const std::vector<PackageInfo>& pkgs, MultiPackageCache& pkg_caches);

        struct other_pkg_mgr_spec
        {
            std::string pkg_mgr;
            std::vector<std::string> deps;
            std::string cwd;
        };

        bool operator==(const other_pkg_mgr_spec& s1, const other_pkg_mgr_spec& s2);

        struct yaml_file_contents
        {
            std::string name;
            std::vector<std::string> dependencies, channels;
            std::vector<other_pkg_mgr_spec> others_pkg_mgrs_specs;
        };

        bool eval_selector(const std::string& selector);

        yaml_file_contents read_yaml_file(fs::u8path yaml_file);

        std::tuple<std::vector<PackageInfo>, std::vector<MatchSpec>>
        parse_urls_to_package_info(const std::vector<std::string>& urls, ChannelContext& channel_context);

        inline void to_json(nlohmann::json&, const other_pkg_mgr_spec&)
        {
        }
    }

}

namespace YAML
{
    template <>
    struct convert<mamba::detail::other_pkg_mgr_spec>
    {
        static Node encode(const mamba::detail::other_pkg_mgr_spec& /*rhs*/)
        {
            return Node();
        }

        static bool decode(const Node& /*node*/, mamba::detail::other_pkg_mgr_spec& /*rhs*/)
        {
            return true;
        }
    };
}

#endif
