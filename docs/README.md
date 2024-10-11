![Agent Zero Logo](res/header.png)
# Agent Zero Documentation
To begin with Agent Zero, follow the links below for detailed guides on various topics:

- **[Installation](installation.md):** Set up Agent Zero on your system.
- **[Quick Start](quickstart.md):** Begin using Agent Zero with practical examples.
- **[Usage Guide](usage.md):** Explore advanced features and capabilities.
- **[Architecture Overview](architecture.md):** Understand the internal workings of the framework.
- **[Contributing](contribution.md):** Learn how to contribute to the Agent Zero project.
- **[Troubleshooting and FAQ](troubleshooting.md):** Find answers to common issues and questions.

## Key Features
- **Dynamic and Organic:** Evolves from past interactions.
- **Transparent and Customizable:** Open framework for user modifications.
- **Computer as a Tool:** Utilize your operating system's full capabilities.
- **Multi-Agent Cooperation:** Hierarchical structure for task management.
- **Persistent Memory:** Remembers past interactions for continuous learning.
- **Safe Code Execution:** Sandboxed Docker container environment for secure code execution.
- **Interactive Terminal Interface:** Real-time observation and intervention in a command-line interface.
- **Web UI:** User-friendly interface for managing agents.

### Your experience with Agent Zero starts now!

- **Join the Community:** Join the Agent Zero [Skool](https://www.skool.com/agent-zero) or [Discord](https://discord.gg/Z2tun2N3) community to discuss ideas, ask questions, and collaborate with other contributors.
- **Share your Work:** Share your Agent Zero creations, workflows and discoverings on our [Show and Tell](https://github.com/frdel/agent-zero/discussions/categories/show-and-tell) area on GitHub.
- **Report Issues:** Use the GitHub issue tracker to report bugs or suggest new features.

## Table of Contents

- [Welcome to the Agent Zero Documentation](#agent-zero-documentation)
  - [Key Features](#key-features)
    - [Start your experience with Agent Zero](#your-experience-with-agent-zero-starts-now)
  - [Table of Contents](#table-of-contents)
- [Installation guide for Windows, MacOS and Linux](installation.md)
  - [Windows Quick Start](installation.md#windows-quick-start)
  - [macOS Quick Start](installation.md#macos-quick-start)
  - [Linux Quick Start](installation.md#linux-quick-start)
  - [In-Depth Guide for Windows and MacOS](installation.md#in-depth-guide-for-windows-and-macos)
    - [1. Install Conda (miniconda)](installation.md#1-install-conda-miniconda)
    - [2. Install Docker (Docker Desktop application)](installation.md#2-install-docker-docker-desktop-application)
    - [3. Download Agent Zero](installation.md#3-download-agent-zero)
    - [4. Set up Conda environment](installation.md#4-set-up-conda-environment)
    - [5. Configure Agent Zero](installation.md#5-configure-agent-zero)
    - [6. Run Agent Zero](installation.md#6-run-agent-zero)
    - [Choosing Your LLMs](installation.md#choosing-your-llms)
      - [Installing and Using Ollama](installation.md#installing-and-using-ollama)
    - [How to update Agent Zero](installation.md#-how-to-update-agent-zero)
    - [Conclusion](installation.md#conclusion)
- [Quick Start](quickstart.md)
  - [Launching the Web UI](quickstart.md#launching-the-web-ui)
  - [Running a Simple Task](quickstart.md#running-a-simple-task)
  - [Example Interaction](quickstart.md#example-interaction)
  - [Next Steps](quickstart.md#next-steps)
- [Architecture Overview](architecture.md)
  - [Core Components](architecture.md#core-components)
  - [Agent Hierarchy and Communication](architecture.md#agent-hierarchy-and-communication)
  - [Interaction Flow](architecture.md#interaction-flow)
  - [Memory System](architecture.md#memory-system)
  - [Knowledge](architecture.md#knowledge)
  - [Prompts](architecture.md#prompts)
  - [Extensions](architecture.md#extensions)
    - [Structure of Extensions](architecture.md#structure-of-extensions)
    - [Types of Default Extensions](architecture.md#types-of-default-extensions)
  - [Key Files](architecture.md#key-files)
  - [Directory Structure](architecture.md#directory-structure)
  - [Customization](architecture.md#customization)
    - [Custom Prompts](architecture.md#custom-prompts)
      - [Changing the System Prompt Folder](architecture.md#changing-the-system-prompt-folder)
      - [Editing Prompts](architecture.md#editing-prompts)
    - [AgentConfig](architecture.md#agentconfig)
    - [Adding Tools](architecture.md#adding-tools)
    - [Adding Extensions](architecture.md#adding-extensions)
    - [Adding Instruments](architecture.md#adding-instruments)
    - [Important Considerations](architecture.md#important-considerations)
- [Usage Guide](usage.md)
  - [Tool Usage](usage.md#tool-usage)
  - [Example: Web Search and Code Execution](usage.md#example-web-search-and-code-execution)
  - [Memory Management](usage.md#memory-management)
  - [Multi-Agent Cooperation](usage.md#multi-agent-cooperation)
  - [Prompt Engineering](usage.md#prompt-engineering)
  - [Agent Behavior](usage.md#agent-behavior)
- [Contributing to Agent Zero](contribution.md)
  - [Getting Started](contribution.md#getting-started)
  - [Making Changes](contribution.md#making-changes)
  - [Submitting a Pull Request](contribution.md#submitting-a-pull-request)
  - [Documentation Stack](contribution.md#documentation-stack)
- [Troubleshooting and FAQ](troubleshooting.md)
  - [Frequently Asked Questions](troubleshooting.md#frequently-asked-questions)
  - [Troubleshooting](troubleshooting.md#troubleshooting)
    - [Installation](troubleshooting.md#installation)
    - [Usage](troubleshooting.md#usage)

## Changelog

### v0.7
- **Hybrid Memory System**: The memory system now operates on a hybrid model where part of the memory is managed automatically by the framework while users can also manually input information.
- **UI Revamp**
    - The chat interface is now fully responsive, has a progress bar and supports both light and dark themes.
- **Instruments**: Users can create custom tools (instruments) using markdown files. These instruments execute commands within the Docker container and can be used to perform various tasks, such as downloading YouTube videos or executing scripts.
- **Extensions Framework**
    - A new extensions framework has been introduced to keep the main agent.py file clean and maintainable. This allows for better organization of code with various subfolders for different functionalities. Files within python/extensions folders are executed in alphabetical order, streamlining processes like memory recall and solution memorization.
- **Reflection**
    - The framework supports advanced AI concepts like Chain of Thought and reflection through customizable prompts. Users can choose between two reflection models: dianoia-small and dianoia-xl.

### ⚠️ Changes to launch files since v0.6:
- main.py file has been replaced with run_ui.py (webui) and run_cli.py (terminal) launch files.
- configuration has been moved to initialize.py for both webui and terminal launch files.