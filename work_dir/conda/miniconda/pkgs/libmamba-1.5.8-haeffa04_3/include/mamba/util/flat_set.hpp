// Copyright (c) 2023, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.


#ifndef MAMBA_UTILFLAT_SET_HPP
#define MAMBA_UTILFLAT_SET_HPP

#include <algorithm>
#include <utility>
#include <vector>

namespace mamba::util
{

    /**
     * A sorted vector behaving like a set.
     *
     * Like, ``std::set``, uniqueness is determined by using the equivalence relation.
     * In imprecise terms, two objects ``a`` and ``b`` are considered equivalent if neither
     * compares less than the other: ``!comp(a, b) && !comp(b, a)``
     *
     * @todo C++23 This is implemented in <flat_set>
     */
    template <typename Key, typename Compare = std::less<Key>, typename Allocator = std::allocator<Key>>
    class flat_set : private std::vector<Key, Allocator>
    {
    public:

        using Base = std::vector<Key, Allocator>;
        using typename Base::allocator_type;
        using typename Base::const_iterator;
        using typename Base::const_reverse_iterator;
        using typename Base::size_type;
        using typename Base::value_type;
        using key_compare = Compare;
        using value_compare = Compare;

        using Base::cbegin;
        using Base::cend;
        using Base::crbegin;
        using Base::crend;

        using Base::clear;
        using Base::empty;
        using Base::reserve;
        using Base::size;

        flat_set() = default;
        flat_set(
            std::initializer_list<value_type> il,
            key_compare compare = key_compare(),
            const allocator_type& alloc = allocator_type()
        );
        template <typename InputIterator>
        flat_set(
            InputIterator first,
            InputIterator last,
            key_compare compare = key_compare(),
            const allocator_type& alloc = Allocator()
        );
        flat_set(const flat_set&) = default;
        flat_set(flat_set&&) = default;
        explicit flat_set(std::vector<Key, Allocator>&& other, key_compare compare = key_compare());
        explicit flat_set(const std::vector<Key, Allocator>& other, key_compare compare = key_compare());

        flat_set& operator=(const flat_set&) = default;
        flat_set& operator=(flat_set&&) = default;

        bool contains(const value_type&) const;
        const value_type& front() const noexcept;
        const value_type& back() const noexcept;
        const value_type& operator[](size_type pos) const;
        const value_type& at(size_type pos) const;

        const_iterator begin() const noexcept;
        const_iterator end() const noexcept;
        const_reverse_iterator rbegin() const noexcept;
        const_reverse_iterator rend() const noexcept;

        /** Insert an element in the set.
         *
         * Like std::vector and unlike std::set, inserting an element invalidates iterators.
         */
        std::pair<const_iterator, bool> insert(value_type&& value);
        std::pair<const_iterator, bool> insert(const value_type& value);
        template <typename InputIterator>
        void insert(InputIterator first, InputIterator last);

        const_iterator erase(const_iterator pos);
        const_iterator erase(const_iterator first, const_iterator last);
        size_type erase(const value_type& value);

    private:

        key_compare m_compare;

        bool key_eq(const value_type& a, const value_type& b) const;
        template <typename U>
        std::pair<const_iterator, bool> insert_impl(U&& value);
        void sort_and_remove_duplicates();

        template <typename K, typename C, typename A>
        friend bool operator==(const flat_set<K, C, A>& lhs, const flat_set<K, C, A>& rhs);
    };

    template <class Key, class Compare = std::less<Key>, class Allocator = std::allocator<Key>>
    flat_set(std::initializer_list<Key>, Compare = Compare(), Allocator = Allocator())
        -> flat_set<Key, Compare, Allocator>;

    template <
        class InputIt,
        class Comp = std::less<typename std::iterator_traits<InputIt>::value_type>,
        class Alloc = std::allocator<typename std::iterator_traits<InputIt>::value_type>>
    flat_set(InputIt, InputIt, Comp = Comp(), Alloc = Alloc())
        -> flat_set<typename std::iterator_traits<InputIt>::value_type, Comp, Alloc>;

    template <class Key, class Compare = std::less<Key>, class Allocator = std::allocator<Key>>
    flat_set(std::vector<Key, Allocator>&&, Compare compare = Compare())
        -> flat_set<Key, Compare, Allocator>;

    template <class Key, class Compare = std::less<Key>, class Allocator = std::allocator<Key>>
    flat_set(const std::vector<Key, Allocator>&, Compare compare = Compare())
        -> flat_set<Key, Compare, Allocator>;

    template <typename Key, typename Compare, typename Allocator>
    bool
    operator==(const flat_set<Key, Compare, Allocator>& lhs, const flat_set<Key, Compare, Allocator>& rhs);

    template <typename Key, typename Compare, typename Allocator>
    bool
    operator!=(const flat_set<Key, Compare, Allocator>& lhs, const flat_set<Key, Compare, Allocator>& rhs);

    /*******************************
     *  vector_set Implementation  *
     *******************************/

    template <typename K, typename C, typename A>
    flat_set<K, C, A>::flat_set(
        std::initializer_list<value_type> il,
        key_compare compare,
        const allocator_type& alloc
    )
        : Base(std::move(il), alloc)
        , m_compare(std::move(compare))
    {
        sort_and_remove_duplicates();
    }

