// Copyright (c) 2019, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_CORE_FS_HPP
#define MAMBA_CORE_FS_HPP

#include <filesystem>
#include <fstream>
#include <string>

#include <fmt/format.h>

#if !defined(_WIN32)
#include <fcntl.h>
#include <sys/stat.h>

// We can use the presence of UTIME_OMIT to detect platforms that provide
// utimensat.
#if defined(UTIME_OMIT)
#define USE_UTIMENSAT
#endif
#endif


//---- RATIONAL: Why do we wrap standard filesystem here? ----
// 1. This codebase relies on `std::string` and `const char*` to denote UTF-8 encoded text.
//    However `std::filesystem::path` constructors cannot assume that `std::string` is in
//    another encoding than the default one for the platform. This leads runtime issues on some
//    platforms (mostly Windows) where unicode paths either lead to exceptions being thrown
//    by standard filesystem functions or invalid unicode characters replacing the paths content.
//    To work around these issues we need to make sure `std::string` and other characters are
//    assumed to be UTF-8 and paths are built with that knowledge (the internal storage is optimal
//    for the platform so it is not a concern). In the same way we need paths to be convertible
//    to UTF-8 when converting them to string.
//    To achieve this we wrap a `std::filesystem::path` into our type `fs::u8path` so that
//    converions always happen correctly in it's conversion functions, like an encoding barrier.
//
// 2. Once using `fs::u8path`, we cannot use the standard library filesystem algorithms even with
//    `fs::u8path` implicit conversions without risking ending up with `std::filesystem::path` in
//    code like this:
//
//        fs::u8path prefix = ...;
//        prefix = rstrip(fs::weakly_canonical(env::expand_user(prefix)).string(), sep);
//
//    Here if `fs::weakly_canonical` is just an alias for `std::filesystem::weakly_canonical` it
//    then returns a `std::filesystem::path` and we then call `.string()` on it. That conversion
//    assumes that the resulting string should be of the system's encoding (it's unspecified by the
//    standard) which leads on Windows for example to the resulting `prefix` with invalid characters
//    which are then rejected by directory creation functions used later.
//    Another example:
//
//    for(const auto& entry : std::filesystem::directory_iterator(some_path))
//         if (ends_with(entry.path().string(), ".json")) { ...
//
//    Here `entry` is a `std::filesystem::directory_entry` therefore `.path()` returns a
//    `std::filesystem::path` which makes `.string()` return a string with unknown encoding.
//    Once passed in `ends_with` which takes a `u8path`, we end up with `???.json` because we
//    assumed in `u8path` constructor that this string would be UTF-8 when it is of unknown
//    encoding.
//
//    This kind of code seems valid but is silently broken. It is very easy to end up in this kind
//    of situation which makes us consider this situation brittle. Therefore, the only way to
//    prevent this kind of issue is to make sure every path value passed to and returned by
//    filesystem functions is first converted to `fs::u8path`, thus giving use guarantees about
//    encoding of our paths whatever the platform (as long as strings filtered to be UTF-8).
//
// 3. Previous versions of this header were using another library `ghc::filesystem` which is an
//    implementation of the standard filesystem library but with a guarantee that
//    `std::filesystem::path::string()` will always return UTF-8 encoding and that constructors
//    taking strings will assume that they are UTF-8. Why did we prefer doing our own wrapping? The
//    main reason we decided to wrap instead is that we want users of the library to be able to use
//    the standard filesystem library in conjonction with this library. As `ghc::filesystem` is a
//    re-implementation of `std::filesystem`, both cannot really be used together (or at least not
//    without a lot of explicit conversions). With our present wrapping we are completely compatible
//    with the standard library as we only add a thin encoding conversion layer over it's interface
//    (at least until the stnadard library provide better options).


namespace fs
{
    // sentinel argument for indicating the current time to last_write_time
    class now
    {
    };

    // Maintain `\` on Windows, `/` on other platforms
    std::filesystem::path normalized_separators(std::filesystem::path path);

    // Returns an utf-8 string given a standard path.
    std::string to_utf8(const std::filesystem::path& path);

    // Returns standard path given an utf-8 string.
    std::filesystem::path from_utf8(std::string_view u8string);

    // Same as std::filesystem::path except we only accept and output UTF-8 paths
    class u8path
    {
    public:

        u8path() = default;

        // Copy is allowed.
        u8path(const u8path& other) = default;
        u8path& operator=(const u8path& other) = default;

        // Move is allowed.
        u8path(u8path&& other) = default;
        u8path& operator=(u8path&& other) = default;

        //---- Construction ----

        u8path(const std::filesystem::path& path)
            : m_path(normalized_separators(path))
        {
        }

        u8path& operator=(const std::filesystem::path& path)
        {
            m_path = normalized_separators(path);
            return *this;
        }

        u8path& operator=(std::filesystem::path&& path)
        {
            m_path = normalized_separators(std::move(path));
            return *this;
        }

        u8path(std::string_view u8string)
            : m_path(from_utf8(u8string))
        {
        }

        u8path& operator=(std::string_view u8string)
        {
            m_path = from_utf8(u8string);
            return *this;
        }

