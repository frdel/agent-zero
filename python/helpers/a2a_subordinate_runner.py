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

# Change to the project root directory to ensure relative imports work
os.chdir(str(project_root))

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
        self.server_task = None
        self.running = False
    
    async def initialize(self):
        """Initialize the subordinate agent"""
        try:
            # ------------------------------------------------------------------
            # Prevent hard OOM-kills: impose a soft address-space limit so that
            # Python raises MemoryError instead of the kernel delivering
            # SIGKILL.  This respects the existing model selections – it simply
            # ensures failures are graceful and observable.
            # The limit can be overridden per process via the environment
            # variable `SUBORDINATE_RAM_GB` (integer, GiB).  A value of 0 or a
            # missing resource module (e.g. on Windows) disables the cap.
            # ------------------------------------------------------------------
            import os as _os
            _ram_cap_gb = int(_os.getenv("SUBORDINATE_RAM_GB", "4") or "0")
            try:
                if _ram_cap_gb > 0:
                    import resource as _resource
                    soft, hard = _resource.getrlimit(_resource.RLIMIT_AS)
                    new_soft = _ram_cap_gb * (1024 ** 3)
                    if soft == _resource.RLIM_INFINITY or new_soft < soft:
                        _resource.setrlimit(_resource.RLIMIT_AS, (new_soft, hard))
                        print(f"SUBORDINATE: RLIMIT_AS set to {_ram_cap_gb} GiB", flush=True)
            except Exception as _e:  # pragma: no cover
                # Never block startup because of rlimit issues – just log.
                print(f"SUBORDINATE: Warning – unable to set RLIMIT_AS: {_e}", flush=True)

            print(f"SUBORDINATE: Initializing A2A subordinate: {self.config_data['role']} (PID: {os.getpid()})", flush=True)
            
            # Check environment variables
            openai_key = os.environ.get('API_KEY_OPENAI', 'NOT_SET')
            print(f"SUBORDINATE: OPENAI_API_KEY: {'SET' if openai_key != 'NOT_SET' else 'NOT_SET'}", flush=True)

            # Debug: Print model configurations
            print(f"SUBORDINATE: Chat model: {self.config_data.get('chat_model', {}).get('provider', 'N/A')}/{self.config_data.get('chat_model', {}).get('name', 'N/A')}", flush=True)
            
            # Create agent configuration
            print("SUBORDINATE: Creating agent configuration...", flush=True)
            agent_config = self._create_agent_config()

            # Create agent context
            print("SUBORDINATE: Creating agent context...", flush=True)
            try:
                self.context = AgentContext(
                    config=agent_config,
                    name=f"Subordinate {self.config_data['role']}",
                    type=AgentContextType.A2A
                )
                print("SUBORDINATE: Agent context created successfully", flush=True)
            except Exception as e:
                print(f"SUBORDINATE: ERROR - Failed to create agent context: {str(e)}", flush=True)
                raise

            # Create agent
            print("SUBORDINATE: Creating agent instance...", flush=True)
            try:
                self.agent = Agent(0, agent_config, self.context)
                print("SUBORDINATE: Agent instance created successfully", flush=True)
            except MemoryError as e:
                print(f"SUBORDINATE: CRITICAL - Out of memory creating agent: {str(e)}", flush=True)
                print(f"SUBORDINATE: Consider increasing SUBORDINATE_RAM_GB (current: {_os.getenv('SUBORDINATE_RAM_GB', '4')})", flush=True)
                raise
            except Exception as e:
                print(f"SUBORDINATE: ERROR - Failed to create agent instance: {str(e)}", flush=True)
                import traceback
                print(f"SUBORDINATE: ERROR - Agent creation traceback:\n{traceback.format_exc()}", flush=True)
                raise

            # Initialize A2A handler
            print("SUBORDINATE: Initializing A2A handler...", flush=True)
            await self._initialize_a2a_handler()

            # Create and start A2A server
            print("SUBORDINATE: Starting A2A server...", flush=True)
            self.server_task = await self._start_a2a_server()

            print(f"SUBORDINATE: A2A subordinate {self.config_data['role']} initialized successfully", flush=True)
            
        except Exception as e:
            import traceback
            error_msg = f"Failed to initialize subordinate: {str(e)}"
            full_traceback = traceback.format_exc()

            print(f"SUBORDINATE: ERROR - {error_msg}", flush=True)
            print(f"SUBORDINATE: ERROR - Full traceback:\n{full_traceback}", flush=True)
            raise
    
    def _create_agent_config(self) -> AgentConfig:
        """Create agent configuration for subordinate"""
        # Use inherited model configurations from parent
        chat_model_config = self.config_data.get('chat_model', {})
        utility_model_config = self.config_data.get('utility_model', {})
        embeddings_model_config = self.config_data.get('embeddings_model', {})
        browser_model_config = self.config_data.get('browser_model', {})

        config = AgentConfig(
            # Model configurations (inherited from parent)
            chat_model=models.ModelConfig(
                type=models.ModelType.CHAT,
                provider=chat_model_config.get('provider', 'openai'),
                name=chat_model_config.get('name', 'gpt-4.1'),
                ctx_length=chat_model_config.get('ctx_length', 8000),
                limit_requests=chat_model_config.get('limit_requests', 50),
                vision=chat_model_config.get('vision', False),
                kwargs=chat_model_config.get('kwargs', {})
            ),
            utility_model=models.ModelConfig(
                type=models.ModelType.CHAT,
                provider=utility_model_config.get('provider', 'openai'),
                name=utility_model_config.get('name', 'gpt-4.1-mini'),
                ctx_length=utility_model_config.get('ctx_length', 4000),
                limit_requests=utility_model_config.get('limit_requests', 100),
                vision=utility_model_config.get('vision', False),
                kwargs=utility_model_config.get('kwargs', {})
            ),
            embeddings_model=models.ModelConfig(
                type=models.ModelType.EMBEDDING,
                provider=embeddings_model_config.get('provider', 'openai'),
                name=embeddings_model_config.get('name', 'text-embedding-3-small'),
                ctx_length=embeddings_model_config.get('ctx_length', 8000),
                limit_requests=embeddings_model_config.get('limit_requests', 500),
                vision=embeddings_model_config.get('vision', False),
                kwargs=embeddings_model_config.get('kwargs', {})
            ),
            browser_model=models.ModelConfig(
                type=models.ModelType.CHAT,
                provider=browser_model_config.get('provider', 'openai'),
                name=browser_model_config.get('name', 'gpt-4.1-mini'),
                ctx_length=browser_model_config.get('ctx_length', 8000),
                limit_requests=browser_model_config.get('limit_requests', 50),
                vision=browser_model_config.get('vision', False),
                kwargs=browser_model_config.get('kwargs', {})
            ),
            
            # Basic settings
            mcp_servers='',
            prompts_subdir=self.config_data.get('prompt_profile', 'default'),
            memory_subdir=f"subordinate_{self.config_data['role']}",
            # Configure subordinate-specific settings  
            knowledge_subdirs=[],  # Disable large knowledge loading
            code_exec_docker_enabled=True,  # Enable code execution for subordinates
            
            # A2A specific settings
            a2a_enabled=True,
            a2a_server_port=self.config_data['port'],
            a2a_server_token=self.config_data.get('a2a_server_token', ''),
            a2a_capabilities=self.config_data['capabilities'],
            a2a_auth_required=False,
            a2a_cors_origins=['*'],
            
            # Enable full tool access for subordinates per A2A protocol
            # Subordinates should have same capabilities as main agent
            
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

        print(f"SUBORDINATE: A2A handler initialized for {self.config_data['role']}", flush=True)
    
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
        
        # Use DynamicA2AProxy for token-based routing if token is available
        a2a_token = self.config_data.get('a2a_server_token', '')
        if a2a_token:
            from python.helpers.a2a_server import DynamicA2AProxy
            
            # Initialize the proxy with server
            proxy = DynamicA2AProxy.get_instance()
            proxy.initialize_server(self.context, server_config)
            proxy.reconfigure(a2a_token)
            
            # Start server using proxy
            server_task = asyncio.create_task(
                self._start_uvicorn_with_proxy(proxy, server_config['host'], server_config['port'])
            )
        else:
            # Fallback to direct A2A server
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

        print(f"SUBORDINATE: A2A server started for {self.config_data['role']} on port {self.config_data['port']}", flush=True)
        
        return server_task
    
    async def _start_uvicorn_with_proxy(self, proxy, host: str, port: int):
        """Start uvicorn server with DynamicA2AProxy"""
        import uvicorn
        
        config = uvicorn.Config(
            proxy,
            host=host,
            port=port,
            log_level="info"
        )
        
        server = uvicorn.Server(config)
        await server.serve()
    
    async def run(self):
        """Run the subordinate agent"""
        self.running = True
        
        try:
            await self.initialize()

            print(f"SUBORDINATE: A2A Subordinate '{self.config_data['role']}' is running and ready for tasks", flush=True)

            # Keep running until shutdown
            while self.running:
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            print("SUBORDINATE: Subordinate received shutdown signal", flush=True)
        except Exception as e:
            print(f"SUBORDINATE: ERROR - Subordinate error: {str(e)}", flush=True)
            raise
        finally:
            await self.cleanup()
    
    async def cleanup(self):
        """Cleanup subordinate resources"""
        print(f"SUBORDINATE: Cleaning up subordinate {self.config_data['role']}", flush=True)

        self.running = False

        if self.a2a_server:
            try:
                await self.a2a_server.stop_server()
            except Exception as e:
                print(f"SUBORDINATE: Error stopping A2A server: {str(e)}", flush=True)

        if self.server_task and not self.server_task.done():
            try:
                self.server_task.cancel()
                await asyncio.sleep(0.1)  # Give it a moment to cancel
            except Exception as e:
                print(f"SUBORDINATE: Error cancelling server task: {str(e)}", flush=True)

        print(f"SUBORDINATE: Subordinate {self.config_data['role']} cleanup complete", flush=True)
    
    def stop(self):
        """Stop the subordinate agent"""
        self.running = False


async def main():
    """Main entry point for subordinate runner"""
    print("SUBORDINATE: Main function started", flush=True)

    if len(sys.argv) != 2:
        print("SUBORDINATE: Usage: a2a_subordinate_runner.py <config_file>", flush=True)
        sys.exit(1)

    config_file = sys.argv[1]
    print(f"SUBORDINATE: Got config file argument: {config_file}", flush=True)
    
    # Set up signal handlers for graceful shutdown
    import signal
    subordinate_instance = None
    
    def signal_handler(signum, frame):
        print(f"SUBORDINATE: Received signal {signum}, shutting down gracefully...", flush=True)
        if subordinate_instance:
            subordinate_instance.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        print(f"SUBORDINATE: Loading configuration from: {config_file}", flush=True)

        # Load configuration
        with open(config_file, 'r') as f:
            config_data = json.load(f)

        print(f"SUBORDINATE: Configuration loaded successfully. Role: {config_data.get('role', 'unknown')}", flush=True)
        print(f"SUBORDINATE: Agent ID: {config_data.get('agent_id', 'unknown')}", flush=True)
        print(f"SUBORDINATE: Port: {config_data.get('port', 'unknown')}", flush=True)

        # Create and run subordinate
        print("SUBORDINATE: Creating subordinate instance...", flush=True)
        subordinate = A2ASubordinate(config_data)
        subordinate_instance = subordinate  # Make available to signal handler

        print("SUBORDINATE: Starting subordinate run...", flush=True)
        await subordinate.run()
        
    except FileNotFoundError:
        print(f"SUBORDINATE: ERROR - Configuration file not found: {config_file}", flush=True)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"SUBORDINATE: ERROR - Invalid JSON in config file: {str(e)}", flush=True)
        sys.exit(1)
    except Exception as e:
        import traceback
        error_msg = f"Subordinate runner error: {str(e)}"
        full_traceback = traceback.format_exc()

        print(f"SUBORDINATE: ERROR - {error_msg}", flush=True)
        print(f"SUBORDINATE: ERROR - Full traceback:\n{full_traceback}", flush=True)
        sys.exit(1)
    finally:
        # Cleanup config file
        try:
            os.unlink(config_file)
        except:
            pass


if __name__ == "__main__":
    print("SUBORDINATE: Script starting...", flush=True)

    # Set up event loop policy for Windows
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    print("SUBORDINATE: About to run main()", flush=True)

    try:
        # Run the subordinate
        asyncio.run(main())
        print("SUBORDINATE: Main completed successfully", flush=True)
    except Exception as e:
        print(f"SUBORDINATE: Main failed with exception: {e}", flush=True)
        import traceback
        print(f"SUBORDINATE: Traceback:\n{traceback.format_exc()}", flush=True)
        raise