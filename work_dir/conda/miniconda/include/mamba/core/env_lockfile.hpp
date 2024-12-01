// Copyright (c) 2022, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.


#ifndef MAMBA_CORE_ENVIRONMENT_LOCKFILE_HPP
#define MAMBA_CORE_ENVIRONMENT_LOCKFILE_HPP

#include <optional>
#include <string>
#include <typeindex>
#include <unordered_map>

#include <tl/expected.hpp>

#include "error_handling.hpp"
#include "fsutil.hpp"
#include "package_info.hpp"

namespace mamba
{
    class ChannelContext;

    enum class file_parsing_error_code
    {
        unknown_failure,     /// Something failed while parsing but we can't identify what.
        unsuported_version,  /// The version of the file does not matched supported ver.
        parsing_failure,     /// The content of the file doesnt match the expected format/language
                             /// structure or constraints.
        invalid_data,        /// The structure of the data in the file is fine but some fields have
                             /// invalid values for our purpose.
    };

    struct EnvLockFileError
    {
        file_parsing_error_code parsing_error_code = file_parsing_error_code::unknown_failure;
        std::optional<std::type_index> yaml_error_type{};

        static const EnvLockFileError& get_details(const mamba_error& error)
        {
            return std::any_cast<const EnvLockFileError&>(error.data());
        }

        template <typename StringT>
        static mamba_error make_error(
            file_parsing_error_code error_code,
            StringT&& msg,
            std::optional<std::type_index> yaml_error_type = std::nullopt
        )
        {
            return mamba_error{ std::forward<StringT>(msg),
                                mamba_error_code::env_lockfile_parsing_failed,
                                EnvLockFileError{ error_code, yaml_error_type } };
        }
    };

    class EnvironmentLockFile
    {
    public:

        struct Channel
        {
            std::string url;
            std::vector<std::string> used_env_vars;
        };

        struct Meta
        {
            std::unordered_map<std::string, std::string> content_hash;
            std::vector<Channel> channels;
            std::vector<std::string> platforms;
            std::vector<std::string> sources;
        };

        struct Package
        {
            mamba::PackageInfo info;
            bool is_optional = false;
            std::string category;
            std::string manager;
            std::string platform;
        };

        EnvironmentLockFile(Meta metadata, std::vector<Package> packages)
            : m_metadata(std::move(metadata))
            , m_packages(std::move(packages))
        {
        }

        std::vector<PackageInfo>
        get_packages_for(std::string_view category, std::string_view platform, std::string_view manager)
            const;

        const std::vector<Package>& get_all_packages() const
        {
            return m_packages;
        }
        const Meta& get_metadata() const
        {
            return m_metadata;
        }

    private:

        Meta m_metadata;
        std::vector<Package> m_packages;
    };

    /// Read an environment lock YAML file and returns it's structured content or an error if
    /// failed.
    tl::expected<EnvironmentLockFile, mamba_error>
    read_environment_lockfile(ChannelContext& channel_context, const fs::u8path& lockfile_location);


    /// Returns `true` if the filename matches names of files which should be interpreted as conda
    /// environment lockfile. NOTE: this does not check if the file exists.
    bool is_env_lockfile_name(std::string_view filename);
}
#endif