        u8path(const char* u8string)
            : m_path(from_utf8(u8string))
        {
        }

        u8path& operator=(const char* u8string)
        {
            m_path = from_utf8(u8string);
            return *this;
        }

        u8path(const std::string& u8string)
            : m_path(from_utf8(u8string))
        {
        }

        u8path& operator=(const std::string& u8string)
        {
            m_path = from_utf8(u8string);
            return *this;
        }

        u8path& operator=(std::string&& u8string)
        {
            m_path = from_utf8(std::move(u8string));
            return *this;
        }

        //---- Wide character support (Windows usage mostly) - no Unicode conversions.

        u8path(const wchar_t* wstr)
            : m_path(normalized_separators(wstr))
        {
        }

        u8path& operator=(const wchar_t* wstr)
        {
            m_path = normalized_separators(wstr);
            return *this;
        }

        u8path(const std::wstring& wstr)
            : m_path(normalized_separators(wstr))
        {
        }

        u8path& operator=(const std::wstring& wstr)
        {
            m_path = normalized_separators(wstr);
            return *this;
        }

        u8path& operator=(std::wstring&& wstr)
        {
            m_path = normalized_separators(std::move(wstr));
            return *this;
        }

        //---- Append ----

        u8path operator/(const u8path& p) const
        {
            return m_path / p.m_path;
        }

        u8path operator/(const std::filesystem::path& p) const
        {
            return m_path / normalized_separators(p);
        }

        u8path operator/(std::string_view str) const
        {
            return m_path / from_utf8(str);
        }

        u8path operator/(std::wstring_view wstr) const
        {
            return m_path / normalized_separators(wstr);
        }

        u8path operator/(const std::string& str) const
        {
            return m_path / from_utf8(str);
        }

        u8path operator/(const std::wstring& wstr) const
        {
            return m_path / normalized_separators(wstr);
        }

        u8path operator/(const char* str) const
        {
            return m_path / from_utf8(str);
        }

        u8path operator/(const wchar_t* wstr) const
        {
            return m_path / normalized_separators(wstr);
        }

        template <typename T>
        u8path& operator/=(T&& some_string)
        {
            *this = *this / std::forward<T>(some_string);
            return *this;
        }

        u8path& operator+=(const u8path& to_append)
        {
            m_path += to_append.m_path;
            return *this;
        }

        u8path& operator+=(const std::filesystem::path& to_append)
        {
            m_path += normalized_separators(to_append);
            return *this;
        }

        u8path& operator+=(std::string_view to_append)
        {
            m_path = from_utf8(this->string().append(to_append));
            return *this;
        }

        u8path& operator+=(std::wstring_view to_append)
        {
            m_path += normalized_separators(to_append);
            return *this;
        }

        u8path& operator+=(const char* to_append)
        {
            m_path = from_utf8(this->string().append(to_append));
            return *this;
        }

        u8path& operator+=(const wchar_t* to_append)
        {
            m_path += normalized_separators(to_append);
            return *this;
        }

        u8path& operator+=(const std::string& to_append)
        {
            m_path = from_utf8(this->string().append(to_append));
            return *this;
        }

        u8path& operator+=(const std::wstring& to_append)
        {
            m_path += normalized_separators(to_append);
            return *this;
        }

        u8path& operator+=(char to_append)
        {
            m_path = from_utf8(this->string().append(1, to_append));
            return *this;
        }

        u8path& operator+=(wchar_t to_append)
        {
            m_path += to_append;
            m_path = normalized_separators(std::move(m_path));
            return *this;
        }


        //---- Conversions ----

        // Returns an utf-8 string.
        std::string string() const
        {
            return to_utf8(m_path);
        }

        // Returns an utf-8 string.
        operator std::string() const
        {
            return this->string();
        }

        // Returns the native wstring (UTF-16 on windows).
        std::wstring wstring() const
        {
            return m_path.wstring();
        }

        // Implicitly convert to native wstring (UTF-16 on windows).
        operator std::wstring() const
        {
            return this->wstring();
        }

        // Returns an utf-8 string using the ``/`` on all systems.
        std::string generic_string() const
        {
            return to_utf8(m_path.generic_string());
        }

        // Implicit conversion to standard path.
        operator std::filesystem::path() const
        {
            return m_path;
        }

        // Explicit conversion to standard path.
        const std::filesystem::path& std_path() const noexcept
        {
            return m_path;
        }

        //---- Parts ----

        u8path stem() const
        {
            return m_path.stem();
        }

        u8path parent_path() const
        {
            return m_path.parent_path();
        }

        u8path root_name() const
        {
            return m_path.root_name();
        }

        u8path root_directory() const
        {
            return m_path.root_directory();
        }

        u8path root_path() const
        {
            return m_path.root_path();
        }

        u8path filename() const
        {
            return m_path.filename();
        }

        u8path extension() const
        {
            return m_path.extension();
        }

        u8path lexically_relative(const u8path& base) const
        {
            return m_path.lexically_relative(base);
        }

        //---- Modifiers ----

        void clear() noexcept
        {
            m_path.clear();
        }

        u8path& remove_filename()
        {
            m_path.remove_filename();
            return *this;
        }

