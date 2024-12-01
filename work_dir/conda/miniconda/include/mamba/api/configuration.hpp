// Copyright (c) 2019, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_API_CONFIGURATION_HPP
#define MAMBA_API_CONFIGURATION_HPP

#include <functional>

#include <yaml-cpp/yaml.h>

#include "mamba/api/configuration_impl.hpp"
#include "mamba/api/constants.hpp"
#include "mamba/core/context.hpp"
#include "mamba/core/environment.hpp"
#include "mamba/core/mamba_fs.hpp"
#include "mamba/core/output.hpp"


namespace mamba
{
    class Configuration;

    enum class ConfigurationLevel
    {
        kApi = 0,
        kCli = 1,
        kEnvVar = 2,
        kFile = 3,
        kDefault = 4
    };


    enum class RCConfigLevel
    {
        kSystemDir = 0,
        kRootPrefix = 1,
        kHomeDir = 2,
        kTargetPrefix = 3
    };
}  // mamba

namespace YAML
{
    template <>
    struct convert<mamba::RCConfigLevel>
    {
        static Node encode(const mamba::RCConfigLevel& rhs)
        {
            switch (rhs)
            {
                case mamba::RCConfigLevel::kHomeDir:
                    return Node("HomeDir");
                case mamba::RCConfigLevel::kRootPrefix:
                    return Node("RootPrefix");
                case mamba::RCConfigLevel::kSystemDir:
                    return Node("SystemDir");
                case mamba::RCConfigLevel::kTargetPrefix:
                    return Node("TargetPrefix");
                default:
                    break;
            }
            return Node();
        }

        static bool decode(const Node& node, mamba::RCConfigLevel& rhs)
        {
            if (!node.IsScalar())
            {
                return false;
            }

            auto str = node.as<std::string>();

            if (str == "HomeDir")
            {
                rhs = mamba::RCConfigLevel::kHomeDir;
            }
            else if (str == "RootPrefix")
            {
                rhs = mamba::RCConfigLevel::kRootPrefix;
            }
            else if (str == "SystemDir")
            {
                rhs = mamba::RCConfigLevel::kSystemDir;
            }
            else if (str == "TargetPrefix")
            {
                rhs = mamba::RCConfigLevel::kTargetPrefix;
            }
            else
            {
                return false;
            }

            return true;
        }
    };
}  // YAML

namespace mamba
{
    namespace detail
    {
        struct ConfigurableImplBase
        {
            virtual ~ConfigurableImplBase() = default;

            bool rc_configured() const;
            bool env_var_configured() const;
            bool env_var_active() const;

            virtual bool cli_configured() const = 0;

            virtual void clear_rc_values() = 0;
            virtual void clear_cli_value() = 0;
            virtual void set_default_value() = 0;

            virtual void set_rc_yaml_value(const YAML::Node& value, const std::string& source) = 0;
            virtual void set_rc_yaml_values(
                const std::map<std::string, YAML::Node>& values,
                const std::vector<std::string>& sources
            ) = 0;
            virtual void set_cli_yaml_value(const YAML::Node& value) = 0;
            virtual void set_cli_yaml_value(const std::string& value) = 0;
            virtual void set_yaml_value(const YAML::Node& value) = 0;
            virtual void set_yaml_value(const std::string& value) = 0;

            virtual void compute(int options, const ConfigurationLevel& level) = 0;


            virtual bool is_valid_serialization(const std::string& value) const = 0;
            virtual bool is_sequence() const = 0;

            virtual YAML::Node yaml_value() const = 0;
            virtual void dump_json(nlohmann::json& node, const std::string& name) const = 0;

            bool is_config_loading() const;

            std::string m_name;
            std::string m_group = "Default";
            std::string m_description = "No description provided";
            std::string m_long_description = "";
            Configuration* m_config = nullptr;

            std::vector<std::string> m_rc_sources;
            std::vector<std::string> m_sources;
            std::vector<std::string> m_source;

            std::set<std::string> m_needed_configs;
            std::set<std::string> m_implied_configs;

            bool m_rc_configurable = false;
            RCConfigLevel m_rc_configurable_policy = RCConfigLevel::kTargetPrefix;

            bool m_rc_configured = false;
            bool m_api_configured = false;

            std::vector<std::string> m_env_var_names = {};

            bool m_single_op_lifetime = false;
            int m_compute_counter = 0;
            bool m_lock = false;

            using post_context_hook_type = std::function<void()>;
            post_context_hook_type p_post_ctx_hook;
        };

