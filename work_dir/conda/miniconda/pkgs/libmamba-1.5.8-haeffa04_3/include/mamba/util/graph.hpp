// Copyright (c) 2019, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_UTIL_GRAPH_HPP
#define MAMBA_UTIL_GRAPH_HPP

#include <algorithm>
#include <cassert>
#include <functional>
#include <iterator>
#include <map>
#include <utility>
#include <vector>

#include "flat_set.hpp"

namespace mamba::util
{
    // Simplified implementation of a directed graph
    template <typename Node, typename Derived>
    class DiGraphBase
    {
    public:

        using node_t = Node;
        using node_id = std::size_t;
        using node_map = std::map<node_id, node_t>;
        using node_id_list = flat_set<node_id>;
        using adjacency_list = std::vector<node_id_list>;

        node_id add_node(const node_t& value);
        node_id add_node(node_t&& value);
        bool add_edge(node_id from, node_id to);
        bool remove_edge(node_id from, node_id to);
        bool remove_node(node_id id);

        bool empty() const;
        std::size_t number_of_nodes() const noexcept;
        std::size_t number_of_edges() const noexcept;
        std::size_t in_degree(node_id id) const noexcept;
        std::size_t out_degree(node_id id) const noexcept;
        const node_map& nodes() const;
        const node_t& node(node_id id) const;
        node_t& node(node_id id);
        const node_id_list& successors(node_id id) const;
        const adjacency_list& successors() const;
        const node_id_list& predecessors(node_id id) const;
        const adjacency_list& predecessors() const;
        bool has_node(node_id id) const;
        bool has_edge(node_id from, node_id to) const;

        // TODO C++20 better to return a range since this search cannot be interupted from the
        // visitor
        template <typename UnaryFunc>
        UnaryFunc for_each_node_id(UnaryFunc func) const;
        template <typename BinaryFunc>
        BinaryFunc for_each_edge_id(BinaryFunc func) const;
        template <typename UnaryFunc>
        UnaryFunc for_each_leaf_id(UnaryFunc func) const;
        template <typename UnaryFunc>
        UnaryFunc for_each_leaf_id_from(node_id source, UnaryFunc func) const;
        template <typename UnaryFunc>
        UnaryFunc for_each_root_id(UnaryFunc func) const;
        template <typename UnaryFunc>
        UnaryFunc for_each_root_id_from(node_id source, UnaryFunc func) const;

    protected:

        using derived_t = Derived;

        DiGraphBase() = default;
        DiGraphBase(const DiGraphBase&) = default;
        DiGraphBase(DiGraphBase&&) = default;
        DiGraphBase& operator=(const DiGraphBase&) = default;
        DiGraphBase& operator=(DiGraphBase&&) = default;
        ~DiGraphBase() = default;

        node_id number_of_node_id() const noexcept;

        Derived& derived_cast();
        const Derived& derived_cast() const;

    private:

        template <class V>
        node_id add_node_impl(V&& value);

        // Source of truth for exsising nodes
        node_map m_node_map;
        // May contains empty slots after `remove_node`
        adjacency_list m_predecessors;
        // May contains empty slots after `remove_node`
        adjacency_list m_successors;
        std::size_t m_number_of_edges = 0;
    };

    // TODO C++20 better to return a range since this search cannot be interupted from the
    // visitor
    // TODO should let user implement reverse with a reverse view when available
    template <typename Graph, typename Visitor>
    void
    dfs_raw(const Graph& graph, Visitor&& visitor, typename Graph::node_id start, bool reverse = false);

    template <typename Graph, typename Visitor>
    void dfs_raw(const Graph& graph, Visitor&& visitor, bool reverse = false);

    template <typename Graph, typename UnaryFunc>
    void dfs_preorder_nodes_for_each_id(
        const Graph& graph,
        UnaryFunc&& func,
        typename Graph::node_id start,
        bool reverse = false
    );

    template <typename Graph, typename UnaryFunc>
    void dfs_preorder_nodes_for_each_id(const Graph& graph, UnaryFunc&& func, bool reverse = false);

    template <typename Graph, typename UnaryFunc>
    void dfs_postorder_nodes_for_each_id(
        const Graph& graph,
        UnaryFunc&& func,
        typename Graph::node_id start,
        bool reverse = false
    );

    template <typename Graph, typename UnaryFunc>
    void dfs_postorder_nodes_for_each_id(const Graph& graph, UnaryFunc&& func, bool reverse = false);