        u8path& replace_filename(const u8path replacement)
        {
            m_path.replace_filename(replacement.m_path);
            return *this;
        }

        u8path& replace_extension(const u8path replacement = u8path())
        {
            m_path.replace_extension(replacement.m_path);
            return *this;
        }

        //---- Operators ----

        friend bool operator==(const u8path& left, const u8path& right) noexcept
        {
            return left.m_path == right.m_path;
        }

        friend bool operator!=(const u8path& left, const u8path& right) noexcept
        {
            return left.m_path != right.m_path;
        }

        friend bool operator<(const u8path& left, const u8path& right) noexcept
        {
            return left.m_path < right.m_path;
        }

        friend bool operator<=(const u8path& left, const u8path& right) noexcept
        {
            return left.m_path <= right.m_path;
        }

        friend bool operator>(const u8path& left, const u8path& right) noexcept
        {
            return left.m_path > right.m_path;
        }

        friend bool operator>=(const u8path& left, const u8path& right) noexcept
        {
            return left.m_path >= right.m_path;
        }

        friend bool operator==(const u8path& left, const std::filesystem::path& right) noexcept
        {
            return left.m_path == right;
        }

        friend bool operator!=(const u8path& left, const std::filesystem::path& right) noexcept
        {
            return left.m_path != right;
        }

        friend bool operator<(const u8path& left, const std::filesystem::path& right) noexcept
        {
            return left.m_path < right;
        }

        friend bool operator<=(const u8path& left, const std::filesystem::path& right) noexcept
        {
            return left.m_path <= right;
        }

        friend bool operator>(const u8path& left, const std::filesystem::path& right) noexcept
        {
            return left.m_path > right;
        }

        friend bool operator>=(const u8path& left, const std::filesystem::path& right) noexcept
        {
            return left.m_path >= right;
        }

        friend bool operator==(const u8path& left, const std::string& right) noexcept
        {
            return left.m_path == from_utf8(right);
        }

        friend bool operator!=(const u8path& left, const std::string& right) noexcept
        {
            return left.m_path != from_utf8(right);
        }

        friend bool operator==(const u8path& left, const char* right) noexcept
        {
            return left.m_path == from_utf8(right);
        }

        friend bool operator!=(const u8path& left, const char* right) noexcept
        {
            return left.m_path != from_utf8(right);
        }

        friend bool operator==(const u8path& left, const std::wstring& right) noexcept
        {
            return left.m_path == right;
        }

        friend bool operator!=(const u8path& left, const std::wstring& right) noexcept
        {
            return left.m_path != right;
        }

        friend bool operator==(const u8path& left, const wchar_t* right) noexcept
        {
            return left.m_path == right;
        }

        friend bool operator!=(const u8path& left, const wchar_t* right) noexcept
        {
            return left.m_path != right;
        }


        //---- State ----

        bool empty() const noexcept
        {
            return m_path.empty();
        }

        bool is_absolute() const
        {
            return m_path.is_absolute();
        }

        bool is_relative() const
        {
            return m_path.is_relative();
        }

        bool has_root_path() const
        {
            return m_path.has_root_path();
        }

        bool has_root_name() const
        {
            return m_path.has_root_name();
        }

        bool has_root_directory() const
        {
            return m_path.has_root_directory();
        }

        bool has_relative_path() const

        {
            return m_path.has_relative_path();
        }

        bool has_parent_path() const
        {
            return m_path.has_parent_path();
        }

        bool has_filename() const
        {
            return m_path.has_filename();
        }

        bool has_stem() const
        {
            return m_path.has_stem();
        }

        bool has_extension() const
        {
            return m_path.has_extension();
        }

        //---- Utility ----

        // Writing to stream always using UTF-8.
        // Note: this will not work well on Windows with std::cout which doesnt know it's UTF-8
        //       In that case use `u8path::std_path()` instead.
        template <typename OutStream>
        friend OutStream& operator<<(OutStream& out, const u8path& path)
        {
            out << std::quoted(path.string());
            return out;
        }

        // Reads stream assuming UTF-8 encoding.
        template <typename InputStream>
        friend InputStream& operator>>(InputStream& in, u8path& path)
        {
            std::string raw_input;
            in >> std::quoted(raw_input);
            path.m_path = from_utf8(raw_input);
            return in;
        }

        friend std::size_t hash_value(const u8path& p) noexcept
        {
            return hash_value(p.m_path);
        }

        friend void swap(u8path& left, u8path& right) noexcept
        {
            swap(left.m_path, right.m_path);
        }

    private:

        std::filesystem::path m_path;
    };

    class directory_entry : private std::filesystem::directory_entry
    {
    public:

        using std::filesystem::directory_entry::exists;
        using std::filesystem::directory_entry::file_size;
        using std::filesystem::directory_entry::hard_link_count;
        using std::filesystem::directory_entry::is_block_file;
        using std::filesystem::directory_entry::is_character_file;
        using std::filesystem::directory_entry::is_directory;
        using std::filesystem::directory_entry::is_fifo;
        using std::filesystem::directory_entry::is_other;
        using std::filesystem::directory_entry::is_regular_file;
        using std::filesystem::directory_entry::is_socket;
        using std::filesystem::directory_entry::is_symlink;
        using std::filesystem::directory_entry::last_write_time;
        using std::filesystem::directory_entry::status;
        using std::filesystem::directory_entry::symlink_status;

