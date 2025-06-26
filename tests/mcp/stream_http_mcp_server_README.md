# FastMCP Hello World Server with Streamable HTTP

A comprehensive hello world example demonstrating how to build an MCP (Model Context Protocol) server using the FastMCP framework with streamable-http transport.

## 🚀 Features

This server demonstrates all three core MCP primitives:

### 🔧 Tools (LLM-callable functions)
- **hello_world** - Personalized greetings with timestamps
- **add_numbers** - Simple math operations
- **get_server_status** - Server status and information with context logging

### 📚 Resources (Data sources)
- **info://server** - Static server information
- **greeting://{user_name}** - Dynamic personalized greetings template

### 💡 Prompts (Reusable templates)
- **introduction_prompt** - Server capability introduction
- **math_prompt** - Math assistance template

## 📋 Prerequisites

- Python 3.10+
- pip or uv package manager

## 🛠️ Installation

### Option 1: Using pip
```bash
# Install dependencies
pip install -r stream_http_mcp_server_requirements.txt

# Or install FastMCP directly
pip install fastmcp
```

### Option 2: Using uv (recommended)
```bash
# Install FastMCP with uv
uv pip install fastmcp
```

## ▶️ Running the Server

### Basic Usage
```bash
# Run with default settings (localhost:8000/mcp)
python stream_http_mcp_server.py
```

### Custom Configuration via Environment Variables
```bash
# Set custom host, port, and path
export MCP_HOST=0.0.0.0
export MCP_PORT=3000
export MCP_PATH=/hello-mcp

python stream_http_mcp_server.py
```

### Expected Output
```
🚀 Starting Hello World MCP Server with Streamable HTTP...
📡 Transport: streamable-http
🌐 Framework: FastMCP 2.0
🔗 Protocol: Model Context Protocol (MCP)

🏠 Host: 127.0.0.1
🚪 Port: 8000
🛤️  Path: /mcp
📍 Full URL: http://127.0.0.1:8000/mcp

✅ Server is ready to accept MCP connections!
💡 Use this server with MCP clients that support streamable-http transport
```

## 🧪 Testing the Server

### Method 1: Using MCP Inspector (Recommended)

1. **Install MCP Inspector**:
   ```bash
   npm install -g @modelcontextprotocol/inspector
   ```

2. **Run the Inspector**:
   ```bash
   npx @modelcontextprotocol/inspector
   ```

3. **Connect to the Server**:
   - Choose "Streamable HTTP" transport
   - Enter URL: `http://localhost:8000/mcp`
   - Click "Connect"

4. **Test Tools**:
   - Go to the "Tools" tab
   - Try `hello_world` with `{"name": "Alice"}`
   - Try `add_numbers` with `{"a": 5, "b": 3}`
   - Try `get_server_status` (no parameters needed)

5. **Test Resources**:
   - Go to "Resources" tab
   - View `info://server`
   - Try `greeting://YourName`

6. **Test Prompts**:
   - Go to "Prompts" tab
   - Try `introduction_prompt` with `{"user_name": "Developer"}`
   - Try `math_prompt` with `{"operation": "multiplication"}`

### Method 2: Agent Zero Integration

Configure Agent Zero to use this server by adding to your MCP servers configuration:

```json
[
  {
    "name": "hello_world_server",
    "type": "streamable-http",
    "url": "http://localhost:8000/mcp",
    "description": "Hello World FastMCP Server with streamable HTTP"
  }
]
```

### Method 3: Custom MCP Client

Example using the MCP Python SDK:

```python
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession

async def test_server():
    async with streamablehttp_client("http://localhost:8000/mcp") as (read, write, get_session_id):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Test tool
            result = await session.call_tool("hello_world", {"name": "Test"})
            print(f"Tool result: {result}")

            # Test resource
            resource = await session.read_resource("info://server")
            print(f"Resource: {resource}")

# Run with: asyncio.run(test_server())
```

## 🔧 Configuration Options

### Environment Variables
- `MCP_HOST` - Server host (default: 127.0.0.1)
- `MCP_PORT` - Server port (default: 8000)
- `MCP_PATH` - Server path (default: /mcp)

### Server Capabilities
This server supports all MCP capabilities:
- ✅ Tools (with async support and context logging)
- ✅ Resources (static and dynamic templates)
- ✅ Prompts (string and message-based)
- ✅ Streamable HTTP transport
- ✅ Session management

## 🎯 Key Concepts Demonstrated

1. **FastMCP Framework**: Modern, production-ready MCP server development
2. **Streamable HTTP Transport**: Scalable transport for web deployments
3. **Type Safety**: Full Python type hints and docstrings
4. **Async Support**: Proper async/await patterns with context
5. **Dynamic Resources**: Template-based resources with parameters
6. **Context Logging**: Using MCP context for client communication
7. **Error Handling**: Graceful startup and shutdown

## 📚 Next Steps

- **Scale Up**: Use FastMCP's server composition to mount multiple apps
- **Add Auth**: Implement OAuth authentication for production
- **Deploy**: Use Docker or cloud platforms for production deployment
- **Integrate**: Connect with Claude Desktop, Agent Zero, or custom clients
- **Extend**: Add more sophisticated tools, resources, and prompts

## 🐛 Troubleshooting

### Server Won't Start
- Check if port 8000 is available: `lsof -i :8000`
- Try a different port: `MCP_PORT=8001 python stream_http_mcp_server.py`

### Connection Issues
- Verify the URL in your client matches the server output
- Check firewall settings for the port
- Ensure you're using "streamable-http" transport type

### Import Errors
- Install FastMCP: `pip install fastmcp`
- Check Python version: `python --version` (requires 3.10+)

## 📖 Documentation Links

- [FastMCP Documentation](https://gofastmcp.com/)
- [MCP Specification](https://spec.modelcontextprotocol.io/)
- [Agent Zero MCP Integration](../../docs/mcp_setup.md)

---

Built with ❤️ using FastMCP 2.0 and the Model Context Protocol