        template <class T>
        struct ConfigurableImpl : ConfigurableImplBase
        {
            bool cli_configured() const override;

            void clear_rc_values() override;
            void clear_cli_value() override;
            void set_default_value() override;

            void set_rc_yaml_value(const YAML::Node& value, const std::string& source) override;
            void set_rc_yaml_values(
                const std::map<std::string, YAML::Node>& values,
                const std::vector<std::string>& sources
            ) override;
            void set_cli_yaml_value(const YAML::Node& value) override;
            void set_cli_yaml_value(const std::string& value) override;
            void set_yaml_value(const YAML::Node& value) override;
            void set_yaml_value(const std::string& value) override;

            void compute(int options, const ConfigurationLevel& level) override;

            bool is_valid_serialization(const std::string& value) const override;
            bool is_sequence() const override;

            YAML::Node yaml_value() const override;
            void dump_json(nlohmann::json& node, const std::string& name) const override;

            void set_rc_value(const T& value, const std::string& source);
            void set_rc_values(
                const std::map<std::string, T>& mapped_values,
                const std::vector<std::string>& sources
            );
            void set_value(const T& value);

            using cli_config_type = detail::cli_config<T>;
            using cli_storage_type = typename cli_config_type::storage_type;

            std::map<std::string, T> m_rc_values;
            std::map<std::string, T> m_values;
            T m_value;
            T m_default_value;
            cli_config_type m_cli_config;
            T* p_context = 0;

            using value_hook_type = std::function<T()>;
            using post_merge_hook_type = std::function<void(T&)>;

            value_hook_type p_default_value_hook;
            value_hook_type p_fallback_value_hook;
            post_merge_hook_type p_post_merge_hook;
        };
    }

    /****************
     * Configurable *
     ****************/

    class Configurable
    {
    public:

        template <class T>
        Configurable(const std::string& name, T* context);

        template <class T>
        Configurable(const std::string& name, const T& init);

        const std::string& name() const;

        const std::string& group() const;
        Configurable&& group(const std::string& group);

        const std::string& description() const;
        Configurable&& description(const std::string& desc);

        const std::string& long_description() const;
        Configurable&& long_description(const std::string& desc);

        const std::vector<std::string>& sources() const;
        const std::vector<std::string>& source() const;

        const std::set<std::string>& needed() const;
        Configurable&& needs(const std::set<std::string>& names);

        const std::set<std::string>& implied() const;
        Configurable&& implies(const std::set<std::string>& names);

        bool rc_configurable() const;
        RCConfigLevel rc_configurable_level() const;
        Configurable&& set_rc_configurable(RCConfigLevel level = RCConfigLevel::kTargetPrefix);

        bool rc_configured() const;
        bool env_var_configured() const;
        bool cli_configured() const;
        bool api_configured() const;
        bool configured() const;

        bool env_var_active() const;
        Configurable&& set_env_var_names(const std::vector<std::string>& names = {});

        bool has_single_op_lifetime() const;
        Configurable&& set_single_op_lifetime();

        void reset_compute_counter();
        void lock();
        void free();
        bool locked();

        template <class T>
        const T& value() const;

        template <class T>
        T& value();

        template <class T>
        const T& cli_value() const;

        template <class T>
        const std::vector<T>& values() const;

        template <class T>
        Configurable&& set_rc_value(const T& value, const std::string& source);

        template <class T>
        Configurable&& set_rc_values(
            const std::map<std::string, T>& mapped_values,
            const std::vector<std::string>& sources
        );

        template <class T>
        Configurable&& set_value(const T& value);

        template <class T>
        Configurable&& set_default_value(const T& value);

        Configurable&& clear_rc_values();
        Configurable&& clear_env_values();
        Configurable&& clear_cli_value();
        Configurable&& clear_api_value();
        Configurable&& clear_values();

        template <class T>
        using value_hook_type = typename detail::ConfigurableImpl<T>::value_hook_type;
        template <class T>
        using post_merge_hook_type = typename detail::ConfigurableImpl<T>::post_merge_hook_type;
        using post_context_hook_type = detail::ConfigurableImplBase::post_context_hook_type;