        directory_entry() = default;
        directory_entry(const directory_entry&) = default;
        directory_entry(directory_entry&&) noexcept = default;
        directory_entry& operator=(const directory_entry&) = default;
        directory_entry& operator=(directory_entry&&) noexcept = default;

        template <typename... OtherArgs>
        explicit directory_entry(const u8path& path, OtherArgs&&... args)
            : std::filesystem::directory_entry(path.std_path(), std::forward<OtherArgs>(args)...)
        {
        }

        directory_entry(const std::filesystem::directory_entry& other)
            : std::filesystem::directory_entry(other)
        {
        }

        directory_entry(std::filesystem::directory_entry&& other)
            : std::filesystem::directory_entry(std::move(other))
        {
        }

        directory_entry& operator=(const std::filesystem::directory_entry& other)
        {
            std::filesystem::directory_entry::operator=(other);
            return *this;
        }

        directory_entry& operator=(std::filesystem::directory_entry&& other) noexcept
        {
            std::filesystem::directory_entry::operator=(std::move(other));
            return *this;
        }

        bool operator==(const directory_entry& other) const noexcept
        {
            return std::filesystem::directory_entry::operator==(other);
        }

        bool operator!=(const directory_entry& other) const noexcept
        {
            return std::filesystem::directory_entry::operator!=(other);
        }

        u8path path() const
        {
            return std::filesystem::directory_entry::path();
        }

        operator u8path() const noexcept
        {
            return std::filesystem::directory_entry::path();
        }

        template <typename... OtherArgs>
        void replace(const u8path p, OtherArgs&&... args)
        {
            std::filesystem::directory_entry::replace_filename(p, std::forward<OtherArgs>(args)...);
        }
    };

    static_assert(std::is_same_v<decltype(std::declval<directory_entry>().path()), u8path>);

    class directory_iterator : private std::filesystem::directory_iterator
    {
    public:

        using iterator_category = std::input_iterator_tag;
        using value_type = directory_entry;
        using difference_type = std::ptrdiff_t;
        using pointer = const directory_entry*;
        using reference = const directory_entry&;

        directory_iterator() = default;
        directory_iterator(const directory_iterator&) = default;
        directory_iterator(directory_iterator&&) noexcept = default;
        directory_iterator& operator=(const directory_iterator&) = default;
        directory_iterator& operator=(directory_iterator&&) noexcept = default;

        template <typename... OtherArgs>
        explicit directory_iterator(const u8path& path, OtherArgs&&... args)
            : std::filesystem::directory_iterator(path.std_path(), std::forward<OtherArgs>(args)...)
        {
        }

        const directory_entry& operator*() const
        {
            current_entry = std::filesystem::directory_iterator::operator*();
            return current_entry;
        }

        const directory_entry* operator->() const
        {
            return &(**this);
        }

        directory_iterator& operator++()
        {
            std::filesystem::directory_iterator::operator++();
            return *this;
        }

        directory_iterator& increment(std::error_code& ec)
        {
            std::filesystem::directory_iterator::increment(ec);
            return *this;
        }

        bool operator==(const directory_iterator& other) const noexcept
        {
            return static_cast<const std::filesystem::directory_iterator&>(*this) == other;
        }

        bool operator!=(const directory_iterator& other) const noexcept
        {
            return static_cast<const std::filesystem::directory_iterator&>(*this) != other;
        }

    private:

        mutable directory_entry current_entry;
    };

    static_assert(std::is_same_v<std::decay_t<decltype(*std::declval<directory_iterator>())>, directory_entry>);

    inline directory_iterator begin(directory_iterator iter) noexcept
    {
        return iter;
    }
    inline directory_iterator end(directory_iterator) noexcept
    {
        return {};
    }

    class recursive_directory_iterator : private std::filesystem::recursive_directory_iterator
    {
    public:

        using iterator_category = std::input_iterator_tag;
        using value_type = directory_entry;
        using difference_type = std::ptrdiff_t;
        using pointer = const directory_entry*;
        using reference = const directory_entry&;

        using std::filesystem::recursive_directory_iterator::depth;
        using std::filesystem::recursive_directory_iterator::disable_recursion_pending;
        using std::filesystem::recursive_directory_iterator::options;
        using std::filesystem::recursive_directory_iterator::pop;
        using std::filesystem::recursive_directory_iterator::recursion_pending;

        recursive_directory_iterator() = default;
        recursive_directory_iterator(const recursive_directory_iterator&) = default;
        recursive_directory_iterator(recursive_directory_iterator&&) noexcept = default;
        recursive_directory_iterator& operator=(const recursive_directory_iterator&) = default;
        recursive_directory_iterator& operator=(recursive_directory_iterator&&) noexcept = default;

        template <typename... OtherArgs>
        explicit recursive_directory_iterator(const u8path& path, OtherArgs&&... args)
            : std::filesystem::recursive_directory_iterator(
                path.std_path(),
                std::forward<OtherArgs>(args)...
            )
        {
        }

