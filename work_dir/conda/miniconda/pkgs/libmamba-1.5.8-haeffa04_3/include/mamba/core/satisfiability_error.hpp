// Copyright (c) 2019, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_PROBLEMS_GRAPH_HPP
#define MAMBA_PROBLEMS_GRAPH_HPP

#include <array>
#include <functional>
#include <initializer_list>
#include <optional>
#include <ostream>
#include <string>
#include <string_view>
#include <unordered_map>
#include <utility>
#include <variant>
#include <vector>

#include <fmt/color.h>

#include "mamba/core/match_spec.hpp"
#include "mamba/core/package_info.hpp"
#include "mamba/util/flat_set.hpp"
#include "mamba/util/graph.hpp"

namespace mamba
{

    class MSolver;
    class MPool;

    template <typename T>
    class conflict_map : private std::unordered_map<T, util::flat_set<T>>
    {
    public:

        using Base = std::unordered_map<T, util::flat_set<T>>;
        using typename Base::const_iterator;
        using typename Base::key_type;
        using typename Base::value_type;

        conflict_map() = default;
        conflict_map(std::initializer_list<std::pair<T, T>> conflicts_pairs);

        using Base::empty;
        using Base::size;
        bool has_conflict(const key_type& a) const;
        auto conflicts(const key_type& a) const -> const util::flat_set<T>&;
        bool in_conflict(const key_type& a, const key_type& b) const;

        using Base::cbegin;
        using Base::cend;
        const_iterator begin() const noexcept;
        const_iterator end() const noexcept;

        using Base::clear;
        bool add(const key_type& a, const key_type& b);
        bool remove(const key_type& a, const key_type& b);
        bool remove(const key_type& a);

    private:

        bool remove_asym(const key_type& a, const key_type& b);
    };

    /**
     * A directed graph of the packages involved in a libsolv conflict.
     */
    class ProblemsGraph
    {
    public:

        struct RootNode
        {
        };
        struct PackageNode : PackageInfo
        {
        };
        struct UnresolvedDependencyNode : MatchSpec
        {
        };
        struct ConstraintNode : MatchSpec
        {
        };

        using node_t = std::variant<RootNode, PackageNode, UnresolvedDependencyNode, ConstraintNode>;

        using edge_t = MatchSpec;

        using graph_t = util::DiGraph<node_t, edge_t>;
        using node_id = graph_t::node_id;
        using conflicts_t = conflict_map<node_id>;

        ProblemsGraph(graph_t graph, conflicts_t conflicts, node_id root_node);

        const graph_t& graph() const noexcept;
        const conflicts_t& conflicts() const noexcept;
        node_id root_node() const noexcept;

    private:

        graph_t m_graph;
        conflicts_t m_conflicts;
        node_id m_root_node;
    };

    /**
     * Hand-crafted hurisitics to simplify conflicts in messy situations.
     */
    ProblemsGraph simplify_conflicts(const ProblemsGraph& pbs);

    class CompressedProblemsGraph
    {
    public:

        using RootNode = ProblemsGraph::RootNode;

        /**
         * A rough comparison for nodes.
         *
         * We need to be able to compare nodes for using them in a set but we do not have
         * proper version parsing.
         * Ideally we would like proper comparison for printing packages in order.
         *
         * As with ``NamedList`` below, the implementation is currently kept private for
         * needed types.
         */
        template <typename T>
        struct RoughCompare
        {
            bool operator()(const T& a, const T& b) const;
        };

        /**
         * A list of objects with a name, version, and build member.
         *
         * For simplicity, the implementation is kept in the translation unit with
         * specialization for needed types.
         */
        template <typename T, typename Allocator = std::allocator<T>>
        class NamedList : private util::flat_set<T, RoughCompare<T>, Allocator>
        {
        public:

            using Base = util::flat_set<T, RoughCompare<T>, Allocator>;
            using typename Base::allocator_type;
            using typename Base::const_iterator;
            using typename Base::const_reverse_iterator;
            using typename Base::value_type;

            NamedList() = default;
            template <typename InputIterator>
            NamedList(InputIterator first, InputIterator last);

            using Base::empty;
            using Base::size;
            const value_type& front() const noexcept;
            const value_type& back() const noexcept;
            using Base::cbegin;
            using Base::cend;
            using Base::crbegin;
            using Base::crend;
            const_iterator begin() const noexcept;
            const_iterator end() const noexcept;
            const_reverse_iterator rbegin() const noexcept;
            const_reverse_iterator rend() const noexcept;

            const std::string& name() const;
            std::pair<std::string, std::size_t> versions_trunc(
                std::string_view sep = "|",
                std::string_view etc = "...",
                std::size_t threshold = 5,
                bool remove_duplicates = true
            ) const;
            std::pair<std::string, std::size_t> build_strings_trunc(
                std::string_view sep = "|",
                std::string_view etc = "...",
                std::size_t threshold = 5,
                bool remove_duplicates = true
            ) const;
            std::pair<std::string, std::size_t> versions_and_build_strings_trunc(
                std::string_view sep = "|",
                std::string_view etc = "...",
                std::size_t threshold = 5,
                bool remove_duplicates = true
            ) const;

