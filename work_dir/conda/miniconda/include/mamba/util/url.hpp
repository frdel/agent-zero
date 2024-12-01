// Copyright (c) 2023, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_UTIL_URL_HPP
#define MAMBA_UTIL_URL_HPP

#include <string>
#include <string_view>

namespace mamba::util
{
    /**
     * Class representing a URL.
     *
     * All URL have a non-empty scheme, host, and path.
     */
    class URL
    {
    public:

        // clang-format off
        enum class StripScheme : bool { no, yes };
        enum class HidePassword : bool { no, yes };
        enum class Encode : bool { no, yes };
        struct Decode
        {
            inline static constexpr struct yes_type {} yes = {};
            inline static constexpr struct no_type {} no = {};
        };
        // clang-format on

        inline static constexpr std::string_view https = "https";
        inline static constexpr std::string_view localhost = "localhost";

        /**
         * Create a URL from a string.
         *
         * The fields of the URL must be percent encoded, otherwise use the individual
         * field setters to encode.
         * For instance, "https://user@email.com@mamba.org/" must be passed as
         *"https://user%40email.com@mamba.org/".The first '@' charater is part of the username
         * "user@email.com" whereas the second is the URL specification for separating username
         * and hostname.
         *
         * @see Encode
         * @see mamba::util::url_encode
         */
        [[nodiscard]] static auto parse(std::string_view url) -> URL;

        /** Create a local URL. */
        URL() = default;

        /** Return the scheme, always non-empty. */
        [[nodiscard]] auto scheme() const -> const std::string&;

        /** Set a non-empty scheme. */
        auto set_scheme(std::string_view scheme) -> URL&;

        /** Return the encoded user, or empty if none. */
        [[nodiscard]] auto user(Decode::no_type) const -> const std::string&;

        /** Retrun the decoded user, or empty if none. */
        [[nodiscard]] auto user(Decode::yes_type = Decode::yes) const -> std::string;

        /** Set or clear the user. */
        auto set_user(std::string_view user, Encode encode = Encode::yes) -> URL&;

        /** Return the encoded password, or empty if none. */
        [[nodiscard]] auto password(Decode::no_type) const -> const std::string&;

        /** Return the decoded password, or empty if none. */
        [[nodiscard]] auto password(Decode::yes_type = Decode::yes) const -> std::string;

        /** Set or clear the password. */
        auto set_password(std::string_view password, Encode encode = Encode::yes) -> URL&;

        /** Return the encoded basic authentication string. */
        [[nodiscard]] auto authentication() const -> std::string;

        /** Return the encoded host, always non-empty. */
        [[nodiscard]] auto host(Decode::no_type) const -> const std::string&;

        /** Return the decoded host, always non-empty. */
        [[nodiscard]] auto host(Decode::yes_type = Decode::yes) const -> std::string;

        /** Set a non-empty host. */
        auto set_host(std::string_view host, Encode encode = Encode::yes) -> URL&;

        /** Return the port, or empty if none. */
        [[nodiscard]] auto port() const -> const std::string&;

        /** Set or clear the port. */
        auto set_port(std::string_view port) -> URL&;

        /** Return the encoded autority part of the URL. */
        [[nodiscard]] auto authority() const -> std::string;

        /** Return the path, always starts with a '/'. */
        [[nodiscard]] auto path() const -> const std::string&;

        /**
         * Return the path.
         *
         * For a "file" scheme, with a Windows path containing a drive, the leading '/' is
         * stripped.
         */
        [[nodiscard]] auto pretty_path() const -> std::string_view;

        /** Set the path, a leading '/' is added if abscent. */
        auto set_path(std::string_view path) -> URL&;

        /**
         * Append a sub path to the current path.
         *
         * Contrary to `std::filesystem::path::append`, this always append and never replace
         * the current path, even if @p subpath starts with a '/'.
         */
        auto append_path(std::string_view subpath) -> URL&;

        /** Return the query, or empty if none. */
        [[nodiscard]] auto query() const -> const std::string&;

        /** Set or clear the query. */
        auto set_query(std::string_view query) -> URL&;

        /** Return the fragment, or empty if none. */
        [[nodiscard]] auto fragment() const -> const std::string&;

        /** Set or clear the fragment. */
        auto set_fragment(std::string_view fragment) -> URL&;

        /**
         * Return the full encoded url.
         *
         * @param strip_scheme If true, remove the scheme and "localhost" on file URI.
         * @param rstrip_path If non-null, remove the given charaters at the end of the path.
         * @param hide_password If true, hide password in the decoded string.
         */
        [[nodiscard]] auto
        str(StripScheme strip_scheme = StripScheme::no,
            char rstrip_path = 0,
            HidePassword hide_password = HidePassword::no) const -> std::string;

    private:

        std::string m_scheme = std::string(https);
        std::string m_user = {};
        std::string m_password = {};
        std::string m_host = std::string(localhost);
        std::string m_path = "/";
        std::string m_port = {};
        std::string m_query = {};
        std::string m_fragment = {};
    };

    auto operator==(URL const& a, URL const& b) -> bool;
    auto operator!=(URL const& a, URL const& b) -> bool;

    /** A functional equivalent to ``URL::append_path``. */
    auto operator/(URL const& url, std::string_view subpath) -> URL;
    auto operator/(URL&& url, std::string_view subpath) -> URL;
}
#endif
