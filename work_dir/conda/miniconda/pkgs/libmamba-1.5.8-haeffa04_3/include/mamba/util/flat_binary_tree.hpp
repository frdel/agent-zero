// Copyright (c) 2023, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_UTIL_FLAT_BINARY_TREE_HPP
#define MAMBA_UTIL_FLAT_BINARY_TREE_HPP

#include <utility>
#include <variant>
#include <vector>

namespace mamba::util
{
    /**
     * In array binary tree.
     *
     * A binary tree, each node is either a leaf, or a node with exactly two children.
     * This data structure is light and nothing prevents the user from representing
     * any kind of binary directed acyclic graph (e.g. there can be multiple trees,
     * or nodes could have multiple parents)
     *
     * For efficency (and simplicity), this data structure can currenlty only grow.
     * The tree must also be grown from the leaves, adding children first and their
     * parents afterwards.
     */
    template <typename Branch, typename Leaf>
    class flat_binary_tree
    {
    public:

        using branch_type = Branch;
        using leaf_type = Leaf;
        struct branch_node
        {
            branch_type data;
            std::size_t left_child = 0;
            std::size_t right_child = 0;
        };
        using leaf_node = leaf_type;
        using node_type = std::variant<branch_node, leaf_node>;
        using node_list = std::vector<node_type>;
        using size_type = typename node_list::size_type;
        using idx_type = size_type;

        [[nodiscard]] auto size() const -> size_type;
        [[nodiscard]] auto empty() const -> bool;

        /** Remove all nodes. */
        void clear();

        /**
         * Reserve (allocate) space for @p nodes.
         *
         * This improves the efficency of ``add_leaf`` and ``add_branch`` but does not
         * modify the tree in any way.
         */
        void reserve(size_type size);

        /**
         * Add a node with no children.
         *
         * Return an ID that can be used to poin to this node as a children in ``add_branch``.
         */
        auto add_leaf(const leaf_type& leaf) -> idx_type;
        auto add_leaf(leaf_type&& leaf) -> idx_type;

        /**
         * Add a node with exactly two children.
         *
         * The children must have been previously added to the tree and thei IDs can be used
         * to point to them.
         */
        auto add_branch(const branch_type& branch, idx_type left_child, idx_type right_child)
            -> idx_type;
        auto add_branch(branch_type&& branch, idx_type left_child, idx_type right_child) -> idx_type;

        [[nodiscard]] auto node(idx_type idx) const -> const node_type&;
        [[nodiscard]] auto node(idx_type idx) -> node_type&;
        [[nodiscard]] auto is_branch(idx_type idx) const -> bool;
        [[nodiscard]] auto is_leaf(idx_type idx) const -> bool;
        [[nodiscard]] auto leaf(idx_type idx) const -> const leaf_type&;
        [[nodiscard]] auto leaf(idx_type idx) -> leaf_type&;
        [[nodiscard]] auto branch(idx_type idx) const -> const branch_type&;
        [[nodiscard]] auto branch(idx_type idx) -> branch_type&;
        [[nodiscard]] auto left(idx_type idx) const -> idx_type;
        [[nodiscard]] auto right(idx_type idx) const -> idx_type;
        [[nodiscard]] auto root() const -> idx_type;

    private:

        node_list m_nodes;
        idx_type m_root = 0;

        template <typename L>
        auto add_leaf_impl(L&& leaf) -> idx_type;
        template <typename B>
        auto add_branch_impl(B&& branch, idx_type left_child, idx_type right_child) -> idx_type;
    };

    /****************************************
     *  Implementation of flat_binary_tree  *
     ****************************************/

    template <typename B, typename L>
    auto flat_binary_tree<B, L>::size() const -> size_type
    {
        return m_nodes.size();
    }

    template <typename B, typename L>
    auto flat_binary_tree<B, L>::empty() const -> bool
    {
        return m_nodes.empty();
    }