    // TODO C++20 rather than providing an empty visitor, use a concept to detect the presence
    // of member function.
    // @warning Inheriting publicly from this class risks calling into the empty overloaded
    // function.
    template <typename Graph>
    class EmptyVisitor
    {
    public:

        using graph_t = Graph;
        using node_id = typename graph_t::node_id;

        void start_node(node_id, const graph_t&)
        {
        }
        void finish_node(node_id, const graph_t&)
        {
        }

        void start_edge(node_id, node_id, const graph_t&)
        {
        }
        void tree_edge(node_id, node_id, const graph_t&)
        {
        }
        void back_edge(node_id, node_id, const graph_t&)
        {
        }
        void forward_or_cross_edge(node_id, node_id, const graph_t&)
        {
        }
        void finish_edge(node_id, node_id, const graph_t&)
        {
        }
    };

    template <typename Graph>
    auto
    is_reachable(const Graph& graph, typename Graph::node_id source, typename Graph::node_id target)
        -> bool;

    template <typename Graph, typename UnaryFunc>
    void topological_sort_for_each_node_id(const Graph& graph, UnaryFunc&& func);

    template <typename Node, typename Edge = void>
    class DiGraph : private DiGraphBase<Node, DiGraph<Node, Edge>>
    {
    public:

        using Base = DiGraphBase<Node, DiGraph<Node, Edge>>;
        using typename Base::adjacency_list;
        using typename Base::node_id;
        using typename Base::node_id_list;
        using typename Base::node_map;
        using typename Base::node_t;
        using edge_t = Edge;
        using edge_id = std::pair<node_id, node_id>;
        using edge_map = std::map<edge_id, edge_t>;

        using Base::empty;
        using Base::has_edge;
        using Base::has_node;
        using Base::in_degree;
        using Base::node;
        using Base::nodes;
        using Base::number_of_edges;
        using Base::number_of_nodes;
        using Base::out_degree;
        using Base::predecessors;
        using Base::successors;

        using Base::for_each_edge_id;
        using Base::for_each_leaf_id;
        using Base::for_each_leaf_id_from;
        using Base::for_each_node_id;
        using Base::for_each_root_id;
        using Base::for_each_root_id_from;

        using Base::add_node;
        bool add_edge(node_id from, node_id to, const edge_t& data);
        bool add_edge(node_id from, node_id to, edge_t&& data);
        bool remove_edge(node_id from, node_id to);
        bool remove_node(node_id id);

        const edge_map& edges() const;
        const edge_t& edge(node_id from, node_id to) const;
        const edge_t& edge(edge_id edge) const;
        edge_t& edge(node_id from, node_id to);
        edge_t& edge(edge_id edge);

    private:

        friend class DiGraphBase<Node, DiGraph<Node, Edge>>;  // required for private CRTP

        template <typename T>
        bool add_edge_impl(node_id from, node_id to, T&& data);

        edge_map m_edges;
    };

    template <typename Node>
    class DiGraph<Node, void> : public DiGraphBase<Node, DiGraph<Node, void>>
    {
    };

    /********************************
     *  DiGraphBase Implementation  *
     ********************************/

    template <typename N, typename G>
    bool DiGraphBase<N, G>::empty() const
    {
        return number_of_nodes() == 0;
    }

    template <typename N, typename G>
    auto DiGraphBase<N, G>::number_of_nodes() const noexcept -> std::size_t
    {
        return m_node_map.size();
    }

    template <typename N, typename G>
    auto DiGraphBase<N, G>::number_of_edges() const noexcept -> std::size_t
    {
        return m_number_of_edges;
    }

    template <typename N, typename G>
    auto DiGraphBase<N, G>::in_degree(node_id id) const noexcept -> std::size_t
    {
        return m_predecessors[id].size();
    }

    template <typename N, typename G>
    auto DiGraphBase<N, G>::out_degree(node_id id) const noexcept -> std::size_t
    {
        return m_successors[id].size();
    }

    template <typename N, typename G>
    auto DiGraphBase<N, G>::nodes() const -> const node_map&
    {
        return m_node_map;
    }

    template <typename N, typename G>
    auto DiGraphBase<N, G>::node(node_id id) const -> const node_t&
    {
        return m_node_map.at(id);
    }

    template <typename N, typename G>
    auto DiGraphBase<N, G>::node(node_id id) -> node_t&
    {
        return m_node_map.at(id);
    }

    template <typename N, typename G>
    auto DiGraphBase<N, G>::successors(node_id id) const -> const node_id_list&
    {
        return m_successors[id];
    }

    template <typename N, typename G>
    auto DiGraphBase<N, G>::successors() const -> const adjacency_list&
    {
        return m_successors;
    }

