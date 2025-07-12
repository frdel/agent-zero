#!/usr/bin/env python3
"""
Hello World MCP Server using FastMCP with Streamable HTTP Protocol

This is a simple example demonstrating how to create an MCP server using
the FastMCP framework with the streamable-http transport protocol.

Features:
- Hello world tool that greets users
- Simple resource that provides server information
- Basic prompt template for greeting
- Runs using streamable-http transport for better scalability
"""

from fastmcp import FastMCP, Context
import os
from datetime import datetime


# Create a FastMCP server instance
mcp: FastMCP = FastMCP(
    "Hello World Server 🚀",
    dependencies=[]  # No special dependencies for this simple example
)


# ========== TOOLS ==========

@mcp.tool()
def hello_world(name: str = "World") -> str:
    """Say hello to someone with a personalized greeting.

    Args:
        name: The name of the person to greet (defaults to "World")

    Returns:
        A friendly greeting message
    """
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"Hello, {name}! 👋 Welcome to the FastMCP Hello World Server. Current time: {current_time}"


@mcp.tool()
def add_numbers(a: float, b: float) -> float:
    """Add two numbers together.

    Args:
        a: First number
        b: Second number

    Returns:
        The sum of the two numbers
    """
    result = a + b
    return result


@mcp.tool()
async def get_server_status(ctx: Context) -> str:
    """Get the current server status and information.

    Returns:
        Server status information including uptime and capabilities
    """
    # Log that someone is checking server status
    await ctx.info("Server status requested")

    # Get basic server info
    server_info = {
        "status": "running",
        "protocol": "MCP (Model Context Protocol)",
        "transport": "streamable-http",
        "framework": "FastMCP 2.0",
        "capabilities": ["tools", "resources", "prompts"],
        "timestamp": datetime.now().isoformat()
    }

    return f"""
🟢 Server Status: {server_info['status'].upper()}

📊 Server Information:
• Protocol: {server_info['protocol']}
• Transport: {server_info['transport']}
• Framework: {server_info['framework']}
• Capabilities: {', '.join(server_info['capabilities'])}
• Last checked: {server_info['timestamp']}

✅ All systems operational!
"""


# ========== RESOURCES ==========

@mcp.resource("info://server")
def get_server_info() -> str:
    """Static resource providing information about this MCP server."""
    return """
🚀 Hello World MCP Server

This is a demonstration MCP server built with FastMCP, showcasing the
streamable-http transport protocol.

Available capabilities:
• Tools: Interactive functions the LLM can call
• Resources: Data sources for context
• Prompts: Reusable message templates

Built with FastMCP 2.0 for production-ready MCP applications.
"""


@mcp.resource("greeting://{user_name}")
def get_personal_greeting(user_name: str) -> str:
    """Dynamic resource template that provides personalized greetings.

    Args:
        user_name: The name of the user to create a greeting for

    Returns:
        A personalized greeting message
    """
    greetings = [
        f"Welcome, {user_name}! 🎉",
        f"Hello there, {user_name}! Great to see you! 👋",
        f"Greetings, {user_name}! Hope you're having a wonderful day! ☀️"
    ]

    # Select greeting based on name length (simple example)
    greeting_index = len(user_name) % len(greetings)
    return greetings[greeting_index]


# ========== PROMPTS ==========

@mcp.prompt()
def introduction_prompt(user_name: str = "friend") -> str:
    """Generate a friendly introduction prompt.

    Args:
        user_name: Name of the person to introduce to

    Returns:
        A prompt for introducing the MCP server capabilities
    """
    return f"""
Hello {user_name}! 👋

I'm your Hello World MCP Server, here to demonstrate the power of the Model Context Protocol with FastMCP!

Here's what I can help you with:

🔧 **Tools I can execute:**
• hello_world - Give you personalized greetings
• add_numbers - Perform simple math operations
• get_server_status - Check my current status

📚 **Resources I can provide:**
• Server information and documentation
• Personalized greeting messages

💡 **How to use me:**
Try asking me to say hello, add some numbers, or check my status!

What would you like to do first?
"""


@mcp.prompt()
def math_prompt(operation: str = "addition") -> str:
    """Create a prompt for helping with math operations.

    Args:
        operation: The type of math operation to help with

    Returns:
        A simple prompt for math assistance
    """
    return (f"I need help with {operation}. I'd be happy to help you with {operation}! "
            f"I can add numbers together using my add_numbers tool. "
            f"Just tell me which numbers you'd like me to work with.")


# ========== SERVER LIFECYCLE ==========

def main():
    """Main function to run the MCP server."""
    print("🚀 Starting Hello World MCP Server with Streamable HTTP...")
    print("📡 Transport: streamable-http")
    print("🌐 Framework: FastMCP 2.0")
    print("🔗 Protocol: Model Context Protocol (MCP)")
    print()

    # Get configuration from environment or use defaults
    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8000"))
    path = os.getenv("MCP_PATH", "/mcp")

    print(f"🏠 Host: {host}")
    print(f"🚪 Port: {port}")
    print(f"🛤️  Path: {path}")
    print(f"📍 Full URL: http://{host}:{port}{path}")
    print()
    print("✅ Server is ready to accept MCP connections!")
    print("💡 Use this server with MCP clients that support streamable-http transport")
    print()

    # Run the server with streamable-http transport
    try:
        mcp.run(
            transport="streamable-http",
            host=host,
            port=port,
            path=path
        )
    except KeyboardInterrupt:
        print("\n👋 Server shutting down gracefully...")
    except Exception as e:
        print(f"❌ Server error: {e}")
        raise


if __name__ == "__main__":
    main()
