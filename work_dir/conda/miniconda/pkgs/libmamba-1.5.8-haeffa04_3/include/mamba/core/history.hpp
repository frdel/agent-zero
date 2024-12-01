// Copyright (c) 2019, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_CORE_HISTORY
#define MAMBA_CORE_HISTORY

#include <set>
#include <string>
#include <unordered_map>
#include <vector>

#include "mamba_fs.hpp"
#include "match_spec.hpp"

namespace mamba
{
    class History
    {
    public:

        History(const fs::u8path& prefix, ChannelContext& channel_context);

        struct ParseResult
        {
            std::string head_line;
            std::set<std::string> diff;
            std::vector<std::string> comments;
        };

        struct UserRequest
        {
            static UserRequest prefilled();

            std::string date;
            std::string cmd;
            std::string conda_version;

            std::vector<std::string> unlink_dists;
            std::vector<std::string> link_dists;

            std::vector<std::string> update;
            std::vector<std::string> remove;
            std::vector<std::string> neutered;
        };

        std::vector<ParseResult> parse();
        bool parse_comment_line(const std::string& line, UserRequest& req);
        std::vector<UserRequest> get_user_requests();
        std::unordered_map<std::string, MatchSpec> get_requested_specs_map();
        void add_entry(const History::UserRequest& entry);

        fs::u8path m_prefix;
        fs::u8path m_history_file_path;
        ChannelContext& m_channel_context;
    };

}  // namespace mamba

#endif
