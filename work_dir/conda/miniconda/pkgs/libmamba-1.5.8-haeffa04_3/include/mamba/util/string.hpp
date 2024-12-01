// Copyright (c) 2019, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_CORE_UTIL_STRING_HPP
#define MAMBA_CORE_UTIL_STRING_HPP

#include <algorithm>
#include <array>
#include <cstdint>
#include <cstring>
#include <iomanip>
#include <iterator>
#include <sstream>
#include <string>
#include <string_view>
#include <type_traits>
#include <utility>
#include <vector>

#include "mamba/util/compare.hpp"

namespace mamba::util
{
    /**
     * Return the string if the pointer is not null, otherwise a pointer to an empty string.
     */
    const char* raw_str_or_empty(const char* ptr);

    /**
     * Safe non utf-8 wrapping of <cctype> (see its doc).
     */
    bool is_control(char c);
    bool is_control(wchar_t c);
    bool is_print(char c);
    bool is_print(wchar_t c);
    bool is_space(char c);
    bool is_space(wchar_t c);
    bool is_blank(char c);
    bool is_blank(wchar_t c);
    bool is_graphic(char c);
    bool is_graphic(wchar_t c);
    bool is_digit(char c);
    bool is_digit(wchar_t c);
    bool is_punct(char c);
    bool is_punct(wchar_t c);
    bool is_alpha(char c);
    bool is_alpha(wchar_t c);
    bool is_alphanum(char c);
    bool is_alphanum(wchar_t c);
    bool is_lower(char c);
    bool is_lower(wchar_t c);
    bool is_upper(char c);
    bool is_upper(wchar_t c);
    char to_lower(char c);
    wchar_t to_lower(wchar_t c);

    std::string to_lower(std::string_view str);
    std::wstring to_lower(std::wstring_view str);
    // The use of a template here serves to exclude the overload for const Char*
    template <typename Char>
    std::basic_string<Char> to_lower(std::basic_string<Char>&& str);
    extern template std::string to_lower(std::string&& str);
    extern template std::wstring to_lower(std::wstring&& str);

    char to_upper(char c);
    wchar_t to_upper(wchar_t c);
    std::string to_upper(std::string_view str);
    std::wstring to_upper(std::wstring_view str);
    // The use of a template here serves to exclude the overload for const Char*
    template <typename Char>
    std::basic_string<Char> to_upper(std::basic_string<Char>&& str);
    extern template std::string to_upper(std::string&& str);
    extern template std::wstring to_upper(std::wstring&& str);

    bool starts_with(std::string_view str, std::string_view prefix);
    bool starts_with(std::string_view str, std::string_view::value_type c);

    bool ends_with(std::string_view str, std::string_view suffix);
    bool ends_with(std::string_view str, std::string_view::value_type c);

    bool contains(std::string_view str, std::string_view sub_str);

    /**
     * Check if any of the strings starts with the prefix.
     */
    template <typename StrRange>
    bool any_starts_with(const StrRange& strs, std::string_view prefix);
    template <typename StrRange>
    bool any_starts_with(const StrRange& strs, std::wstring_view prefix);

    /**
     * Check if the string starts with any of the prefix.
     */
    template <typename StrRange>
    bool starts_with_any(std::string_view str, const StrRange& prefix);
    template <typename StrRange>
    bool starts_with_any(std::wstring_view str, const StrRange& prefix);

    /**
     * Return a view to the input without the prefix if present.
     */
    std::string_view remove_prefix(std::string_view str, std::string_view prefix);
    std::string_view remove_prefix(std::string_view str, std::string_view::value_type c);

    /**
     * Return a view to the input without the suffix if present.
     */
    std::string_view remove_suffix(std::string_view str, std::string_view suffix);
    std::string_view remove_suffix(std::string_view str, std::string_view::value_type c);

    std::string_view lstrip(std::string_view input, char c);
    std::wstring_view lstrip(std::wstring_view input, wchar_t c);
    std::string_view lstrip(std::string_view input, std::string_view chars);
    std::wstring_view lstrip(std::wstring_view input, std::wstring_view chars);
    std::string_view lstrip(std::string_view input);
    std::wstring_view lstrip(std::wstring_view input);

    std::array<std::string_view, 2> lstrip_parts(std::string_view input, char c);
    std::array<std::wstring_view, 2> lstrip_parts(std::wstring_view input, wchar_t c);
    std::array<std::string_view, 2> lstrip_parts(std::string_view input, std::string_view chars);
    std::array<std::wstring_view, 2> lstrip_parts(std::wstring_view input, std::wstring_view chars);

