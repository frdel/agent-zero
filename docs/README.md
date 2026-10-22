![Agent Zero Logo](res/header.png)
# Agent Zero Documentation

Welcome to the Agent Zero documentation hub. Start with the practical guides
below: install it, open the Web UI, connect your host machine when needed, and
learn the main workflows by sight.

For architecture and source-linked internals, use
[DeepWiki for Agent Zero](https://deepwiki.com/agent0ai/agent-zero). The local
docs focus on practical setup, screenshots, and user workflows.

## Quick Start

- **[Quickstart Guide](quickstart.md):** Get up and running in 5 minutes with Agent Zero.
- **[Agent Zero Launcher](guides/launcher.md):** Use the desktop app to set up Docker, install Agent Zero, open Instances, or connect a remote Instance.
- **[First-Run Onboarding](guides/onboarding.md):** Choose Cloud, AI account, or Local access, then select main and utility models.
- **[Installation Guide](setup/installation.md):** A0 Launcher downloads, A0 Install, direct Docker, updates, and advanced Docker setup (includes [How to Update](setup/installation.md#how-to-update-agent-zero)).
- **[A0 CLI Connector](guides/a0-cli-connector.md):** Install the host connector for a running Agent Zero instance, use the command palette, and switch Browser modes.
- **[Self Update](guides/self-update.md):** How the in-app updater works (technical reference).
- **[VPS Deployment](setup/vps-deployment.md):** Deploy Agent Zero on a remote server.
- **[Development Setup](setup/dev-setup.md):** Set up a local development environment.

## User Guides

- **[Usage Guide](guides/usage.md):** Practical tour of Agent Zero's main workflows.
- **[Agent Zero Launcher](guides/launcher.md):** Fresh-machine setup, Installs, Instances, and workspace folder or Docker volume choices.
- **[Use Local Folders With Agent Zero](guides/local-folders.md):** Bind mounts, persistent user data, separate work folders, Docker CLI/Desktop/Compose examples, and Launcher storage links.
- **[First-Run Onboarding](guides/onboarding.md):** Set up OpenRouter, our proxy API or another provider with the guided wizard.
- **[Browser Guide](guides/browser.md):** Use the built-in Browser, live Canvas surface, annotations, screenshots, host browser mode, and extensions.
- **[Desktop Guide](guides/desktop.md):** Use the built-in Linux desktop, GUI apps, and LibreOffice Writer/Calc/Impress Cowork.
- **[A0 CLI Connector](guides/a0-cli-connector.md):** Terminal-first host connector for Agent Zero, with screenshots of the host picker, connected shell, command palette, and Browser modes.
- **[Create a Small Plugin](guides/create-plugin.md):** Build and review a tiny Web UI plugin that adds an unread dot to the chat list.
- **[Skills Guide](guides/skills.md):** Open the Skills selector, add active skills, and remove prompt protocol entries you no longer need.
- **[Agent Profiles](guides/agent-profiles.md):** Create and manage profiles in Easy or Advanced mode, set project availability, and control Tool, MCP, and Skill access.
- **[Model Presets](guides/model-presets.md):** Create simple named shortcuts for model setups.
- **[Memory Guide](guides/memory.md):** Search, edit, delete, and curate memories so useful context does not become stale noise.
- **[Projects Tutorial](guides/projects.md):** Learn to create isolated workspaces with dedicated context and memory.
- **[API Integration](guides/api-integration.md):** Add external APIs without writing code.
- **[MCP Setup](guides/mcp-setup.md):** Configure Model Context Protocol servers.
- **[A2A Setup](guides/a2a-setup.md):** Enable agent-to-agent communication.
- **[Troubleshooting](guides/troubleshooting.md):** Solutions to common issues and FAQs.

## Technical Reference

- **[DeepWiki for Agent Zero](https://deepwiki.com/agent0ai/agent-zero):** Architecture, Web UI internals, plugin lifecycle, backend APIs, deployment details, and source-linked explanations.
- **[Architecture](developer/architecture.md):** Short local handoff to DeepWiki plus practical starting points.
- **[Plugins](developer/plugins.md):** Compact plugin starting points and sharing checklist.
- **[Extensions](developer/extensions.md):** Short guide for when an extension is the right tool.
- **[Connectivity](developer/connectivity.md):** Choose between A0 CLI, MCP, A2A, and external APIs.
- **[WebSockets](developer/websockets.md):** Short local handoff to DeepWiki and source files.
- **[MCP Configuration](developer/mcp-configuration.md):** Compact reference for MCP JSON.
- **[Notifications](developer/notifications.md):** Notification system architecture and setup.
- **[Contributing Skills](developer/contributing-skills.md):** Create and share agent skills.
- **[Contributing Guide](guides/contribution.md):** Contribute to the Agent Zero project.

## Community & Support

- **Join the Community:** Connect with other users on [Discord](https://discord.gg/B8KZKNsPpj) to discuss ideas, ask questions, and collaborate.
- **Share Your Work:** Show off your Agent Zero creations and workflows in the [Show and Tell](https://github.com/agent0ai/agent-zero/discussions/categories/show-and-tell) area.
- **Report Issues:** Use the [GitHub issue tracker](https://github.com/agent0ai/agent-zero/issues) to report bugs or suggest features.
- **Follow Updates:** Subscribe to the [YouTube channel](https://www.youtube.com/@AgentZeroFW) for tutorials and release videos.

---

## Table of Contents

- [Quick Start](#quick-start)
  - [Quickstart Guide](quickstart.md)
  - [Agent Zero Launcher](guides/launcher.md)
  - [First-Run Onboarding](guides/onboarding.md)
  - [Installation Guide](setup/installation.md)
    - [How to Update Agent Zero](setup/installation.md#how-to-update-agent-zero)
    - [Manual Installation (Advanced)](setup/installation.md#manual-installation-advanced)
    - [Step 1: Install Docker Desktop](setup/installation.md#step-1-install-docker-desktop)
      - [Windows Installation](setup/installation.md#windows-installation)
      - [macOS Installation](setup/installation.md#macos-installation)
      - [Linux Installation](setup/installation.md#linux-installation)
    - [Step 2: Run Agent Zero](setup/installation.md#step-2-run-agent-zero)
      - [Pull Docker Image](setup/installation.md#21-pull-the-agent-zero-docker-image)
      - [Map Folders for Persistence](setup/installation.md#22-optional-map-folders-for-persistence)
      - [Run the Container](setup/installation.md#23-run-the-container)
      - [Access the Web UI](setup/installation.md#24-access-the-web-ui)
    - [Step 3: Configure Agent Zero](setup/installation.md#step-3-configure-agent-zero)
      - [Settings Configuration](setup/installation.md#settings-configuration)
      - [Agent Configuration](setup/installation.md#agent-configuration)
      - [Chat Model Settings](setup/installation.md#chat-model-settings)
      - [API Keys](setup/installation.md#api-keys)
      - [Authentication](setup/installation.md#authentication)
    - [Choosing Your LLMs](setup/installation.md#choosing-your-llms)
    - [Installing Ollama (Local Models)](setup/installation.md#installing-and-using-ollama-local-models)
    - [Using on Mobile Devices](setup/installation.md#using-agent-zero-on-your-mobile-device)
  - [Self Update (technical)](guides/self-update.md)
  - [VPS Deployment](setup/vps-deployment.md)
  - [Development Setup](setup/dev-setup.md)
  - [A0 CLI Connector](guides/a0-cli-connector.md)

- [User Guides](#user-guides)
  - [Usage Guide](guides/usage.md)
    - [Basic Operations](guides/usage.md#basic-operations)
    - [Plugins And Plugin Hub](guides/usage.md#plugins-and-plugin-hub)
    - [Skills, Agent Profiles, And Model Presets](guides/usage.md#skills-agent-profiles-and-model-presets)
      - [Skills](guides/usage.md#skills)
      - [Agent Profiles](guides/usage.md#agent-profiles)
      - [Model Presets](guides/usage.md#model-presets)
    - [File Attachments](guides/usage.md#file-attachments)
    - [Tool Usage](guides/usage.md#tool-usage)
      - [Browser Tool And Surface](guides/usage.md#browser-tool-and-surface)
      - [Desktop Surface](guides/usage.md#desktop-surface)
      - [Agent-To-Agent Communication](guides/usage.md#agent-to-agent-communication)
      - [Multi-Agent Cooperation](guides/usage.md#multi-agent-cooperation)
    - [Projects](guides/usage.md#projects)
    - [Tasks And Scheduling](guides/usage.md#tasks-and-scheduling)
    - [Secrets And Variables](guides/usage.md#secrets-and-variables)
    - [Remote Access Via Tunneling](guides/usage.md#remote-access-via-tunneling)
    - [Voice Interface](guides/usage.md#voice-interface)
    - [Mathematical Expressions](guides/usage.md#mathematical-expressions)
    - [File Browser](guides/usage.md#file-browser)
    - [Memory Management](guides/usage.md#memory-management)
    - [Backup And Restore](guides/usage.md#backup-and-restore)
  - [Agent Zero Launcher](guides/launcher.md)
    - [Workspace Storage](guides/launcher.md#workspace-storage)
  - [Use Local Folders With Agent Zero](guides/local-folders.md)
  - [Browser Guide](guides/browser.md)
  - [Desktop Guide](guides/desktop.md)
  - [A0 CLI Connector](guides/a0-cli-connector.md)
  - [Create a Small Plugin](guides/create-plugin.md)
  - [Skills Guide](guides/skills.md)
  - [Agent Profiles](guides/agent-profiles.md)
  - [Model Presets](guides/model-presets.md)
  - [Memory Guide](guides/memory.md)
  - [Projects Tutorial](guides/projects.md)
  - [API Integration](guides/api-integration.md)
  - [MCP Setup](guides/mcp-setup.md)
  - [A2A Setup](guides/a2a-setup.md)
  - [Troubleshooting](guides/troubleshooting.md)

- [Technical Reference](#technical-reference)
  - [DeepWiki for Agent Zero](https://deepwiki.com/agent0ai/agent-zero)
  - [Architecture](developer/architecture.md)
  - [Plugins](developer/plugins.md)
  - [Extensions](developer/extensions.md)
  - [Connectivity](developer/connectivity.md)
  - [WebSockets](developer/websockets.md)
  - [MCP Configuration](developer/mcp-configuration.md)
  - [Notifications](developer/notifications.md)
  - [Contributing Skills](developer/contributing-skills.md)
  - [Contributing Guide](guides/contribution.md)

---

## Documentation Ownership

| Content type | Home |
| --- | --- |
| Setup, screenshots, and everyday workflows | These docs |
| Architecture and source-linked internals | [DeepWiki](https://deepwiki.com/agent0ai/agent-zero) |
| Exact behavior | The current source code |
| Community help and examples | Discord, Skool, GitHub discussions |

### Your journey with Agent Zero starts now!

Ready to dive in? Start with the [Quickstart Guide](quickstart.md) for the fastest path to your first chat, or follow the [Installation Guide](setup/installation.md) for a detailed setup walkthrough.
