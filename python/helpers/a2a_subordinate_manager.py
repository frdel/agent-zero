#!/usr/bin/env python3
"""
A2A Subordinate Manager

Manages A2A-based subordinate agents with proper lifecycle management,
auto-port allocation, and inter-agent communication coordination.
"""

import asyncio
import fcntl
import json
import os
import psutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

from python.helpers.print_style import PrintStyle
from python.helpers.a2a_client import A2AClient
from python.helpers.a2a_handler import A2AHandler, A2AError, A2AErrorType


class GlobalSpawningLock:
    """Global file-based lock to prevent concurrent subordinate spawning across processes"""

    def __init__(self):
        self.lock_dir = Path(tempfile.gettempdir()) / "agent_zero_locks"
        self.lock_dir.mkdir(exist_ok=True)
        self._local_locks = {}  # Thread-local locks
        self._lock = threading.Lock()

    def acquire_spawn_lock(self, role: str, timeout: int = 30) -> bool:
        """Acquire a spawn lock for a specific role"""
        lock_file = self.lock_dir / f"spawn_{role}.lock"

        with self._lock:
            if role in self._local_locks:
                # Already locked by this process
                return False

        try:
            # Create lock file
            fd = os.open(str(lock_file), os.O_CREAT | os.O_WRONLY | os.O_TRUNC)

            # Try to acquire exclusive lock with timeout
            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    # Write PID and timestamp to lock file
                    lock_info = {
                        "pid": os.getpid(),
                        "role": role,
                        "timestamp": datetime.now().isoformat(),
                        "timeout": timeout
                    }
                    os.write(fd, json.dumps(lock_info).encode())
                    os.fsync(fd)

                    # Store file descriptor for later release
                    with self._lock:
                        self._local_locks[role] = fd

                    PrintStyle(font_color="cyan").print(f"🔒 Acquired spawn lock for role: {role}")
                    return True

                except (OSError, IOError):
                    # Lock is held by another process, wait a bit
                    time.sleep(0.1)

            # Timeout reached
            os.close(fd)
            return False

        except Exception as e:
            PrintStyle(font_color="red").print(f"Failed to acquire spawn lock for {role}: {e}")
            return False

    def release_spawn_lock(self, role: str):
        """Release a spawn lock for a specific role"""
        with self._lock:
            if role not in self._local_locks:
                return

            fd = self._local_locks.pop(role)

        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

            # Remove lock file
            lock_file = self.lock_dir / f"spawn_{role}.lock"
            if lock_file.exists():
                lock_file.unlink()

            PrintStyle(font_color="cyan").print(f"🔓 Released spawn lock for role: {role}")

        except Exception as e:
            PrintStyle(font_color="yellow").print(f"Warning: Failed to release spawn lock for {role}: {e}")

    def is_role_being_spawned(self, role: str) -> bool:
        """Check if a role is currently being spawned by any process"""
        lock_file = self.lock_dir / f"spawn_{role}.lock"

        if not lock_file.exists():
            return False

        try:
            # Try to read lock file
            with open(lock_file, 'r') as f:
                lock_info = json.loads(f.read())

            # Check if the process that created the lock is still alive
            try:
                pid = lock_info.get("pid")
                if pid and psutil.pid_exists(pid):
                    # Check if lock is still valid (not expired)
                    lock_time = datetime.fromisoformat(lock_info.get("timestamp", ""))
                    timeout = lock_info.get("timeout", 30)
                    if (datetime.now() - lock_time).seconds < timeout * 2:  # Give extra time
                        return True
            except Exception:
                pass

            # Lock is stale, remove it
            lock_file.unlink()
            return False

        except Exception:
            return False


# Global instance
_global_spawn_lock = GlobalSpawningLock()


@dataclass
class SubordinateInfo:
    """Information about a subordinate agent"""
    agent_id: str
    role: str
    url: str
    port: int
    process_id: Optional[int]
    status: str  # 'starting', 'ready', 'busy', 'idle', 'error', 'stopping'
    parent_agent_id: str
    spawned_at: datetime
    last_contact: datetime
    capabilities: List[str] = field(default_factory=list)
    shared_context: Dict[str, Any] = field(default_factory=dict)
    process: Optional[subprocess.Popen] = None


