<div align="center">

<img src="docs/res/a0-vector-graphics/horizontal_banner.svg" alt="Agent Zero Banner" width="100%"/>

# Agent Zero
### Give your agent a full Linux computer.

Agent Zero is an open agent framework for work that needs more than chat: a Dockerized Linux desktop, a browser with DOM annotation, live document cowork, projects, skills, plugins, and a bridge back to your host machine.

[![Website](https://img.shields.io/badge/Website-agent--zero.ai-0A192F?style=for-the-badge&logo=vercel&logoColor=white)](https://agent-zero.ai)
[![Docs](https://img.shields.io/badge/Docs-Read%20the%20guides-1F6FEB?style=for-the-badge&logo=readthedocs&logoColor=white)](./docs/)
[![Discord](https://img.shields.io/badge/Discord-Join%20us-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.gg/B8KZKNsPpj)
[![GitHub Sponsors](https://img.shields.io/badge/Sponsors-Thank%20you-FF69B4?style=for-the-badge&logo=githubsponsors&logoColor=white)](https://github.com/sponsors/agent0ai)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/agent0ai/agent-zero)

[Quick Start](#quick-start) |
[Why Agent Zero](#why-agent-zero) |
[Try These First](#try-these-first) |
[Deep Dives](#deep-dives) |
[Docs](#documentation)

</div>

<div align="center">
<img alt="Agent Zero driving Blender in its built-in XFCE desktop" src="docs/res/usage/webui/agentzero-xfce-computer.gif" width="100%" />
</div>

# Why Agent Zero

| Feature | Why it matters |
| --- | --- |
| **Full Linux desktop** | The agent can use real GUI software, terminals, files, and desktop apps inside the Canvas. |
| **Browser DOM annotation** | Click page elements and turn them into inspect, change, lift, or review instructions. |
| **Live document cowork** | Edit Markdown, Writer, Spreadsheet, and Presentation files together instead of losing work in chat. |
| **Plugin Hub** | Install 100+ community plugins or publish your own extension points. |
| **Projects and memory** | Keep files, instructions, secrets, memories, repositories, and model-preset choices isolated per project. |
| **Host-machine bridge** | Connect with the A0 CLI so the same agent can work in your real local repositories. |
| **Multi-agent cooperation** | Let agents delegate research, coding, analysis, or review tasks to focused subagents. |
| **Transparent internals** | Prompts, tools, plugins, skills, and settings are inspectable and editable. |

# Quick Start

## Recommended: A0 Launcher

The desktop **A0 Launcher** is the fastest guided path on a personal machine. Download it, open it, and let it check Docker, create Instances, manage ports, and connect to local or remote Agent Zero installs.

Agent Zero runs wherever Docker runs, from a $6 VPS or Raspberry Pi to a local workstation or GPU server.

| Architecture | macOS | Linux | Windows |
| --- | --- | --- | --- |
| x86 | [Mac Intel](https://github.com/agent0ai/a0-launcher/releases/download/v1.9/a0-launcher-1.9-macos-x64.dmg) | [Linux x86](https://github.com/agent0ai/a0-launcher/releases/download/v1.9/a0-launcher-1.9-linux-x64.AppImage) | [Windows x86](https://github.com/agent0ai/a0-launcher/releases/download/v1.9/a0-launcher-1.9-windows-x64.exe) |
| ARM64 | [Mac Apple Silicon](https://github.com/agent0ai/a0-launcher/releases/download/v1.9/a0-launcher-1.9-macos-arm64.dmg) | [Linux ARM64](https://github.com/agent0ai/a0-launcher/releases/download/v1.9/a0-launcher-1.9-linux-arm64.AppImage) | [Windows ARM64](https://github.com/agent0ai/a0-launcher/releases/download/v1.9/a0-launcher-1.9-windows-arm64.exe) |

See the [A0 Launcher v1.9 release](https://github.com/agent0ai/a0-launcher/releases/tag/v1.9) for release notes and updater metadata. See the [Launcher guide](./docs/guides/launcher.md) for the first-run walkthrough.

<details>
<summary><strong>Other install paths</strong></summary>

## A0 Install

Use **A0 Install** when you want the terminal path: SSH sessions, servers, recovery shells, or a scriptable setup. It creates Dockerized Agent Zero instances, mounts each instance's data into `/a0/usr` inside the container, and uses a reuse-before-setup policy: it tries your current Docker CLI configuration, `DOCKER_HOST`, Docker contexts, and known local Docker-compatible endpoints before setting up a runtime.

### macOS / Linux

```bash
curl -fsSL https://bash.agent-zero.ai | bash
```

### Windows PowerShell

```powershell
irm https://ps.agent-zero.ai | iex
```

### Headless / scripted

For servers and automation, run the installer in Quick Start mode so it creates one instance and exits without opening menus:

```bash
curl -fsSL https://bash.agent-zero.ai | bash -s -- --quick-start --name agent-zero --port 5080
```

```powershell
& ([scriptblock]::Create((irm https://ps.agent-zero.ai))) -QuickStart -Name agent-zero -Port 5080
```

Use `--skip-runtime-setup` / `-SkipRuntimeSetup` when Docker must already be working and the installer should not try to set up a runtime. See the [A0 Install repository](https://github.com/agent0ai/a0-install) for all installer flags.

## Docker already installed? Run this directly

```bash
docker run -p 80:80 -v a0_usr:/a0/usr agent0ai/agent-zero
```

Open the Web UI, configure your LLM provider, and start with a concrete task. For the full setup and onboarding experience, see the [Installation guide](./docs/setup/installation.md).

</details>

## Troubleshooting

- **Docker is not running:** start Docker Desktop or your Docker service, then reopen the Launcher or rerun the install command.
- **Port 80 is already in use:** use the Launcher to pick another port, or run Docker directly with `-p 5080:80` and open `http://localhost:5080`.
- **Installing on a server:** use the A0 Install Quick Start command with `--quick-start --name agent-zero --port 5080`.
- **Still blocked:** see the [Troubleshooting guide](./docs/guides/troubleshooting.md).

# One-Click Deploy

<a href="https://repocloud.io/details/Agent%20Zero/"><img src="https://d16t0pc4846x52.cloudfront.net/deploylobe.svg" alt="Deploy on RepoCloud" height="40"></a>
<a href="https://railway.com/deploy/agent-zero"><img src="https://railway.com/button.svg" alt="Deploy on Railway" height="40"></a>

# Try These First

- **Annotate a design you like:** "Open this template site in the Browser. I'll annotate the hero section - re-implement it in my project's React + Tailwind stack."
- **Cowork on a spreadsheet:** "Create an editable ODS budget model with assumptions and monthly projections."
- **Drive a desktop app:** "Use the Linux Desktop to open Blender and create a simple 3D logo for me."
- **Review a web UI:** "Open my local app in the Browser. I will annotate the page with comments; then implement the requested UI fixes."
- **Create a specialist:** "Create an Agent Profile for financial analysis with cautious reasoning, clear assumptions, and spreadsheet-first deliverables."
- **Recover a workspace:** "Show me recent Time Travel snapshots and explain what changed before I revert anything."

# Deep Dives

## A Real Linux Desktop in the Canvas

Agent Zero opens its own Linux desktop inside the right-side Canvas. Not a remote VM, not a shared clipboard, but a real XFCE desktop session running in the container.

That means the agent can drive *real desktop software*: open Blender to model a 3D object, jump into a terminal window, manage files visually, run a GUI tool that has no API.

You watch every action, and you can intervene at any moment because your mouse and keyboard share the same desktop.

See the [Desktop guide](./docs/guides/desktop.md) for the walkthrough, prompt examples, and how Desktop differs from Browser.

## Native Browser With DOM Annotations

<img alt="Annotating a webpage element in the Agent Zero browser" src="docs/res/usage/browser/annotation.gif" />
<br>

Agent Zero ships a built-in Browser with an optional live surface in the Canvas. The agent can open pages, read them, click, type, upload files, and take screenshots - the usual. The unusual part is **Annotate mode**.

Annotate mode turns any webpage into an interactive directive surface. Click an element to:

- **Change it** - "make this button blue and round the corners" runs as a JS instruction the agent applies and verifies.
- **Inspect it** - pull the DOM, the styles, the parent chain, the framework hints into the conversation.
- **Lift it** - see a card, hero, or component on someone else's site that you like? Capture it and have the agent re-implement it in your own project's stack.
- **Comment it** - leave actionable notes pinned to elements during a UI review; the agent reads the comments and ships the fixes.

The Docker browser is the default live Browser surface. Browser history keeps screenshots of important steps, so older chats can still show what the agent saw. The Browser also supports Chrome extensions inside the Docker browser, and **Bring Your Own Browser** through the A0 CLI Connector lets the agent drive Chrome, Edge, Brave, Opera, Vivaldi, or Chromium on your own machine.

See the [Browser guide](./docs/guides/browser.md) for screenshots, settings, host-browser setup, and troubleshooting.

## Cowork on Documents

### Markdown Editor With Live Cowork

<img alt="Agent Zero writing a TODO plan in the Canvas markdown editor" src="docs/res/usage/webui/markdown-editor.gif" />
<br>

The Canvas includes a rich Markdown editor designed for genuine cowork. Ask the agent to "write a plan to do X in a TODO.md in the open doc" and you'll see the file appear in the editor, character by character, while you keep typing in another section.

It's not a preview pane. It's a real editor with toolbar, formatting buttons, tables, and an editable source view - built so that the agent's edits and yours are equal first-class operations on the same document.

Use it for plans, TODOs, meeting notes, RFCs, project handoffs, or any artifact where the deliverable should *live as text* rather than be trapped inside chat scrollback.

### LibreOffice Integration

LibreOffice Writer, Calc, and Impress are wired up so you can type by hand while Agent Zero creates, updates, saves, and verifies the same files in real time.

ODT, ODS, and ODP binary formats are first-class citizens in the Agent Zero Desktop environment to align with the Open Document Format (ODF).

Use the Desktop toolbar to create and edit Writer, Spreadsheet, and Presentation LibreOffice files.

## Plugin Hub - 100+ Community Plugins

<img alt="Agent Zero Plugin Hub showing community plugins" src="docs/res/usage/plugins/plugin-hub-browse.png" />
<br>

Agent Zero is built for extension, not just configuration. The built-in **Plugin Hub** browses a growing catalog of community plugins - currently more than 100, covering:

- **Development frameworks** like the [BMAD Method](https://github.com/bmad-code-org/bmad-method) (full software development lifecycle with 20 specialist agents) and [Agent Skills](https://github.com/addyosmani/agent-skills).
- **Memory systems** - alternative memory backends, intelligent consolidation strategies, vector recall plugins.
- **Tools and integrations** - embedded terminals, custom browsers, deployment helpers, API clients.
- **UI extensions** - chat rename controls, sidebar tweaks, theme packs, custom Canvas panels.
- **Workflow plugins** - schedulers, multi-agent orchestration, project automations.

Install with a click from the Web UI, or publish your own to the index repository. Combined with custom prompts in `prompts/`, custom tools in `tools/`, MCP servers, A2A connectors, and project-scoped configuration, Agent Zero gives you a real surface area to shape the agent into whatever you need.

See the [Skills guide](./docs/guides/skills.md), the [Create a Small Plugin](./docs/guides/create-plugin.md) tutorial, and the [MCP setup](./docs/guides/mcp-setup.md) guide.

## Use Your OpenAI Codex Plan

<img alt="OAuth LLM plans in Agent Zero" src="docs/res/codex-screenshot.png" />
<br>

Agent Zero connects to your OpenAI Codex plan through the new OAuth flow. Sign in with your account, pick the Codex-backed provider, and let Agent Zero use the plan you already have. Click "Connect", enter the device code in the OpenAI page, choose your model, and you're set.

This is the first step toward account-backed LLM plans in Agent Zero. More integrations are coming, including Gemini CLI and Claude Code through extra-usage.

## A0 CLI Connector: Extend Onto Your Host Machine

<img alt="A0 CLI driving the host browser through a Google Cloud VM creation flow" src="docs/res/usage/a0-cli/host-browser.gif" />
<br>

The **A0 CLI Connector** is not a separate CLI agent. It connects to a running Agent Zero instance and gives that instance a terminal-native bridge to your host machine - so the same agent (with all its memory, projects, and skills) can also work on real files outside the Docker container.

Install the connector on the machine you want Agent Zero to work on, **not** inside the Agent Zero container.

### macOS / Linux

```bash
curl -LsSf https://cli.agent-zero.ai/install.sh | sh
```

### Windows PowerShell

```powershell
irm https://cli.agent-zero.ai/install.ps1 | iex
```

Then run `a0` to connect your terminal to an existing Agent Zero instance. It can usually discover a local instance automatically, or you can point it at a remote URL hosted somewhere else, such as a VPS or tunnel.

This is especially useful if you:

- prefer CLI workflows;
- want Agent Zero to work in an existing local repository;
- are running Agent Zero on a remote server;
- want Docker isolation for Agent Zero while still granting explicit, controlled access to host-side work.

For full setup, see the [A0 CLI Connector guide](https://www.agent-zero.ai/p/docs/a0-cli-connector/) (or the [in-repo guide](./docs/guides/a0-cli-connector.md)).

## Projects, Skills, Agent Profiles, and Model Presets

**Projects** isolate workspaces, instructions, memory, secrets, knowledge, repositories, and model-preset choices. Clone a public or private Git repo into a project and give the agent context that belongs to that work alone.

**Skills** can be loaded on demand by Agent Zero, or pinned from the chat input when you want a specific procedure to stay active.

**Agent Profiles** change the broader working style of the current chat.

**Model Presets** are named shortcuts for model setups, so you can quickly switch between fast, balanced, cheap, local, or high-power model choices.

## Multi-Agent Cooperation

Every agent can create subordinate agents to break down work. The superior gives tasks and receives reports; subagents keep their own contexts focused and return their findings when done.

This makes Agent Zero useful for research, software engineering, data analysis, plugin development, and tasks where several specialized perspectives are better than one overloaded context.

## Transparent and Extensible by Design

Almost nothing is hidden. Prompts live in `prompts/`, tools live in `tools/` or plugins, and built-in behavior can be inspected, changed, replaced, or extended.

Agent Zero supports plugins, MCP, A2A, custom tools, custom prompts, project-scoped configuration, environment-based deployment settings, and a Web UI designed to keep the agent's work readable in real time.

## Time Travel

Time Travel gives Agent Zero-owned `/a0/usr` workspaces snapshot history, diff inspection, travel, and revert. It is designed for recoverable agent work: see what changed, compare files, inspect a past state, and roll back when needed.

<img alt="Time Travel" src="docs/res/time-travel.png" />

It is not a replacement for Git or backups. It is a practical safety layer for the workspace where agents are actively creating and editing files.

## Real-World Use Cases

- **Software engineering:** inspect a codebase, make scoped edits, run tests, explain tradeoffs, and keep a recoverable history of file changes.
- **Host-machine development:** connect with `a0` and let Agent Zero work in your real local repositories, or clone them through Git Projects feature in the Web UI.
- **Design inspiration and UI iteration:** browse the web, annotate elements you like, and pull components into your own stack.
- **Financial analysis and charting:** collect data, correlate events, create spreadsheets, and generate editable charts.
- **Office deliverables:** cowork on documents, spreadsheets, and presentation decks instead of trapping the result in chat text.
- **Web and mobile QA:** browse an app, annotate UI issues, install browser extensions, and turn visual comments into actionable fixes.
- **API integration:** paste an API snippet, let the agent build a working example, and store the pattern for future use.
- **Client/project isolation:** keep memory, secrets, instructions, files, and model choices separated by project.
- **Scheduled operations:** run recurring checks and monitoring tasks with project-scoped context and credentials.

## Documentation

| I want to... | Start here |
| --- | --- |
| Install or update Agent Zero | [Installation](./docs/setup/installation.md) |
| Learn the UI and basic workflow | [Quickstart](./docs/quickstart.md) |
| Browse, annotate, and use Browser screenshots | [Browser guide](./docs/guides/browser.md) |
| Use the Linux desktop and LibreOffice | [Desktop guide](./docs/guides/desktop.md) |
| Connect Agent Zero to host-machine files and shell | [A0 CLI Connector](https://www.agent-zero.ai/p/docs/a0-cli-connector/) |
| Use projects and Git workspaces | [Projects guide](./docs/guides/projects.md) |
| Create a small plugin | [Create a Small Plugin](./docs/guides/create-plugin.md) |
| Add or remove active skills | [Skills guide](./docs/guides/skills.md) |
| Create or switch Agent Profiles | [Agent Profiles](./docs/guides/agent-profiles.md) |
| Create or switch Model Presets | [Model Presets](./docs/guides/model-presets.md) |
| Manage and curate memories | [Memory guide](./docs/guides/memory.md) |
| Learn the everyday chat controls | [Usage guide](./docs/guides/usage.md) |
| Configure MCP or external tools | [MCP setup](./docs/guides/mcp-setup.md) |
| Understand the architecture and internals | [DeepWiki for Agent Zero](https://deepwiki.com/agent0ai/agent-zero) |
| Build an advanced extension | [Extensions](./docs/developer/extensions.md) |
| Contribute to the project | [Contributing](./docs/guides/contribution.md) |
| Troubleshoot problems | [Troubleshooting](./docs/guides/troubleshooting.md) |

## Build With Us

Agent Zero is built for people who want to understand and shape their tools.

You can help by improving docs, creating skills, publishing plugins, testing model/provider setups, reporting bugs, sharing workflows, or contributing core improvements. Start with the [Contributing guide](./docs/guides/contribution.md), browse the [Plugin Hub](https://www.agent-zero.ai/p/docs/plugins/#plugin-hub), or bring ideas to Discord.

## Community and Support

- [Discord](https://discord.gg/B8KZKNsPpj) for live discussion and help.
- [Skool Community](https://www.skool.com/agent-zero) for community learning.
- [YouTube](https://www.youtube.com/@AgentZeroFW) for demos and tutorials.
- [X](https://x.com/Agent0ai), [LinkedIn](https://www.linkedin.com/company/109758317), and [Warpcast](https://warpcast.com/agent-zero) for updates.
- [GitHub Issues](https://github.com/agent0ai/agent-zero/issues) for bugs and feature requests.

[Space Agent](https://github.com/agent0ai/space-agent) is the related, more polished product direction for the agent-shaped workspace. Agent Zero remains the open framework and Linux-powered workbench.

## Safety Model

Agent Zero is powerful because it can use a real environment.

- Keep it running inside Docker or another isolated environment.
- Do not mount your entire home directory unless you understand the risk.
- Grant A0 CLI Read+Write access and remote code execution only for machines and workspaces you trust.
- Store credentials in project secrets or settings, not in prompts or public files.
- Review actions that touch accounts, money, production systems, or private data.
- Keep backups for important workspaces.
