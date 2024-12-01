// Copyright (c) 2023, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_UTIL_URL_MANIP_HPP
#define MAMBA_UTIL_URL_MANIP_HPP

#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace mamba::util
{
    /**
     * Escape reserved URL reserved characters with '%' encoding.
     *
     * Does not parse URL in any way so '/' in "http://mamba.org/page" get encoded.
     *
     * @see url_decode
     */
    [[nodiscard]] auto url_encode(std::string_view url) -> std::string;

    /**
     * Unescape percent encoded string to their URL reserved characters.
     *
     * @see url_encode
     */
    [[nodiscard]] auto url_decode(std::string_view url) -> std::string;

    std::string concat_scheme_url(const std::string& scheme, const std::string& location);

    std::string build_url(
        const std::optional<std::string>& auth,
        const std::string& scheme,
        const std::string& base,
        bool with_credential
    );

    void split_platform(
        const std::vector<std::string>& known_platforms,
        const std::string& url,
        const std::string& context_platform,
        std::string& cleaned_url,
        std::string& platform
    );

    /**
     * If @p url starts with a scheme, return it, otherwise return empty string.
     *
     * Does not include "://"
     */
    [[nodiscard]] auto url_get_scheme(std::string_view url) -> std::string_view;

    /**
     * Retrun true if @p url starts with a URL scheme.
     */
    [[nodiscard]] auto url_has_scheme(std::string_view url) -> bool;

    void split_anaconda_token(const std::string& url, std::string& cleaned_url, std::string& token);

    void split_scheme_auth_token(
        const std::string& url,
        std::string& remaining_url,
        std::string& scheme,
        std::string& auth,
        std::string& token
    );

    bool compare_cleaned_url(const std::string& url1, const std::string& url2);

    std::string path_to_url(const std::string& path);

    template <class S, class... Args>
    std::string join_url(const S& s, const Args&... args);

    /**
     * Convert UNC2 file URI to UNC4.
     *
     * Windows paths can be expressed in a form, called UNC, where it is possible to express a
     * server location, as in "\\hostname\folder\data.xml".
     * This can be succefully encoded in a file URI like "file://hostname/folder/data.xml"
     * since file URI contain a part for the hostname (empty hostname file URI must start with
     * "file:///").
     * Since CURL does not support hostname in file URI, we can encode UNC hostname as part
     * of the path (called 4-slash), where it becomes "file:////hostname/folder/data.xml".
     *
     * This function leaves all non-matching URI (inluding a number of invalid URI for unkown
     * legacy reasons taken from ``url_to_path`` in conda.common.path) unchanged.
     *
     * @see https://learn.microsoft.com/en-us/dotnet/standard/io/file-path-formats#unc-paths
     * @see https://en.wikipedia.org/wiki/File_URI_scheme
     */
    std::string file_uri_unc2_to_unc4(std::string_view url);

    // Only returns a cache name without extension
    std::string cache_name_from_url(const std::string& url);

    namespace detail
    {
        inline std::string join_url_impl(std::string& s)
        {
            return s;
        }

        template <class S, class... Args>
        inline std::string join_url_impl(std::string& s1, const S& s2, const Args&... args)
        {
            if (!s2.empty())
            {
                if (s1.empty() || s1.back() != '/')
                {
                    s1 += '/';
                }
                s1 += s2;
            }
            return join_url_impl(s1, args...);
        }

        template <class... Args>
        inline std::string join_url_impl(std::string& s1, const char* s2, const Args&... args)
        {
            if (s1.size() && s1.back() != '/')
            {
                s1 += '/';
            }
            s1 += s2;
            return join_url_impl(s1, args...);
        }
    }  // namespace detail

    inline std::string join_url()
    {
        return "";
    }

    template <class S, class... Args>
    inline std::string join_url(const S& s, const Args&... args)
    {
        std::string res = s;
        return detail::join_url_impl(res, args...);
    }
}  // namespace mamba

#endif