    template <typename N, typename G>
    auto DiGraphBase<N, G>::predecessors(node_id id) const -> const node_id_list&
    {
        return m_predecessors[id];
    }

    template <typename N, typename G>
    auto DiGraphBase<N, G>::predecessors() const -> const adjacency_list&
    {
        return m_predecessors;
    }

    template <typename N, typename G>
    auto DiGraphBase<N, G>::has_node(node_id id) const -> bool
    {
        return nodes().count(id) > 0;
    }

    template <typename N, typename G>
    auto DiGraphBase<N, G>::has_edge(node_id from, node_id to) const -> bool
    {
        return has_node(from) && successors(from).contains(to);
    }

    template <typename N, typename G>
    auto DiGraphBase<N, G>::add_node(const node_t& value) -> node_id
    {
        return add_node_impl(value);
    }

    template <typename N, typename G>
    auto DiGraphBase<N, G>::add_node(node_t&& value) -> node_id
    {
        return add_node_impl(std::move(value));
    }

    template <typename N, typename G>
    template <class V>
    auto DiGraphBase<N, G>::add_node_impl(V&& value) -> node_id
    {
        const node_id id = number_of_node_id();
        m_node_map.emplace(id, std::forward<V>(value));
        m_successors.push_back(node_id_list());
        m_predecessors.push_back(node_id_list());
        return id;
    }

    template <typename N, typename G>
    bool DiGraphBase<N, G>::remove_node(node_id id)
    {
        if (!has_node(id))
        {
            return false;
        }

        const auto succs = successors(id);  // Cannot iterate on object being modified
        for (const auto& to : succs)
        {
            remove_edge(id, to);
        }
        const auto preds = predecessors(id);  // Cannot iterate on object being modified
        for (const auto& from : preds)
        {
            remove_edge(from, id);
        }
        m_node_map.erase(id);

        return true;
    }

    template <typename N, typename G>
    bool DiGraphBase<N, G>::add_edge(node_id from, node_id to)
    {
        if (has_edge(from, to))
        {
            return false;
        }
        m_successors[from].insert(to);
        m_predecessors[to].insert(from);
        ++m_number_of_edges;
        return true;
    }

    template <typename N, typename G>
    bool DiGraphBase<N, G>::remove_edge(node_id from, node_id to)
    {
        if (!has_edge(from, to))
        {
            return false;
        }
        m_successors[from].erase(to);
        m_predecessors[to].erase(from);
        --m_number_of_edges;
        return true;
    }

    template <typename N, typename G>
    template <typename UnaryFunc>
    UnaryFunc DiGraphBase<N, G>::for_each_node_id(UnaryFunc func) const
    {
        for (const auto& [i, _] : m_node_map)
        {
            func(i);
        }
        return func;
    }

    template <typename N, typename G>
    template <typename BinaryFunc>
    BinaryFunc DiGraphBase<N, G>::for_each_edge_id(BinaryFunc func) const
    {
        for_each_node_id(
            [&](node_id i)
            {
                for (node_id j : successors(i))
                {
                    func(i, j);
                }
            }
        );
        return func;
    }

    template <typename N, typename G>
    template <typename UnaryFunc>
    UnaryFunc DiGraphBase<N, G>::for_each_leaf_id(UnaryFunc func) const
    {
        for_each_node_id(
            [&](node_id i)
            {
                if (out_degree(i) == 0)
                {
                    func(i);
                }
            }
        );
        return func;
    }

    template <typename N, typename G>
    template <typename UnaryFunc>
    UnaryFunc DiGraphBase<N, G>::for_each_root_id(UnaryFunc func) const
    {
        for_each_node_id(
            [&](node_id i)
            {
                if (in_degree(i) == 0)
                {
                    func(i);
                }
            }
        );
        return func;
    }

    template <typename N, typename G>
    template <typename UnaryFunc>
    UnaryFunc DiGraphBase<N, G>::for_each_leaf_id_from(node_id source, UnaryFunc func) const
    {
        // Explore the directed graph starting with the given source node.
        // When we explore a node with no outgoing edge, we know it is a leaf that is also a
        // descendent of source.
        // The pre or post order used in the node has no importance.
        dfs_preorder_nodes_for_each_id(
            derived_cast(),
            [&](node_id n)
            {
                if (out_degree(n) == 0)
                {
                    func(n);
                }
            },
            source
        );
        return func;
    }