        const directory_entry& operator*() const noexcept
        {
            current_entry = std::filesystem::recursive_directory_iterator::operator*();
            return current_entry;
        }

        const directory_entry* operator->() const noexcept
        {
            return &(**this);
        }

        recursive_directory_iterator& operator++()
        {
            std::filesystem::recursive_directory_iterator::operator++();
            return *this;
        }

        recursive_directory_iterator& increment(std::error_code& ec)
        {
            std::filesystem::recursive_directory_iterator::increment(ec);
            return *this;
        }

        bool operator==(const recursive_directory_iterator& other) const noexcept
        {
            return static_cast<const std::filesystem::recursive_directory_iterator&>(*this) == other;
        }

        bool operator!=(const recursive_directory_iterator& other) const noexcept
        {
            return static_cast<const std::filesystem::recursive_directory_iterator&>(*this) != other;
        }

    private:

        mutable directory_entry current_entry;
    };

    static_assert(std::is_same_v<std::decay_t<decltype(*std::declval<directory_iterator>())>, directory_entry>);

    inline recursive_directory_iterator begin(recursive_directory_iterator iter) noexcept
    {
        return iter;
    }

    inline recursive_directory_iterator end(recursive_directory_iterator) noexcept
    {
        return {};
    }

    //---- Standard Filesystem element we reuse here -----

    using std::filesystem::copy_options;
    using std::filesystem::directory_options;
    using std::filesystem::file_status;
    using std::filesystem::file_time_type;
    using std::filesystem::file_type;
    using std::filesystem::filesystem_error;
    using std::filesystem::perm_options;
    using std::filesystem::perms;
    using std::filesystem::space_info;

    //----- Wrapped versions of std::filesystem algorithm that returns a `u8path` instead of
    //`std::filesystem::path`

    // path absolute(const path& p);
    // path absolute(const path& p, error_code& ec);
    template <typename... OtherArgs>
    u8path absolute(const u8path& path, OtherArgs&&... args)
    {
        return std::filesystem::absolute(path, std::forward<OtherArgs>(args)...);
    }

    // path canonical(const path& p);
    // path canonical(const path& p, error_code& ec);
    template <typename... OtherArgs>
    u8path canonical(const u8path& path, OtherArgs&&... args)
    {
        return std::filesystem::canonical(path, std::forward<OtherArgs>(args)...);
    }

    // void copy(const path& from, const path& to);
    // void copy(const path& from, const path& to, error_code& ec);
    // void copy(const path& from, const path& to, copy_options options);
    // void copy(const path& from, const path& to, copy_options options, error_code& ec);
    template <typename... OtherArgs>
    void copy(const u8path& from, const u8path& to, OtherArgs&&... args)
    {
        std::filesystem::copy(from, to, std::forward<OtherArgs>(args)...);
    }

    // bool copy_file(const path& from, const path& to);
    // bool copy_file(const path& from, const path& to, error_code& ec);
    // bool copy_file(const path& from, const path& to, copy_options option);
    // bool copy_file(const path& from, const path& to, copy_options option, error_code& ec);
    template <typename... OtherArgs>
    bool copy_file(const u8path& from, const u8path& to, OtherArgs&&... args)
    {
        return std::filesystem::copy_file(from, to, std::forward<OtherArgs>(args)...);
    }

    // void copy_symlink(const path& existing_symlink, const path& new_symlink);
    // void copy_symlink(const path& existing_symlink,
    //                   const path& new_symlink,
    //                   error_code& ec) noexcept;
    template <typename... OtherArgs>
    void copy_symlink(const u8path& existing_symlink, const u8path& new_symlink, OtherArgs&&... args)
    {
        std::filesystem::copy_symlink(existing_symlink, new_symlink, std::forward<OtherArgs>(args)...);
    }

    // bool create_directories(const path& p);
    // bool create_directories(const path& p, error_code& ec);
    template <typename... OtherArgs>
    bool create_directories(const u8path& path, OtherArgs&&... args)
    {
        return std::filesystem::create_directories(path, std::forward<OtherArgs>(args)...);
    }

    // bool create_directory(const path& p);
    // bool create_directory(const path& p, error_code& ec) noexcept;
    template <typename... OtherArgs>
    bool create_directory(const u8path& path, OtherArgs&&... args)
    {
        return std::filesystem::create_directory(path, std::forward<OtherArgs>(args)...);
    }

    // bool create_directory(const path& p, const path& attributes);
    // bool create_directory(const path& p, const path& attributes, error_code& ec) noexcept;
    template <typename... OtherArgs>
    bool create_directory(const u8path& path, const u8path& attributes, OtherArgs&&... args)
    {
        return std::filesystem::create_directory(path, attributes, std::forward<OtherArgs>(args)...);
    }


    // void create_directory_symlink(const path& to, const path& new_symlink);
    // void create_directory_symlink(const path& to, const path& new_symlink, error_code& ec)
    // noexcept;
    template <typename... OtherArgs>
    void create_directory_symlink(const u8path& to, const u8path& new_symlink, OtherArgs&&... args)
    {
        std::filesystem::create_directory_symlink(to, new_symlink, std::forward<OtherArgs>(args)...);
    }

