# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Agent Zero is an organic agentic framework that grows and learns with you. It's a general-purpose personal assistant that uses the computer as a tool to accomplish tasks. The framework is fully transparent, customizable, and designed to be dynamic rather than pre-programmed for specific tasks.

## Key Architecture Components

### Core Architecture
- **Agent-based system**: Multi-agent cooperation where each agent has a superior and can create subordinates
- **Tool-based execution**: Uses operating system tools, code execution, and web search rather than pre-programmed single-purpose tools
- **Prompt-driven behavior**: Everything is controlled through prompts in the `prompts/` folder
- **Persistent memory**: Agents can memorize solutions, code, facts, and instructions for future use
- **MCP integration**: Can act as both MCP Server and Client for external LLM tools

### Main Entry Points
- `run_ui.py`: Primary web UI and API server (port 50001 by default)
- `run_cli.py`: CLI interface (discontinued but still functional)
- `run_tunnel.py`: Tunnel management for remote access
- `agent.py`: Core agent class and context management
- `initialize.py`: Framework initialization and configuration

### Key Directories
- `prompts/`: All system prompts and message templates that control agent behavior
- `python/tools/`: Built-in tools (browser, code execution, memory, search, etc.)
- `python/helpers/`: Utility modules for various functionalities
- `python/api/`: REST API endpoints for web interface
- `python/extensions/`: Extension system for customizing agent behavior
- `webui/`: Frontend web interface files
- `work_dir/`: Agent's working directory for file operations
- `memory/`: Persistent memory storage
- `knowledge/`: Knowledge base storage
- `logs/`: Session logs and outputs

## Development Commands

### Running the Application
```bash
# Primary method - Web UI with API
python run_ui.py

# CLI interface (discontinued but functional)
python run_cli.py

# With Docker (recommended)
docker pull frdel/agent-zero-run
docker run -p 50001:80 frdel/agent-zero-run
```

### Environment Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp example.env .env
# Edit .env with your API keys and configuration
```

### Testing and Development
- No formal test suite exists in this codebase
- Testing is primarily done through the web interface or CLI
- Docker provides isolated runtime environment for safe testing
- Use the web interface's debug features (Context, History, Nudge buttons)

## Model Configuration

The framework supports multiple AI providers:
- **OpenAI**: Primary chat and embedding models
- **Anthropic**: Alternative chat models
- **Google**: Gemini models
- **Ollama**: Local models
- **OpenRouter**: Model marketplace
- **Groq**: Fast inference
- **HuggingFace**: Open source models
- **Azure OpenAI**: Enterprise OpenAI access

Models are configured in `initialize.py` and can be overridden via runtime arguments or environment variables.

## Key Configuration Files

### Settings Management
- `settings.json`: Runtime configuration (created automatically)
- `.env`: Environment variables and API keys
- Agent configuration is managed through the web UI settings page

### Prompt System
- `prompts/default/`: Default prompt templates
- `prompts/{custom}/`: Custom prompt overrides
- All agent behavior is controlled through these markdown files
- Key prompts: `agent.system.main.md`, `agent.system.tools.md`, `agent.system.behaviour.md`

## Extension System

Extensions allow customizing agent behavior at specific points:
- `message_loop_start/`: Before each message loop iteration
- `message_loop_end/`: After each message loop iteration  
- `monologue_start/`: Before agent starts responding
- `monologue_end/`: After agent finishes responding
- `system_prompt/`: System prompt modification

## Tool Development

Custom tools should inherit from `python.helpers.tool.Tool`:
- Place in `python/tools/{toolname}.py`
- Implement `execute()` method
- Return `ToolResponse` with message and break_loop flag
- Tools are automatically discovered and loaded

## MCP Integration

Agent Zero supports Model Context Protocol (MCP):
- Can act as MCP Server for other LLM tools
- Can use external MCP servers as tools
- Configuration in settings under MCP servers section
- Dynamic tool loading from MCP servers

## Working with the Codebase

### Key Patterns
- Async/await throughout for non-blocking operations
- Extensions for customizing behavior
- Prompt templates for all agent communication
- Rate limiting for API calls
- Docker containerization for execution environment

### File Operations
- Use `python.helpers.files` for file operations
- Work within `work_dir/` for agent file operations
- Support for file attachments through web interface

### Memory and Knowledge
- Automatic memory persistence in `memory/` directory
- Knowledge base in `knowledge/` directory
- Vector embeddings for semantic search
- Configurable retention and recall strategies

## Security Considerations

- Docker isolation for code execution
- SSH-based secure command execution
- Basic authentication for web interface
- API key protection in environment variables
- Loopback-only access for certain endpoints

## Debugging and Monitoring

- Real-time streaming output in web interface
- Context window inspection via web UI
- Message history in JSON format
- Progress logging and error handling
- Intervention capabilities during agent execution