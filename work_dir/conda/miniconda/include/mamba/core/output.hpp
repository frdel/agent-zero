// Copyright (c) 2019, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_CORE_OUTPUT_HPP
#define MAMBA_CORE_OUTPUT_HPP

#include <iosfwd>
#include <sstream>
#include <string>
#include <string_view>
#include <vector>

#include <fmt/color.h>
#include <nlohmann/json.hpp>

#include "mamba/core/common_types.hpp"
#include "mamba/core/progress_bar.hpp"

namespace mamba
{
    std::string cut_repo_name(const std::string& reponame);

    namespace printers
    {
        struct FormattedString
        {
            std::string s;
            fmt::text_style style = {};

            FormattedString() = default;

            inline FormattedString(const std::string& i)
                : s(i)
            {
            }

            inline FormattedString(const std::string_view i)
                : s(i)
            {
            }

            inline FormattedString(const char* i)
                : s(i)
            {
            }

            inline std::size_t size() const
            {
                return s.size();
            }
        };

        enum class alignment
        {
            left,
            right,
        };

        constexpr auto alignmentMarker(alignment a) -> std::string_view
        {
            switch (a)
            {
                case alignment::right:
                    return "alignment_right";
                case alignment::left:
                    return "alignment_right";
                default:
                    assert(false);
                    return "";
            }
        }

        class Table
        {
        public:

            Table(const std::vector<FormattedString>& header);

            void set_alignment(const std::vector<alignment>& a);
            void set_padding(const std::vector<int>& p);
            void add_row(const std::vector<FormattedString>& r);
            void
            add_rows(const std::string& header, const std::vector<std::vector<FormattedString>>& rs);

            std::ostream& print(std::ostream& out);

        private:

            std::vector<FormattedString> m_header;
            std::vector<alignment> m_align;
            std::vector<int> m_padding;
            std::vector<std::vector<FormattedString>> m_table;
        };

        std::ostringstream table_like(const std::vector<std::string>& data, std::size_t max_width);
    }  // namespace printers

    // Todo: replace public inheritance with
    // private one + using directives
    class ConsoleStream : public std::stringstream
    {
    public:

        ConsoleStream() = default;
        ~ConsoleStream();
    };

    class ProgressBarManager;
    class ConsoleData;

    class Console
    {
    public:

        Console(const Console&) = delete;
        Console& operator=(const Console&) = delete;

        Console(Console&&) = delete;
        Console& operator=(Console&&) = delete;

        static Console& instance();
        static ConsoleStream stream();
        static bool prompt(std::string_view message, char fallback = '_');
        static bool prompt(std::string_view message, char fallback, std::istream& input_stream);

        ProgressProxy add_progress_bar(const std::string& name, size_t expected_total = 0);
        void clear_progress_bars();
        ProgressBarManager& init_progress_bar_manager(ProgressBarMode mode = ProgressBarMode::multi);
        void terminate_progress_bar_manager();
        ProgressBarManager& progress_bar_manager();

        static std::string hide_secrets(std::string_view str);

        void print(std::string_view str, bool force_print = false);
        void json_write(const nlohmann::json& j);
        void json_append(const std::string& value);
        void json_append(const nlohmann::json& j);
        void json_down(const std::string& key);
        void json_up();

        static void print_buffer(std::ostream& ostream);

        void cancel_json_print();

    protected:

        Console();
        ~Console();

    private:

        void json_print();
        void deactivate_progress_bar(std::size_t idx, std::string_view msg = "");

        std::unique_ptr<ConsoleData> p_data;

        friend class ProgressProxy;
    };

    class MessageLogger
    {
    public:

        MessageLogger(const char* file, int line, log_level level);
        ~MessageLogger();

        std::stringstream& stream();

        static void activate_buffer();
        static void deactivate_buffer();
        static void print_buffer(std::ostream& ostream);

    private:

        std::string m_file;
        int m_line;
        log_level m_level;
        std::stringstream m_stream;

        static void emit(const std::string& msg, const log_level& level);
    };

}  // namespace mamba

#undef LOG
#undef LOG_TRACE
#undef LOG_DEBUG
#undef LOG_INFO
#undef LOG_WARNING
#undef LOG_ERROR
#undef LOG_CRITICAL

#define LOG(severity) mamba::MessageLogger(__FILE__, __LINE__, severity).stream()
#define LOG_TRACE LOG(mamba::log_level::trace)
#define LOG_DEBUG LOG(mamba::log_level::debug)
#define LOG_INFO LOG(mamba::log_level::info)
#define LOG_WARNING LOG(mamba::log_level::warn)
#define LOG_ERROR LOG(mamba::log_level::err)
#define LOG_CRITICAL LOG(mamba::log_level::critical)

#endif  // MAMBA_CORE_OUTPUT_HPP
