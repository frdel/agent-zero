// Copyright (c) 2019, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_UTIL_ITERATOR_HPP
#define MAMBA_UTIL_ITERATOR_HPP

#include <cstddef>
#include <iterator>
#include <optional>
#include <type_traits>

namespace mamba::util
{
    /********************************
     * class xforward_iterator_base *
     ********************************/

    template <class I, class T, class D = std::ptrdiff_t, class P = T*, class R = T&>
    class xforward_iterator_base
    {
    public:

        using derived_type = I;
        using value_type = T;
        using reference = R;
        using pointer = P;
        using difference_type = D;
        using iterator_category = std::forward_iterator_tag;

        friend derived_type operator++(derived_type& d, int)
        {
            derived_type tmp(d);
            ++d;
            return tmp;
        }

        friend bool operator!=(const derived_type& lhs, const derived_type& rhs)
        {
            return !(lhs == rhs);
        }
    };

    template <class Iterator, class Traits>
    using xforward_iterator_base_from_traits = xforward_iterator_base<
        Iterator,
        typename Traits::value_type,
        typename Traits::difference_type,
        typename Traits::pointer,
        typename Traits::reference>;

    /**************************************
     * class xbidirectional_iterator_base *
     **************************************/

    template <class I, class T, class D = std::ptrdiff_t, class P = T*, class R = T&>
    class xbidirectional_iterator_base : public xforward_iterator_base<I, T, D, P, R>
    {
    public:

        using derived_type = I;
        using value_type = T;
        using reference = R;
        using pointer = P;
        using difference_type = D;
        using iterator_category = std::bidirectional_iterator_tag;


        friend derived_type operator--(derived_type& d, int)
        {
            derived_type tmp(d);
            --d;
            return tmp;
        }
    };

    template <class Iterator, class Traits>
    using xbidirectional_iterator_base_from_traits = xbidirectional_iterator_base<
        Iterator,
        typename Traits::value_type,
        typename Traits::difference_type,
        typename Traits::pointer,
        typename Traits::reference>;

    /********************************
     * xrandom_access_iterator_base *
     ********************************/

    template <class I, class T, class D = std::ptrdiff_t, class P = T*, class R = T&>
    class xrandom_access_iterator_base : public xbidirectional_iterator_base<I, T, D, P, R>
    {
    public:

        using derived_type = I;
        using value_type = T;
        using reference = R;
        using pointer = P;
        using difference_type = D;
        using iterator_category = std::random_access_iterator_tag;

        reference operator[](difference_type n) const
        {
            return *(*static_cast<const derived_type*>(this) + n);
        }

        friend derived_type operator+(const derived_type& it, difference_type n)
        {
            derived_type tmp(it);
            return tmp += n;
        }

        friend derived_type operator+(difference_type n, const derived_type& it)
        {
            derived_type tmp(it);
            return tmp += n;
        }

        friend derived_type operator-(const derived_type& it, difference_type n)
        {
            derived_type tmp(it);
            return tmp -= n;
        }

        friend bool operator<=(const derived_type& lhs, const derived_type& rhs)
        {
            return !(rhs < lhs);
        }

        friend bool operator>=(const derived_type& lhs, const derived_type& rhs)
        {
            return !(lhs < rhs);
        }

        friend bool operator>(const derived_type& lhs, const derived_type& rhs)
        {
            return rhs < lhs;
        }
    };

    template <class Iterator, class Traits>
    using xrandom_access_iterator_base_from_traits = xrandom_access_iterator_base<
        Iterator,
        typename Traits::value_type,
        typename Traits::difference_type,
        typename Traits::pointer,
        typename Traits::reference>;

    /************************
     * select_iterator_base *
     ************************/

    namespace detail
    {
        template <class Iterator>
        using iterator_category_t = typename std::iterator_traits<Iterator>::iterator_category;

        template <class Iterator>
        using is_random_access_iterator = std::
            is_same<iterator_category_t<Iterator>, std::random_access_iterator_tag>;

        template <class Iterator>
        inline constexpr bool is_random_access_iterator_v = is_random_access_iterator<Iterator>::value;

