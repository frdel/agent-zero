// Copyright (c) 2019, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_CORE_CHANNEL_HPP
#define MAMBA_CORE_CHANNEL_HPP

#include <map>
#include <optional>
#include <string>
#include <utility>
#include <vector>

#include "mamba/core/package_cache.hpp"
#include "mamba/core/validate.hpp"

namespace mamba
{
    std::vector<std::string> get_known_platforms();
    // Note: Channels can only be created using ChannelContext.
    class Channel
    {
    public:

        Channel(const Channel&) = delete;
        Channel& operator=(const Channel&) = delete;
        Channel(Channel&&) noexcept = default;
        Channel& operator=(Channel&&) noexcept = default;

        const std::string& scheme() const;
        const std::string& location() const;
        const std::string& name() const;
        const std::string& canonical_name() const;
        const std::vector<std::string>& platforms() const;
        const std::optional<std::string>& auth() const;
        const std::optional<std::string>& token() const;
        const std::optional<std::string>& package_filename() const;
        const validation::RepoChecker& repo_checker(MultiPackageCache& caches) const;

        std::string base_url() const;
        std::string platform_url(std::string platform, bool with_credential = true) const;
        // The pairs consist of (platform,url)
        std::vector<std::pair<std::string, std::string>>
        platform_urls(bool with_credential = true) const;
        std::vector<std::string> urls(bool with_credential = true) const;

    private:

        Channel(
            const std::string& scheme,
            const std::string& location,
            const std::string& name,
            const std::string& canonical_name,
            const std::optional<std::string>& auth = {},
            const std::optional<std::string>& token = {},
            const std::optional<std::string>& package_filename = {}
        );

        std::string m_scheme;
        std::string m_location;
        std::string m_name;
        std::string m_canonical_name;
        std::vector<std::string> m_platforms;
        std::optional<std::string> m_auth;
        std::optional<std::string> m_token;
        std::optional<std::string> m_package_filename;

        // This is used to make sure that there is a unique repo for every channel
        mutable std::unique_ptr<validation::RepoChecker> p_repo_checker;

        friend class ChannelContext;
    };

    bool operator==(const Channel& lhs, const Channel& rhs);
    bool operator!=(const Channel& lhs, const Channel& rhs);


    using ChannelCache = std::map<std::string, Channel>;

    class ChannelContext
    {
    public:

        using channel_list = std::vector<std::string>;
        using channel_map = std::map<std::string, Channel>;
        using multichannel_map = std::map<std::string, std::vector<std::string>>;

        ChannelContext();
        ~ChannelContext();

        ChannelContext(const ChannelContext&) = delete;
        ChannelContext& operator=(const ChannelContext&) = delete;
        ChannelContext(ChannelContext&&) = delete;
        ChannelContext& operator=(ChannelContext&&) = delete;

        const Channel& make_channel(const std::string& value);
        std::vector<const Channel*> get_channels(const std::vector<std::string>& channel_names);

        const Channel& get_channel_alias() const;
        const channel_map& get_custom_channels() const;
        const multichannel_map& get_custom_multichannels() const;

    private:

        ChannelCache m_channel_cache;
        Channel m_channel_alias;
        channel_map m_custom_channels;
        multichannel_map m_custom_multichannels;

        Channel build_channel_alias();
        void init_custom_channels();

        Channel make_simple_channel(
            const Channel& channel_alias,
            const std::string& channel_url,
            const std::string& channel_name,
            const std::string& channel_canonical_name
        );

        Channel from_url(const std::string& url);
        Channel from_name(const std::string& name);
        Channel from_value(const std::string& value);
        Channel from_alias(
            const std::string& scheme,
            const std::string& location,
            const std::optional<std::string>& auth = {},
            const std::optional<std::string>& token = {}
        );
    };

}  // namespace mamba

#endif
