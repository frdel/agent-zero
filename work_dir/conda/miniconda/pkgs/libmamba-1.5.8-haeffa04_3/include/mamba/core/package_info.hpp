// Copyright (c) 2019, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_CORE_PACKAGE_INFO
#define MAMBA_CORE_PACKAGE_INFO

#include <set>
#include <string>
#include <vector>

#include <nlohmann/json.hpp>

namespace mamba
{
    class PackageInfo
    {
    public:

        using field_getter = std::function<std::string(const PackageInfo&)>;
        using compare_fun = std::function<bool(const PackageInfo&, const PackageInfo&)>;

        static field_getter get_field_getter(std::string_view field_name);
        static compare_fun less(std::string_view member);
        static compare_fun equal(std::string_view member);

        PackageInfo() = default;
        explicit PackageInfo(nlohmann::json&& j);
        explicit PackageInfo(std::string name);
        PackageInfo(std::string name, std::string version, std::string build_string, std::size_t build_number);

        bool operator==(const PackageInfo& other) const;

        nlohmann::json json_record() const;
        nlohmann::json json_signable() const;
        std::string str() const;
        std::string long_str() const;

        std::string name = {};
        std::string version = {};
        std::string build_string = {};
        std::string noarch = {};
        std::size_t build_number = 0;
        /**
         * Could contain "conda-forge", "conda-forge/linux-64", or a url.
         *
         * @todo need to use a proper type for channels
         */
        std::string channel = {};
        std::string url = {};
        std::string subdir = {};
        std::string fn = {};
        std::string license = {};
        std::size_t size = 0;
        std::size_t timestamp = 0;
        std::string md5 = {};
        std::string sha256 = {};
        std::vector<std::string> track_features = {};
        std::vector<std::string> depends = {};
        std::vector<std::string> constrains = {};
        std::string signatures = {};
        std::set<std::string> defaulted_keys = {};
    };
}  // namespace mamba

#endif