    template <typename B, typename L>
    auto flat_binary_tree<B, L>::node(idx_type idx) const -> const node_type&
    {
        return m_nodes.at(idx);
    }

    template <typename B, typename L>
    auto flat_binary_tree<B, L>::node(idx_type idx) -> node_type&
    {
        return m_nodes.at(idx);
    }

    template <typename B, typename L>
    auto flat_binary_tree<B, L>::is_branch(idx_type idx) const -> bool
    {
        return std::holds_alternative<branch_node>(node(idx));
    }

    template <typename B, typename L>
    auto flat_binary_tree<B, L>::is_leaf(idx_type idx) const -> bool
    {
        return std::holds_alternative<leaf_node>(node(idx));
    }

    template <typename B, typename L>
    auto flat_binary_tree<B, L>::leaf(idx_type idx) const -> const leaf_type&
    {
        return std::get<leaf_node>(node(idx));
    }

    template <typename B, typename L>
    auto flat_binary_tree<B, L>::leaf(idx_type idx) -> leaf_type&
    {
        return std::get<leaf_node>(node(idx));
    }

    template <typename B, typename L>
    auto flat_binary_tree<B, L>::branch(idx_type idx) const -> const branch_type&
    {
        return std::get<branch_node>(node(idx)).data;
    }

    template <typename B, typename L>
    auto flat_binary_tree<B, L>::branch(idx_type idx) -> branch_type&
    {
        return std::get<branch_node>(node(idx)).data;
    }

    template <typename B, typename L>
    auto flat_binary_tree<B, L>::left(idx_type idx) const -> idx_type
    {
        return std::get<branch_node>(node(idx)).left_child;
    }

    template <typename B, typename L>
    auto flat_binary_tree<B, L>::right(idx_type idx) const -> idx_type
    {
        return std::get<branch_node>(node(idx)).right_child;
    }

    template <typename B, typename L>
    auto flat_binary_tree<B, L>::root() const -> idx_type
    {
        return m_root;
    }

    template <typename B, typename L>
    void flat_binary_tree<B, L>::clear()
    {
        return m_nodes.clear();
    }

    template <typename B, typename L>
    void flat_binary_tree<B, L>::reserve(size_type size)
    {
        return m_nodes.reserve(size);
    }

    template <typename B, typename L>
    template <typename Leaf>
    auto flat_binary_tree<B, L>::add_leaf_impl(Leaf&& leaf) -> idx_type
    {
        m_nodes.emplace_back(std::forward<Leaf>(leaf));
        return size() - 1;
    }

    template <typename B, typename L>
    auto flat_binary_tree<B, L>::add_leaf(const leaf_type& leaf) -> idx_type
    {
        return add_leaf_impl(leaf);
    }

    template <typename B, typename L>
    auto flat_binary_tree<B, L>::add_leaf(leaf_type&& leaf) -> idx_type
    {
        return add_leaf_impl(std::move(leaf));
    }

    template <typename B, typename L>
    template <typename Branch>
    auto
    flat_binary_tree<B, L>::add_branch_impl(Branch&& branch, idx_type left_child, idx_type right_child)
        -> idx_type
    {
        m_nodes.emplace_back(branch_node{ std::forward<Branch>(branch), left_child, right_child });
        const auto idx = size() - 1;
        if ((left_child == root()) || right_child == root())
        {
            m_root = idx;
        }
        return idx;
    }

    template <typename B, typename L>
    auto
    flat_binary_tree<B, L>::add_branch(const branch_type& branch, idx_type left_child, idx_type right_child)
        -> idx_type
    {
        return add_branch_impl(branch, left_child, right_child);
    }

    template <typename B, typename L>
    auto
    flat_binary_tree<B, L>::add_branch(branch_type&& branch, idx_type left_child, idx_type right_child)
        -> idx_type
    {
        return add_branch_impl(std::move(branch), left_child, right_child);
    }
}
#endif
