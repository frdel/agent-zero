#ifndef MAMBA_ERROR_HANDLING_HPP
#define MAMBA_ERROR_HANDLING_HPP

#include <any>
#include <stdexcept>
#include <string>
#include <vector>

#include "tl/expected.hpp"

namespace mamba
{

    /*********************
     * Mamba exceptions *
     *********************/

    enum class mamba_error_code
    {
        unknown,
        aggregated,
        prefix_data_not_loaded,
        subdirdata_not_loaded,
        cache_not_loaded,
        repodata_not_loaded,
        configurable_bad_cast,
        env_lockfile_parsing_failed,
        openssl_failed,
        internal_failure,
        lockfile_failure,
        selfupdate_failure,
        satisfiablitity_error,
        user_interrupted,
    };

    class mamba_error : public std::runtime_error
    {
    public:

        using base_type = std::runtime_error;

        mamba_error(const std::string& msg, mamba_error_code ec);
        mamba_error(const char* msg, mamba_error_code ec);
        mamba_error(const std::string& msg, mamba_error_code ec, std::any&& data);
        mamba_error(const char* msg, mamba_error_code ec, std::any&& data);

        mamba_error_code error_code() const noexcept;
        const std::any& data() const noexcept;

    private:

        mamba_error_code m_error_code;
        std::any m_data;
    };

    class mamba_aggregated_error : public mamba_error
    {
    public:

        using base_type = mamba_error;
        using error_list_t = std::vector<mamba_error>;

        explicit mamba_aggregated_error(error_list_t&& error_list);

        const char* what() const noexcept override;

    private:

        error_list_t m_error_list;
        mutable std::string m_aggregated_message;
        static constexpr const char* m_base_message = "Multiple errors occured:\n";
    };

    /********************************
     * wrappers around tl::expected *
     ********************************/

    template <class T, class E>
    class expected_ref_wrapper : private tl::expected<std::reference_wrapper<T>, E>
    {
    public:

        using value_type = T;
        using self_type = expected_ref_wrapper<T, E>;
        using reference = std::reference_wrapper<T>;
        using base_type = tl::expected<reference, E>;

        using base_type::base_type;
        using base_type::operator=;
        using base_type::emplace;
        using base_type::error;
        using base_type::operator bool;
        using base_type::has_value;

        constexpr void swap(self_type& rhs) noexcept;

        constexpr const T* operator->() const noexcept;
        constexpr T* operator->() noexcept;
        constexpr const T& operator*() const& noexcept;
        constexpr T& operator*() & noexcept;
        constexpr const T&& operator*() const&& noexcept;
        constexpr T&& operator*() && noexcept;

        constexpr T& value() &;
        constexpr const T&& value() const&&;
        constexpr T&& value() &&;

        template <class U>
        constexpr T value_or(U&&) const&;
        template <class U>
        constexpr T value_or(U&&) &&;

        template <class T2, class E2>
        friend constexpr bool operator==(const self_type& x, const expected_ref_wrapper<T2, E2>& y);

        template <class T2>
        friend constexpr bool operator==(const self_type&, const T2&);

        template <class E2>
        friend constexpr bool operator==(const self_type&, const tl::unexpected<E2>&);
    };

    namespace detail
    {
        template <class T, class E>
        struct get_expected
        {
            using type = tl::expected<T, E>;
        };

        template <class T, class E>
        struct get_expected<T&, E>
        {
            using type = expected_ref_wrapper<T, E>;
        };
    }

    template <class T, class E = mamba_error>
    using expected_t = typename detail::get_expected<T, E>::type;

    /********************
     * helper functions *
     ********************/

    tl::unexpected<mamba_error> make_unexpected(const char* msg, mamba_error_code ec);

    tl::unexpected<mamba_error> make_unexpected(const std::string& msg, mamba_error_code sc);

    tl::unexpected<mamba_aggregated_error> make_unexpected(std::vector<mamba_error>&& error_list);

    template <class T, class E>
    tl::unexpected<E> forward_error(const tl::expected<T, E>& exp);

    template <class T, class E>
    tl::unexpected<E> forward_error(const expected_ref_wrapper<T, E>& exp);

    template <class T, class E>
    T& extract(tl::expected<T, E>& exp);

    template <class T, class E>
    const T& extract(const tl::expected<T, E>& exp);

    template <class T, class E>
    T&& extract(tl::expected<T, E>&& exp);

    template <class T, class E>
    T& extract(expected_ref_wrapper<T, E>& exp);

    template <class T, class E>
    const T& extract(const expected_ref_wrapper<T, E>& exp);

    template <class T, class E>
    T&& extract(expected_ref_wrapper<T, E>&& exp);

