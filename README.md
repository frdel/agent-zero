<div align="center">

# `Agent Zero`


[![Agent Zero Website](https://img.shields.io/badge/Website-agent--zero.ai-0A192F?style=for-the-badge&logo=vercel&logoColor=white)](https://agent-zero.ai) [![Thanks to Sponsors](https://img.shields.io/badge/GitHub%20Sponsors-Thanks%20to%20Sponsors-FF69B4?style=for-the-badge&logo=githubsponsors&logoColor=white)](https://github.com/sponsors/frdel) [![Follow on X](https://img.shields.io/badge/X-Follow-000000?style=for-the-badge&logo=x&logoColor=white)](https://x.com/Agent0ai) [![Join our Discord](https://img.shields.io/badge/Discord-Join%20our%20server-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.gg/B8KZKNsPpj) [![Subscribe on YouTube](https://img.shields.io/badge/YouTube-Subscribe-red?style=for-the-badge&logo=youtube&logoColor=white)](https://www.youtube.com/@AgentZeroFW) [![Connect on LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-blue?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/jan-tomasek/) [![Follow on Warpcast](https://img.shields.io/badge/Warpcast-Follow-5A32F3?style=for-the-badge)](https://warpcast.com/agent-zero)

[Introduction](#a-personal-organic-agentic-framework-that-grows-and-learns-with-you) •
[Installation](./docs/installation.md#windows-macos-and-linux-setup-guide) •
[Hacking Edition](#hacking-edition) •
[How to update](./docs/installation.md#how-to-update-agent-zero) •
[Documentation](./docs/README.md) •
[Usage](./docs/usage.md#basic-operations)

</div>


<div align="center">

> ### 📢 **NEWS: Agent Zero now includes MCP Server & Client functionality!** 📢
>
> Agent Zero can now act as an MCP Server for other LLM tools and use external MCP servers as tools
> [Learn more about MCP setup.](./docs/mcp_setup.md)

</div>



[![Showcase](/docs/res/showcase-thumb.png)](https://youtu.be/lazLNcEYsiQ)



## A personal, organic agentic framework that grows and learns with you


```mermaid
graph TD
    A[User] --> B(Agent Zero Core);
    B --> C[Persistent Memory];
    B --> D["Tools (Code, Search, etc.)"];
    B --> E[Customizable Prompts];
    B --> F[Multi-agent Cooperation];
    B --> G[Knowledge Base];
    B --> H[Instruments];

    style B fill:#0A192F,stroke:#0A192F,stroke-width:2px,color:#fff
    style C fill:#FF69B4,stroke:#FF69B4,stroke-width:2px,color:#fff
    style D fill:#5865F2,stroke:#5865F2,stroke-width:2px,color:#fff
    style E fill:#00A8E8,stroke:#00A8E8,stroke-width:2px,color:#fff
    style F fill:#FFBF00,stroke:#FFBF00,stroke-width:2px,color:#000
    style G fill:#39FF14,stroke:#39FF14,stroke-width:2px,color:#000
    style H fill:#9B59B6,stroke:#9B59B6,stroke-width:2px,color:#fff
```

- Agent Zero is not a predefined agentic framework. It is designed to be dynamic, organically growing, and learning as you use it.
- Agent Zero is fully transparent, readable, comprehensible, customizable, and interactive.
- Agent Zero uses the computer as a tool to accomplish its (your) tasks.

# 💡 Key Features

1. **General-purpose Assistant**

- Agent Zero is not pre-programmed for specific tasks (but can be). It is meant to be a general-purpose personal assistant. Give it a task, and it will gather information, execute commands and code, cooperate with other agent instances, and do its best to accomplish it.
- It has a persistent memory, allowing it to memorize previous solutions, code, facts, instructions, etc., to solve tasks faster and more reliably in the future.

![Agent 0 Working](/docs/res/ui-screen-2.png)

2. **Computer as a Tool**

- Agent Zero uses the operating system as a tool to accomplish its tasks. It has no single-purpose tools pre-programmed. Instead, it can write its own code and use the terminal to create and use its own tools as needed.
- The only default tools in its arsenal are online search, memory features, communication (with the user and other agents), and code/terminal execution. Everything else is created by the agent itself or can be extended by the user.
- Tool usage functionality has been developed from scratch to be the most compatible and reliable, even with very small models.
- [Default Tools:](./docs/architecture.md#built-in-tools) Agent Zero includes tools like knowledge, webpage content, code execution, and communication.
- [Creating Custom Tools:](./docs/hacking_and_customization.md#custom-tools) Extend Agent Zero's functionality by creating your own custom tools.
- [Instruments:](./docs/architecture.md#6-instruments) Instruments are a new type of tool that allow you to create custom functions and procedures that can be called by Agent Zero.

3. [Multi-agent Cooperation](./docs/usage.md#multi-agent-cooperation)

- Every agent has a superior agent giving it tasks and instructions. Every agent then reports back to its superior.
- In the case of the first agent in the chain (Agent 0), the superior is the human user; the agent sees no difference.
- Every agent can create its subordinate agent to help break down and solve subtasks. This helps all agents keep their context clean and focused.

```mermaid
sequenceDiagram
    participant User
    participant Agent 0 (Primary)
    participant Subordinate Agent

    User->>Agent 0 (Primary): Task/Instruction
    Agent 0 (Primary)->>Subordinate Agent: Delegates Sub-task
    Subordinate Agent-->>Agent 0 (Primary): Sub-task Result/Report
    Agent 0 (Primary)-->>User: Final Response/Report
```

![Multi-agent](docs/res/physics.png)
![Multi-agent 2](docs/res/physics-2.png)

4. [Completely Customizable and Extensible](./docs/hacking_and_customization.md)

- Almost nothing in this framework is hard-coded. Nothing is hidden. Everything can be extended or changed by the user.
- The whole behavior is defined by a system prompt in the **prompts/default/agent.system.md** file. Change this prompt and change the framework dramatically.
- The framework does not guide or limit the agent in any way. There are no hard-coded rails that agents have to follow.
- Every prompt, every small message template sent to the agent in its communication loop can be found in the **prompts/** folder and changed.
- Every default tool can be found in the **python/tools/** folder and changed or copied to create new predefined tools.

```mermaid
graph TD
    X(Agent Zero Core) --> P["Prompts (Personas, Behavior)"];
    X --> T["Tools (Custom Logic)"];
    X --> I["Instruments (Scripts, Procedures)"];
    X --> E["Extensions (Framework Modifications)"];

    style X fill:#0A192F,stroke:#0A192F,stroke-width:2px,color:#fff
    style P fill:#00A8E8,stroke:#00A8E8,stroke-width:2px,color:#fff
    style T fill:#5865F2,stroke:#5865F2,stroke-width:2px,color:#fff
    style I fill:#9B59B6,stroke:#9B59B6,stroke-width:2px,color:#fff
    style E fill:#FF69B4,stroke:#FF69B4,stroke-width:2px,color:#fff
```

![Prompts](/docs/res/prompts.png)

5. **Communication is Key**

- Give your agent a proper system prompt and instructions, and it can do miracles.
- Agents can communicate with their superiors and subordinates, asking questions, giving instructions, and providing guidance. Instruct your agents in the system prompt on how to communicate effectively.
- The terminal interface is real-time streamed and interactive. You can stop and intervene at any point. If you see your agent heading in the wrong direction, just stop and tell it right away.
- There is a lot of freedom in this framework. You can instruct your agents to regularly report back to superiors asking for permission to continue. You can instruct them to use point-scoring systems when deciding when to delegate subtasks. Superiors can double-check subordinates' results and dispute. The possibilities are endless.

## 🚀 Things you can build with Agent Zero

- **Development Projects** - `"Create a React dashboard with real-time data visualization"`

- **Data Analysis** - `"Analyze last quarter's NVIDIA sales data and create trend reports"`

- **Content Creation** - `"Write a technical blog post about microservices"`

- **System Admin** - `"Set up a monitoring system for our web servers"`

- **Research** - `"Gather and summarize five recent AI papers about CoT prompting"`

# Hacking Edition
- Agent Zero also offers a Hacking Edition based on Kali linux with modified prompts for cybersecurity tasks
- The setup is the same as the regular version, just use the frdel/agent-zero-run:hacking image instead of frdel/agent-zero-run


# ⚙️ Installation

Click to open a video to learn how to install Agent Zero:

[![Easy Installation guide](/docs/res/easy_ins_vid.png)](https://www.youtube.com/watch?v=L1_peV8szf8)

A detailed setup guide for Windows, macOS, and Linux with a video can be found in the Agent Zero Documentation at [this page](./docs/installation.md#windows-macos-and-linux-setup-guide).

### ⚡ Quick Start

```bash
# Pull and run with Docker

docker pull frdel/agent-zero-run
docker run -p 50001:80 frdel/agent-zero-run

# Visit http://localhost:50001 to start
```

## 🐳 Fully Dockerized, with [Speech-to-Text and TTS](./docs/usage.md#voice-interface)

![Settings](docs/res/settings-page-ui.png)

- Customizable settings allow users to tailor the agent's behavior and responses to their needs.
- The Web UI output is very clean, fluid, colorful, readable, and interactive; nothing is hidden.
- You can load or save chats directly within the Web UI.
- The same output you see in the terminal is automatically saved to an HTML file in **logs/** folder for every session.

![Time example](/docs/res/time_example.jpg)

- Agent output is streamed in real-time, allowing users to read along and intervene at any time.
- No coding is required; only prompting and communication skills are necessary.
- With a solid system prompt, the framework is reliable even with small models, including precise tool usage.

## 👀 Keep in Mind

1. **Agent Zero Can Be Dangerous!**

- With proper instruction, Agent Zero is capable of many things, even potentially dangerous actions concerning your computer, data, or accounts. Always run Agent Zero in an isolated environment (like Docker) and be careful what you wish for.

2. **Agent Zero Is Prompt-based.**

- The whole framework is guided by the **prompts/** folder. Agent guidelines, tool instructions, messages, utility AI functions, it's all there.


## 📚 Read the Documentation

| Page | Description |
|-------|-------------|
| [Installation](./docs/installation.md#windows-macos-and-linux-setup-guide) | Installation, setup and configuration |
| [Usage](./docs/usage.md#basic-operations) | Basic and advanced usage |
| [Architecture](./docs/architecture.md) | System design and components |
| [Contributing](./docs/contribution.md) | How to contribute |
| [Troubleshooting](./docs/troubleshooting.md) | Common issues and their solutions |

## Coming soon

## 🎯 Changelog

### v0.8.7 - Formatting, Document RAG Latest
[Release video](https://youtu.be/OQJkfofYbus)
- markdown rendering in responses
- live response rendering
- document Q&A tool

### v0.8.6 - Merge and update
[Release video](https://youtu.be/l0qpK3Wt65A)
- Merge with Hacking Edition
- browser-use upgrade and integration re-work
- tunnel provider switch

### v0.8.5 - **MCP Server + Client**
[Release video](https://youtu.be/pM5f4Vz3_IQ)

- Agent Zero can now act as MCP Server
- Agent Zero can use external MCP servers as tools

### v0.8.4.1 - 2
Default models set to gpt-4.1
- Code execution tool improvements
- Browser agent improvements
- Memory improvements
- Various bugfixes related to context management
- Message formatting improvements
- Scheduler improvements
- New model provider
- Input tool fix
- Compatibility and stability improvements

### v0.8.4
[Release video](https://youtu.be/QBh_h_D_E24)

- **Remote access (mobile)**

### v0.8.3.1
[Release video](https://youtu.be/AGNpQ3_GxFQ)

- **Automatic embedding**


### v0.8.3
[Release video](https://youtu.be/bPIZo0poalY)

- ***Planning and scheduling***

### v0.8.2
[Release video](https://youtu.be/xMUNynQ9x6Y)

- **Multitasking in terminal**
- **Chat names**

### v0.8.1
[Release video](https://youtu.be/quv145buW74)

- **Browser Agent**
- **UX Improvements**

### v0.8
[Release video](https://youtu.be/cHDCCSr1YRI)

- **Docker Runtime**
- **New Messages History and Summarization System**
- **Agent Behavior Change and Management**
- **Text-to-Speech (TTS) and Speech-to-Text (STT)**
- **Settings Page in Web UI**
- **SearXNG Integration Replacing Perplexity + DuckDuckGo**
- **File Browser Functionality**
- **KaTeX Math Visualization Support**
- **In-chat File Attachments**

### v0.7
[Release video](https://youtu.be/U_Gl0NPalKA)

- **Automatic Memory**
- **UI Improvements**
- **Instruments**
- **Extensions Framework**
- **Reflection Prompts**
- **Bug Fixes**

## 🤝 Community and Support

- [Join our Discord](https://discord.gg/B8KZKNsPpj) for live discussions or [visit our Skool Community](https://www.skool.com/agent-zero).
- [Follow our YouTube channel](https://www.youtube.com/@AgentZeroFW) for hands-on explanations and tutorials
- We welcome contributions! See our [Contribution Guidelines](./docs/contribution.md) to get started.
- [Report Issues](https://github.com/frdel/agent-zero/issues) for bug fixes and features