    // void create_hard_link(const path& to, const path& new_hard_link);
    // void create_hard_link(const path& to, const path& new_hard_link, error_code& ec) noexcept;
    template <typename... OtherArgs>
    void create_hard_link(const u8path& to, const u8path& new_hard_link, OtherArgs&&... args)
    {
        std::filesystem::create_hard_link(to, new_hard_link, std::forward<OtherArgs>(args)...);
    }

    // void create_symlink(const path& to, const path& new_symlink);
    // void create_symlink(const path& to, const path& new_symlink, error_code& ec) noexcept;
    template <typename... OtherArgs>
    void create_symlink(const u8path& to, const u8path& new_symlink, OtherArgs&&... args)
    {
        std::filesystem::create_symlink(to, new_symlink, std::forward<OtherArgs>(args)...);
    }

    // path current_path();
    inline u8path current_path()
    {
        return std::filesystem::current_path();
    }

    // path current_path(error_code& ec);
    inline u8path current_path(std::error_code& ec)
    {
        return std::filesystem::current_path(ec);
    }

    // void current_path(const path& p);
    // void current_path(const path& p, error_code& ec) noexcept;
    template <typename... OtherArgs>
    void current_path(const u8path& path, OtherArgs&&... args)
    {
        std::filesystem::current_path(path, std::forward<OtherArgs>(args)...);
    }


    // bool equivalent(const path& p1, const path& p2);
    // bool equivalent(const path& p1, const path& p2, error_code& ec) noexcept;
    template <typename... OtherArgs>
    bool equivalent(const u8path& p1, const u8path& p2, OtherArgs&&... args)
    {
        return std::filesystem::equivalent(p1, p2, std::forward<OtherArgs>(args)...);
    }

    // bool exists(file_status s) noexcept;
    inline bool exists(file_status s) noexcept
    {
        return std::filesystem::exists(s);
    }

    // bool exists(const path& p);
    // bool exists(const path& p, error_code& ec) noexcept;
    template <typename... OtherArgs>
    bool exists(const u8path& path, OtherArgs&&... args)
    {
        return std::filesystem::exists(path, std::forward<OtherArgs>(args)...);
    }

    // uintmax_t file_size(const path& p);
    // uintmax_t file_size(const path& p, error_code& ec) noexcept;
    template <typename... OtherArgs>
    uintmax_t file_size(const u8path& path, OtherArgs&&... args)
    {
        return std::filesystem::file_size(path, std::forward<OtherArgs>(args)...);
    }

    // uintmax_t hard_link_count(const path& p);
    // uintmax_t hard_link_count(const path& p, error_code& ec) noexcept;
    template <typename... OtherArgs>
    uintmax_t hard_link_count(const u8path& path, OtherArgs&&... args)
    {
        return std::filesystem::hard_link_count(path, std::forward<OtherArgs>(args)...);
    }

    // bool is_block_file(file_status s) noexcept;
    inline bool is_block_file(file_status s) noexcept
    {
        return std::filesystem::is_block_file(s);
    }

    // bool is_block_file(const path& p);
    // bool is_block_file(const path& p, error_code& ec) noexcept;
    template <typename... OtherArgs>
    bool is_block_file(const u8path& path, OtherArgs&&... args)
    {
        return std::filesystem::is_block_file(path, std::forward<OtherArgs>(args)...);
    }

    // bool is_character_file(file_status s) noexcept;
    inline bool is_character_file(file_status s) noexcept
    {
        return std::filesystem::is_character_file(s);
    }

    // bool is_character_file(const path& p);
    // bool is_character_file(const path& p, error_code& ec) noexcept;
    template <typename... OtherArgs>
    bool is_character_file(const u8path& path, OtherArgs&&... args)
    {
        return std::filesystem::is_character_file(path, std::forward<OtherArgs>(args)...);
    }

    // bool is_directory(file_status s) noexcept;
    inline bool is_directory(file_status s) noexcept
    {
        return std::filesystem::is_directory(s);
    }

    // bool is_directory(const path& p);
    // bool is_directory(const path& p, error_code& ec) noexcept;
    template <typename... OtherArgs>
    bool is_directory(const u8path& path, OtherArgs&&... args)
    {
        return std::filesystem::is_directory(path, std::forward<OtherArgs>(args)...);
    }

    // bool is_empty(const path& p);
    // bool is_empty(const path& p, error_code& ec);
    template <typename... OtherArgs>
    bool is_empty(const u8path& path, OtherArgs&&... args)
    {
        return std::filesystem::is_empty(path, std::forward<OtherArgs>(args)...);
    }

    // bool is_fifo(file_status s) noexcept;
    inline bool is_fifo(file_status s) noexcept
    {
        return std::filesystem::is_fifo(s);
    }

    // bool is_fifo(const path& p);
    // bool is_fifo(const path& p, error_code& ec) noexcept;
    template <typename... OtherArgs>
    bool is_fifo(const u8path& path, OtherArgs&&... args)
    {
        return std::filesystem::is_fifo(path, std::forward<OtherArgs>(args)...);
    }

    // bool is_other(file_status s) noexcept;
    inline bool is_other(file_status s) noexcept
    {
        return std::filesystem::is_other(s);
    }

