
#ifndef MAMBA_CORE_UTIL_SCOPE_HPP
#define MAMBA_CORE_UTIL_SCOPE_HPP

#include <stdexcept>

#include "mamba/core/output.hpp"

#include "spdlog/spdlog.h"

namespace mamba
{

    template <typename F>
    struct on_scope_exit
    {
        F func;

        explicit on_scope_exit(F&& f)
            : func(std::forward<F>(f))
        {
        }

        ~on_scope_exit()
        {
            try
            {
                func();
            }
            catch (const std::exception& ex)
            {
                LOG_ERROR << fmt::format("Scope exit error (catched and ignored): {}", ex.what());
            }
            catch (...)
            {
                LOG_ERROR << "Scope exit unknown error (catched and ignored)";
            }
        }

        // Deactivate copy & move until we implement moves
        on_scope_exit(const on_scope_exit&) = delete;
        on_scope_exit& operator=(const on_scope_exit&) = delete;
        on_scope_exit(on_scope_exit&&) = delete;
        on_scope_exit& operator=(on_scope_exit&&) = delete;
    };
}

#endif
