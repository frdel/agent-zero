# Architecture Overview
Agent Zero is built on a flexible and modular architecture designed for extensibility and customization. This document outlines the key components and their interactions.

## Core Components
Agent Zero's architecture revolves around the following key components:

1. **Agents:** The core actors within the framework. Agents receive instructions, reason, make decisions, and utilize tools to achieve their objectives. Agents operate within a hierarchical structure, with superior agents delegating tasks to subordinate agents.

2. **Tools:** Tools are functionalities that agents can leverage. These can include anything from web search and code execution to interacting with APIs or controlling external software. Agent Zero provides a mechanism for defining and integrating both built-in and custom tools.

3. **Memory:** Agents have persistent memory that stores past experiences, knowledge, and information. This memory is used to inform decision-making and improve performance over time.

4. **Prompts:** Prompts guide agent behavior and communication. The system prompt defines the agent's overall role and objectives, while message prompts structure the interaction and flow of information between agents and tools.

5. **Knowledge:** Knowledge refers to the user-provided information and data that agents can leverage. This can include documents, databases, or any other relevant resources. Agents can retrieve and utilize this knowledge to answer questions, make decisions, and perform RAG-augmented tasks.

6. **Instruments:** Instruments provide a way to add custom functionalities to Agent Zero. They can modify agent behavior introducing new procedures, call for tools, or scripts to integrate with other systems.

7. **Docker Container:** Agent Zero execute commands in a Docker container, which provides isolation and security. This ensures that agents can safely and securely interact with tools and external systems.

This simplified diagram illustrates the hierarchical relationship between agents and their interaction with tools, prompts, memory, knowledge base and instruments. 

```mermaid
graph TD;    
    User(((User))) <-.-> AgentZero((Agent 0));
    Data[(
    Prompts,
    Memory,
    Knowledge,
    Instruments)]
    Data --> AgentZero;
    Data --> SubAgent1;
    AgentZero <-.-> SubAgent1((Subordinate 
    Agent 1));
    AgentZero <--> Tools[Tools];
    SubAgent1 <--> Tools;
    Tools --- CodeExec;

    subgraph "Docker"
        CodeExec[Code Execution Tool] <--> WorkDir[Work Directory
        work_dir]; 
    end

    User <.-> WorkDir;
    classDef grey stroke:#333,stroke-width:2px;
    class Data,Tools,CodeExec,WorkDir grey;
```

The user or Agent 0 is at the top of the hierarchy, delegating tasks to subordinate agents, which can further delegate to other agents.  Each agent can utilize tools and access the shared assets (prompts, memory, knowledge, and instruments) to perform its tasks.

## Agent Hierarchy and Communication
Agent Zero employs a hierarchical agent structure, where a top-level agent (often the user) can delegate tasks to subordinate agents. This hierarchy allows for the efficient breakdown of complex tasks into smaller, more manageable sub-tasks.

Communication flows between agents through messages, which are structured according to the prompt templates.  These messages typically include:

| Argument | Description |
| --- | --- |
| `Thoughts:` | The agent's internal reasoning and planning process. |
| `Tool name:` | The specific tool used by the agent. |
| `Responses or queries:` | Results, feedback or queries from tools or other agents. |

## Interaction Flow
A typical interaction flow within Agent Zero might look like this:

1.  The user provides an instruction to Agent 0.
2.  Agents access and update shared memory as needed.
3.  Agent 0 analyzes the instruction and formulates a plan using `thoughts` argument, possibly involving the use of tools or the creation of sub-agents.
4.  If necessary, Agent 0 delegates sub-tasks to subordinate agents.
5.  Agents use tools to perform actions, both providing arguments and responses or queries.
6.  Agents communicate results and feedback back up the hierarchy.
7.  Agent 0 provides the final response to the user.