        template <class T>
        Configurable&& set_default_value_hook(value_hook_type<T> hook);
        template <class T>
        Configurable&& set_default_value_hook(T (*hook)());
        template <class T>
        Configurable&& set_fallback_value_hook(value_hook_type<T> hook);
        template <class T>
        Configurable&& set_fallback_value_hook(T (*hook)());
        template <class T>
        Configurable&& set_post_merge_hook(post_merge_hook_type<T> hook);
        template <class T>
        Configurable&& set_post_merge_hook(void (*hook)(T&));
        Configurable&& set_post_context_hook(post_context_hook_type hook);

        template <class T>
        using cli_storage_type = typename detail::ConfigurableImpl<T>::cli_storage_type;
        template <class T>
        Configurable&& set_cli_value(const T& value);
        template <class T>
        cli_storage_type<T>& get_cli_config();

        Configurable&& set_rc_yaml_value(const YAML::Node& value, const std::string& source);
        Configurable&& set_rc_yaml_values(
            const std::map<std::string, YAML::Node>& values,
            const std::vector<std::string>& sources
        );
        Configurable&& set_cli_yaml_value(const YAML::Node& value);
        Configurable&& set_cli_yaml_value(const std::string& value);
        Configurable&& set_yaml_value(const YAML::Node& value);
        Configurable&& set_yaml_value(const std::string& value);

        Configurable&&
        compute(int options = 0, const ConfigurationLevel& level = ConfigurationLevel::kDefault);

        bool is_valid_serialization(const std::string& value) const;
        bool is_sequence() const;

        YAML::Node yaml_value() const;
        void dump_json(nlohmann::json& node, const std::string& name) const;

        void set_configuration(Configuration& config)
        {
            p_impl->m_config = &config;
            assert(p_impl->m_config);
        }

    private:

        template <class T>
        detail::ConfigurableImpl<T>& get_wrapped();

        template <class T>
        const detail::ConfigurableImpl<T>& get_wrapped() const;

        std::unique_ptr<detail::ConfigurableImplBase> p_impl;
    };

    const int MAMBA_SHOW_CONFIG_VALUES = 1 << 0;
    const int MAMBA_SHOW_CONFIG_SRCS = 1 << 1;
    const int MAMBA_SHOW_CONFIG_DESCS = 1 << 2;
    const int MAMBA_SHOW_CONFIG_LONG_DESCS = 1 << 3;
    const int MAMBA_SHOW_CONFIG_GROUPS = 1 << 4;
    const int MAMBA_SHOW_ALL_CONFIGS = 1 << 5;
    const int MAMBA_SHOW_ALL_RC_CONFIGS = 1 << 6;

    /*****************
     * Configuration *
     * ***************/

    class Configuration
    {
    public:

        Configuration();
        ~Configuration();

        std::map<std::string, Configurable>& config();
        const std::map<std::string, Configurable>& config() const;

        Configurable& at(const std::string& name);
        const Configurable& at(const std::string& name) const;

        using grouped_config_type = std::pair<std::string, std::vector<const Configurable*>>;
        std::vector<grouped_config_type> get_grouped_config() const;

        std::vector<fs::u8path> sources() const;
        std::vector<fs::u8path> valid_sources() const;

        void set_rc_values(std::vector<fs::u8path> possible_rc_paths, const RCConfigLevel& level);

        void load();

        bool is_loading();

        void clear_rc_values();
        void clear_cli_values();
        void clear_values();

        /**
         * Pop values that should have a single operation lifetime to avoid memroy effect
         * between multiple operations.
         * It corresponds to CLI values in most of the cases, but may also include API
         * values if the `Configurable::has_single_op_lifetime` method returns true.
         * RC files and environment variables are always overriden when loading the
         * configuration.
         */
        void operation_teardown();

        std::string
        dump(int opts = MAMBA_SHOW_CONFIG_VALUES, std::vector<std::string> names = {}) const;

        Configurable& insert(Configurable configurable, bool allow_redefinition = false);

        void reset_configurables();

    protected:

        Configuration(const Configuration&) = delete;
        Configuration& operator=(const Configuration&) = delete;
        Configuration(Configuration&&) = delete;
        Configuration& operator=(Configuration&&) = delete;

        void set_configurables();

        void reset_compute_counters();

        void compute_loading_sequence();

        void clear_rc_sources();

        void
        add_to_loading_sequence(std::vector<std::string>& seq, const std::string& name, std::vector<std::string>&);

        static YAML::Node load_rc_file(const fs::u8path& file);

        static std::vector<fs::u8path> compute_default_rc_sources(const RCConfigLevel& level);

        std::vector<fs::u8path>
        get_existing_rc_sources(const std::vector<fs::u8path>& possible_rc_paths);

