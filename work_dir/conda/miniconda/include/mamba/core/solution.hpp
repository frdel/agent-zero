// Copyright (c) 2023, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_CORE_SOLUTION_HPP
#define MAMBA_CORE_SOLUTION_HPP

#include <type_traits>
#include <variant>
#include <vector>

#include "package_info.hpp"

namespace mamba
{
    namespace detail
    {
        template <typename T, typename... U>
        inline constexpr bool is_any_of_v = std::disjunction_v<std::is_same<T, U>...>;
    }

    struct Solution
    {
        struct Omit
        {
            PackageInfo what;
        };
        struct Upgrade
        {
            PackageInfo remove;
            PackageInfo install;
        };
        struct Downgrade
        {
            PackageInfo remove;
            PackageInfo install;
        };
        struct Change
        {
            PackageInfo remove;
            PackageInfo install;
        };
        struct Reinstall
        {
            PackageInfo what;
        };
        struct Remove
        {
            PackageInfo remove;
        };
        struct Install
        {
            PackageInfo install;
        };

        template <typename T>
        inline static constexpr bool has_remove_v = detail::is_any_of_v<T, Upgrade, Downgrade, Change, Remove>;

        template <typename T>
        inline static constexpr bool has_install_v = detail::is_any_of_v<T, Upgrade, Downgrade, Change, Install>;

        using Action = std::variant<Omit, Upgrade, Downgrade, Change, Reinstall, Remove, Install>;
        using action_list = std::vector<Action>;

        action_list actions = {};
    };

    template <typename Iter, typename UnaryFunc>
    void for_each_to_remove(Iter first, Iter last, UnaryFunc&& func);
    template <typename Range, typename UnaryFunc>
    void for_each_to_remove(Range&& actions, UnaryFunc&& func);

    template <typename Iter, typename UnaryFunc>
    void for_each_to_install(Iter first, Iter last, UnaryFunc&& func);
    template <typename Range, typename UnaryFunc>
    void for_each_to_install(Range&& actions, UnaryFunc&& func);

    template <typename Iter, typename UnaryFunc>
    void for_each_to_omit(Iter first, Iter last, UnaryFunc&& func);
    template <typename Range, typename UnaryFunc>
    void for_each_to_omit(Range&& actions, UnaryFunc&& func);

    /********************************
     *  Implementation of Solution  *
     ********************************/

    namespace detail
    {
        template <typename Action>
        auto to_remove_ptr(Action& action)
        {
            using PackageInfoPtr = std::conditional_t<std::is_const_v<Action>, const PackageInfo*, PackageInfo*>;
            return std::visit(
                [](auto& a) -> PackageInfoPtr
                {
                    using A = std::decay_t<decltype(a)>;
                    if constexpr (Solution::has_remove_v<A>)
                    {
                        return &(a.remove);
                    }
                    else if constexpr (std::is_same_v<A, Solution::Reinstall>)
                    {
                        return &(a.what);
                    }
                    return nullptr;
                },
                action
            );
        }
    }

    template <typename Iter, typename UnaryFunc>
    void for_each_to_remove(Iter first, Iter last, UnaryFunc&& func)
    {
        for (; first != last; ++first)
        {
            if (auto* const ptr = detail::to_remove_ptr(*first))
            {
                func(*ptr);
            }
        }
    }

    template <typename Range, typename UnaryFunc>
    void for_each_to_remove(Range&& actions, UnaryFunc&& func)
    {
        return for_each_to_remove(actions.begin(), actions.end(), std::forward<UnaryFunc>(func));
    }

    namespace detail
    {
        template <typename Action>
        auto to_install_ptr(Action& action)
        {
            using PackageInfoPtr = std::conditional_t<std::is_const_v<Action>, const PackageInfo*, PackageInfo*>;
            return std::visit(
                [](auto& a) -> PackageInfoPtr
                {
                    using A = std::decay_t<decltype(a)>;
                    if constexpr (Solution::has_install_v<A>)
                    {
                        return &(a.install);
                    }
                    else if constexpr (std::is_same_v<A, Solution::Reinstall>)
                    {
                        return &(a.what);
                    }
                    return nullptr;
                },
                action
            );
        }
    }

    template <typename Iter, typename UnaryFunc>
    void for_each_to_install(Iter first, Iter last, UnaryFunc&& func)
    {
        for (; first != last; ++first)
        {
            if (auto* const ptr = detail::to_install_ptr(*first))
            {
                func(*ptr);
            }
        }
    }

    template <typename Range, typename UnaryFunc>
    void for_each_to_install(Range&& actions, UnaryFunc&& func)
    {
        return for_each_to_install(actions.begin(), actions.end(), std::forward<UnaryFunc>(func));
    }

    namespace detail
    {
        template <typename Action>
        auto to_omit_ptr(Action& action)
        {
            using PackageInfoPtr = std::conditional_t<std::is_const_v<Action>, const PackageInfo*, PackageInfo*>;
            return std::visit(
                [](auto& a) -> PackageInfoPtr
                {
                    using A = std::decay_t<decltype(a)>;
                    if constexpr (std::is_same_v<A, Solution::Omit>)
                    {
                        return &(a.what);
                    }
                    return nullptr;
                },
                action
            );
        }
    }

    template <typename Iter, typename UnaryFunc>
    void for_each_to_omit(Iter first, Iter last, UnaryFunc&& func)
    {
        for (; first != last; ++first)
        {
            if (auto* const ptr = detail::to_omit_ptr(*first))
            {
                func(*ptr);
            }
        }
    }

    template <typename Range, typename UnaryFunc>
    void for_each_to_omit(Range&& actions, UnaryFunc&& func)
    {
        return for_each_to_omit(actions.begin(), actions.end(), std::forward<UnaryFunc>(func));
    }
}
#endif
