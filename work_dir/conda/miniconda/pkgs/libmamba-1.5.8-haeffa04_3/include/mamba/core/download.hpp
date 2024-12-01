// Copyright (c) 2019, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_CORE_DOWNLOAD_HPP
#define MAMBA_CORE_DOWNLOAD_HPP

#include <functional>
#include <optional>
#include <string>
#include <variant>

#include <tl/expected.hpp>

#include "mamba/core/context.hpp"

namespace mamba
{
    struct TransferData
    {
        int http_status = 0;
        std::string effective_url = "";
        std::size_t downloaded_size = 0;
        std::size_t average_speed = 0;
    };

    struct DownloadSuccess
    {
        std::string filename = "";
        TransferData transfer = {};
        std::string cache_control = "";
        std::string etag = "";
        std::string last_modified = "";
        std::size_t attempt_number = std::size_t(1);
    };

    struct DownloadError
    {
        std::string message = "";
        std::optional<std::size_t> retry_wait_seconds = std::nullopt;
        std::optional<TransferData> transfer = std::nullopt;
        std::size_t attempt_number = std::size_t(1);
    };

    struct DownloadProgress
    {
        std::size_t downloaded_size = 0;
        std::size_t total_to_download = 0;
    };

    using DownloadEvent = std::variant<DownloadProgress, DownloadError, DownloadSuccess>;

    struct DownloadRequest
    {
        using progress_callback_t = std::function<void(const DownloadEvent&)>;

        // TODO: remove these functions when we plug a library with continuation
        using on_success_callback_t = std::function<bool(const DownloadSuccess&)>;
        using on_failure_callback_t = std::function<void(const DownloadError&)>;

        std::string name;
        std::string url;
        std::string filename;
        bool head_only;
        bool ignore_failure;
        std::optional<std::size_t> expected_size = std::nullopt;
        std::optional<std::string> if_none_match = std::nullopt;
        std::optional<std::string> if_modified_since = std::nullopt;

        std::optional<progress_callback_t> progress = std::nullopt;
        std::optional<on_success_callback_t> on_success = std::nullopt;
        std::optional<on_failure_callback_t> on_failure = std::nullopt;

        DownloadRequest(
            const std::string& lname,
            const std::string& lurl,
            const std::string& lfilename,
            bool lhead_only = false,
            bool lignore_failure = false
        );
    };

    using DownloadRequestList = std::vector<DownloadRequest>;

    struct MultiDownloadRequest
    {
        DownloadRequestList requests;
    };

    using DownloadResult = tl::expected<DownloadSuccess, DownloadError>;
    using DownloadResultList = std::vector<DownloadResult>;

    struct MultiDownloadResult
    {
        DownloadResultList results;
    };

    struct DownloadOptions
    {
        bool fail_fast = false;
        bool sort = true;
    };

    MultiDownloadResult
    download(MultiDownloadRequest requests, const Context& context, DownloadOptions options = {});
}

#endif