        template <class Iterator>
        using is_bidirectional_iterator = std::disjunction<
            std::is_same<iterator_category_t<Iterator>, std::bidirectional_iterator_tag>,
            is_random_access_iterator<Iterator>>;

        template <class Iterator>
        inline constexpr bool is_bidirectional_iterator_v = is_bidirectional_iterator<Iterator>::value;
    }

    template <class Iterator>
    struct select_iterator_base
    {
        template <class I, class T, class D = std::ptrdiff_t, class P = T*, class R = T&>
        using type = std::conditional_t<
            detail::is_random_access_iterator_v<Iterator>,
            xrandom_access_iterator_base<I, T, D, P, R>,
            std::conditional_t<
                detail::is_bidirectional_iterator_v<Iterator>,
                xbidirectional_iterator_base<I, T, D, P, R>,
                xforward_iterator_base<I, T, D, P, R>>>;

        template <class I, class T>
        using from_traits = std::conditional_t<
            detail::is_random_access_iterator_v<Iterator>,
            xrandom_access_iterator_base_from_traits<I, T>,
            std::conditional_t<
                detail::is_bidirectional_iterator_v<Iterator>,
                xbidirectional_iterator_base_from_traits<I, T>,
                xforward_iterator_base_from_traits<I, T>>>;
    };

    template <class Iterator, class R = void>
    using enable_bidirectional_iterator = std::enable_if_t<detail::is_bidirectional_iterator_v<Iterator>, R>;

    template <class Iterator, class R = void>
    using enable_random_access_iterator = std::enable_if_t<detail::is_random_access_iterator_v<Iterator>, R>;

    /*******************
     * filter_iterator *
     *******************/

    template <class Predicate, class Iterator>
    class filter_iterator;

    template <class Predicate, class Iterator>
    struct select_filter_iterator_base
    {
        using type = typename select_iterator_base<Iterator>::
            template from_traits<filter_iterator<Predicate, Iterator>, std::iterator_traits<Iterator>>;
    };

    template <class Predicate, class Iterator>
    using select_filter_iterator_base_t = typename select_filter_iterator_base<Predicate, Iterator>::type;


    template <class Predicate, class Iterator>
    class filter_iterator : public select_filter_iterator_base_t<Predicate, Iterator>
    {
    public:

        using self_type = filter_iterator<Predicate, Iterator>;
        using base_type = select_filter_iterator_base_t<Predicate, Iterator>;

        using reference = typename base_type::reference;
        using pointer = typename base_type::pointer;
        using difference_type = typename base_type::difference_type;
        using iterator_category = typename base_type::iterator_category;

        filter_iterator() = default;

        filter_iterator(Iterator iter, Iterator begin, Iterator end)
            : m_pred()
            , m_iter(iter)
            , m_begin_limit(begin)
            , m_end(end)
        {
            if constexpr (detail::is_bidirectional_iterator<Iterator>::value)
            {
                --m_begin_limit;
            }
            next_valid_iterator();
        }

        template <class Pred>
        filter_iterator(Pred&& pred, Iterator iter, Iterator begin, Iterator end)
            : m_pred(std::forward<Pred>(pred))
            , m_iter(iter)
            , m_begin_limit(begin)
            , m_end(end)
        {
            next_valid_iterator();
        }

        ~filter_iterator() = default;
        filter_iterator(const filter_iterator&) = default;
        filter_iterator(filter_iterator&&) = default;

        self_type& operator=(const self_type& rhs)
        {
            m_pred.reset();
            if (rhs.m_pred)
            {
                m_pred.emplace(*(rhs.m_pred));
            }
            m_iter = rhs.m_iter;
            m_begin_limit = rhs.m_begin_limit;
            m_end = rhs.m_end;
            return *this;
        }

        self_type& operator=(self_type&& rhs)
        {
            m_pred.reset();
            if (rhs.m_pred)
            {
                m_pred.emplace(*std::move(rhs.m_pred));
            }
            m_iter = std::move(rhs.m_iter);
            m_begin_limit = std::move(rhs.m_begin_limit);
            m_end = std::move(rhs.m_end);
            return *this;
        }