    template <typename UnaryFunc>
    std::string_view lstrip_if(std::string_view input, UnaryFunc should_strip);
    template <typename UnaryFunc>
    std::wstring_view lstrip_if(std::wstring_view input, UnaryFunc should_strip);

    template <typename UnaryFunc>
    std::array<std::string_view, 2> lstrip_if_parts(std::string_view input, UnaryFunc should_strip);
    template <typename UnaryFunc>
    std::array<std::wstring_view, 2> lstrip_if_parts(std::wstring_view input, UnaryFunc should_strip);

    std::string_view rstrip(std::string_view input, char c);
    std::wstring_view rstrip(std::wstring_view input, wchar_t c);
    std::string_view rstrip(std::string_view input, std::string_view chars);
    std::wstring_view rstrip(std::wstring_view input, std::wstring_view chars);
    std::string_view rstrip(std::string_view input);
    std::wstring_view rstrip(std::wstring_view input);

    std::array<std::string_view, 2> rstrip_parts(std::string_view input, char c);
    std::array<std::wstring_view, 2> rstrip_parts(std::wstring_view input, wchar_t c);
    std::array<std::string_view, 2> rstrip_parts(std::string_view input, std::string_view chars);
    std::array<std::wstring_view, 2> rstrip_parts(std::wstring_view input, std::wstring_view chars);

    template <typename UnaryFunc>
    std::string_view rstrip_if(std::string_view input, UnaryFunc should_strip);
    template <typename UnaryFunc>
    std::wstring_view rstrip_if(std::wstring_view input, UnaryFunc should_strip);

    template <typename UnaryFunc>
    std::array<std::string_view, 2> rstrip_if_parts(std::string_view input, UnaryFunc should_strip);
    template <typename UnaryFunc>
    std::array<std::wstring_view, 2> rstrip_if_parts(std::wstring_view input, UnaryFunc should_strip);

    std::string_view strip(std::string_view input, char c);
    std::wstring_view strip(std::wstring_view input, wchar_t c);
    std::string_view strip(std::string_view input, std::string_view chars);
    std::wstring_view strip(std::wstring_view input, std::wstring_view chars);
    std::string_view strip(std::string_view input);
    std::wstring_view strip(std::wstring_view input);

    std::array<std::string_view, 3> strip_parts(std::string_view input, char c);
    std::array<std::wstring_view, 3> strip_parts(std::wstring_view input, wchar_t c);
    std::array<std::string_view, 3> strip_parts(std::string_view input, std::string_view chars);
    std::array<std::wstring_view, 3> strip_parts(std::wstring_view input, std::wstring_view chars);

    template <typename UnaryFunc>
    std::string_view strip_if(std::string_view input, UnaryFunc should_strip);
    template <typename UnaryFunc>
    std::wstring_view strip_if(std::wstring_view input, UnaryFunc should_strip);

    template <typename UnaryFunc>
    std::array<std::string_view, 3> strip_if_parts(std::string_view input, UnaryFunc should_strip);
    template <typename UnaryFunc>
    std::array<std::wstring_view, 3> strip_if_parts(std::wstring_view input, UnaryFunc should_strip);

    std::vector<std::string>
    split(std::string_view input, std::string_view sep, std::size_t max_split = SIZE_MAX);
    std::vector<std::wstring>
    split(std::wstring_view input, std::wstring_view sep, std::size_t max_split = SIZE_MAX);

    std::vector<std::string>
    rsplit(std::string_view input, std::string_view sep, std::size_t max_split = SIZE_MAX);
    std::vector<std::wstring>
    rsplit(std::wstring_view input, std::wstring_view sep, std::size_t max_split = SIZE_MAX);

    void replace_all(std::string& data, std::string_view search, std::string_view replace);
    void replace_all(std::wstring& data, std::wstring_view search, std::wstring_view replace);

    namespace detail
    {
        struct PlusEqual
        {
            template <typename T, typename U>
            auto operator()(T& left, const U& right);
        };
    }

    /**
     * Execute the function @p func on each element of a join iteration.
     *
     * The join iteration of an iterator pair (@p first, @p last) with a separator @p sep is
     * defined by iterating through the ``n`` elements of the iterator pair, interleaving the
     * separator in between the elements (thus appearing ``n-1`` times).
     */
    template <typename InputIt, typename UnaryFunction, typename Value>
    UnaryFunction join_for_each(InputIt first, InputIt last, UnaryFunction func, const Value& sep);