        std::vector<fs::u8path> m_sources;
        std::vector<fs::u8path> m_valid_sources;
        std::map<fs::u8path, YAML::Node> m_rc_yaml_nodes_cache;

        bool m_load_lock = false;

        std::map<std::string, Configurable> m_config;
        std::vector<std::string> m_config_order, m_loading_sequence;
    };

    /***********************************
     * ConfigurableImpl implementation *
     ***********************************/

    namespace detail
    {
        template <class T>
        bool ConfigurableImpl<T>::cli_configured() const
        {
            return m_cli_config.has_value();
        };

        template <class T>
        void ConfigurableImpl<T>::clear_rc_values()
        {
            this->m_rc_sources.clear();
            m_rc_values.clear();
            this->m_rc_configured = false;
        }

        template <class T>
        void ConfigurableImpl<T>::clear_cli_value()
        {
            m_cli_config.reset();
        }

        template <class T>
        void ConfigurableImpl<T>::set_default_value()
        {
            m_value = m_default_value;
        }

        template <class T>
        void
        ConfigurableImpl<T>::set_rc_yaml_value(const YAML::Node& value, const std::string& source)
        {
            try
            {
                set_rc_value(value.as<T>(), source);
            }
            catch (const YAML::Exception& e)
            {
                LOG_ERROR << "Bad conversion of configurable '" << this->m_name << "' from source '"
                          << source << "' : " << e.what();
            }
        }

        template <class T>
        void ConfigurableImpl<T>::set_rc_yaml_values(
            const std::map<std::string, YAML::Node>& values,
            const std::vector<std::string>& sources
        )
        {
            std::map<std::string, T> converted_values;
            for (auto& y : values)
            {
                converted_values.insert({ y.first, y.second.as<T>() });
            }
            set_rc_values(converted_values, sources);
        }

        template <class T>
        void ConfigurableImpl<T>::set_cli_yaml_value(const YAML::Node& value)
        {
            m_cli_config.storage() = value.as<T>();
        }

        template <class T>
        void ConfigurableImpl<T>::set_cli_yaml_value(const std::string& value)
        {
            m_cli_config.storage() = detail::Source<T>::deserialize(value);
        }

        template <class T>
        void ConfigurableImpl<T>::set_yaml_value(const YAML::Node& value)
        {
            set_value(value.as<T>());
        }

        template <class T>
        void ConfigurableImpl<T>::set_yaml_value(const std::string& value)
        {
            try
            {
                set_value(detail::Source<T>::deserialize(value));
            }
            catch (const YAML::Exception& e)
            {
                LOG_ERROR << "Bad conversion of configurable '" << this->m_name << "' with value '"
                          << value << "' : " << e.what();
                throw e;
            }
        }

        template <class T>
        bool ConfigurableImpl<T>::is_valid_serialization(const std::string& value) const
        {
            try
            {
                detail::Source<T>::deserialize(value);
                return true;
            }
            catch (...)
            {
                return false;
            }
        }

        template <class T>
        bool ConfigurableImpl<T>::is_sequence() const
        {
            return detail::Source<T>::is_sequence();
        }

        template <class T>
        YAML::Node ConfigurableImpl<T>::yaml_value() const
        {
            return YAML::Node(m_value);
        }

        template <class T>
        void ConfigurableImpl<T>::dump_json(nlohmann::json& node, const std::string& name) const
        {
            node[name] = m_value;
        }

        template <>
        inline void
        ConfigurableImpl<fs::u8path>::dump_json(nlohmann::json& node, const std::string& name) const
        {
            node[name] = m_value.string();
        }

        template <>
        inline void ConfigurableImpl<std::vector<fs::u8path>>::dump_json(
            nlohmann::json& node,
            const std::string& name
        ) const
        {
            std::vector<std::string> values(m_value.size());
            std::transform(
                m_value.begin(),
                m_value.end(),
                values.begin(),
                [](const auto& value) { return value.string(); }
            );
            node[name] = values;
        }

        template <class T>
        void ConfigurableImpl<T>::set_rc_value(const T& value, const std::string& source)
        {
            this->m_rc_sources.push_back(source);
            m_rc_values[source] = value;
            this->m_rc_configured = true;
        }

