#ifndef MAMBA_CORE_TIMEREF_HPP
#define MAMBA_CORE_TIMEREF_HPP

#include <chrono>
#include <string>

namespace mamba::validation
{

    /** Define a time reference.
     * TUF 5.1 'Record fixed update start time'
     * https://theupdateframework.github.io/specification/latest/#fix-time
     */
    class TimeRef
    {
    public:

        void set(const std::time_t& time);
        void set_now();
        std::string timestamp() const;

        TimeRef(const std::time_t& time);
        TimeRef();
        ~TimeRef() = default;

    private:

        std::time_t m_time_ref;
    };

}

#endif