class A2ASubordinateManager:
    """
    Manages A2A-based subordinate agents for enhanced multi-agent communication
    
    This manager handles:
    - Spawning subordinates as independent A2A processes
    - Port allocation and management
    - Subordinate lifecycle (start, monitor, stop)
    - Inter-agent communication coordination
    - Registry of active subordinates
    """
    
    def __init__(self, agent_context, base_port: int = 8100):
        self.agent_context = agent_context
        self.subordinates: Dict[str, SubordinateInfo] = {}
        self.subordinate_registry: Dict[str, str] = {}  # role -> agent_id mapping
        self.base_port = base_port
        self.port_counter = 0  # Track allocated ports
        self.used_ports = set()  # Track ports in use
        self._process_groups: Dict[str, int] = {}  # role -> pgid mapping
        self._subordinate_locks: Dict[str, asyncio.Lock] = {}
        self._spawn_lock = asyncio.Lock()  # Global spawn lock
        # Get A2A token from configuration for URL-based auth
        a2a_token = getattr(agent_context.config, 'a2a_server_token', None)
        self.a2a_client = A2AClient(timeout=30.0, max_retries=2, url_token=a2a_token)
        self._shutdown_in_progress = False

        # Agent hierarchy tracking
        self.agent_hierarchy: Dict[str, str] = {}  # child_id -> parent_id
        self.subordinate_registry: Dict[str, str] = {}  # role -> agent_id

        # Process groups for better cleanup
        self._process_groups: Dict[str, int] = {}  # role -> pgid

        # Note: Global spawning locks are now handled by GlobalSpawningLock class

        # Cleanup on exit - register multiple cleanup methods for robustness
        import atexit
        import signal
        atexit.register(self.cleanup_all_subordinates)

        # Also register signal handlers for proper cleanup
        try:
            signal.signal(signal.SIGTERM, self._signal_handler)
            signal.signal(signal.SIGINT, self._signal_handler)
        except Exception:
            # Signal handling might not work in all environments
            pass

        # Cleanup any existing orphaned processes on startup
        self._cleanup_orphaned_processes()

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals to ensure proper cleanup"""
        if self._shutdown_in_progress:
            return
        self._shutdown_in_progress = True
        PrintStyle(font_color="yellow").print(f"Received signal {signum}, cleaning up subordinates...")
        self.cleanup_all_subordinates()

    def _is_port_free(self, port: int) -> bool:
        """Check if port is free to use"""
        import socket
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', port))
                return True
        except OSError:
            return False
    
    def _allocate_port(self) -> int:
        """Allocate unique port for subordinate"""
        while True:
            port = self.base_port + self.port_counter
            self.port_counter += 1
            if port not in self.used_ports and self._is_port_free(port):
                self.used_ports.add(port)
                return port
    
    def _is_port_in_use(self, port: int) -> bool:
        """Check if a port is currently in use"""
        try:
            import subprocess
            result = subprocess.run(
                ['ss', '-tulpn'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return f":{port}" in result.stdout
        except Exception:
            # Fallback to socket method
            try:
                import socket
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    result = sock.connect_ex(('localhost', port))
                    return result == 0
            except Exception:
                return False

    def _can_bind_port(self, port: int) -> bool:
        """Test if we can actually bind to a port"""
        try:
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(('localhost', port))
                return True
        except Exception:
            return False
    
    def release_port(self, port: int):
        """Release an allocated port"""
        if port in self.used_ports:
            self.used_ports.remove(port)
            PrintStyle(font_color="cyan").print(f"Released port {port}")
    
    async def spawn_subordinate(
        self,
        role: str,
        prompt_profile: str = "default",
        capabilities: List[str] = None,
        shared_context: Dict[str, Any] = None,
        force_new: bool = False
    ) -> SubordinateInfo:
        """Spawn or get existing subordinate agent"""
        
        # Normalize role to prevent duplicates
        role = role.strip().lower()
        
        # Check for existing subordinate with this role
        existing = self.get_subordinate_by_role(role)
        
        # If subordinate exists and is not in error/stopped state, reuse it
        if existing and not force_new:
            if existing.status in ['ready', 'idle', 'busy', 'working']:
                PrintStyle(font_color="cyan").print(f"Reusing existing subordinate: {role} (status: {existing.status})")
                return existing
            elif existing.status == 'starting':
                # Wait for existing subordinate to finish starting
                PrintStyle(font_color="yellow").print(f"Subordinate {role} is already starting, waiting...")
                max_wait = 60  # seconds
                waited = 0
                while existing.status == 'starting' and waited < max_wait:
                    await asyncio.sleep(1)
                    waited += 1
                if existing.status in ['ready', 'idle']:
                    PrintStyle(font_color="green").print(f"Subordinate {role} is now ready")
                    return existing
                else:
                    PrintStyle(font_color="red").print(f"Subordinate {role} failed to start (status: {existing.status})")
            elif existing.status in ['error', 'stopped', 'oom_killed']:
                # Clean up failed subordinate before spawning new one
                PrintStyle(font_color="yellow").print(f"Cleaning up failed subordinate: {role} (status: {existing.status})")
                await self.remove_subordinate(existing.agent_id)

        # Check if role is being spawned globally (across all processes)
        if _global_spawn_lock.is_role_being_spawned(role):
            PrintStyle(font_color="yellow").print(f"Subordinate {role} is being spawned by another process, waiting...")
            # Wait for existing spawn to complete
            max_wait = 30  # 30 seconds max wait
            waited = 0
            while _global_spawn_lock.is_role_being_spawned(role) and waited < max_wait:
                time.sleep(1)
                waited += 1

            # Check if spawn completed successfully
            if role in self.subordinate_registry:
                existing_id = self.subordinate_registry[role]
                if existing_id in self.subordinates:
                    subordinate = self.subordinates[existing_id]
                    if subordinate.status in ['ready', 'idle']:
                        PrintStyle(font_color="green").print(f"Using subordinate spawned by concurrent process: {role}")
                        return subordinate

        # Acquire global spawning lock
        if not _global_spawn_lock.acquire_spawn_lock(role, timeout=30):
            raise A2AError(
                A2AErrorType.INVALID_AGENT_RESPONSE,
                f"Failed to acquire spawn lock for role {role} - another process may be spawning the same role"
            )
        
        # Generate subordinate details - use proper agent numbering A1, A2, A3, etc.
        base_agent_name = self.agent_context.agent0.agent_name.rstrip('0')  # Remove trailing 0 from A0
        
        # Find the next available agent number (handle concurrent spawning)
        existing_numbers = set()
        for sub_id in self.subordinates.keys():
            if sub_id.startswith(base_agent_name) and sub_id[len(base_agent_name):].isdigit():
                existing_numbers.add(int(sub_id[len(base_agent_name):]))
        
        next_agent_number = 1
        while next_agent_number in existing_numbers:
            next_agent_number += 1
            
        agent_id = f"{base_agent_name}{next_agent_number}"
        port = self._allocate_port()
        url = f"http://localhost:{port}"
        
        PrintStyle(font_color="cyan").print(f"Spawning A2A subordinate: {role} on port {port}")
        
        # Create subordinate info
        subordinate = SubordinateInfo(
            agent_id=agent_id,
            role=role,
            url=url,
            port=port,
            process_id=None,
            status='starting',
            parent_agent_id=self.agent_context.agent0.agent_name,
            spawned_at=datetime.now(timezone.utc),
            last_contact=datetime.now(timezone.utc),
            capabilities=capabilities or ["task_execution", "code_execution"],
            shared_context=shared_context or {}
        )
        
        try:
            # Create subordinate configuration
            subordinate_config = self._create_subordinate_config(subordinate, prompt_profile)
            
            # Spawn subordinate process
            process = await self._spawn_subordinate_process(subordinate_config)
            subordinate.process = process
            subordinate.process_id = process.pid
            
            # Register subordinate
            self.subordinates[agent_id] = subordinate
            self.subordinate_registry[role] = agent_id
            self.agent_hierarchy[agent_id] = self.agent_context.agent0.agent_name
            
            # Wait for subordinate to be ready
            await self._wait_for_subordinate_ready(subordinate)
            
            subordinate.status = 'ready'
            subordinate.last_contact = datetime.now(timezone.utc)
            
            # Register subordinate context with main agent for UI visibility
            await self._register_subordinate_context(subordinate)
            
            PrintStyle(font_color="green").print(f"Subordinate {role} ready at {url}")
            
            # Update agent context
            self.agent_context.add_a2a_peer(agent_id, {
                "role": role,
                "url": url,
                "capabilities": subordinate.capabilities,
                "type": "subordinate"
            })

            # Release global spawning lock on success
            _global_spawn_lock.release_spawn_lock(role)

            return subordinate

        except Exception as e:
            # Cleanup on failure
            if subordinate.process:
                try:
                    subordinate.process.terminate()
                    # Wait a bit for graceful shutdown
                    import time
                    time.sleep(2)
                    if subordinate.process.poll() is None:
                        subordinate.process.kill()
                except:
                    pass

            self.release_port(port)
            subordinate.status = 'error'

            # Release global spawning lock on failure
            _global_spawn_lock.release_spawn_lock(role)

            # Remove from registries if added
            if role in self.subordinate_registry:
                del self.subordinate_registry[role]
            if agent_id in self.subordinates:
                del self.subordinates[agent_id]
            if agent_id in self.agent_hierarchy:
                del self.agent_hierarchy[agent_id]

            PrintStyle(font_color="red").print(f"Failed to spawn subordinate {role}: {str(e)}")
            raise A2AError(
                A2AErrorType.INVALID_AGENT_RESPONSE,
                f"Failed to spawn subordinate {role}: {str(e)}"
            )
    
    def _create_subordinate_config(self, subordinate: SubordinateInfo, prompt_profile: str) -> Dict[str, Any]:
        """Create configuration for subordinate agent"""
        # Get parent agent configuration to inherit model settings
        parent_config = self.agent_context.config

        config = {
            "agent_id": subordinate.agent_id,
            "role": subordinate.role,
            "port": subordinate.port,
            "prompt_profile": prompt_profile,
            "capabilities": subordinate.capabilities,
            "parent_agent": self.agent_context.agent0.agent_name,
            "parent_context_id": self.agent_context.context_id,
            "shared_context": subordinate.shared_context,
            "a2a_enabled": True,      
            "a2a_server_port": subordinate.port,
            "a2a_server_token": getattr(parent_config, 'a2a_server_token', ''),
            "a2a_auth_required": False,  # Simplified for subordinates
            "working_directory": os.getcwd(),
            
            # Parent agent info for peer discovery
            "parent_agent_url": f"http://localhost:{getattr(parent_config, 'a2a_server_port', 8008)}",
            "parent_agent_token": getattr(parent_config, 'a2a_server_token', ''),

            # Inherit model configurations from parent
            "chat_model": {
                "provider": parent_config.chat_model.provider,
                "name": parent_config.chat_model.name,
                "ctx_length": parent_config.chat_model.ctx_length,
                "limit_requests": parent_config.chat_model.limit_requests,
                "vision": parent_config.chat_model.vision,
                "kwargs": parent_config.chat_model.kwargs
            },
            "utility_model": {
                "provider": parent_config.utility_model.provider,
                "name": parent_config.utility_model.name,
                "ctx_length": parent_config.utility_model.ctx_length,
                "limit_requests": parent_config.utility_model.limit_requests,
                "vision": parent_config.utility_model.vision,
                "kwargs": parent_config.utility_model.kwargs
            },
            "embeddings_model": {
                "provider": parent_config.embeddings_model.provider,
                "name": parent_config.embeddings_model.name,
                "ctx_length": parent_config.embeddings_model.ctx_length,
                "limit_requests": parent_config.embeddings_model.limit_requests,
                "vision": parent_config.embeddings_model.vision,
                "kwargs": parent_config.embeddings_model.kwargs
            },
            "browser_model": {
                "provider": parent_config.browser_model.provider,
                "name": parent_config.browser_model.name,
                "ctx_length": parent_config.browser_model.ctx_length,
                "limit_requests": parent_config.browser_model.limit_requests,
                "vision": parent_config.browser_model.vision,
                "kwargs": parent_config.browser_model.kwargs
            }
        }

        return config
    
    async def _spawn_subordinate_process(self, config: Dict[str, Any]) -> subprocess.Popen:
        """Spawn subordinate as independent Python process"""
        # Create temporary config file
        config_file = f"/tmp/subordinate_config_{config['agent_id']}.json"
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        # Python command to spawn subordinate
        # Priority: 1) Virtual env Python 2) sys.executable 3) system Python
        python_path = None
        
        # First, try to find virtual environment Python
        project_root = Path(__file__).parent.parent.parent
        venv_python = project_root / ".venv" / "bin" / "python3"
        if venv_python.exists():
            python_path = str(venv_python)
            PrintStyle(font_color="cyan").print(f"Using virtual environment Python: {python_path}")
        else:
            # Fallback to sys.executable if not from Cursor/AppImage
            python_path = sys.executable
            if 'Cursor' in python_path or 'AppImage' in python_path:
                # Last resort: system Python
                import shutil
                python_path = shutil.which('python3') or shutil.which('python') or '/usr/bin/python3'
                PrintStyle(font_color="yellow").print(f"Using system Python: {python_path}")
            else:
                PrintStyle(font_color="cyan").print(f"Using sys.executable: {python_path}")

        script_path = os.path.join(os.path.dirname(__file__), "a2a_subordinate_runner.py")
        working_dir = config["working_directory"]
        
        # Set PYTHONPATH to ensure proper imports
        env = os.environ.copy()
        env['PYTHONPATH'] = working_dir
        env['TOKENIZERS_PARALLELISM'] = 'false'  # Disable tokenizers parallelism to avoid fork warnings
        
        # Set subordinate RAM limit (default 8GB if not set)
        if 'SUBORDINATE_RAM_GB' not in env:
            env['SUBORDINATE_RAM_GB'] = '8'
        
        # Map API keys for subordinate compatibility
        if 'API_KEY_OPENAI' in env and 'OPENAI_API_KEY' not in env:
            env['OPENAI_API_KEY'] = env['API_KEY_OPENAI']
        if 'API_KEY_ANTHROPIC' in env and 'ANTHROPIC_API_KEY' not in env:
            env['ANTHROPIC_API_KEY'] = env['API_KEY_ANTHROPIC']
        
        # Spawn process with unbuffered output
        process = subprocess.Popen([
            python_path, "-u", script_path, config_file  # -u for unbuffered output
        ], cwd=working_dir,
           stdout=subprocess.PIPE,
           stderr=subprocess.STDOUT,  # Combine stderr with stdout
           env=env,
           bufsize=0,  # Unbuffered
           preexec_fn=os.setsid if os.name != 'nt' else None)
        
        PrintStyle(font_color="cyan").print(f"Spawned subordinate process PID: {process.pid}")
        
        # Store process group ID for cleanup
        if os.name != 'nt':
            try:
                pgid = os.getpgid(process.pid)
                role = config.get('role', 'unknown')
                self._process_groups[role] = pgid
                PrintStyle(font_color="cyan").print(f"Process group ID for {role}: {pgid}")
            except Exception:
                pass  # Process might have already exited
        
        return process
    
    async def _wait_for_subordinate_ready(self, subordinate: SubordinateInfo, timeout: int = 60):
        """Wait for subordinate to be ready for communication"""
        start_time = datetime.now()
        last_error = None
        retry_count = 0
        max_retries = 3

        PrintStyle(font_color="cyan").print(f"Waiting for subordinate {subordinate.role} to be ready...")

        while (datetime.now() - start_time).seconds < timeout:
            try:
                # Check if process is still running first
                if subordinate.process and subordinate.process.poll() is not None:
                    raise Exception(f"Subordinate process died with exit code {subordinate.process.poll()}")

                # Try health check with reduced retries to avoid long waits
                async with self.a2a_client as client:
                    health_url = f"{subordinate.url}/health"
                    health_response = await client._make_request("GET", health_url, retries=1)
                    if health_response:
                        PrintStyle(font_color="green").print(f"Agent health check passed: {subordinate.url}")

                        # Try agent card to ensure full readiness
                        try:
                            agent_card = await client.discover_agent(subordinate.url)
                            if agent_card and agent_card.get("name"):
                                PrintStyle(font_color="green").print(f"Subordinate {subordinate.role} is fully ready")
                                return
                        except Exception as card_error:
                            # Health passed but agent card failed - still consider it ready after a few retries
                            retry_count += 1
                            if retry_count >= max_retries:
                                PrintStyle(font_color="yellow").print(f"Subordinate {subordinate.role} is ready (health only)")
                                return
                            else:
                                PrintStyle(font_color="gray").print(f"Agent card check failed (retry {retry_count}/{max_retries}): {str(card_error)[:50]}")

            except Exception as e:
                last_error = str(e)
                if "connection" in last_error.lower() or "refused" in last_error.lower():
                    # Connection errors are expected during startup
                    pass
                else:
                    PrintStyle(font_color="gray").print(f"A2A connection error, retrying {retry_count}/{max_retries}")
                    PrintStyle(font_color="gray").print(f"Waiting for {subordinate.role}: {last_error[:100]}...")
            
            # Check if process is still running
            if subordinate.process and subordinate.process.poll() is not None:
                # Capture subprocess output for debugging
                try:
                    stdout, _ = subordinate.process.communicate(timeout=5)  # Increased timeout
                    output_text = stdout.decode('utf-8') if stdout else "No output"

                    PrintStyle(font_color="red").print(f"Subordinate {subordinate.role} process output:")
                    PrintStyle(font_color="red").print(f"OUTPUT:\n{output_text}")

                except Exception as e:
                    PrintStyle(font_color="red").print(f"Failed to capture subprocess output: {e}")

                    # Try to read any available output without waiting
                    try:
                        if subordinate.process.stdout:
                            output = subordinate.process.stdout.read()
                            if output:
                                PrintStyle(font_color="red").print(f"Partial output: {output.decode('utf-8', errors='ignore')}")
                    except Exception:
                        pass

                rc = subordinate.process.returncode
                # Exit code 137 (128+9) or 9 -> SIGKILL, often OOM
                if rc in (9, 137):
                    subordinate.status = 'oom_killed'
                    # Unregister proxy context before raising error
                    self._unregister_subordinate_context(subordinate)
                    # Release the port immediately
                    if subordinate.port in self.used_ports:
                        self.used_ports.remove(subordinate.port)
                        PrintStyle(font_color="cyan").print(f"Released port {subordinate.port} after OOM kill")
                    raise RuntimeError(
                        f"Subordinate {subordinate.role} was killed (likely out-of-memory, exit code {rc}). "
                        "Consider increasing SUBORDINATE_RAM_GB or using lighter tasks."
                    )
                # Unregister proxy context for any exit
                self._unregister_subordinate_context(subordinate)
                # Release port for any other exit
                if subordinate.port in self.used_ports:
                    self.used_ports.remove(subordinate.port)
                    PrintStyle(font_color="cyan").print(f"Released port {subordinate.port} after exit")
                raise RuntimeError(f"Subordinate process {subordinate.role} exited prematurely (exit code: {rc})")
            
            await asyncio.sleep(1)
        
        raise TimeoutError(f"Subordinate {subordinate.role} failed to start within {timeout} seconds")
    
    async def send_message_to_subordinate(
        self,
        role: str,
        message: str,
        context_data: Dict[str, Any] = None,
        timeout: int = 1800  # 30 minutes for complex multi-step tasks
    ) -> str:
        """Send a message to a subordinate agent"""
        if role not in self.subordinate_registry:
            raise A2AError(
                A2AErrorType.TASK_NOT_FOUND,
                f"No subordinate found with role: {role}"
            )
        
        agent_id = self.subordinate_registry[role]
        subordinate = self.subordinates[agent_id]
        
        # Allow communication even if busy - subordinates should handle queuing
        if subordinate.status not in ['ready', 'idle', 'busy']:
            PrintStyle(font_color="yellow").print(f"Warning: Subordinate {role} is {subordinate.status}, but attempting communication anyway")
            # Only block if subordinate is in error state or stopping
            if subordinate.status in ['error', 'stopping', 'stopped']:
                raise A2AError(
                    A2AErrorType.TASK_NOT_CANCELABLE,
                    f"Subordinate {role} is not available (status: {subordinate.status})"
                )
        
        # Update status
        subordinate.status = 'busy'
        subordinate.last_contact = datetime.now(timezone.utc)
        
        try:
            # Prepare task data
            task_data = {
                "description": message,
                "inputData": context_data or {},
                "metadata": {
                    "role": role,
                    "parent_agent": self.agent_context.agent0.agent_name,
                    "context_id": self.agent_context.context_id
                }
            }

            PrintStyle(font_color="cyan").print(f"Sending task to subordinate {role} at {subordinate.url}")

            # Update proxy context log if available
            proxy_context_id = f"subordinate_{subordinate.agent_id}"
            from agent import AgentContext
            proxy_context = AgentContext.get(proxy_context_id)
            if proxy_context and hasattr(proxy_context, 'log'):
                proxy_context.log.log("user", f"Task sent to subordinate: {message[:100]}...")

            # Send task via A2A client with error handling
            response = await self.a2a_client.submit_task_with_sse(
                peer_url=subordinate.url,
                task_data=task_data,
                timeout=timeout
            )
            
            subordinate.status = 'idle'
            subordinate.last_contact = datetime.now(timezone.utc)
            
            # Update proxy context log with response if available
            if proxy_context and hasattr(proxy_context, 'log'):
                proxy_context.log.log("agent", f"Task completed by subordinate {role}")
            
            # Extract response message with improved content extraction
            response_content = ""
            
            # First try to get from artifacts
            if response.get("artifacts") and len(response["artifacts"]) > 0:
                for artifact in response["artifacts"]:
                    if artifact.get("type") == "text/plain" and artifact.get("content"):
                        response_content = artifact.get("content", "")
                        break
                # If no text/plain artifact found, take the first one with content
                if not response_content:
                    for artifact in response["artifacts"]:
                        if artifact.get("content"):
                            response_content = artifact.get("content", "")
                            break
            
            # If no content from artifacts, try other response fields
            if not response_content:
                # Try direct response content
                if response.get("response"):
                    response_content = response.get("response", "")
                elif response.get("content"):
                    response_content = response.get("content", "")
                # Try status result
                elif response.get("status", {}).get("result"):
                    response_content = response.get("status", {}).get("result", "")
                # Try status artifacts
                elif response.get("status", {}).get("artifacts"):
                    status_artifacts = response.get("status", {}).get("artifacts", [])
                    for artifact in status_artifacts:
                        if artifact.get("content"):
                            response_content = artifact.get("content", "")
                            break
            
            # Fallback if still no content
            if not response_content:
                response_content = f"Task completed successfully (no detailed response available)"
                PrintStyle(font_color="yellow").print(f"Warning: No response content found for subordinate {role}")
                PrintStyle(font_color="gray").print(f"Response structure: {str(response)[:200]}...")
            
            # Update proxy context log with response content
            if proxy_context and hasattr(proxy_context, 'log'):
                proxy_context.log.log("agent", f"Response: {response_content[:500]}{'...' if len(response_content) > 500 else ''}")
            
            return response_content
            
        except Exception as e:
            subordinate.status = 'error'
            error_msg = str(e)

            # Update proxy context log with error if available
            if proxy_context and hasattr(proxy_context, 'log'):
                proxy_context.log.log("error", f"Error communicating with subordinate: {error_msg}")

            # Track communication failures
            if not hasattr(subordinate, 'failure_count'):
                subordinate.failure_count = 0
            subordinate.failure_count += 1

            # Check if this is a heartbeat timeout (task stuck)
            if "heartbeats without progress" in error_msg:
                PrintStyle(font_color="red").print(f"Subordinate {role} task appears stuck - received only heartbeats without task completion")
                PrintStyle(font_color="yellow").print(f"Consider restarting subordinate {role} if this persists")
            else:
                PrintStyle(font_color="red").print(f"Error communicating with subordinate {role}: {error_msg}")

            # If connection failures are repeated, mark for cleanup
            if "connection" in error_msg.lower() or "failed after" in error_msg.lower():
                if subordinate.failure_count >= 2:
                    PrintStyle(font_color="red").print(f"Subordinate {role} has failed {subordinate.failure_count} times - marking as error")
                    subordinate.status = 'error'
                    # Unregister proxy context for failed subordinate
                    self._unregister_subordinate_context(subordinate)
            
            raise
    
    def get_subordinate_by_role(self, role: str) -> Optional[SubordinateInfo]:
        """Get subordinate info by role"""
        if role in self.subordinate_registry:
            agent_id = self.subordinate_registry[role]
            return self.subordinates.get(agent_id)
        return None
    
    def get_subordinate_by_agent_id(self, agent_id: str) -> Optional[SubordinateInfo]:
        """Get subordinate info by agent ID"""
        return self.subordinates.get(agent_id)
    
    def get_all_subordinates(self) -> List[SubordinateInfo]:
        """Get all active subordinates"""
        return list(self.subordinates.values())

    def get_subordinate_by_role(self, role: str) -> Optional[SubordinateInfo]:
        """Get subordinate by role"""
        if role in self.subordinate_registry:
            agent_id = self.subordinate_registry[role]
            return self.subordinates.get(agent_id)
        return None

    def is_subordinate_busy(self, role: str) -> bool:
        """Check if subordinate is currently busy with a task"""
        subordinate = self.get_subordinate_by_role(role)
        return subordinate is not None and subordinate.status in ['working', 'starting']
    
    def get_subordinate_hierarchy(self) -> Dict[str, List[str]]:
        """Get agent hierarchy mapping"""
        hierarchy = {}
        for child_id, parent_id in self.agent_hierarchy.items():
            if parent_id not in hierarchy:
                hierarchy[parent_id] = []
            hierarchy[parent_id].append(child_id)
        return hierarchy
    
    async def shutdown_subordinate(self, role: str, force: bool = False):
        """Shutdown a specific subordinate"""
        if role not in self.subordinate_registry:
            return False
        
        agent_id = self.subordinate_registry[role]
        subordinate = self.subordinates.get(agent_id)
        
        if not subordinate:
            return False
        
        PrintStyle(font_color="yellow").print(f"Shutting down subordinate: {role}")
        
        subordinate.status = 'stopping'
        
        try:
            # Try graceful shutdown first
            if not force and subordinate.process:
                if os.name != 'nt':
                    os.killpg(os.getpgid(subordinate.process.pid), signal.SIGTERM)
                else:
                    subordinate.process.terminate()
                
                # Wait for graceful shutdown
                try:
                    subordinate.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    force = True
            
            # Force kill if necessary
            if force and subordinate.process:
                if os.name != 'nt':
                    os.killpg(os.getpgid(subordinate.process.pid), signal.SIGKILL)
                else:
                    subordinate.process.kill()
        
        except Exception as e:
            PrintStyle(font_color="yellow").print(f"Warning: Error shutting down subordinate {role}: {str(e)}")
        
        # Cleanup
        self.release_port(subordinate.port)
        
        # Remove subordinate proxy context from UI
        self._unregister_subordinate_context(subordinate)
        
        del self.subordinates[agent_id]
        del self.subordinate_registry[role]
        self.agent_hierarchy.pop(agent_id, None)
        
        # Remove from agent context
        self.agent_context.remove_a2a_peer(agent_id)
        
        PrintStyle(font_color="green").print(f"Subordinate {role} shutdown complete")
        return True
    
    def _force_cleanup_subordinate(self, role: str):
        """Force cleanup a subordinate without async (for exit handlers)"""
        if role not in self.subordinate_registry:
            return
        
        agent_id = self.subordinate_registry[role]
        subordinate = self.subordinates.get(agent_id)
        
        if not subordinate:
            return
        
        PrintStyle(font_color="yellow").print(f"Force cleaning up subordinate: {role}")
        
        try:
            # Force kill the process and its children
            if subordinate.process:
                try:
                    if os.name != 'nt':
                        # Kill the entire process group
                        pgid = os.getpgid(subordinate.process.pid)
                        os.killpg(pgid, signal.SIGKILL)
                    else:
                        subordinate.process.kill()
                except (ProcessLookupError, PermissionError):
                    pass  # Process already dead
        except Exception as e:
            PrintStyle(font_color="yellow").print(f"Warning: Error force killing subordinate {role}: {str(e)}")
        
        # Cleanup resources
        self.release_port(subordinate.port)
        
        # Remove subordinate proxy context from UI
        self._unregister_subordinate_context(subordinate)
        
        self.subordinates.pop(agent_id, None)
        self.subordinate_registry.pop(role, None)
        self.agent_hierarchy.pop(agent_id, None)
        self._process_groups.pop(role, None)
    
    def _cleanup_orphaned_processes(self):
        """Cleanup orphaned subordinate processes"""
        try:
            import subprocess
            # Find processes running a2a_subordinate_runner.py
            result = subprocess.run(
                ['pgrep', '-f', 'a2a_subordinate_runner.py'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    if pid.strip():
                        try:
                            os.kill(int(pid), signal.SIGKILL)
                            PrintStyle(font_color="yellow").print(f"Killed orphaned subordinate process {pid}")
                        except (ProcessLookupError, PermissionError, ValueError):
                            pass
        except Exception:
            # Fallback method using ps
            try:
                result = subprocess.run(
                    ['ps', 'aux'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                for line in result.stdout.split('\n'):
                    if 'a2a_subordinate_runner.py' in line and str(os.getpid()) not in line:
                        try:
                            pid = int(line.split()[1])
                            os.kill(pid, signal.SIGKILL)
                            PrintStyle(font_color="yellow").print(f"Killed orphaned subordinate process {pid}")
                        except (ProcessLookupError, PermissionError, ValueError, IndexError):
                            pass
            except Exception:
                pass
    
    def _cleanup_dead_ports(self):
        """Release ports from dead processes"""
        dead_ports = []
        for port in list(self.used_ports):
            if not self._is_port_in_use(port):
                dead_ports.append(port)
        
        for port in dead_ports:
            self.used_ports.discard(port)
            PrintStyle(font_color="cyan").print(f"Released dead port {port}")
    
    def _get_port_processes(self) -> Dict[int, str]:
        """Get mapping of ports to process info in the subordinate range"""
        port_processes = {}
        try:
            import subprocess
            result = subprocess.run(
                ['ss', '-tulpn'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            for line in result.stdout.split('\n'):
                if ':' in line:
                    parts = line.split()
                    for part in parts:
                        if ':' in part and not part.startswith('['):
                            try:
                                port = int(part.split(':')[-1])
                                if self.base_port <= port <= self.base_port + 1000:
                                    # Extract process info
                                    if 'users:' in line:
                                        proc_info = line.split('users:')[1].strip()
                                        port_processes[port] = proc_info
                                    else:
                                        port_processes[port] = "unknown"
                            except (ValueError, IndexError):
                                continue
        except Exception:
            pass
        
        return port_processes
    
    async def _register_subordinate_context(self, subordinate: SubordinateInfo):
        """Register subordinate context with main agent for UI visibility"""
        try:
            # First, unregister any existing proxy context with same agent_id to prevent duplicates
            from agent import AgentContext
            proxy_context_id = f"subordinate_{subordinate.agent_id}"
            existing_context = AgentContext.get(proxy_context_id)
            if existing_context:
                PrintStyle(font_color="yellow").print(f"Removing existing proxy context for {subordinate.agent_id}")
                AgentContext.remove(proxy_context_id)
            
            # Get subordinate context info via HTTP endpoint
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{subordinate.url}/context/info", timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("success"):
                            context_info = data.get("context_info", {})
                            
                            # Create a simplified proxy context for UI display
                            from agent import AgentContext, AgentContextType
                            proxy_context = AgentContext(
                                config=self.agent_context.config,
                                id=f"subordinate_{subordinate.agent_id}",  # Unique ID for subordinate
                                name=f"🤖 {subordinate.role} (Subordinate)",
                                type=AgentContextType.A2A,
                                created_at=subordinate.spawned_at,
                                paused=False
                            )
                            
                            # Set subordinate-specific properties
                            proxy_context.subordinate_info = {
                                "role": subordinate.role,
                                "url": subordinate.url,
                                "capabilities": subordinate.capabilities,
                                "status": subordinate.status,
                                "agent_id": subordinate.agent_id,
                                "port": subordinate.port,
                                "parent_context": self.agent_context.id,
                                "original_context_id": context_info.get("context_id", "unknown")
                            }
                            
                            # Mark as subordinate context
                            proxy_context.is_subordinate = True
                            
                            # Create a dummy agent for the proxy context
                            from agent import Agent
                            proxy_agent = Agent(0, self.agent_context.config, proxy_context)
                            proxy_context.agent0 = proxy_agent
                            proxy_context.streaming_agent = proxy_agent
                            
                            # Initialize log proxy for the proxy context that forwards logs from subordinate
                            from python.helpers.log import Log
                            proxy_log = Log()
                            
                            # Add initial log entry
                            proxy_log.log("agent", f"Subordinate agent '{subordinate.role}' initialized", subordinate_info=proxy_context.subordinate_info)
                            
                            proxy_context.log = proxy_log
                            
                            PrintStyle(font_color="cyan").print(f"Registered subordinate context for {subordinate.role}")
                        else:
                            PrintStyle(font_color="yellow").print(f"Failed to get context info for {subordinate.role}: {data.get('error', 'Unknown error')}")
                    else:
                        PrintStyle(font_color="yellow").print(f"HTTP error getting context info for {subordinate.role}: {response.status}")
                
        except Exception as e:
            PrintStyle(font_color="yellow").print(f"Could not register subordinate context for {subordinate.role}: {str(e)}")
    
    def _unregister_subordinate_context(self, subordinate: SubordinateInfo):
        """Remove subordinate proxy context from UI"""
        try:
            from agent import AgentContext
            proxy_context_id = f"subordinate_{subordinate.agent_id}"
            
            # Remove from global context registry
            if proxy_context_id in AgentContext._contexts:
                AgentContext.remove(proxy_context_id)
                PrintStyle(font_color="cyan").print(f"Unregistered subordinate context for {subordinate.role}")
                
        except Exception as e:
            PrintStyle(font_color="yellow").print(f"Could not unregister subordinate context for {subordinate.role}: {str(e)}")
    
    async def remove_subordinate(self, agent_id: str):
        """Remove a subordinate and clean up its resources"""
        if agent_id not in self.subordinates:
            return
        
        subordinate = self.subordinates[agent_id]
        role = subordinate.role
        
        PrintStyle(font_color="yellow").print(f"Removing subordinate {role} ({agent_id})")
        
        # Try graceful shutdown first
        try:
            if subordinate.process and subordinate.process.poll() is None:
                subordinate.process.terminate()
                await asyncio.sleep(2)  # Give it time to shut down
                
                # Force kill if still alive
                if subordinate.process.poll() is None:
                    subordinate.process.kill()
        except Exception as e:
            PrintStyle(font_color="gray").print(f"Error terminating subordinate: {e}")
        
        # Release port
        if subordinate.port in self.used_ports:
            self.used_ports.remove(subordinate.port)
            PrintStyle(font_color="cyan").print(f"Released port {subordinate.port}")
        
        # Remove from registries
        del self.subordinates[agent_id]
        if role in self.subordinate_registry and self.subordinate_registry[role] == agent_id:
            del self.subordinate_registry[role]
        
        # Remove from hierarchy
        if agent_id in self.agent_hierarchy:
            del self.agent_hierarchy[agent_id]
        
        PrintStyle(font_color="green").print(f"Subordinate {role} removed")
    
    def cleanup_all_subordinates(self):
        """Cleanup all subordinates on exit"""
        if self._shutdown_in_progress:
            return
        self._shutdown_in_progress = True
        
        if not self.subordinates:
            # Still cleanup any orphaned processes
            self._cleanup_orphaned_processes()
            return

        PrintStyle(font_color="yellow").print("Cleaning up all subordinates...")

        # Release any global spawn locks held by this process
        for role in list(self.subordinate_registry.keys()):
            _global_spawn_lock.release_spawn_lock(role)

        # Force kill all subordinates immediately on shutdown
        for role in list(self.subordinate_registry.keys()):
            try:
                # Use synchronous cleanup for exit handlers
                self._force_cleanup_subordinate(role)
            except Exception as e:
                PrintStyle(font_color="red").print(f"Error cleaning up subordinate {role}: {str(e)}")

        # Cleanup any remaining orphaned processes
        self._cleanup_orphaned_processes()
        
        PrintStyle(font_color="green").print("Subordinate cleanup complete")
    
    async def monitor_subordinates(self):
        """Monitor subordinate health and restart if necessary"""
        while True:
            try:
                for subordinate in list(self.subordinates.values()):
                    # Check process status
                    if subordinate.process and subordinate.process.poll() is not None:
                        PrintStyle(font_color="red").print(
                            f"Subordinate {subordinate.role} process died, restarting..."
                        )
                        await self.restart_subordinate(subordinate.role)
                    
                    # Check communication
                    elif subordinate.status in ['ready', 'idle']:
                        try:
                            await self.a2a_client.ping_peer(subordinate.url)
                            subordinate.last_contact = datetime.now(timezone.utc)
                        except Exception:
                            PrintStyle(font_color="yellow").print(
                                f"Lost communication with subordinate {subordinate.role}"
                            )
                            subordinate.status = 'error'
                
                await asyncio.sleep(10)  # Monitor every 10 seconds
                
            except Exception as e:
                PrintStyle(font_color="red").print(f"Error in subordinate monitoring: {str(e)}")
                await asyncio.sleep(5)
    
    async def restart_subordinate(self, role: str) -> bool:
        """Restart a failed subordinate"""
        subordinate = self.get_subordinate_by_role(role)
        if not subordinate:
            return False
        
        # Save configuration
        old_config = {
            "role": subordinate.role,
            "capabilities": subordinate.capabilities,
            "shared_context": subordinate.shared_context
        }
        
        # Shutdown old instance
        await self.shutdown_subordinate(role, force=True)
        
        # Restart with same configuration
        try:
            await self.spawn_subordinate(**old_config)
            return True
        except Exception as e:
            PrintStyle(font_color="red").print(f"Failed to restart subordinate {role}: {str(e)}")
            return False