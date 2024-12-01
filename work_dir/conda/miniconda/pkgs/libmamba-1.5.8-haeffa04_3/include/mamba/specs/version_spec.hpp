// Copyright (c) 2023, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_SPECS_VERSION_SPEC_HPP
#define MAMBA_SPECS_VERSION_SPEC_HPP

#include <functional>
#include <string_view>
#include <variant>

#include "mamba/specs/version.hpp"
#include "mamba/util/flat_bool_expr_tree.hpp"

namespace mamba::specs
{
    class VersionPredicate
    {
    public:

        [[nodiscard]] static auto make_free() -> VersionPredicate;
        [[nodiscard]] static auto make_equal_to(Version ver) -> VersionPredicate;
        [[nodiscard]] static auto make_not_equal_to(Version ver) -> VersionPredicate;
        [[nodiscard]] static auto make_greater(Version ver) -> VersionPredicate;
        [[nodiscard]] static auto make_greater_equal(Version ver) -> VersionPredicate;
        [[nodiscard]] static auto make_less(Version ver) -> VersionPredicate;
        [[nodiscard]] static auto make_less_equal(Version ver) -> VersionPredicate;
        [[nodiscard]] static auto make_starts_with(Version ver) -> VersionPredicate;
        [[nodiscard]] static auto make_not_starts_with(Version ver) -> VersionPredicate;
        [[nodiscard]] static auto make_compatible_with(Version ver, std::size_t level)
            -> VersionPredicate;

        /** Construct an free interval. */
        VersionPredicate() = default;

        [[nodiscard]] auto contains(const Version& point) const -> bool;

    private:

        struct free_interval
        {
            auto operator()(const Version&, const Version&) const -> bool;
        };

        struct starts_with
        {
            auto operator()(const Version&, const Version&) const -> bool;
        };

        struct not_starts_with
        {
            auto operator()(const Version&, const Version&) const -> bool;
        };

        struct compatible_with
        {
            std::size_t level;
            auto operator()(const Version&, const Version&) const -> bool;
        };

        /**
         * Operator to compare with the stored version.
         *
         * We could store arbitrary binary operators, but since this is tightly coupled with
         * ``VersionSpec`` parsing (hence not user-extensible), and performance-sensitive,
         * we choose an ``std::variant`` for dynamic dispatch.
         * An alternative could be a type-erased wrapper with local storage.
         */
        using BinaryOperator = std::variant<
            free_interval,
            std::equal_to<Version>,
            std::not_equal_to<Version>,
            std::greater<Version>,
            std::greater_equal<Version>,
            std::less<Version>,
            std::less_equal<Version>,
            starts_with,
            not_starts_with,
            compatible_with>;

        Version m_version = {};
        BinaryOperator m_operator = free_interval{};

        VersionPredicate(Version ver, BinaryOperator op);

        friend auto operator==(free_interval, free_interval) -> bool;
        friend auto operator==(starts_with, starts_with) -> bool;
        friend auto operator==(not_starts_with, not_starts_with) -> bool;
        friend auto operator==(compatible_with, compatible_with) -> bool;
        friend auto operator==(const VersionPredicate& lhs, const VersionPredicate& rhs) -> bool;
    };

    auto operator==(const VersionPredicate& lhs, const VersionPredicate& rhs) -> bool;
    auto operator!=(const VersionPredicate& lhs, const VersionPredicate& rhs) -> bool;

    class VersionSpec
    {
    public:

        using tree_type = util::flat_bool_expr_tree<VersionPredicate>;

        static constexpr char and_token = ',';
        static constexpr char or_token = '|';
        static constexpr char left_parenthesis_token = '(';
        static constexpr char right_parenthesis_token = ')';

        static constexpr std::string_view starts_with_str = "=";
        static constexpr std::string_view equal_str = "==";
        static constexpr std::string_view not_equal_str = "!=";
        static constexpr std::string_view greater_str = ">";
        static constexpr std::string_view greater_equal_str = ">=";
        static constexpr std::string_view less_str = "<";
        static constexpr std::string_view less_equal_str = "<=";
        static constexpr std::string_view compatible_str = "~=";
        static constexpr std::string_view glob_suffix_str = ".*";
        static constexpr char glob_suffix_token = '*';

        [[nodiscard]] static auto parse(std::string_view str) -> VersionSpec;

        /** Construct VersionSpec that match all versions. */
        VersionSpec() = default;
        explicit VersionSpec(tree_type&& tree) noexcept;

        [[nodiscard]] auto str() const -> std::string;
        [[nodiscard]] auto contains(const Version& point) const -> bool;

    private:

        tree_type m_tree;
    };

    namespace version_spec_literals
    {
        auto operator""_vs(const char* str, std::size_t len) -> VersionSpec;
    }
}

#endif
