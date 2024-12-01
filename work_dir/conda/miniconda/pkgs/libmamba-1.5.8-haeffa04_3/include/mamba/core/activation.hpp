// Copyright (c) 2019, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_CORE_ACTIVATION_HPP
#define MAMBA_CORE_ACTIVATION_HPP

#include <map>
#include <string>
#include <utility>
#include <vector>

#include "mamba_fs.hpp"

// TODO write a map that keeps insertion order

namespace mamba
{
    enum class ActivationType
    {
        ACTIVATE,
        DEACTIVATE,
        REACTIVATE
    };

    struct EnvironmentTransform
    {
        std::string export_path;
        std::vector<std::string> unset_vars;
        std::vector<std::pair<std::string, std::string>> set_vars;
        std::vector<std::pair<std::string, std::string>> export_vars;
        std::vector<fs::u8path> activate_scripts;
        std::vector<fs::u8path> deactivate_scripts;
    };

    class Activator
    {
    public:

        virtual ~Activator() = default;

        Activator(const Activator&) = delete;
        Activator& operator=(const Activator&) = delete;
        Activator(Activator&&) = delete;
        Activator& operator=(Activator&&) = delete;

        virtual std::string script(const EnvironmentTransform& env) = 0;
        virtual std::pair<std::string, std::string>
        update_prompt(const std::string& conda_prompt_modifier) = 0;
        virtual std::string shell_extension() = 0;
        virtual std::string shell() = 0;

        std::vector<fs::u8path> get_activate_scripts(const fs::u8path& prefix);
        std::vector<fs::u8path> get_deactivate_scripts(const fs::u8path& prefix);

        std::string get_default_env(const fs::u8path& prefix);
        std::vector<std::pair<std::string, std::string>>
        get_environment_vars(const fs::u8path& prefix);

        std::string get_prompt_modifier(
            const fs::u8path& prefix,
            const std::string& conda_default_env,
            int old_conda_shlvl
        );

        std::vector<fs::u8path> get_PATH();

        std::string add_prefix_to_path(const fs::u8path& prefix, int old_conda_shlvl);
        std::string
        replace_prefix_in_path(const fs::u8path& old_prefix, const fs::u8path& new_prefix);
        std::string remove_prefix_from_path(const fs::u8path& prefix);

        void get_export_unset_vars(
            EnvironmentTransform& envt,
            const std::vector<std::pair<std::string, std::string>>& to_export
        );

        EnvironmentTransform build_reactivate();
        EnvironmentTransform build_deactivate();
        EnvironmentTransform build_activate(const fs::u8path& prefix);

        std::string activate(const fs::u8path& prefix, bool stack);
        std::string reactivate();
        std::string deactivate();

        virtual std::string hook_preamble() = 0;
        virtual std::string hook_postamble() = 0;
        virtual fs::u8path hook_source_path() = 0;

        std::string hook(const std::string& shell_type);

    protected:

        Activator();

        bool m_stack = false;
        ActivationType m_action;

        std::map<std::string, std::string> m_env;
    };

    class PosixActivator : public Activator
    {
    public:

        PosixActivator() = default;
        virtual ~PosixActivator() = default;

        std::string script(const EnvironmentTransform& env_transform) override;
        std::pair<std::string, std::string>
        update_prompt(const std::string& conda_prompt_modifier) override;
        std::string shell_extension() override;
        std::string shell() override;

        std::string hook_preamble() override;
        std::string hook_postamble() override;
        fs::u8path hook_source_path() override;
    };

    class CshActivator : public Activator
    {
    public:

        CshActivator() = default;
        virtual ~CshActivator() = default;

        std::string script(const EnvironmentTransform& env_transform) override;
        std::pair<std::string, std::string>
        update_prompt(const std::string& conda_prompt_modifier) override;
        std::string shell_extension() override;
        std::string shell() override;

        std::string hook_preamble() override;
        std::string hook_postamble() override;
        fs::u8path hook_source_path() override;
    };

    class CmdExeActivator : public Activator
    {
    public:

        CmdExeActivator() = default;
        virtual ~CmdExeActivator() = default;

        std::string script(const EnvironmentTransform& env_transform) override;
        std::pair<std::string, std::string>
        update_prompt(const std::string& conda_prompt_modifier) override;
        std::string shell_extension() override;
        std::string shell() override;

        std::string hook_preamble() override;
        std::string hook_postamble() override;
        fs::u8path hook_source_path() override;
    };

    class PowerShellActivator : public Activator
    {
    public:

        PowerShellActivator() = default;
        virtual ~PowerShellActivator() = default;

        std::string script(const EnvironmentTransform& env_transform) override;
        std::pair<std::string, std::string>
        update_prompt(const std::string& conda_prompt_modifier) override;
        std::string shell_extension() override;
        std::string shell() override;

        std::string hook_preamble() override;
        std::string hook_postamble() override;
        fs::u8path hook_source_path() override;
    };

    class XonshActivator : public Activator
    {
    public:

        XonshActivator() = default;
        virtual ~XonshActivator() = default;

        std::string script(const EnvironmentTransform& env_transform) override;
        std::pair<std::string, std::string>
        update_prompt(const std::string& conda_prompt_modifier) override;
        std::string shell_extension() override;
        std::string shell() override;

        std::string hook_preamble() override;
        std::string hook_postamble() override;
        fs::u8path hook_source_path() override;
    };

    class FishActivator : public Activator
    {
    public:

        FishActivator() = default;
        virtual ~FishActivator() = default;

        std::string script(const EnvironmentTransform& env_transform) override;
        std::pair<std::string, std::string>
        update_prompt(const std::string& conda_prompt_modifier) override;
        std::string shell_extension() override;
        std::string shell() override;

        std::string hook_preamble() override;
        std::string hook_postamble() override;
        fs::u8path hook_source_path() override;
    };


    std::vector<fs::u8path> get_path_dirs(const fs::u8path& prefix);

}  // namespace mamba

#endif
