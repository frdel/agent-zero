// Copyright (c) 2019, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_CORE_SUBDIRDATA_HPP
#define MAMBA_CORE_SUBDIRDATA_HPP

#include <memory>
#include <regex>
#include <string>

#include "mamba/core/channel.hpp"
#include "mamba/core/context.hpp"
#include "mamba/core/error_handling.hpp"
#include "mamba/core/fetch.hpp"
#include "mamba/core/mamba_fs.hpp"
#include "mamba/core/package_cache.hpp"
#include "mamba/core/pool.hpp"
#include "mamba/core/repo.hpp"
#include "mamba/core/util.hpp"

#include "package_handling.hpp"

namespace mamba
{
    struct subdir_metadata
    {
        struct checked_at
        {
            bool value;
            std::time_t last_checked;

            bool has_expired() const
            {
                // difference in seconds, check every 14 days
                return std::difftime(std::time(nullptr), last_checked) > 60 * 60 * 24 * 14;
            }
        };

        static tl::expected<subdir_metadata, mamba_error> from_stream(std::istream& in);

        std::string url;
        std::string etag;
        std::string mod;
        std::string cache_control;
#ifdef _WIN32
        std::chrono::system_clock::time_point stored_mtime;
#else
        fs::file_time_type stored_mtime;
#endif
        std::size_t stored_file_size;
        std::optional<checked_at> has_zst;
        std::optional<checked_at> has_bz2;
        std::optional<checked_at> has_jlap;

        void store_file_metadata(const fs::u8path& path);
        bool check_valid_metadata(const fs::u8path& path);

        void serialize_to_stream(std::ostream& out) const;
        void serialize_to_stream_tiny(std::ostream& out) const;

        bool check_zst(ChannelContext& channel_context, const Channel* channel);
    };


    /**
     * Represents a channel subdirectory (i.e. a platform)
     * packages index. Handles downloading of the index
     * from the server and cache generation as well.
     */
    class MSubdirData
    {
    public:

        static expected_t<MSubdirData> create(
            ChannelContext& channel_context,
            const Channel& channel,
            const std::string& platform,
            const std::string& url,
            MultiPackageCache& caches,
            const std::string& repodata_fn = "repodata.json"
        );

        ~MSubdirData() = default;

        MSubdirData(const MSubdirData&) = delete;
        MSubdirData& operator=(const MSubdirData&) = delete;

        MSubdirData(MSubdirData&&);
        MSubdirData& operator=(MSubdirData&&);

        // TODO return seconds as double
        fs::file_time_type::duration
        check_cache(const fs::u8path& cache_file, const fs::file_time_type::clock::time_point& ref) const;
        bool loaded() const;

        bool forbid_cache();
        void clear_cache();

        expected_t<std::string> cache_path() const;
        const std::string& name() const;

        std::vector<std::unique_ptr<DownloadTarget>>& check_targets();
        DownloadTarget* target();

        bool finalize_check(const DownloadTarget& target);
        bool finalize_transfer(const DownloadTarget& target);
        void finalize_checks();
        expected_t<MRepo> create_repo(MPool& pool);

    private:

        MSubdirData(
            ChannelContext& channel_context,
            const Channel& channel,
            const std::string& platform,
            const std::string& url,
            MultiPackageCache& caches,
            const std::string& repodata_fn = "repodata.json"
        );

        bool load(MultiPackageCache& caches, ChannelContext& channel_context);
        void check_repodata_existence();
        void create_target();
        std::size_t get_cache_control_max_age(const std::string& val);
        void refresh_last_write_time(const fs::u8path& json_file, const fs::u8path& solv_file);

        std::unique_ptr<DownloadTarget> m_target = nullptr;
        std::vector<std::unique_ptr<DownloadTarget>> m_check_targets;

        bool m_json_cache_valid = false;
        bool m_solv_cache_valid = false;

        fs::u8path m_valid_cache_path;
        fs::u8path m_expired_cache_path;
        fs::u8path m_writable_pkgs_dir;

        ProgressProxy m_progress_bar;
        ProgressProxy m_progress_bar_check;

        bool m_loaded;
        bool m_download_complete;
        std::string m_repodata_url;
        std::string m_name;
        std::string m_json_fn;
        std::string m_solv_fn;
        bool m_is_noarch;
        subdir_metadata m_metadata;
        std::unique_ptr<TemporaryFile> m_temp_file;
        const Channel* p_channel = nullptr;
    };

    // Contrary to conda original function, this one expects a full url
    // (that is channel url + / + repodata_fn). It is not the
    // responsibility of this function to decide whether it should
    // concatenate base url and repodata depending on repodata value
    // and old behavior support.
    std::string cache_fn_url(const std::string& url);
    std::string create_cache_dir(const fs::u8path& cache_path);

}  // namespace mamba

#endif  // MAMBA_SUBDIRDATA_HPP