    template <typename K, typename C, typename A>
    template <typename InputIterator>
    flat_set<K, C, A>::flat_set(
        InputIterator first,
        InputIterator last,
        key_compare compare,
        const allocator_type& alloc
    )
        : Base(first, last, alloc)
        , m_compare(std::move(compare))
    {
        sort_and_remove_duplicates();
    }

    template <typename K, typename C, typename A>
    flat_set<K, C, A>::flat_set(std::vector<K, A>&& other, C compare)
        : Base(std::move(other))
        , m_compare(std::move(compare))
    {
        sort_and_remove_duplicates();
    }

    template <typename K, typename C, typename A>
    flat_set<K, C, A>::flat_set(const std::vector<K, A>& other, C compare)
        : Base(std::move(other))
        , m_compare(std::move(compare))
    {
        sort_and_remove_duplicates();
    }

    template <typename K, typename C, typename A>
    auto flat_set<K, C, A>::contains(const value_type& value) const -> bool
    {
        return std::binary_search(begin(), end(), value);
    }

    template <typename K, typename C, typename A>
    auto flat_set<K, C, A>::front() const noexcept -> const value_type&
    {
        return Base::front();
    }

    template <typename K, typename C, typename A>
    auto flat_set<K, C, A>::back() const noexcept -> const value_type&
    {
        return Base::back();
    }

    template <typename K, typename C, typename A>
    auto flat_set<K, C, A>::operator[](size_type pos) const -> const value_type&
    {
        return Base::operator[](pos);
    }

    template <typename K, typename C, typename A>
    auto flat_set<K, C, A>::at(size_type pos) const -> const value_type&
    {
        return Base::at(pos);
    }

    template <typename K, typename C, typename A>
    auto flat_set<K, C, A>::begin() const noexcept -> const_iterator
    {
        return Base::begin();
    }

    template <typename K, typename C, typename A>
    auto flat_set<K, C, A>::end() const noexcept -> const_iterator
    {
        return Base::end();
    }

    template <typename K, typename C, typename A>
    auto flat_set<K, C, A>::rbegin() const noexcept -> const_reverse_iterator
    {
        return Base::rbegin();
    }

    template <typename K, typename C, typename A>
    auto flat_set<K, C, A>::rend() const noexcept -> const_reverse_iterator
    {
        return Base::rend();
    }

    template <typename K, typename C, typename A>
    auto flat_set<K, C, A>::insert(const value_type& value) -> std::pair<const_iterator, bool>
    {
        return insert_impl(value);
    }

    template <typename K, typename C, typename A>
    auto flat_set<K, C, A>::insert(value_type&& value) -> std::pair<const_iterator, bool>
    {
        return insert_impl(std::move(value));
    }

    template <typename K, typename C, typename A>
    bool flat_set<K, C, A>::key_eq(const value_type& a, const value_type& b) const
    {
        return !m_compare(a, b) && !m_compare(b, a);
    }

    template <typename K, typename C, typename A>
    void flat_set<K, C, A>::sort_and_remove_duplicates()
    {
        std::sort(Base::begin(), Base::end(), m_compare);
        auto is_eq = [this](const value_type& a, const value_type& b) { return key_eq(a, b); };
        Base::erase(std::unique(Base::begin(), Base::end(), is_eq), Base::end());
    }

    template <typename K, typename C, typename A>
    template <typename InputIterator>
    void flat_set<K, C, A>::insert(InputIterator first, InputIterator last)
    {
        Base::insert(Base::end(), first, last);
        sort_and_remove_duplicates();
    }

    template <typename K, typename C, typename A>
    template <typename U>
    auto flat_set<K, C, A>::insert_impl(U&& value) -> std::pair<const_iterator, bool>
    {
        auto it = std::lower_bound(begin(), end(), value, m_compare);
        if ((it != end()) && (key_eq(*it, value)))
        {
            return { it, false };
        }
        it = Base::insert(it, std::forward<U>(value));
        return { it, true };
    }

    template <typename K, typename C, typename A>
    auto flat_set<K, C, A>::erase(const_iterator pos) -> const_iterator
    {
        // No need to sort or remove duplicates again
        return Base::erase(pos);
    }

    template <typename K, typename C, typename A>
    auto flat_set<K, C, A>::erase(const_iterator first, const_iterator last) -> const_iterator
    {
        // No need to sort or remove duplicates again
        return Base::erase(first, last);
    }

    template <typename K, typename C, typename A>
    auto flat_set<K, C, A>::erase(const value_type& value) -> size_type
    {
        auto it = std::lower_bound(begin(), end(), value, m_compare);
        if ((it == end()) || (!(key_eq(*it, value))))
        {
            return 0;
        }
        erase(it);
        return 1;
    }

    template <typename K, typename C, typename A>
    bool operator==(const flat_set<K, C, A>& lhs, const flat_set<K, C, A>& rhs)
    {
        auto is_eq = [&lhs](const auto& a, const auto& b) { return lhs.key_eq(a, b); };
        return std::equal(lhs.cbegin(), lhs.cend(), rhs.cbegin(), rhs.cend(), is_eq);
    }

    template <typename K, typename C, typename A>
    bool operator!=(const flat_set<K, C, A>& lhs, const flat_set<K, C, A>& rhs)
    {
        return !(lhs == rhs);
    }

}
#endif
