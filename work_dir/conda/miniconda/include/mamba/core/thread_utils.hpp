// Copyright (c) 2019, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_CORE_THREAD_UTILS_HPP
#define MAMBA_CORE_THREAD_UTILS_HPP

#include <condition_variable>
#include <csignal>
#include <exception>
#include <functional>
#include <mutex>
#include <thread>
#include <utility>

namespace mamba
{

    /***********************
     * thread interruption *
     ***********************/

#ifndef _WIN32
    void set_signal_handler(const std::function<void(sigset_t)>& handler);

    int stop_receiver_thread();
    int kill_receiver_thread();
    void reset_sig_interrupted();
#endif

    void set_default_signal_handler();
    bool is_sig_interrupted() noexcept;
    void set_sig_interrupted() noexcept;


    void interruption_point();

    class thread_interrupted : public std::exception
    {
    public:

        thread_interrupted() = default;
        const char* what() const throw()
        {
            return "Thread interrupted";
        }
    };

    /****************
     * thread count *
     ****************/

    void increase_thread_count();
    void decrease_thread_count();
    int get_thread_count();

    // Waits until all other threads have finished
    // Must be called by the cleaning thread to ensure
    // it won't free ressources that could be required
    // by threads still active.
    void wait_for_all_threads();

    /**********
     * thread *
     **********/

    // Thread that increases the threads count upon
    // creation and decreases it upon deletion. Use it
    // when you need to ensure all threads have exited
    class thread
    {
    public:

        thread() = default;
        ~thread() = default;

        thread(const thread&) = delete;
        thread& operator=(const thread&) = delete;

        thread(thread&&) noexcept = default;
        thread& operator=(thread&&) = default;

        template <class Function, class... Args>
        explicit thread(Function&& func, Args&&... args);

        bool joinable() const noexcept;
        std::thread::id get_id() const noexcept;

        void join();
        void detach();
        std::thread::native_handle_type native_handle();

        std::thread extract()
        {
            return std::move(m_thread);
        }

    private:

        std::thread m_thread;
    };

    template <class Function, class... Args>
    inline thread::thread(Function&& func, Args&&... args)
    {
        increase_thread_count();
        auto f = std::bind(std::forward<Function>(func), std::forward<Args>(args)...);
        m_thread = std::thread(
            [f]()
            {
                try
                {
                    f();
                }
                catch (thread_interrupted&)
                {
                    errno = EINTR;
                }
                decrease_thread_count();
            }
        );
    }

    /**********************
     * interruption_guard *
     **********************/

    class interruption_guard
    {
    public:

        template <class Function, class... Args>
        interruption_guard(Function&& func, Args&&... args);
        ~interruption_guard();

        interruption_guard(const interruption_guard&) = delete;
        interruption_guard& operator=(const interruption_guard&) = delete;

        interruption_guard(interruption_guard&&) = delete;
        interruption_guard& operator=(interruption_guard&&) = delete;

    private:

        static std::function<void()> m_cleanup_function;
    };

    template <class Function, class... Args>
    inline interruption_guard::interruption_guard(Function&& func, Args&&... args)
    {
        m_cleanup_function = std::bind(std::forward<Function>(func), std::forward<Args>(args)...);
    }

    class counting_semaphore
    {
    public:

        inline counting_semaphore(std::ptrdiff_t max = 0);
        inline void lock();
        inline void unlock();
        inline std::ptrdiff_t get_max();
        inline void set_max(std::ptrdiff_t value);

    private:

        std::ptrdiff_t m_value, m_max;
        std::mutex m_access_mutex;
        std::condition_variable m_cv;
    };

    /*************************************
     * counting_semaphore implementation *
     *************************************/

    inline counting_semaphore::counting_semaphore(std::ptrdiff_t max)
    {
        set_max(max);
        m_value = m_max;
    }

    inline void counting_semaphore::lock()
    {
        std::unique_lock<std::mutex> lock(m_access_mutex);
        m_cv.wait(lock, [&]() { return m_value > 0; });
        --m_value;
    }

    inline void counting_semaphore::unlock()
    {
        {
            std::lock_guard<std::mutex> lock(m_access_mutex);
            if (++m_value <= 0)
            {
                return;
            }
        }
        m_cv.notify_all();
    }

    inline std::ptrdiff_t counting_semaphore::get_max()
    {
        return m_max;
    }

    inline void counting_semaphore::set_max(std::ptrdiff_t value)
    {
        std::ptrdiff_t new_max;
        if (value == 0)
        {
            new_max = std::thread::hardware_concurrency();
        }
        else if (value < 0)
        {
            new_max = std::thread::hardware_concurrency() + value;
        }
        else
        {
            new_max = value;
        }

        m_value += new_max - m_max;
        m_max = new_max;
    }
}  // namespace mamba

#endif