    /**
     * Concatenate the elements of the container @p container by interleaving a separator.
     *
     * Joining is done by successively joining (using the provided @p joiner) the aggregate with
     * element of the container and the separator, such that the separator only appears
     * in-between two elements of the range.
     *
     * @see join_for_each
     */
    template <class Range, class Value, class Joiner = detail::PlusEqual>
    auto join(const Value& sep, const Range& container, Joiner joiner = detail::PlusEqual{}) ->
        typename Range::value_type;

    /**
     * Execute the function @p func on each element of a tuncated join iteration.
     *
     * The join iteration of an iterator pair (@p first, @p last) with a separator @p sep
     * and a trunction symbol @p etc is define by the join iteration of either all the elements
     * in the iterator pair if they are less than @p threshold, a limited number of elements, with
     * middle elements represented by @p etc.
     * defined by iterating through the ``n`` elements of the iterator pair, interleaving the
     * separator in between the elements (thus appearing ``n-1`` times).
     *
     * @param first The iterator pointing to the begining of the range of elements to join.
     * @param last The iterator pointing to past the end of the range of elements to join.
     * @param func The unary function to apply to all elements (separation and truncation included).
     * @param sep The separator used in between elements.
     * @param etc The value used to represent the truncation of the elements.
     * @param threshold Distance between the iterator pair beyond which truncation is preformed.
     * @param show Number of elements to keep at the begining/end when truncation is preformed.
     *
     * @see join_for_each
     */
    template <typename InputIt, typename UnaryFunction, typename Value>
    UnaryFunction join_trunc_for_each(
        InputIt first,
        InputIt last,
        UnaryFunction func,
        const Value& sep,
        const Value& etc,
        std::size_t threshold = 5,
        std::pair<std::size_t, std::size_t> show = { 2, 1 }
    );

    /**
     * Join elements of a range, with possible truncation.
     *
     * @param range Elements to join.
     * @param sep The separator used in between elements.
     * @param etc The value used to represent the truncation of the elements.
     * @param threshold Distance between the iterator pair beyond which truncation is preformed.
     * @param show Number of elements to keep at the begining/end when truncation is preformed.
     *
     * @see join_trunc_for_each
     * @see join
     */
    template <typename Range, typename Joiner = detail::PlusEqual>
    auto join_trunc(
        const Range& range,
        std::string_view sep = ", ",
        std::string_view etc = "...",
        std::size_t threshold = 5,
        std::pair<std::size_t, std::size_t> show = { 2, 1 },
        Joiner joiner = detail::PlusEqual{}
    ) -> typename Range::value_type;
    ;

    /************************
     *  Implementation misc *
     ************************/

    inline const char* raw_str_or_empty(const char* ptr)
    {
        return ptr ? ptr : "";
    }

    /********************************************
     *  Implementation of start_with functions  *
     ********************************************/

    template <typename StrRange, typename Char>
    bool any_starts_with(const StrRange& strs, std::basic_string_view<Char> prefix)
    {
        return std::any_of(
            strs.cbegin(),
            strs.cend(),
            [&prefix](const auto& s) { return starts_with(s, prefix); }
        );
    }

    template <typename StrRange>
    bool any_starts_with(const StrRange& strs, std::string_view prefix)
    {
        return any_starts_with<StrRange, decltype(prefix)::value_type>(strs, prefix);
    }

    template <typename StrRange>
    bool any_starts_with(const StrRange& strs, std::wstring_view prefix)
    {
        return any_starts_with<StrRange, decltype(prefix)::value_type>(strs, prefix);
    }

    extern template bool any_starts_with(const std::vector<std::string>&, std::string_view);
    extern template bool any_starts_with(const std::vector<std::string_view>&, std::string_view);

    template <typename StrRange, typename Char>
    bool starts_with_any(std::basic_string_view<Char> str, const StrRange& prefix)
    {
        return std::any_of(
            prefix.cbegin(),
            prefix.cend(),
            [&str](const auto& p) { return starts_with(str, p); }
        );
    }

    template <typename StrRange>
    bool starts_with_any(std::string_view str, const StrRange& prefix)
    {
        return starts_with_any<StrRange, char>(str, prefix);
    }

    template <typename StrRange>
    bool starts_with_any(std::wstring_view str, const StrRange& prefix)
    {
        return starts_with_any<StrRange, wchar_t>(str, prefix);
    }

    extern template bool starts_with_any(std::string_view, const std::vector<std::string>&);
    extern template bool starts_with_any(std::string_view, const std::vector<std::string_view>&);

    /***************************************
     *  Implementation of strip functions  *
     ***************************************/