        template <class T>
        void ConfigurableImpl<T>::set_rc_values(
            const std::map<std::string, T>& mapped_values,
            const std::vector<std::string>& sources
        )
        {
            assert(mapped_values.size() == sources.size());
            this->m_rc_sources.insert(this->m_rc_sources.end(), sources.begin(), sources.end());
            m_rc_values.insert(mapped_values.begin(), mapped_values.end());
            this->m_rc_configured = true;
        }

        template <class T>
        void ConfigurableImpl<T>::set_value(const T& value)
        {
            m_value = value;
            this->m_api_configured = true;
        }

        template <class T>
        void ConfigurableImpl<T>::compute(int options, const ConfigurationLevel& level)
        {
            bool hook_disabled = options & MAMBA_CONF_DISABLE_HOOK;
            bool force_compute = options & MAMBA_CONF_FORCE_COMPUTE;

            if (force_compute)
            {
                LOG_TRACE << "Update configurable '" << this->m_name << "'";
            }
            else
            {
                LOG_TRACE << "Compute configurable '" << this->m_name << "'";
            }

            if (!force_compute && ((is_config_loading() && (m_compute_counter > 0))))
            {
                throw std::runtime_error(
                    "Multiple computation of '" + m_name + "' detected during loading sequence."
                );
            }

            auto& ctx = Context::instance();
            m_sources.clear();
            m_values.clear();

            if (this->m_api_configured && (level >= ConfigurationLevel::kApi))
            {
                m_sources.push_back("API");
                m_values.insert({ "API", m_value });
            }

            if (cli_configured() && (level >= ConfigurationLevel::kCli))
            {
                m_sources.push_back("CLI");
                m_values.insert({ "CLI", m_cli_config.value() });
            }

            if (env_var_configured() && env_var_active() && (level >= ConfigurationLevel::kEnvVar))
            {
                for (const auto& env_var : m_env_var_names)
                {
                    auto env_var_value = env::get(env_var);
                    if (env_var_value)
                    {
                        try
                        {
                            m_values.insert(
                                { env_var, detail::Source<T>::deserialize(env_var_value.value()) }
                            );
                            m_sources.push_back(env_var);
                        }
                        catch (const YAML::Exception& e)
                        {
                            LOG_ERROR << "Bad conversion of configurable '" << this->m_name
                                      << "' from environment variable '" << env_var
                                      << "' with value '" << env_var_value.value()
                                      << "' : " << e.what();
                            throw e;
                        }
                    }
                }
            }

            if (rc_configured() && !ctx.src_params.no_rc && (level >= ConfigurationLevel::kFile))
            {
                m_sources.insert(m_sources.end(), m_rc_sources.begin(), m_rc_sources.end());
                m_values.insert(m_rc_values.begin(), m_rc_values.end());
            }

            if ((p_default_value_hook != NULL) && (level >= ConfigurationLevel::kDefault))
            {
                m_sources.push_back("default");
                m_values.insert({ "default", p_default_value_hook() });
            }

            if (m_sources.empty() && (p_fallback_value_hook != NULL))
            {
                m_sources.push_back("fallback");
                m_values.insert({ "fallback", p_fallback_value_hook() });
            }

            if (!m_sources.empty())
            {
                detail::Source<T>::merge(m_values, m_sources, m_value, m_source);
            }
            else
            {
                m_value = m_default_value;
                m_source = detail::Source<T>::default_value(m_default_value);
            }

            if (!hook_disabled && (p_post_merge_hook != NULL))
            {
                p_post_merge_hook(m_value);
            }

            ++m_compute_counter;
            if (p_context != nullptr)
            {
                *p_context = m_value;
            }

            if (p_post_ctx_hook != nullptr)
            {
                p_post_ctx_hook();
            }
        }
    }

    /*******************************
     * Configurable implementation *
     *******************************/

    template <class T>
    Configurable::Configurable(const std::string& name, T* context)
        : p_impl(std::make_unique<detail::ConfigurableImpl<T>>())
    {
        auto& wrapped = get_wrapped<T>();
        wrapped.m_name = name;
        wrapped.m_value = *context;
        wrapped.m_default_value = *context;
        wrapped.m_source = detail::Source<T>::default_value(*context);
        wrapped.p_context = context;
    }

    template <class T>
    Configurable::Configurable(const std::string& name, const T& init)
        : p_impl(std::make_unique<detail::ConfigurableImpl<T>>())
    {
        auto& wrapped = get_wrapped<T>();
        wrapped.m_name = name;
        wrapped.m_value = init;
        wrapped.m_default_value = init;
        wrapped.m_source = detail::Source<T>::default_value(init);
    }