    // bool is_other(const path& p);
    // bool is_other(const path& p, error_code& ec) noexcept;
    template <typename... OtherArgs>
    bool is_other(const u8path& path, OtherArgs&&... args)
    {
        return std::filesystem::is_other(path, std::forward<OtherArgs>(args)...);
    }

    // bool is_regular_file(file_status s) noexcept;
    inline bool is_regular_file(file_status s) noexcept
    {
        return std::filesystem::is_regular_file(s);
    }

    // bool is_regular_file(const path& p);
    // bool is_regular_file(const path& p, error_code& ec) noexcept;
    template <typename... OtherArgs>
    bool is_regular_file(const u8path& path, OtherArgs&&... args)
    {
        return std::filesystem::is_regular_file(path, std::forward<OtherArgs>(args)...);
    }

    // bool is_socket(file_status s) noexcept;
    inline bool is_socket(file_status s) noexcept
    {
        return std::filesystem::is_socket(s);
    }

    // bool is_socket(const path& p);
    // bool is_socket(const path& p, error_code& ec) noexcept;
    template <typename... OtherArgs>
    bool is_socket(const u8path& path, OtherArgs&&... args)
    {
        return std::filesystem::is_socket(path, std::forward<OtherArgs>(args)...);
    }

    // bool is_symlink(file_status s) noexcept;
    inline bool is_symlink(file_status s) noexcept
    {
        return std::filesystem::is_symlink(s);
    }

    // bool is_symlink(const path& p);
    // bool is_symlink(const path& p, error_code& ec) noexcept;
    template <typename... OtherArgs>
    bool is_symlink(const u8path& path, OtherArgs&&... args)
    {
        return std::filesystem::is_symlink(path, std::forward<OtherArgs>(args)...);
    }

    // file_time_type last_write_time(const path& p);
    // file_time_type last_write_time(const path& p, error_code& ec) noexcept;
    template <typename... OtherArgs>
    file_time_type last_write_time(const u8path& path, OtherArgs&&... args)
    {
        return std::filesystem::last_write_time(path, std::forward<OtherArgs>(args)...);
    }

    // void last_write_time(const path& p, now _, error_code& ec) noexcept;
    inline void last_write_time(const u8path& path, now, std::error_code& ec) noexcept
    {
#if defined(USE_UTIMENSAT)
        if (utimensat(AT_FDCWD, path.string().c_str(), NULL, 0) == -1)
        {
            ec = std::error_code(errno, std::generic_category());
        }
#else
        auto new_time = fs::file_time_type::clock::now();
        std::filesystem::last_write_time(path, new_time, ec);
#endif
    }

    // void last_write_time(const path& p, now _);
    inline void last_write_time(const u8path& path, now sentinel)
    {
        std::error_code ec;
        last_write_time(path, sentinel, ec);
        if (ec)
        {
            throw filesystem_error("last_write_time", path, ec);
        }
    }

    // void last_write_time(const path& p, file_time_type new_time);
    // void last_write_time(const path& p, file_time_type new_time, error_code& ec) noexcept;
    template <typename... OtherArgs>
    void last_write_time(const u8path& path, file_time_type new_time, OtherArgs&&... args)
    {
        return std::filesystem::last_write_time(path, new_time, std::forward<OtherArgs>(args)...);
    }

    // void permissions(const path& p, perms prms, perm_options opts = perm_options::replace);
    // void permissions(const path& p, perms prms, error_code& ec) noexcept;
    // void permissions(const path& p, perms prms, perm_options opts, error_code& ec);
    template <typename... OtherArgs>
    void permissions(const u8path& path, OtherArgs&&... args)
    {
        std::filesystem::permissions(path, std::forward<OtherArgs>(args)...);
    }

    // path proximate(const path& p, error_code& ec);
    // path proximate(const path& p, const path& base = current_path());
    template <typename... OtherArgs>
    u8path proximate(const u8path& path, OtherArgs&&... args)
    {
        return std::filesystem::proximate(path, std::forward<OtherArgs>(args)...);
    }

    // path proximate(const path& p, const path& base, error_code& ec);
    template <typename... OtherArgs>
    u8path proximate(const u8path& path, const u8path& base, OtherArgs&&... args)
    {
        return std::filesystem::proximate(path, base, std::forward<OtherArgs>(args)...);
    }

    // path read_symlink(const path& p);
    // path read_symlink(const path& p, error_code& ec);
    template <typename... OtherArgs>
    u8path read_symlink(const u8path& path, OtherArgs&&... args)
    {
        return std::filesystem::read_symlink(path, std::forward<OtherArgs>(args)...);
    }

    // path relative(const path& p, error_code& ec);
    // path relative(const path& p, const path& base = current_path());
    template <typename... OtherArgs>
    u8path relative(const u8path& path, OtherArgs&&... args)
    {
        return std::filesystem::relative(path, std::forward<OtherArgs>(args)...);
    }

    // path relative(const path& p, const path& base, error_code& ec);
    template <typename... OtherArgs>
    u8path relative(const u8path& path, const u8path& base, OtherArgs&&... args)
    {
        return std::filesystem::relative(path, base, std::forward<OtherArgs>(args)...);
    }