    template <typename N, typename G>
    template <typename UnaryFunc>
    UnaryFunc DiGraphBase<N, G>::for_each_root_id_from(node_id source, UnaryFunc func) const
    {
        // Explore in reverse (going in the opposite direction of the edges the directed graph
        // starting with the given source node.
        // When we explore a node with no incoming edge, we know it is a root that is also an
        // ascendent of source.
        // The pre or post order used in the node has no importance.
        dfs_preorder_nodes_for_each_id(
            derived_cast(),
            [&](node_id n)
            {
                if (in_degree(n) == 0)
                {
                    func(n);
                }
            },
            source,
            /* reverse= */ true
        );
        return func;
    }

    template <typename N, typename G>
    auto DiGraphBase<N, G>::number_of_node_id() const noexcept -> node_id
    {
        // Not number_of_nodes because due to remove nodes it may be larger
        return m_successors.size();
    }

    template <typename N, typename G>
    auto DiGraphBase<N, G>::derived_cast() -> derived_t&
    {
        return static_cast<derived_t&>(*this);
    }

    template <typename N, typename G>
    auto DiGraphBase<N, G>::derived_cast() const -> const derived_t&
    {
        return static_cast<const derived_t&>(*this);
    }

    /*******************************
     *  Algorithms implementation  *
     *******************************/

    namespace detail
    {
        enum struct Visited
        {
            yes,
            ongoing,
            no
        };

        template <typename Graph, typename Visitor>
        void dfs_raw_impl(
            const Graph& graph,
            Visitor&& visitor,
            typename Graph::node_id start,
            std::vector<Visited>& status,
            const typename Graph::adjacency_list& adjacency
        )
        {
            assert(status.size() == graph.successors().size());
            assert(adjacency.size() == graph.successors().size());
            assert(start < status.size());
            status[start] = Visited::ongoing;
            visitor.start_node(start, graph);
            for (auto child : adjacency[start])
            {
                visitor.start_edge(start, child, graph);
                if (status[child] == Visited::no)
                {
                    visitor.tree_edge(start, child, graph);
                    dfs_raw_impl(graph, visitor, child, status, adjacency);
                }
                else if (status[child] == Visited::ongoing)
                {
                    visitor.back_edge(start, child, graph);
                }
                else
                {
                    visitor.forward_or_cross_edge(start, child, graph);
                }
                visitor.finish_edge(start, child, graph);
            }
            status[start] = Visited::yes;
            visitor.finish_node(start, graph);
        }
    }

    template <typename Graph, typename Visitor>
    void dfs_raw(const Graph& graph, Visitor&& visitor, typename Graph::node_id start, bool reverse)
    {
        if (!graph.empty())
        {
            auto& adjacency = reverse ? graph.predecessors() : graph.successors();
            auto status = std::vector<detail::Visited>(adjacency.size(), detail::Visited::no);
            detail::dfs_raw_impl(graph, std::forward<Visitor>(visitor), start, status, adjacency);
        }
    }

    template <typename Graph, typename Visitor>
    void dfs_raw(const Graph& graph, Visitor&& visitor, bool reverse)
    {
        if (graph.empty())
        {
            return;
        }

        using node_id = typename Graph::node_id;

        auto& adjacency = reverse ? graph.predecessors() : graph.successors();
        const auto max_node_id = adjacency.size();
        auto status = std::vector<detail::Visited>(max_node_id, detail::Visited::no);

        // Iterating over all ids, which may be a super set of the valid ids since some ids
        // could have been removed.
        // Hence we need to check ``graph.has_node``.
        for (node_id n = 0; n < max_node_id; ++n)
        {
            if (graph.has_node(n) && (status[n] == detail::Visited::no))
            {
                detail::dfs_raw_impl(graph, std::forward<Visitor>(visitor), n, status, adjacency);
            }
        }
    }

    namespace detail
    {
        template <typename Graph, typename UnaryFunc>
        class PreorderVisitor : public EmptyVisitor<Graph>
        {
        public:

            using node_id = typename Graph::node_id;

            template <typename UnaryFuncU>
            PreorderVisitor(UnaryFuncU&& func)
                : m_func{ std::forward<UnaryFuncU>(func) }
            {
            }

            void start_node(node_id n, const Graph&)
            {
                m_func(n);
            }

        private:

            UnaryFunc m_func;
        };

        template <typename Graph, typename UnaryFunc>
        class PostorderVisitor : public EmptyVisitor<Graph>
        {
        public:

            using node_id = typename Graph::node_id;

            template <typename UnaryFuncU>
            PostorderVisitor(UnaryFuncU&& func)
                : m_func{ std::forward<UnaryFuncU>(func) }
            {
            }

            void finish_node(node_id n, const Graph&)
            {
                m_func(n);
            }