    template <class T>
    const T& Configurable::value() const
    {
        return const_cast<Configurable*>(this)->value<T>();
    }

    template <class T>
    T& Configurable::value()
    {
        if (p_impl->is_config_loading() && p_impl->m_compute_counter == 0)
        {
            throw std::runtime_error("Using '" + name() + "' value without previous computation.");
        }
        return get_wrapped<T>().m_value;
    }

    template <class T>
    const T& Configurable::cli_value() const
    {
        if (!cli_configured())
        {
            throw std::runtime_error("Trying to get unset CLI value of '" + name() + "'");
        }

        return get_wrapped<T>().m_cli_config.value();
    }

    template <class T>
    const std::vector<T>& Configurable::values() const
    {
        return get_wrapped<T>().m_values;
    }

    template <class T>
    Configurable&& Configurable::set_rc_value(const T& value, const std::string& source)
    {
        get_wrapped<T>().set_rc_value(value, source);
        return std::move(*this);
    }

    template <class T>
    Configurable&& Configurable::set_rc_values(
        const std::map<std::string, T>& mapped_values,
        const std::vector<std::string>& sources
    )
    {
        get_wrapped<T>().set_rc_values(mapped_values, sources);
        return std::move(*this);
    }

    template <class T>
    Configurable&& Configurable::set_value(const T& value)
    {
        get_wrapped<T>().set_value(value);
        return std::move(*this);
    }

    template <class T>
    Configurable&& Configurable::set_default_value(const T& value)
    {
        auto& wrapped = get_wrapped<T>();
        wrapped.m_default_value = value;
        wrapped.m_value = value;
        return std::move(*this);
    }

    template <class T>
    Configurable&& Configurable::set_default_value_hook(value_hook_type<T> hook)
    {
        get_wrapped<T>().p_default_value_hook = hook;
        return std::move(*this);
    }

    template <class T>
    Configurable&& Configurable::set_default_value_hook(T (*hook)())
    {
        return set_default_value_hook<T>(value_hook_type<T>(hook));
    }

    template <class T>
    Configurable&& Configurable::set_fallback_value_hook(value_hook_type<T> hook)
    {
        get_wrapped<T>().p_fallback_value_hook = hook;
        return std::move(*this);
    }

    template <class T>
    Configurable&& Configurable::set_fallback_value_hook(T (*hook)())
    {
        return set_fallback_value_hook<T>(value_hook_type<T>(hook));
    }

    template <class T>
    Configurable&& Configurable::set_post_merge_hook(post_merge_hook_type<T> hook)
    {
        get_wrapped<T>().p_post_merge_hook = hook;
        return std::move(*this);
    }

    template <class T>
    Configurable&& Configurable::set_post_merge_hook(void (*hook)(T&))
    {
        return set_post_merge_hook<T>(post_merge_hook_type<T>(hook));
    }

    template <class T>
    Configurable&& Configurable::set_cli_value(const T& value)
    {
        get_wrapped<T>().m_cli_config = value;
        return std::move(*this);
    }

    template <class T>
    auto Configurable::get_cli_config() -> cli_storage_type<T>&
    {
        return get_wrapped<T>().m_cli_config.m_storage;
    }

    template <class T>
    detail::ConfigurableImpl<T>& Configurable::get_wrapped()
    {
        try
        {
            auto& derived = dynamic_cast<detail::ConfigurableImpl<T>&>(*p_impl);
            return derived;
        }
        catch (const std::bad_cast& e)
        {
            LOG_ERROR << "Bad cast of Configurable '" << name() << "'";
            throw e;
        }
    }

    template <class T>
    const detail::ConfigurableImpl<T>& Configurable::get_wrapped() const
    {
        return const_cast<Configurable&>(*this).get_wrapped<T>();
    }

    /********************************
     * Configuration implementation *
     ********************************/

    inline Configurable& Configuration::insert(Configurable configurable, bool allow_redefinition)
    {
        std::string name = configurable.name();
        if (m_config.count(name) == 0)
        {
            auto [it, success] = m_config.insert({ name, std::move(configurable) });
            it->second.set_configuration(*this);
            m_config_order.push_back(name);
        }
        else
        {
            if (!allow_redefinition)
            {
                throw std::runtime_error("Redefinition of configurable '" + name + "' not allowed.");
            }
        }

        return m_config.at(name);
    }

    void use_conda_root_prefix(Configuration& config, bool force = false);
}

#endif  // MAMBA_CONFIG_HPP