    namespace detail
    {
        template <typename Char, typename UnaryFunc>
        std::array<std::basic_string_view<Char>, 2>
        lstrip_if_parts_impl(std::basic_string_view<Char> input, UnaryFunc should_strip)
        {
            const auto start_iter = std::find_if(
                input.cbegin(),
                input.cend(),
                [&should_strip](Char c) -> bool { return !should_strip(c); }
            );
            const auto start_idx = static_cast<std::size_t>(start_iter - input.cbegin());
            return { input.substr(0, start_idx), input.substr(start_idx) };
        }
    }

    template <typename UnaryFunc>
    std::string_view lstrip_if(std::string_view input, UnaryFunc should_strip)
    {
        return lstrip_if_parts(input, std::move(should_strip))[1];
    }

    template <typename UnaryFunc>
    std::wstring_view lstrip_if(std::wstring_view input, UnaryFunc should_strip)
    {
        return lstrip_if_parts(input, std::move(should_strip))[1];
    }

    template <typename UnaryFunc>
    std::array<std::string_view, 2> lstrip_if_parts(std::string_view input, UnaryFunc should_strip)
    {
        return detail::lstrip_if_parts_impl(input, std::move(should_strip));
    }

    template <typename UnaryFunc>
    std::array<std::wstring_view, 2> lstrip_if_parts(std::wstring_view input, UnaryFunc should_strip)
    {
        return detail::lstrip_if_parts_impl(input, std::move(should_strip));
    }

    namespace detail
    {
        template <typename Char, typename UnaryFunc>
        std::array<std::basic_string_view<Char>, 2>
        rstrip_if_parts_impl(std::basic_string_view<Char> input, UnaryFunc should_strip)
        {
            const auto rstart_iter = std::find_if(
                input.crbegin(),
                input.crend(),
                [&should_strip](Char c) -> bool { return !should_strip(c); }
            );
            const auto past_end_idx = static_cast<std::size_t>(input.crend() - rstart_iter);
            return { input.substr(0, past_end_idx), input.substr(past_end_idx) };
        }
    }

    template <typename UnaryFunc>
    std::string_view rstrip_if(std::string_view input, UnaryFunc should_strip)
    {
        return rstrip_if_parts(input, std::move(should_strip))[0];
    }

    template <typename UnaryFunc>
    std::wstring_view rstrip_if(std::wstring_view input, UnaryFunc should_strip)
    {
        return rstrip_if_parts(input, std::move(should_strip))[0];
    }

    template <typename UnaryFunc>
    std::array<std::string_view, 2> rstrip_if_parts(std::string_view input, UnaryFunc should_strip)
    {
        return detail::rstrip_if_parts_impl(input, std::move(should_strip));
    }

    template <typename UnaryFunc>
    std::array<std::wstring_view, 2> rstrip_if_parts(std::wstring_view input, UnaryFunc should_strip)
    {
        return detail::rstrip_if_parts_impl(input, std::move(should_strip));
    }

    namespace detail
    {
        template <typename Char, typename UnaryFunc>
        std::array<std::basic_string_view<Char>, 3>
        strip_if_parts_impl(std::basic_string_view<Char> input, UnaryFunc should_strip)
        {
            const auto [head, not_head] = lstrip_if_parts(input, should_strip);
            const auto [body, tail] = rstrip_if_parts(not_head, std::move(should_strip));
            return { head, body, tail };
        }
    }

    template <typename UnaryFunc>
    std::string_view strip_if(std::string_view input, UnaryFunc should_strip)
    {
        return strip_if_parts(input, std::move(should_strip))[1];
    }

    template <typename UnaryFunc>
    std::wstring_view strip_if(std::wstring_view input, UnaryFunc should_strip)
    {
        return strip_if_parts(input, std::move(should_strip))[1];
    }

    template <typename UnaryFunc>
    std::array<std::string_view, 3> strip_if_parts(std::string_view input, UnaryFunc should_strip)
    {
        return detail::strip_if_parts_impl(input, std::move(should_strip));
    }

    template <typename UnaryFunc>
    std::array<std::wstring_view, 3> strip_if_parts(std::wstring_view input, UnaryFunc should_strip)
    {
        return detail::strip_if_parts_impl(input, std::move(should_strip));
    }

    /**************************************
     *  Implementation of join functions  *
     **************************************/

    namespace detail
    {
        template <typename T, typename U>
        auto PlusEqual::operator()(T& left, const U& right)
        {
            left += right;
        }

        template <class T, class = void>
        struct has_reserve : std::false_type
        {
        };
        template <class T>
        struct has_reserve<T, std::void_t<decltype(std::declval<T>().reserve(std::size_t()))>>
            : std::true_type
        {
        };
        template <typename T>
        inline constexpr bool has_reserve_v = has_reserve<T>::value;

