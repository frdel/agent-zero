// Copyright (c) 2019, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_CORE_PROGRESS_BAR_HPP
#define MAMBA_CORE_PROGRESS_BAR_HPP

#include <chrono>
#include <cstddef>
#include <functional>
#include <string>

namespace mamba
{
    class ProgressBar;
    // TODO: find a way to define it here without
    // impoorting spdlog and modst of the STL.
    class ProgressBarRepr;

    enum ProgressBarMode
    {
        multi,
        aggregated
    };

    class ProgressProxy
    {
    public:

        ProgressProxy() = default;
        ProgressProxy(ProgressBar* ptr);
        ~ProgressProxy() = default;

        ProgressProxy(const ProgressProxy&) = default;
        ProgressProxy& operator=(const ProgressProxy&) = default;
        ProgressProxy(ProgressProxy&&) = default;
        ProgressProxy& operator=(ProgressProxy&&) = default;

        bool defined() const;
        operator bool() const;
        ProgressProxy& set_bar(ProgressBar* ptr);

        ProgressProxy& set_progress(std::size_t current, std::size_t total);
        ProgressProxy& update_progress(std::size_t current, std::size_t total);
        ProgressProxy& set_progress(double progress);
        ProgressProxy& set_current(std::size_t current);
        ProgressProxy& set_in_progress(std::size_t in_progress);
        ProgressProxy& update_current(std::size_t current);
        ProgressProxy& set_total(std::size_t total);
        ProgressProxy& set_speed(std::size_t speed);
        ProgressProxy& set_full();
        ProgressProxy& activate_spinner();
        ProgressProxy& deactivate_spinner();

        std::size_t current() const;
        std::size_t in_progress() const;
        std::size_t total() const;
        std::size_t speed() const;
        std::size_t
        avg_speed(const std::chrono::milliseconds& ref_duration = std::chrono::milliseconds::max());
        double progress() const;
        bool completed() const;

        ProgressProxy& set_prefix(const std::string& text);
        ProgressProxy& set_postfix(const std::string& text);
        ProgressProxy& set_repr_hook(std::function<void(ProgressBarRepr&)> f);
        ProgressProxy& set_progress_hook(std::function<void(ProgressProxy&)> f);
        ProgressProxy&
        mark_as_completed(const std::chrono::milliseconds& delay = std::chrono::milliseconds::zero());

        std::string elapsed_time_to_str() const;
        std::string prefix() const;

        ProgressBarRepr& update_repr(bool compute_progress = true);
        const ProgressBarRepr& repr() const;
        ProgressBarRepr& repr();
        ProgressProxy& print(std::ostream& stream, std::size_t width = 0, bool with_endl = true);

        ProgressProxy& start();
        ProgressProxy& pause();
        ProgressProxy& resume();
        ProgressProxy& stop();

        bool started() const;

        int width() const;

    private:

        ProgressBar* p_bar = nullptr;

        friend class ProgressBarManager;
    };
}

#endif