    /***************************************
     * expected_ref_wrapper implementation *
     ***************************************/

    template <class T, class E>
    constexpr void expected_ref_wrapper<T, E>::swap(self_type& rhs) noexcept
    {
        base_type::swap(rhs);
    }

    template <class T, class E>
    constexpr const T* expected_ref_wrapper<T, E>::operator->() const noexcept
    {
        return &(base_type::operator->()->get());
    }

    template <class T, class E>
    constexpr T* expected_ref_wrapper<T, E>::operator->() noexcept
    {
        return &(base_type::operator->()->get());
    }

    template <class T, class E>
    constexpr const T& expected_ref_wrapper<T, E>::operator*() const& noexcept
    {
        return base_type::operator*().get();
    }

    template <class T, class E>
    constexpr T& expected_ref_wrapper<T, E>::operator*() & noexcept
    {
        return base_type::operator*().get();
    }

    template <class T, class E>
    constexpr const T&& expected_ref_wrapper<T, E>::operator*() const&& noexcept
    {
        return std::move(base_type::operator*().get());
    }

    template <class T, class E>
    constexpr T&& expected_ref_wrapper<T, E>::operator*() && noexcept
    {
        return std::move(base_type::operator*().get());
    }

    template <class T, class E>
    constexpr T& expected_ref_wrapper<T, E>::value() &
    {
        return base_type::value().get();
    }

    template <class T, class E>
    constexpr const T&& expected_ref_wrapper<T, E>::value() const&&
    {
        return std::move(base_type::value().get());
    }

    template <class T, class E>
    constexpr T&& expected_ref_wrapper<T, E>::value() &&
    {
        return std::move(base_type::value().get());
    }

    template <class T, class E>
    template <class U>
    constexpr T expected_ref_wrapper<T, E>::value_or(U&& u) const&
    {
        return base_type::value_or(std::move(u)).get();
    }

    template <class T, class E>
    template <class U>
    constexpr T expected_ref_wrapper<T, E>::value_or(U&& u) &&
    {
        return base_type::value_or(std::move(u)).get();
    }

    template <class T1, class E1, class T2, class E2>
    constexpr bool
    operator==(const expected_ref_wrapper<T1, E1>& x, const expected_ref_wrapper<T2, E2>& y)
    {
        using base_type1 = typename expected_ref_wrapper<T1, E1>::base_type;
        using base_type2 = typename expected_ref_wrapper<T2, E2>::base_type;
        return operator==(static_cast<const base_type1&>(x), static_cast<const base_type2&>(y));
    }

    template <class T1, class E1, class T2>
    constexpr bool operator==(const expected_ref_wrapper<T1, E1>& x, const T2& y)
    {
        using base_type1 = typename expected_ref_wrapper<T1, E1>::base_type;
        return operator==(static_cast<const base_type1&>(x), y);
    }

    template <class T1, class E1, class E2>
    constexpr bool operator==(const expected_ref_wrapper<T1, E1>& x, const tl::unexpected<E2>& y)
    {
        using base_type1 = typename expected_ref_wrapper<T1, E1>::base_type;
        return operator==(static_cast<const base_type1&>(x), y);
    }

    /***********************************
     * helper funcitons implementation *
     ***********************************/

    template <class T, class E>
    tl::unexpected<E> forward_error(const tl::expected<T, E>& exp)
    {
        return tl::make_unexpected(exp.error());
    }

    template <class T, class E>
    tl::unexpected<E> forward_error(const expected_ref_wrapper<T, E>& exp)
    {
        return tl::make_unexpected(exp.error());
    }

    namespace detail
    {
        template <class T>
        decltype(auto) extract_impl(T&& exp)
        {
            if (exp)
            {
                return std::forward<T>(exp).value();
            }
            else
            {
                throw exp.error();
            }
        }
    }

    template <class T, class E>
    T& extract(tl::expected<T, E>& exp)
    {
        return detail::extract_impl(exp);
    }

    template <class T, class E>
    const T& extract(const tl::expected<T, E>& exp)
    {
        return detail::extract_impl(exp);
    }

    template <class T, class E>
    T&& extract(tl::expected<T, E>&& exp)
    {
        return detail::extract_impl(std::move(exp));
    }

    template <class T, class E>
    T& extract(expected_ref_wrapper<T, E>& exp)
    {
        return detail::extract_impl(exp);
    }

    template <class T, class E>
    const T& extract(const expected_ref_wrapper<T, E>& exp)
    {
        return detail::extract_impl(exp);
    }

    template <class T, class E>
    T&& extract(expected_ref_wrapper<T, E>&& exp)
    {
        return detail::extract_impl(std::move(exp));
    }

}

#endif