        std::size_t length(const char* s);
        std::size_t length(const wchar_t* s);
        std::size_t length(const char c);
        std::size_t length(const wchar_t c);
        template <class T>
        std::size_t length(const T& s)
        {
            return s.length();
        }
    }

    // TODO(C++20) Use ``std::ranges::join_view`` (or ``std::ranges::join``)
    template <typename InputIt, typename UnaryFunction, typename Value>
    UnaryFunction join_for_each(InputIt first, InputIt last, UnaryFunction func, const Value& sep)
    {
        if (first < last)
        {
            func(*(first++));
            for (; first < last; ++first)
            {
                func(sep);
                func(*first);
            }
        }
        return func;
    }

    template <class Range, class Value, class Joiner>
    auto join(const Value& sep, const Range& container, Joiner joiner) -> typename Range::value_type
    {
        using Result = typename Range::value_type;
        Result out{};
        if constexpr (detail::has_reserve_v<Result>)
        {
            std::size_t final_size = 0;
            auto inc_size = [&final_size](const auto& val) { final_size += detail::length(val); };
            join_for_each(container.begin(), container.end(), inc_size, sep);
            out.reserve(final_size);
        }
        auto out_joiner = [&](auto&& val) { joiner(out, std::forward<decltype(val)>(val)); };
        join_for_each(container.begin(), container.end(), out_joiner, sep);
        return out;
    }

    /********************************************
     *  Implementation of join_trunc functions  *
     ********************************************/

    // TODO(C++20) Take an input range and return a range
    template <typename InputIt, typename UnaryFunction, typename Value>
    UnaryFunction join_trunc_for_each(
        InputIt first,
        InputIt last,
        UnaryFunction func,
        const Value& sep,
        const Value& etc,
        std::size_t threshold,
        std::pair<std::size_t, std::size_t> show
    )
    {
        if (util::cmp_less_equal(last - first, threshold))
        {
            return join_for_each(first, last, std::move(func), sep);
        }

        // Working around non-assignable function types, such as lambda with references.
        auto join_for_each_func = [&func](auto f, auto l, auto val)
        {
            if constexpr (std::is_assignable_v<UnaryFunction, UnaryFunction>)
            {
                func = join_for_each(f, l, std::move(func), val);
            }
            else
            {
                join_for_each(f, l, func, val);
            }
        };

        const auto [show_head, show_tail] = show;
        if (show_head > 0)
        {
            join_for_each_func(first, first + static_cast<std::ptrdiff_t>(show_head), sep);
            func(sep);
        }
        func(etc);
        if (show_tail)
        {
            func(sep);
            join_for_each_func(last - static_cast<std::ptrdiff_t>(show_tail), last, sep);
        }
        return func;
    }

    template <typename Range, typename Joiner>
    auto join_trunc(
        const Range& range,
        std::string_view sep,
        std::string_view etc,
        std::size_t threshold,
        std::pair<std::size_t, std::size_t> show,
        Joiner joiner
    ) -> typename Range::value_type
    {
        using Result = typename Range::value_type;
        Result out{};
        if constexpr (detail::has_reserve_v<Result>)
        {
            std::size_t final_size = 0;
            auto inc_size = [&final_size](const auto& val) { final_size += detail::length(val); };
            join_trunc_for_each(range.begin(), range.end(), inc_size, sep, etc, threshold, show);
            out.reserve(final_size);
        }

        auto out_joiner = [&](auto&& val) { joiner(out, std::forward<decltype(val)>(val)); };
        join_trunc_for_each(range.begin(), range.end(), out_joiner, sep, etc, threshold, show);
        return out;
    }

    template <typename... Args>
    std::string concat(const Args&... args)
    {
        std::string result;
        result.reserve((detail::length(args) + ...));
        ((result += args), ...);
        return result;
    }

    template <class B>
    std::string hex_string(const B& buffer, std::size_t size)
    {
        std::ostringstream oss;
        oss << std::hex;
        for (std::size_t i = 0; i < size; ++i)
        {
            oss << std::setw(2) << std::setfill('0') << static_cast<int>(buffer[i]);
        }
        return oss.str();
    }

    template <class B>
    std::string hex_string(const B& buffer)
    {
        return hex_string(buffer, buffer.size());
    }

    /**
     * Return the common parts of two strings by blocks located between the given sep,
     * and considering that these common parts would be located at the end of str1 (search from
     * left to right).
     * str1 is considered smaller than (or equal to) str2.
     * cf. Channels use case.
     */
    std::string get_common_parts(std::string_view str1, std::string_view str2, std::string_view sep);
}

#endif