        self_type& operator++()
        {
            ++m_iter;
            next_valid_iterator();
            return *this;
        }

        template <class It = Iterator>
        enable_bidirectional_iterator<It, self_type&> operator--()
        {
            --m_iter;
            while (m_iter != m_begin_limit && !(m_pred.value()(*m_iter)))
            {
                --m_iter;
            }
            return *this;
        }

        template <class It = Iterator>
        enable_random_access_iterator<It, self_type> operator+=(difference_type n)
        {
            advance(n);
            return *this;
        }

        template <class It = Iterator>
        enable_random_access_iterator<It, self_type> operator-=(difference_type n)
        {
            advance(-n);
            return *this;
        }

        template <class It = Iterator>
        enable_random_access_iterator<It, difference_type> operator-(const It& rhs) const
        {
            It tmp = rhs;
            difference_type res = 0;
            while (tmp++ != *this)
            {
                ++res;
            }
            return res;
        }

        reference operator*() const
        {
            return *m_iter;
        }

        pointer operator->() const
        {
            return m_iter.operator->();
        }

        friend bool operator==(const self_type& lhs, const self_type& rhs)
        {
            return lhs.m_iter == rhs.m_iter;
        }

        template <class It = Iterator>
        friend enable_random_access_iterator<It, bool>
        operator<(const self_type& lhs, const self_type& rhs)
        {
            return lhs.m_iter < rhs.m_iter;
        }

    private:

        void advance(difference_type n)
        {
            while (m_iter != m_end && n > 0)
            {
                ++(*this);
                --n;
            }
            while (m_iter != m_begin_limit && n < 0)
            {
                --(*this);
                ++n;
            }
        }

        void next_valid_iterator()
        {
            while (m_iter != m_end && !(m_pred.value()(*m_iter)))
            {
                ++m_iter;
            }
        }

        // Trick to enable move and copy assignment: since lambdas are
        // not assignable, we encapsulate them in an std::optional and
        // rely on it to implement assignment operators. The optional
        // should be replaced with a dedicated wrapper.
        std::optional<Predicate> m_pred;
        Iterator m_iter;
        Iterator m_begin_limit;
        Iterator m_end;
    };

    // TODO: move the following to a dedicated file if we code new ranges type
    // objects in the future.

    /**********
     * filter *
     **********/

    template <class Range, class Predicate>
    class filter
    {
    public:

        using range_iterator = decltype(std::declval<Range>().begin());
        using const_range_iterator = decltype(std::declval<Range>().cbegin());
        using iterator = filter_iterator<std::decay_t<Predicate>, range_iterator>;
        using const_iterator = filter_iterator<std::decay_t<Predicate>, const_range_iterator>;

        filter(Range& range, Predicate pred)
            : m_range(range)
            , m_pred(pred)
        {
        }

        iterator begin()
        {
            build_cache(m_first, m_range.get().begin(), m_range.get().begin(), m_range.get().end());
            return m_first.value();
        }

        iterator end()
        {
            build_cache(m_last, m_range.get().end(), m_range.get().begin(), m_range.get().end());
            return m_last.value();
        }

        const_iterator cbegin() const
        {
            build_cache(
                m_const_first,
                m_range.get().cbegin(),
                m_range.get().cbegin(),
                m_range.get().cend()
            );
            return m_const_first.value();
        }

        const_iterator cend() const
        {
            build_cache(m_const_last, m_range.get().cend(), m_range.get().cbegin(), m_range.get().cend());
            return m_const_last.value();
        }

    private:

        template <class FI, class I>
        void build_cache(std::optional<FI>& iter, I pos, I first, I last) const
        {
            if (!iter)
            {
                iter = FI(m_pred, pos, first, last);
            }
        }

        std::reference_wrapper<Range> m_range;
        Predicate m_pred;
        mutable std::optional<iterator> m_first;
        mutable std::optional<iterator> m_last;
        mutable std::optional<const_iterator> m_const_first;
        mutable std::optional<const_iterator> m_const_last;
    };
}

#endif
