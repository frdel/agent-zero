#!/usr/bin/env python3
"""
A2A Subordinate Runner

This script runs a subordinate Agent Zero instance as an independent A2A server.
It's spawned by the A2ASubordinateManager and runs as a separate process.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from agent import Agent, AgentConfig, AgentContext, AgentContextType
from python.helpers.a2a_server import A2AServer
from python.helpers.a2a_handler import A2AHandler
from python.helpers.print_style import PrintStyle
import models


class A2ASubordinate:
    """A2A Subordinate Agent Runner"""
    
    def __init__(self, config_data: dict):
        self.config_data = config_data
        self.agent = None
        self.context = None
        self.a2a_server = None
        self.running = False
    
    async def initialize(self):
        """Initialize the subordinate agent"""
        try:
            PrintStyle(font_color="cyan").print(
                f"Initializing A2A subordinate: {self.config_data['role']} (PID: {os.getpid()})"
            )
            
            # Create agent configuration
            agent_config = self._create_agent_config()
            
            # Create agent context
            self.context = AgentContext(
                config=agent_config,
                name=f"Subordinate {self.config_data['role']}",
                type=AgentContextType.A2A
            )
            
            # Create agent
            self.agent = Agent(0, agent_config, self.context)
            
            # Initialize A2A handler
            await self._initialize_a2a_handler()
            
            # Create and start A2A server
            await self._start_a2a_server()
            
            PrintStyle(font_color="green").print(
                f"A2A subordinate {self.config_data['role']} initialized successfully"
            )
            
        except Exception as e:
            PrintStyle(font_color="red").print(f"Failed to initialize subordinate: {str(e)}")
            raise
    
    def _create_agent_config(self) -> AgentConfig:
        """Create agent configuration for subordinate"""
        # Use same models as parent but with subordinate-specific settings
        config = AgentConfig(
            # Model configurations (inherit from parent)
            chat_model=models.ModelConfig('openai', 'gpt-4o', 8000, 50, False),
            utility_model=models.ModelConfig('openai', 'gpt-4o-mini', 4000, 100, False),
            embeddings_model=models.ModelConfig('openai', 'text-embedding-3-small', 8000, 500, False),
            browser_model=models.ModelConfig('openai', 'gpt-4o', 8000, 50, False),
            
            # Basic settings
            mcp_servers='',
            prompts_subdir=self.config_data.get('prompt_profile', 'default'),
            memory_subdir=f"subordinate_{self.config_data['role']}",
            
            # A2A specific settings
            a2a_enabled=True,
            a2a_server_port=self.config_data['port'],
            a2a_capabilities=self.config_data['capabilities'],
            a2a_auth_required=False,
            a2a_cors_origins=['*'],
            
            # Additional metadata
            additional={
                'role': self.config_data['role'],
                'parent_agent': self.config_data['parent_agent'],
                'parent_context_id': self.config_data['parent_context_id'],
                'subordinate_type': 'a2a_spawned',
                'agent_id': self.config_data['agent_id']
            }
        )
        
        return config
    
    async def _initialize_a2a_handler(self):
        """Initialize A2A protocol handler"""
        handler = A2AHandler.get_instance()
        
        handler_config = {
            "agent_name": f"Subordinate {self.config_data['role']}",
            "agent_description": f"A2A subordinate agent specialized in {self.config_data['role']}",
            "capabilities": self.config_data['capabilities'],
            "input_types": ["text/plain", "application/json"],
            "output_types": ["text/plain", "application/json"],
            "agent_id": self.config_data['agent_id'],
            "role": self.config_data['role'],
            "parent_agent": self.config_data['parent_agent']
        }
        
        handler.initialize(handler_config)
        
        PrintStyle(font_color="green").print(
            f"A2A handler initialized for {self.config_data['role']}"
        )
    
    async def _start_a2a_server(self):
        """Start A2A server for this subordinate"""
        server_config = {
            'auth_required': False,
            'host': '0.0.0.0',
            'port': self.config_data['port'],
            'base_url': f"http://localhost:{self.config_data['port']}",
            'agent_name': f"Subordinate {self.config_data['role']}",
            'agent_description': f"A2A subordinate agent specialized in {self.config_data['role']}",
            'capabilities': self.config_data['capabilities'],
            'cors_origins': ['*'],
            'agent_id': self.config_data['agent_id'],
            'role': self.config_data['role']
        }
        
        self.a2a_server = A2AServer(server_config, self.context)
        
        # Start server in background
        server_task = asyncio.create_task(
            self.a2a_server.start_server(
                host=server_config['host'],
                port=server_config['port']
            )
        )
        
        # Wait a moment for server to start
        await asyncio.sleep(1)
        
        PrintStyle(font_color="green").print(
            f"A2A server started for {self.config_data['role']} on port {self.config_data['port']}"
        )
        
        return server_task
    
    async def run(self):
        """Run the subordinate agent"""
        self.running = True
        
        try:
            await self.initialize()
            
            PrintStyle(font_color="green", bold=True).print(
                f"A2A Subordinate '{self.config_data['role']}' is running and ready for tasks"
            )
            
            # Keep running until shutdown
            while self.running:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            PrintStyle(font_color="yellow").print("Subordinate received shutdown signal")
        except Exception as e:
            PrintStyle(font_color="red").print(f"Subordinate error: {str(e)}")
            raise
        finally:
            await self.cleanup()
    
    async def cleanup(self):
        """Cleanup subordinate resources"""
        PrintStyle(font_color="yellow").print(f"Cleaning up subordinate {self.config_data['role']}")
        
        self.running = False
        
        if self.a2a_server:
            try:
                await self.a2a_server.stop_server()
            except Exception as e:
                PrintStyle(font_color="yellow").print(f"Error stopping A2A server: {str(e)}")
        
        PrintStyle(font_color="green").print(f"Subordinate {self.config_data['role']} cleanup complete")
    
    def stop(self):
        """Stop the subordinate agent"""
        self.running = False


async def main():
    """Main entry point for subordinate runner"""
    if len(sys.argv) != 2:
        print("Usage: a2a_subordinate_runner.py <config_file>")
        sys.exit(1)
    
    config_file = sys.argv[1]
    
    try:
        # Load configuration
        with open(config_file, 'r') as f:
            config_data = json.load(f)
        
        # Create and run subordinate
        subordinate = A2ASubordinate(config_data)
        await subordinate.run()
        
    except FileNotFoundError:
        PrintStyle(font_color="red").print(f"Configuration file not found: {config_file}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        PrintStyle(font_color="red").print(f"Invalid JSON in config file: {str(e)}")
        sys.exit(1)
    except Exception as e:
        PrintStyle(font_color="red").print(f"Subordinate runner error: {str(e)}")
        sys.exit(1)
    finally:
        # Cleanup config file
        try:
            os.unlink(config_file)
        except:
            pass


if __name__ == "__main__":
    # Set up event loop policy for Windows
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    # Run the subordinate
    asyncio.run(main())