        private:

            UnaryFunc m_func;
        };
    }

    template <typename Graph, typename UnaryFunc>
    void dfs_preorder_nodes_for_each_id(
        const Graph& graph,
        UnaryFunc&& func,
        typename Graph::node_id start,
        bool reverse
    )
    {
        dfs_raw(
            graph,
            detail::PreorderVisitor<Graph, UnaryFunc>(std::forward<UnaryFunc>(func)),
            start,
            reverse
        );
    }

    template <typename Graph, typename UnaryFunc>
    void dfs_preorder_nodes_for_each_id(const Graph& graph, UnaryFunc&& func, bool reverse)
    {
        dfs_raw(graph, detail::PreorderVisitor<Graph, UnaryFunc>(std::forward<UnaryFunc>(func)), reverse);
    }

    template <typename Graph, typename UnaryFunc>
    void dfs_postorder_nodes_for_each_id(
        const Graph& graph,
        UnaryFunc&& func,
        typename Graph::node_id start,
        bool reverse
    )
    {
        dfs_raw(
            graph,
            detail::PostorderVisitor<Graph, UnaryFunc>(std::forward<UnaryFunc>(func)),
            start,
            reverse
        );
    }

    template <typename Graph, typename UnaryFunc>
    void dfs_postorder_nodes_for_each_id(const Graph& graph, UnaryFunc&& func, bool reverse)
    {
        dfs_raw(graph, detail::PostorderVisitor<Graph, UnaryFunc>(std::forward<UnaryFunc>(func)), reverse);
    }

    template <typename Graph>
    auto
    is_reachable(const Graph& graph, typename Graph::node_id source, typename Graph::node_id target)
        -> bool
    {
        struct : EmptyVisitor<Graph>
        {
            using node_id = typename Graph::node_id;
            node_id target;
            bool target_visited = false;

            void start_node(node_id node, const Graph&)
            {
                target_visited = target_visited || (node == target);
            }
        } visitor{ {}, target };

        dfs_raw(graph, visitor, source);
        return visitor.target_visited;
    }

    template <typename Graph, typename UnaryFunc>
    void topological_sort_for_each_node_id(const Graph& graph, UnaryFunc&& func)
    {
        dfs_postorder_nodes_for_each_id(graph, func, /* reverse= */ true);
    }

    /*********************************
     *  DiGraph Edge Implementation  *
     *********************************/

    template <typename N, typename E>
    bool DiGraph<N, E>::add_edge(node_id from, node_id to, const edge_t& data)
    {
        return add_edge_impl(from, to, data);
    }

    template <typename N, typename E>
    bool DiGraph<N, E>::add_edge(node_id from, node_id to, edge_t&& data)
    {
        return add_edge_impl(from, to, std::move(data));
    }

    template <typename N, typename E>
    template <typename T>
    bool DiGraph<N, E>::add_edge_impl(node_id from, node_id to, T&& data)
    {
        if (const bool added = Base::add_edge(from, to); added)
        {
            auto l_edge_id = std::pair(from, to);
            m_edges.insert(std::pair(l_edge_id, std::forward<T>(data)));
            return true;
        }
        return false;
    }

    template <typename N, typename E>
    bool DiGraph<N, E>::remove_edge(node_id from, node_id to)
    {
        m_edges.erase({ from, to });  // No-op if edge does not exists
        return Base::remove_edge(from, to);
    }

    template <typename N, typename E>
    bool DiGraph<N, E>::remove_node(node_id id)
    {
        // No-op if edge does not exists
        for (const auto& to : successors(id))
        {
            m_edges.erase({ id, to });
        }
        for (const auto& from : predecessors(id))
        {
            m_edges.erase({ from, id });
        }
        return Base::remove_node(id);
    }

    template <typename N, typename E>
    auto DiGraph<N, E>::edges() const -> const edge_map&
    {
        return m_edges;
    }

    template <typename N, typename E>
    auto DiGraph<N, E>::edge(edge_id edge) const -> const edge_t&
    {
        return m_edges.at(edge);
    }

    template <typename N, typename E>
    auto DiGraph<N, E>::edge(node_id from, node_id to) const -> const edge_t&
    {
        return edge({ from, to });
    }

    template <typename N, typename E>
    auto DiGraph<N, E>::edge(edge_id edge) -> edge_t&
    {
        return m_edges[edge];
    }

    template <typename N, typename E>
    auto DiGraph<N, E>::edge(node_id from, node_id to) -> edge_t&
    {
        return edge({ from, to });
    }
}
#endif
