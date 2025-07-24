# A2A Protocol Integration for Agent Zero

## Overview

The Agent-to-Agent (A2A) Protocol integration enables Agent Zero to communicate and collaborate with other A2A-compliant agents across different systems and networks. This integration provides peer-to-peer communication capabilities while maintaining full backward compatibility with existing Agent Zero functionality.

## Table of Contents

1. [Features](#features)
2. [Architecture](#architecture)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Usage](#usage)
6. [API Reference](#api-reference)
7. [Examples](#examples)
8. [Security](#security)
9. [Troubleshooting](#troubleshooting)
10. [Contributing](#contributing)

## Features

### Core Capabilities

- **Peer-to-Peer Communication**: Direct communication between Agent Zero instances and other A2A-compliant agents
- **Multiple Interaction Patterns**: Support for polling, Server-Sent Events (SSE), and webhook-based communication
- **Agent Discovery**: Automatic discovery of peer agents and their capabilities
- **Tool Wrapping**: Seamless integration of remote agent capabilities as local tools
- **Backward Compatibility**: Full compatibility with existing Agent Zero hierarchical communication
- **Security**: Enterprise-grade authentication and encryption support

### Protocol Compliance

- **A2A Protocol v1.1.0**: Full compliance with the standard A2A protocol specification
- **JSON-RPC 2.0**: Standard JSON-RPC communication format
- **AgentCard Discovery**: Automatic capability advertisement via `/.well-known/agent.json`
- **Standard Error Handling**: Comprehensive error taxonomy and recovery mechanisms

## Architecture

### Component Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Agent Zero    │    │  A2A Protocol   │    │  Peer Agents    │
│   (Enhanced)    │◄──►│   Integration   │◄──►│ (A2A Compliant) │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌────────▼────────┐             │
         │              │ A2A Components  │             │
         │              │                 │             │
         └──────────────►│ • A2A Handler  │             │
                         │ • A2A Server   │             │
                         │ • A2A Client   │             │
                         │ • A2A Tools    │             │
                         │ • A2A Agent    │◄────────────┘
                         └─────────────────┘
```

### Key Components

1. **A2A Handler** (`python/helpers/a2a_handler.py`)
   - Core protocol management
   - Task lifecycle management
   - Agent Card handling
   - Peer registry management

2. **A2A Server** (`python/helpers/a2a_server.py`)
   - HTTP/HTTPS server implementation
   - A2A protocol endpoints
   - Authentication and authorization
   - Server-Sent Events support

3. **A2A Client** (`python/helpers/a2a_client.py`)
   - Outbound communication client
   - Retry logic and error handling
   - Multiple interaction patterns
   - Connection pooling

4. **A2A Communication Tool** (`python/tools/a2a_communication.py`)
   - Agent Zero tool integration
   - Direct peer communication
   - Message format conversion

5. **A2A Tool Wrapper** (`python/helpers/a2a_tool_wrapper.py`)
   - Remote capability wrapping
   - Dynamic tool discovery
   - Tool registry management

6. **A2A Agent Layer** (`python/helpers/a2a_agent.py`)
   - Peer-to-peer messaging
   - Broadcast capabilities
   - Legacy format conversion

## Installation

### Prerequisites

- Python 3.8 or higher
- Agent Zero framework installed
- Network connectivity for peer communication

### Dependencies

The A2A integration requires additional dependencies:

```bash
pip install starlette uvicorn[standard] httpx httpx-sse pydantic
```

Or install from the updated requirements.txt:

```bash
pip install -r requirements.txt
```

### Enable A2A in Agent Zero

1. **Update Agent Configuration**:
   ```python
   config = AgentConfig(
       # ... existing configuration ...
       a2a_enabled=True,
       a2a_server_port=8008,
       a2a_capabilities=["task_execution", "code_execution", "web_search"],
       a2a_auth_required=True,
       a2a_api_keys={"peer_agent_1": "your-api-key-here"}
   )
   ```

2. **Initialize A2A Handler**:
   ```python
   from python.helpers.a2a_handler import A2AHandler
   
   handler = A2AHandler.get_instance()
   handler.initialize({
       "agent_name": "My Agent Zero Instance",
       "agent_description": "Agent Zero with A2A capabilities",
       "capabilities": ["task_execution", "analysis", "reporting"]
   })
   ```

## Configuration

### Agent Configuration

The `AgentConfig` class has been extended with A2A-specific settings:

```python
@dataclass
class AgentConfig:
    # ... existing fields ...
    
    # A2A Protocol Configuration
    a2a_enabled: bool = False
    a2a_server_host: str = "0.0.0.0"
    a2a_server_port: int = 8008
    a2a_server_base_url: str = ""
    a2a_auth_required: bool = True
    a2a_auth_schemes: List[str] = ["bearer", "api_key"]
    a2a_api_keys: Dict[str, str] = {}
    a2a_peer_registry: List[str] = []
    a2a_ssl_keyfile: Optional[str] = None
    a2a_ssl_certfile: Optional[str] = None
    a2a_capabilities: List[str] = ["task_execution", "code_execution", "web_search"]
    a2a_input_types: List[str] = ["text/plain", "application/json"]
    a2a_output_types: List[str] = ["text/plain", "application/json"]
    a2a_protocol_version: str = "1.1.0"
    a2a_cors_origins: List[str] = ["*"]
    a2a_max_task_age_hours: int = 24
```

### Environment Variables

You can also configure A2A settings via environment variables:

```bash
export A2A_ENABLED=true
export A2A_SERVER_PORT=8008
export A2A_AUTH_REQUIRED=true
export A2A_PEER_REGISTRY="https://peer1.example.com,https://peer2.example.com"
```

### Server Configuration

For production deployments, configure HTTPS:

```python
config.a2a_ssl_keyfile = "/path/to/private.key"
config.a2a_ssl_certfile = "/path/to/certificate.crt"
config.a2a_server_base_url = "https://my-agent.example.com"
```

## Usage

### Basic Peer Communication

```python
# Using the A2A Communication tool
{
    "thoughts": ["Need to analyze data", "Delegating to specialist agent"],
    "tool_name": "a2a_communication",
    "tool_args": {
        "peer_url": "https://analytics-agent.example.com",
        "task_description": "Analyze quarterly revenue trends",
        "interaction_type": "polling",
        "context": {
            "data_source": "revenue_q4_2024.csv",
            "analysis_type": "trend_analysis"
        }
    }
}
```

### Programmatic API Usage

```python
from python.helpers.a2a_agent import A2AAgent

# Create A2A agent helper
a2a_agent = A2AAgent(agent, context)

# Send peer message
response = await a2a_agent.send_peer_message(
    peer_url="https://peer-agent.example.com",
    message="Please analyze this data set",
    context_data={"dataset": "financial_data.csv"},
    interaction_type="sse"
)

# Broadcast to multiple peers
responses = await a2a_agent.broadcast_to_peers(
    message="Task completed successfully",
    peer_urls=["https://peer1.com", "https://peer2.com"]
)
```

### Server Mode

Start Agent Zero as an A2A server:

```python
# Start A2A server
context.start_a2a_server({
    "host": "0.0.0.0",
    "port": 8008,
    "auth_required": True,
    "ssl_keyfile": "/path/to/key.pem",
    "ssl_certfile": "/path/to/cert.pem"
})
```

### Tool Discovery

```python
from python.helpers.a2a_tool_wrapper import get_a2a_tool_registry

# Discover tools from peer agents
registry = get_a2a_tool_registry()

peer_urls = ["https://peer1.com", "https://peer2.com"]
discovered_tools = await registry.discover_tools_from_registry(peer_urls)

# List available tools
available_tools = registry.list_available_tools()
print(f"Discovered {len(available_tools)} remote tools")
```

## API Reference

### A2A Protocol Endpoints

When running as a server, Agent Zero exposes these A2A-compliant endpoints:

#### Agent Card Discovery
- **GET** `/.well-known/agent.json`
- Returns agent capabilities and metadata

#### Task Management
- **POST** `/tasks/submit` - Submit a new task
- **GET** `/tasks/{id}` - Get task status
- **POST** `/tasks/{id}/cancel` - Cancel a task

#### Real-time Communication
- **GET** `/message/stream` - Server-Sent Events stream
- **POST** `/push/{token}` - Webhook endpoint

#### Health Check
- **GET** `/health` - Server health status

### Python API

#### A2AHandler

```python
class A2AHandler:
    def initialize(config: Dict[str, Any])
    async def create_task(description: str, input_data: Dict) -> str
    def get_task(task_id: str) -> Optional[A2ATask]
    def update_task_state(task_id: str, state: TaskState) -> bool
    async def execute_task(task_id: str, agent_context: Any) -> bool
    def register_peer(peer_id: str, agent_card: AgentCard, base_url: str)
    async def discover_peer(peer_url: str) -> Optional[AgentCard]
```

#### A2AClient

```python
class A2AClient:
    async def discover_agent(base_url: str) -> Dict[str, Any]
    async def submit_task(peer_url: str, task_data: Dict) -> str
    async def get_task_status(peer_url: str, task_id: str) -> Dict
    async def submit_task_with_sse(peer_url: str, task_data: Dict, timeout: int) -> Dict
    async def cancel_task(peer_url: str, task_id: str) -> bool
```

#### A2AAgent

```python
class A2AAgent:
    async def send_peer_message(peer_url: str, message: str, **kwargs) -> str
    async def broadcast_to_peers(message: str, peer_urls: List[str]) -> Dict[str, str]
    async def discover_peers_from_registry(registry_urls: List[str]) -> List[str]
    def get_peer_capabilities(peer_url: str) -> List[str]
```

## Examples

### Example 1: Multi-Agent Data Analysis Pipeline

```python
#!/usr/bin/env python3
"""
Multi-agent data analysis pipeline using A2A protocol
"""

import asyncio
from agent import Agent, AgentConfig, AgentContext
from python.helpers.a2a_agent import A2AAgent

async def run_analysis_pipeline():
    # Setup main orchestrator agent
    config = AgentConfig(
        # ... configuration ...
        a2a_enabled=True,
        a2a_peer_registry=[
            "https://data-preprocessor.agents.ai",
            "https://ml-analyst.agents.ai", 
            "https://report-generator.agents.ai"
        ]
    )
    
    context = AgentContext(config=config)
    agent = Agent(0, config, context)
    a2a_agent = A2AAgent(agent, context)
    
    # Step 1: Data preprocessing
    preprocess_response = await a2a_agent.send_peer_message(
        peer_url="https://data-preprocessor.agents.ai",
        message="Clean and prepare dataset for analysis",
        context_data={"dataset": "sales_data_2024.csv"}
    )
    
    # Step 2: Machine learning analysis
    analysis_response = await a2a_agent.send_peer_message(
        peer_url="https://ml-analyst.agents.ai",
        message="Perform predictive analysis on cleaned data",
        context_data={"preprocessed_data": preprocess_response}
    )
    
    # Step 3: Report generation
    report_response = await a2a_agent.send_peer_message(
        peer_url="https://report-generator.agents.ai",
        message="Generate executive summary report",
        context_data={"analysis_results": analysis_response}
    )
    
    print("Analysis pipeline completed!")
    print(f"Final report: {report_response}")

if __name__ == "__main__":
    asyncio.run(run_analysis_pipeline())
```

### Example 2: Creative Collaboration Network

```python
#!/usr/bin/env python3
"""
Creative collaboration between specialized agents
"""

async def creative_collaboration():
    # Setup creative orchestrator
    a2a_agent = A2AAgent(agent, context)
    
    # Discover creative agents
    creative_peers = await a2a_agent.discover_peers_from_registry([
        "https://story-writer.creative-agents.ai",
        "https://visual-artist.creative-agents.ai",
        "https://music-composer.creative-agents.ai"
    ])
    
    # Collaborative story creation
    story_outline = await a2a_agent.send_peer_message(
        peer_url="https://story-writer.creative-agents.ai",
        message="Create a science fiction story outline",
        context_data={"genre": "sci-fi", "length": "short_story"}
    )
    
    # Parallel creative tasks
    visual_task = a2a_agent.send_peer_message(
        peer_url="https://visual-artist.creative-agents.ai",
        message="Create concept art based on story",
        context_data={"story_outline": story_outline}
    )
    
    music_task = a2a_agent.send_peer_message(
        peer_url="https://music-composer.creative-agents.ai",
        message="Compose background music for story",
        context_data={"story_outline": story_outline, "mood": "atmospheric"}
    )
    
    # Wait for both creative tasks
    visual_art, background_music = await asyncio.gather(visual_task, music_task)
    
    print("Creative collaboration completed!")
    print(f"Story: {story_outline[:100]}...")
    print(f"Visual: {visual_art[:100]}...")
    print(f"Music: {background_music[:100]}...")
```

### Example 3: Running the Complete Demo

```bash
# Navigate to the Agent Zero directory
cd /path/to/agent-zero

# Run the comprehensive A2A demo
python examples/a2a_multi_agent_workflow.py
```

This demo will:
1. Start three Agent Zero instances with different specializations
2. Demonstrate peer discovery and registration
3. Show task delegation using different interaction patterns
4. Integrate results from multiple agents
5. Clean up resources automatically

## Security

### Authentication Methods

The A2A integration supports multiple authentication schemes:

1. **Bearer Token Authentication**
   ```python
   config.a2a_auth_schemes = ["bearer"]
   # Clients send: Authorization: Bearer <token>
   ```

2. **API Key Authentication**
   ```python
   config.a2a_auth_schemes = ["api_key"]
   config.a2a_api_keys = {"trusted_peer": "secure-api-key-123"}
   # Clients send: X-API-Key: secure-api-key-123
   ```

3. **OAuth2 (Recommended for Production)**
   ```python
   config.a2a_auth_schemes = ["oauth2"]
   # Implement OAuth2 flow with your identity provider
   ```

### Transport Security

- **HTTPS Only**: All production deployments must use HTTPS
- **Certificate Validation**: Always validate peer certificates
- **Data Encryption**: All communication is encrypted in transit

### Best Practices

1. **Never share sensitive data** without proper authorization
2. **Validate peer agent identity** before trusting responses
3. **Use appropriate authentication** for your security requirements
4. **Monitor and log** all peer communications
5. **Implement rate limiting** to prevent abuse
6. **Regular security updates** of dependencies

### Network Security

```python
# Configure firewall rules
# Only allow HTTPS traffic on A2A port
# Block direct access to internal services

# Example iptables rules:
# iptables -A INPUT -p tcp --dport 8008 -j ACCEPT  # A2A port
# iptables -A INPUT -p tcp --dport 22 -s trusted_subnet -j ACCEPT
# iptables -A INPUT -j DROP  # Default deny
```

## Troubleshooting

### Common Issues

#### 1. Connection Refused
**Problem**: Cannot connect to peer agent
**Solutions**:
- Check if peer agent is running and accessible
- Verify network connectivity and firewall rules
- Ensure correct URL and port configuration
- Check SSL/TLS certificate validity

#### 2. Authentication Failures
**Problem**: 401 Unauthorized responses
**Solutions**:
- Verify API keys or bearer tokens are correct
- Check authentication scheme configuration
- Ensure peer agent accepts your auth method
- Validate token expiration dates

#### 3. Task Timeout
**Problem**: Tasks timeout before completion
**Solutions**:
- Increase timeout values for complex tasks
- Check peer agent resource availability
- Monitor network latency and bandwidth
- Consider breaking large tasks into smaller parts

#### 4. Protocol Version Mismatch
**Problem**: Incompatible A2A protocol versions
**Solutions**:
- Update to compatible A2A protocol version
- Check peer agent protocol support
- Use protocol negotiation if available
- Consider fallback communication methods

### Debugging Tools

#### Enable Debug Logging
```python
import logging
logging.getLogger('a2a').setLevel(logging.DEBUG)
```

#### Check Server Status
```bash
# Health check endpoint
curl -X GET https://your-agent.example.com/health

# Agent card discovery
curl -X GET https://your-agent.example.com/.well-known/agent.json
```

#### Monitor Network Traffic
```bash
# Monitor A2A traffic
tcpdump -i any -A 'port 8008'

# Check SSL/TLS handshake
openssl s_client -connect peer-agent.example.com:8008
```

### Performance Optimization

1. **Connection Pooling**: Reuse HTTP connections for multiple requests
2. **Caching**: Cache agent cards and capability information
3. **Parallel Processing**: Use concurrent requests when appropriate
4. **Resource Monitoring**: Monitor CPU, memory, and network usage
5. **Load Balancing**: Distribute requests across multiple peer instances

## Contributing

### Development Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/agent0ai/agent-zero.git
   cd agent-zero
   ```

2. **Install development dependencies**:
   ```bash
   pip install -e .
   pip install pytest pytest-asyncio
   ```

3. **Run tests**:
   ```bash
   python -m pytest tests/test_a2a_integration.py -v
   ```

### Code Style

- Follow PEP 8 Python style guidelines
- Use type hints for all function parameters and return values
- Include comprehensive docstrings for all public methods
- Write unit tests for new functionality

### Pull Request Guidelines

1. **Feature Branches**: Create feature branches from main
2. **Tests**: Include tests for all new functionality
3. **Documentation**: Update documentation for API changes
4. **Backward Compatibility**: Maintain compatibility with existing code
5. **Security Review**: Security-sensitive changes require additional review

### Reporting Issues

When reporting issues, please include:

- Agent Zero version and A2A integration version
- Python version and operating system
- Complete error messages and stack traces
- Steps to reproduce the issue
- Expected vs. actual behavior
- Network and security configuration details

## License

The A2A Protocol integration for Agent Zero is released under the same license as the main Agent Zero project. See the LICENSE file for details.

## Support

- **Documentation**: Check this guide and the Agent Zero documentation
- **Community**: Join the Agent Zero Discord server for community support
- **Issues**: Report bugs and feature requests on GitHub
- **Commercial Support**: Contact the Agent Zero team for enterprise support

---

For more information about the A2A Protocol specification, visit [a2aprotocol.net](https://a2aprotocol.net).