##  Key Files
| File | Description |
| --- | --- |
| `agent.py` | Contains the core logic for the `AgentConfig` class, which defines the `prompts_subdir`, rate limits for models, and mechanisms for tweaking SSH and Docker connections. |
| `example.env` | Contains environment variables for configuring API keys and other settings of Agent Zero. |
| `initialize.py` | Defines Agent Zero's core configuration, including model choices and other critical settings. This is the central point for customizing the framework's behavior. See [Choosing Your LLMs](#choosing-your-llms) for more details. |
| `models.py` | Defines the `get_provider_chat` or `..._embedding` functions, which specifies the model provider, model name, and other parameters for adding support for new models or custom models. |
| `requirements.txt` | Lists the dependencies used by pip to install the necessary packages when you setup Agent Zero. |
| `run_cli.py` | Starts the Agent Zero CLI. |
| `run_ui.py` | Starts the Agent Zero Web UI. |

## Directory Structure
| Directory | Description |
| --- | --- |
| `docker/` | Dockerfiles and related files for building Docker image |
| `docs/` | Quickstart and installation guide |
| `instruments/` | Instruments for interacting with the environment |
| `knowledge/` | Knowledge base for storing and retrieving information |
| `logs/` | HTML chat log files |
| `memory/` | Memory storage for storing and retrieving information |
| `prompts/` | Main Agent and tools system prompts folders |
| `python/` | Python code for the main agent and tools |
| `tests/` | Unit tests for the project |
| `tmp/` | Temporary files |
| `webui/` | Web UI for the project |
| `work_dir/` | Working directory for the Agent |

# Customization
Agent Zero's strength lies in its flexibility. This section details how to customize various aspects of the framework, tailoring it to your specific needs and preferences.

## Choosing Your LLMs
The `initialize.py` file is the control center for selecting the Large Language Models (LLMs) that power Agent Zero.  You can choose different LLMs for different roles:

| LLM Role | Description |
| --- | --- |
| `chat_llm` | This is the primary LLM used for conversations and generating responses. |
| `utility_llm` | This LLM handles internal tasks like summarizing messages, managing memory, and processing internal prompts.  Using a smaller, less expensive model here can improve efficiency. |
| `embedding_llm` | This LLM is responsible for generating embeddings used for memory retrieval and knowledge base lookups. |

**How to Change:**
1. Open `initialize.py`.
2. Locate the lines where these LLMs are initialized (at the beginning of the file).
3. Uncomment the line for the provider and model you want to use, and comment out the others.  For example, to use `gpt-4o-mini` for chat:
   ```python
   chat_llm = models.get_openai_chat(model_name="gpt-4o-mini", temperature=0)
   ```
4. Ensure only one model is uncommented for each LLM role.

### Installing and Using Ollama
If you're interested in Ollama, which is a powerful tool that allows you to run various large language models locally, here's how to install and use it:

#### First step: installation
**On Windows:**
```
Download Ollama from the official website and install it on your machine.
[Download Ollama](https://ollama.com/download/OllamaSetup.exe)
```
**On MacOS:**
```
brew install ollama
```
**On Linux:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**Finding Model Names:**
Visit the [Ollama model library](https://ollama.com/library) for a list of available models and their corresponding names.  The format is usually `provider/model-name` (or just `model-name` in some cases).

#### Second step: pulling the model
**On Windows, MacOS, and Linux:**
```
ollama pull <model-name>
```

Replace `<model-name>` with the name of the model you want to use.  For example, to pull the Mistral Large model, you would use the command `ollama pull mistral-large`.

#### Managing your downloaded models
Once you've downloaded some models, you might want to check which ones you have available or remove any you no longer need.

* **Listing downloaded models:** 
  To see a list of all the models you've downloaded, use the command:
  ```
  ollama list
  ```
* **Removing a model:**
  If you need to remove a downloaded model, you can use the `ollama rm` command followed by the model name:
  ```
  ollama rm <model-name>
  ```

## Using Knowledge and Solutions

* **Knowledge:** Place your knowledge files (`.txt`, `.pdf`, `.csv`, `.html`, `.json`, `.md`) directly inside `/knowledge/custom/main`. Agent Zero will automatically import them. The list of supported file formats is yet to be expanded.
* **Solutions:** These are predefined workflows or code snippets written in `.md` files. Place them inside `/knowledge/custom/solutions`.  The agent can then use these solutions as templates for solving specific types of tasks.

## Agent Configuration (`AgentConfig`)

The `AgentConfig` class in `initialize.py` provides further customization options:

* **`prompts_subdir`:** Specifies the directory containing your custom prompts.  This allows you to create and manage different sets of prompts for different use cases.  (See *Prompt Customization* below).

* **`knowledge_subdirs`:** Defines the directories where Agent Zero searches for knowledge files.

* **Rate Limiting:** Control API usage and prevent rate limit errors by setting `rate_limit_seconds` and `rate_limit_requests`.

* **Docker and SSH:** Configure Docker and SSH settings for code execution, if needed.

## Prompt Customization
### Changing the System Prompt Folder
1. Create a new directory inside the `prompts` directory (e.g., `prompts/my-custom-prompts`).
2. When copying the contents of the `prompts/default` directory into your new directory, take into account that Agent Zero will merge the contents of the `default` directory with the contents of your custom directory. This means that you can copy only the files you want to modify, and the rest will be taken from the `default` directory.
3. Modify the prompts in your custom directory as needed.
4. In `initialize.py`, update the `prompts_subdir` parameter in `AgentConfig` to point to your custom directory:
   ```python
   config = AgentConfig(..., prompts_subdir="my-custom-prompts", ...)
   ```

### Editing Prompts
The `prompts` directory contains various Markdown files that control agent behavior and communication. The most important file is `agent.system.main.md`, which acts as a central hub, referencing other prompt files.  

**Key Prompt Files:**
| Prompt File | Description |
|---|---|
| agent.system.main.role.md | Defines the agent's overall role. |
| agent.system.main.communication.md | Specifies how the agent should communicate. |
| agent.system.main.solving.md | Describes the agent's approach to problem-solving. |
| agent.system.main.tips.md | Provides additional tips or guidance to the agent. |
| agent.system.tools.md | Organizes and calls the individual tool prompt files. |
| agent.system.tool.*.md | Individual tool prompt files (with * as the tool name). |

You can customize any of these files.  Agent Zero will use the files in your custom `prompts_subdir` if they exist, otherwise, it will fall back to the files in `prompts/default`.

## Adding Tools
While good prompting can often achieve the desired behavior, sometimes custom tools are necessary.

1. Create a new file named `agent.system.tool.$TOOL_NAME.md` inside your `prompts/$SUBDIR` directory. This file will contain the prompt for your custom tool.
2. Open `agent.system.tools.md` and add a reference to your new tool prompt.
3. If your tool requires specific code or external API calls, create a Python file for it in the `python/tools` directory, implementing the `Tool` base class.

## Adding Instruments
Instruments allow you to add predefined actions or workflows to Agent Zero without adding to the token count of the system prompt.

1. Create a new folder with the name of your instrument (without spaces) inside `instruments/custom`.
2. Inside this folder, create a `.md` file with the description of the instrument and a `.sh` script (or other executable) with the actual implementation. The `.md` file acts as the interface for the Agent to interact with the Instrument, and the agent will call the `.sh` with the given user arguments. The agent will parse the `.md` file, using the Instrument's name, description, and arguments described in it.

## Important Considerations

* The agent will automatically detect and use your custom instruments.
*  Changing the `embedding_llm` requires clearing the `memory` folder to avoid errors, as the embeddings can't be mixed in the vector database. The `knowledge` folder will be automatically imported again.
*  Experiment with different model combinations to find the balance of performance and cost that best suits your needs. E.g., using a smaller model for `utility_llm` can save costs without significantly impacting performance.