    // bool remove(const path& p);
    // bool remove(const path& p, error_code& ec) noexcept;
    template <typename... OtherArgs>
    bool remove(const u8path& path, OtherArgs&&... args)
    {
#if defined(WIN32) && _MSC_VER < 1930  // Workaround https://github.com/microsoft/STL/issues/1511
        std::error_code errc;
        const auto file_status = std::filesystem::status(path, errc);
        if (!errc
            && (file_status.permissions() & std::filesystem::perms::owner_read)
                   != std::filesystem::perms::none
            && (file_status.permissions() & std::filesystem::perms::owner_write)
                   == std::filesystem::perms::none)
        {
            // The target file is read-only, we need to change that to fix the
            // VS bug.
            fs::permissions(path, fs::perms::owner_write, fs::perm_options::add);
        }
#endif
        return std::filesystem::remove(path, std::forward<OtherArgs>(args)...);
    }

    // uintmax_t remove_all(const path& p);
    // uintmax_t remove_all(const path& p, error_code& ec);
    template <typename... OtherArgs>
    uintmax_t remove_all(const u8path& path, OtherArgs&&... args)
    {
#if defined(WIN32) && _MSC_VER < 1930  // Workaround https://github.com/microsoft/STL/issues/1511
        if (!fs::exists(path))
        {
            return 0;
        }

        uintmax_t counter = 0;
        for (const auto& entry : fs::recursive_directory_iterator(path, args...))
        {
            if (fs::is_directory(entry.path()))
            {  // Skip directories, we'll delete them later.
                continue;
            }

            if (fs::remove(entry.path(), args...))
            {
                ++counter;
            }
            else
            {
                break;
            }
        }

        // Now remove all the directories resting.
        counter += std::filesystem::remove_all(path, args...);

        return counter;
#else
        return std::filesystem::remove_all(path, std::forward<OtherArgs>(args)...);
#endif
    }

    // void rename(const path& from, const path& to);
    // void rename(const path& from, const path& to, error_code& ec) noexcept;
    template <typename... OtherArgs>
    void rename(const u8path& from, const u8path& to, OtherArgs&&... args)
    {
        std::filesystem::rename(from, to, std::forward<OtherArgs>(args)...);
    }

    // void resize_file(const path& p, uintmax_t size);
    // void resize_file(const path& p, uintmax_t size, error_code& ec) noexcept;
    template <typename... OtherArgs>
    void resize_file(const u8path& path, OtherArgs&&... args)
    {
        std::filesystem::resize_file(path, std::forward<OtherArgs>(args)...);
    }

    // space_info space(const path& p);
    // space_info space(const path& p, error_code& ec) noexcept;
    template <typename... OtherArgs>
    space_info space(const u8path& path, OtherArgs&&... args)
    {
        return std::filesystem::space(path, std::forward<OtherArgs>(args)...);
    }

    // file_status status(const path& p);
    // file_status status(const path& p, error_code& ec) noexcept;
    template <typename... OtherArgs>
    file_status status(const u8path& path, OtherArgs&&... args)
    {
        return std::filesystem::status(path, std::forward<OtherArgs>(args)...);
    }

    // bool status_known(file_status s) noexcept;
    inline bool status_known(file_status s) noexcept
    {
        return std::filesystem::status_known(s);
    }

    // file_status symlink_status(const path& p);
    // file_status symlink_status(const path& p, error_code& ec) noexcept;
    template <typename... OtherArgs>
    file_status symlink_status(const u8path& path, OtherArgs&&... args)
    {
        return std::filesystem::symlink_status(path, std::forward<OtherArgs>(args)...);
    }

    // path temp_directory_path();
    // path temp_directory_path(error_code& ec);
    template <typename... OtherArgs>
    u8path temp_directory_path(OtherArgs&&... args)
    {
        return std::filesystem::temp_directory_path(std::forward<OtherArgs>(args)...);
    }

    // path weakly_canonical(const path& p);
    // path weakly_canonical(const path& p, error_code& ec);
    template <typename... OtherArgs>
    u8path weakly_canonical(const u8path& path, OtherArgs&&... args)
    {
        return std::filesystem::weakly_canonical(path, std::forward<OtherArgs>(args)...);
    }

}

template <>
struct std::hash<::fs::u8path>
{
    std::size_t operator()(const ::fs::u8path& path) const noexcept
    {
        return std::filesystem::hash_value(path.std_path()
        );  // TODO: once we stop using gcc < 12 we can properly use
            // std::hash<std::filesystem::path>{}(path.std_path());
    }
};

template <>
struct fmt::formatter<::fs::u8path>
{
    constexpr auto parse(format_parse_context& ctx) -> decltype(ctx.begin())
    {
        // make sure that range is empty
        if (ctx.begin() != ctx.end() && *ctx.begin() != '}')
        {
            throw format_error("invalid format");
        }
        return ctx.begin();
    }

    template <class FormatContext>
    auto format(const ::fs::u8path& path, FormatContext& ctx)
    {
        return fmt::format_to(ctx.out(), "'{}'", path.string());
    }
};
#endif
