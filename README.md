# Agent Zero

[![Join our Skool Community](https://img.shields.io/badge/Skool-Join%20our%20Community-4A90E2?style=for-the-badge&logo=skool&logoColor=white)](https://www.skool.com/agent-zero) [![Join our Discord](https://img.shields.io/badge/Discord-Join%20our%20server-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.gg/B8KZKNsPpj) [![Subscribe on YouTube](https://img.shields.io/badge/YouTube-Subscribe-red?style=for-the-badge&logo=youtube&logoColor=white)](https://www.youtube.com/@AgentZeroFW) [![Connect on LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-blue?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/jan-tomasek/) [![Follow on X.com](https://img.shields.io/badge/X.com-Follow-1DA1F2?style=for-the-badge&logo=x&logoColor=white)](https://x.com/JanTomasekDev)

[![Intro Video](/docs/res/new_vid.jpg)](https://www.youtube.com/watch?v=U_Gl0NPalKA)

**Personal and organic AI framework**

- Agent Zero is not a predefined agentic framework. It is designed to be dynamic, organically growing, and learning as you use it.
- Agent Zero is fully transparent, readable, comprehensible, customizable, and interactive.
- Agent Zero uses the computer as a tool to accomplish its (your) tasks.

## Now fully Dockerized, with TTS and STT:

![Dockerized Agent Zero](https://github.com/user-attachments/assets/58e5462b-481d-4f43-8a4c-e989b9acfdf7)

## Key Concepts

1. **General-purpose Assistant**
   - Agent Zero is not pre-programmed for specific tasks (but can be). It is meant to be a general-purpose personal assistant. Give it a task, and it will gather information, execute commands and code, cooperate with other agent instances, and do its best to accomplish it.
   - It has a persistent memory, allowing it to memorize previous solutions, code, facts, instructions, etc., to solve tasks faster and more reliably in the future.

2. **Computer as a Tool**
   - Agent Zero uses the operating system as a tool to accomplish its tasks. It has no single-purpose tools pre-programmed. Instead, it can write its own code and use the terminal to create and use its own tools as needed.
   - The only default tools in its arsenal are online search, memory features, communication (with the user and other agents), and code/terminal execution. Everything else is created by the agent itself or can be extended by the user.
   - Tool usage functionality has been developed from scratch to be the most compatible and reliable, even with very small models.

   * **Default Tools:** Agent Zero includes tools like knowledge, webpage content, code execution, and communication.
   * **Creating Custom Tools:** Extend Agent Zero's functionality by creating your own custom tools.
   * **Instruments:** Instruments are a new type of tool that allow you to create custom functions and procedures that can be called by Agent Zero.

3. **Multi-agent Cooperation**
   - Every agent has a superior agent giving it tasks and instructions. Every agent then reports back to its superior.
   - In the case of the first agent in the chain (Agent 0), the superior is the human user; the agent sees no difference.
   - Every agent can create its subordinate agent to help break down and solve subtasks. This helps all agents keep their context clean and focused.

4. **Completely Customizable and Extensible**
   - Almost nothing in this framework is hard-coded. Nothing is hidden. Everything can be extended or changed by the user.
   - The whole behavior is defined by a system prompt in the **prompts/default/agent.system.md** file. Change this prompt and change the framework dramatically.
   - The framework does not guide or limit the agent in any way. There are no hard-coded rails that agents have to follow.
   - Every prompt, every small message template sent to the agent in its communication loop can be found in the **prompts/** folder and changed.
   - Every default tool can be found in the **python/tools/** folder and changed or copied to create new predefined tools.
   - Of course, it is open-source (except for some tools like Perplexity, but that will be replaced with an open-source alternative as well in the future).

5. **Communication is Key**
   - Give your agent a proper system prompt and instructions, and it can do miracles.
   - Agents can communicate with their superiors and subordinates, asking questions, giving instructions, and providing guidance. Instruct your agents in the system prompt on how to communicate effectively.
   - The terminal interface is real-time streamed and interactive. You can stop and intervene at any point. If you see your agent heading in the wrong direction, just stop and tell it right away.
   - There is a lot of freedom in this framework. You can instruct your agents to regularly report back to superiors asking for permission to continue. You can instruct them to use point-scoring systems when deciding when to delegate subtasks. Superiors can double-check subordinates' results and dispute. The possibilities are endless.

![Agent Zero](/docs/res/splash_wide.png)

## Nice Features to Have

- The new GUI output is very clean, fluid, colorful, readable, and interactive; nothing is hidden.
- The same colorful output you see in the terminal is automatically saved to an HTML file in **logs/** folder for every session.
- Agent output is streamed in real-time, allowing users to read along and intervene at any time.
- No coding is required; only prompting and communication skills are necessary.
- With a solid system prompt, the framework is reliable even with small models, including precise tool usage.

![Agent 1 System Load](/docs/res/ui_screen.png)

## Keep in Mind

1. **Agent Zero Can Be Dangerous!**
   - With proper instruction, Agent Zero is capable of many things, even potentially dangerous actions concerning your computer, data, or accounts. Always run Agent Zero in an isolated environment (like Docker) and be careful what you wish for.

2. **Agent Zero Is Not Pre-programmed; It Is Prompt-based.**
   - The whole framework contains only a minimal amount of code and does not guide the agent in any way. Everything lies in the system prompt located in the **prompts/** folder.

3. **If You Cannot Provide the Ideal Environment, Let Your Agent Know.**
   - Agent Zero is made to be used in an isolated virtual environment (for safety) with some tools preinstalled and configured.

[![David Ondrej video](/docs/res/david_vid.jpg)](https://www.youtube.com/watch?v=_Pionjv4hGc)

## Known Problems

1. The system prompt may need improvements; contributions are welcome!
2. Communication between agents via SSH within Docker containers may occasionally break; restarting might resolve issues.
3. The agent may inadvertently alter its operating environment; cleaning up the **work_dir/** often fixes this.

## Ideal Environment

- **Docker Container**: The ideal environment for running Agent Zero is within a Docker container; ensure Docker is running (e.g., Docker Desktop).
- **Internet Access**: Required for online knowledge tools; adjust prompts if offline operation is preferred.

![Time example](/docs/res/time_example.jpg)

## Setup

A detailed setup guide for Windows, macOS, and Linux with a video can be found in the new Agent Zero Documentation at [this page](docs/installation.md#windows-macos-and-linux-setup-guide).

You can download full binaries for your system from the [releases page](https://github.com/frdel/agent-zero/releases).

## Consult the Documentation

The documentation dives deep into the framework's features; it's an excellent starting point for new users. Click [here](docs/README.md) for more information.

## Coming Up

- **User Interaction Refinements**
- **Browser Use and RAG Tools**

### Changelog [since version 0.7]

> [!IMPORTANT]
>
> **Changes to frdel/agent-zero Docker image since v0.8:**
>
> - In version 0.8, the Docker image has changed to frdel/agent-zero-run using a new Dockerfile and image.

#### v0.8
- **Docker Runtime**
- **New Messages History and Summarization System**
- **Agent Behavior Change and Management**
- **Text-to-Speech (TTS) and Speech-to-Text (STT)**
- **Settings Page in Web UI**
- **SearXNG Integration Replacing Perplexity + DuckDuckGo Knowledge Tool**
- **File Browser Functionality**
- **KaTeX Math Visualization Support**
- **In-chat File Attachments**

#### v0.7
- **Automatic Memory**
- **UI Improvements**
- **Instruments**
- **Extensions Framework**
- **Reflection Prompts**
- **Bug Fixes**