            using Base::clear;
            using Base::reserve;
            void insert(const value_type& e);
            void insert(value_type&& e);
            template <typename InputIterator>
            void insert(InputIterator first, InputIterator last);

        private:

            template <typename T_>
            void insert_impl(T_&& e);
        };

        using PackageListNode = NamedList<ProblemsGraph::PackageNode>;
        using UnresolvedDependencyListNode = NamedList<ProblemsGraph::UnresolvedDependencyNode>;
        using ConstraintListNode = NamedList<ProblemsGraph::ConstraintNode>;
        using node_t = std::variant<
            RootNode,  //
            PackageListNode,
            UnresolvedDependencyListNode,
            ConstraintListNode>;

        using edge_t = NamedList<MatchSpec>;

        using graph_t = util::DiGraph<node_t, edge_t>;
        using node_id = graph_t::node_id;
        using conflicts_t = conflict_map<node_id>;

        using merge_criteria_t = std::function<
            bool(const ProblemsGraph&, ProblemsGraph::node_id, ProblemsGraph::node_id)>;

        static auto
        from_problems_graph(const ProblemsGraph& pbs, const merge_criteria_t& merge_criteria = {})
            -> CompressedProblemsGraph;

        CompressedProblemsGraph(graph_t graph, conflicts_t conflicts, node_id root_node);

        const graph_t& graph() const noexcept;
        const conflicts_t& conflicts() const noexcept;
        node_id root_node() const noexcept;

    private:

        graph_t m_graph;
        conflicts_t m_conflicts;
        node_id m_root_node;
    };

    /**
     * Formatting options for error message functions.
     */
    struct ProblemsMessageFormat
    {
        fmt::text_style unavailable = fmt::fg(fmt::terminal_color::red);
        fmt::text_style available = fmt::fg(fmt::terminal_color::green);
        std::array<std::string_view, 4> indents = { "│  ", "   ", "├─ ", "└─ " };
    };

    std::ostream& print_problem_tree_msg(
        std::ostream& out,
        const CompressedProblemsGraph& pbs,
        const ProblemsMessageFormat& format = {}
    );
    std::string
    problem_tree_msg(const CompressedProblemsGraph& pbs, const ProblemsMessageFormat& format = {});

    /************************************
     *  Implementation of conflict_map  *
     ************************************/

    template <typename T>
    conflict_map<T>::conflict_map(std::initializer_list<std::pair<T, T>> conflicts_pairs)
    {
        for (const auto& [a, b] : conflicts_pairs)
        {
            add(a, b);
        }
    }

    template <typename T>
    bool conflict_map<T>::has_conflict(const key_type& a) const
    {
        return Base::find(a) != end();
    }

    template <typename T>
    auto conflict_map<T>::conflicts(const key_type& a) const -> const util::flat_set<T>&
    {
        return Base::at(a);
    }

    template <typename T>
    bool conflict_map<T>::in_conflict(const key_type& a, const key_type& b) const
    {
        return has_conflict(a) && Base::at(a).contains(b);
    }

    template <typename T>
    auto conflict_map<T>::begin() const noexcept -> const_iterator
    {
        return Base::begin();
    }

    template <typename T>
    auto conflict_map<T>::end() const noexcept -> const_iterator
    {
        return Base::end();
    }

    template <typename T>
    bool conflict_map<T>::add(const key_type& a, const key_type& b)
    {
        auto [_, inserted] = Base::operator[](a).insert(b);
        if (a != b)
        {
            Base::operator[](b).insert(a);
        }
        return inserted;
    }

    template <typename T>
    bool conflict_map<T>::remove_asym(const key_type& a, const key_type& b)
    {
        auto iter = Base::find(a);
        if (iter == Base::end())
        {
            return false;
        }
        auto& cflcts = iter->second;
        const bool erased = cflcts.erase(b);
        if (cflcts.empty())
        {
            Base::erase(a);
        }
        return erased;
    };

    template <typename T>
    bool conflict_map<T>::remove(const key_type& a, const key_type& b)
    {
        return remove_asym(a, b) && ((a == b) || remove_asym(b, a));
    }

    template <typename T>
    bool conflict_map<T>::remove(const key_type& a)
    {
        auto a_iter = Base::find(a);
        if (a_iter == Base::end())
        {
            return false;
        }
        for (const auto& b : a_iter->second)
        {
            if (a != b)  // Cannot modify while we iterate on it
            {
                remove_asym(b, a);
            }
        }
        Base::erase(a);
        return true;
    }

    /*********************************
     *  Implementation of NamedList  *
     *********************************/

    template <typename T, typename A>
    template <typename InputIterator>
    void CompressedProblemsGraph::NamedList<T, A>::insert(InputIterator first, InputIterator last)
    {
        for (; first < last; ++first)
        {
            insert(*first);
        }
    }
}

#endif  // MAMBA_PROBLEMS_GRAPH_HPP
