#!/usr/bin/env python3
"""
A2A Subordinate Manager

Manages A2A-based subordinate agents with proper lifecycle management,
auto-port allocation, and inter-agent communication coordination.
"""

import asyncio
import json
import os
import psutil
import signal
import subprocess
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

from python.helpers.print_style import PrintStyle
from python.helpers.a2a_client import A2AClient
from python.helpers.a2a_handler import A2AHandler, A2AError, A2AErrorType


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
        self.base_port = base_port
        self.subordinates: Dict[str, SubordinateInfo] = {}
        self.allocated_ports: Set[int] = set()
        self.a2a_client = A2AClient(timeout=30.0, max_retries=2)
        
        # Agent hierarchy tracking
        self.agent_hierarchy: Dict[str, str] = {}  # child_id -> parent_id
        self.subordinate_registry: Dict[str, str] = {}  # role -> agent_id
        
        # Cleanup on exit
        import atexit
        atexit.register(self.cleanup_all_subordinates)
    
    def allocate_port(self) -> int:
        """Allocate an available port for a new subordinate"""
        port = self.base_port
        while port in self.allocated_ports or self._is_port_in_use(port):
            port += 1
            if port > self.base_port + 1000:  # Safety limit
                raise RuntimeError("Unable to allocate port for subordinate")
        
        self.allocated_ports.add(port)
        return port
    
    def _is_port_in_use(self, port: int) -> bool:
        """Check if a port is currently in use"""
        try:
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                result = sock.connect_ex(('localhost', port))
                return result == 0
        except Exception:
            return False
    
    def release_port(self, port: int):
        """Release a port back to the pool"""
        self.allocated_ports.discard(port)
    
    async def spawn_subordinate(
        self,
        role: str,
        prompt_profile: str = "default",
        capabilities: List[str] = None,
        shared_context: Dict[str, Any] = None,
        force_new: bool = False
    ) -> SubordinateInfo:
        """
        Spawn a new A2A subordinate agent
        
        Args:
            role: Role/specialty of the subordinate (e.g., 'coder', 'analyst')
            prompt_profile: Prompt profile to use for the subordinate
            capabilities: List of capabilities the subordinate should have
            shared_context: Context data to share with subordinate
            force_new: Force creation of new subordinate even if one exists
        
        Returns:
            SubordinateInfo object with subordinate details
        """
        # Check if subordinate with this role already exists
        if not force_new and role in self.subordinate_registry:
            existing_id = self.subordinate_registry[role]
            if existing_id in self.subordinates:
                subordinate = self.subordinates[existing_id]
                if subordinate.status in ['ready', 'idle']:
                    PrintStyle(font_color="yellow").print(f"Reusing existing subordinate: {role}")
                    return subordinate
        
        # Generate subordinate details
        agent_id = f"{self.agent_context.agent0.agent_name}.{role}.{uuid.uuid4().hex[:8]}"
        port = self.allocate_port()
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
            
            PrintStyle(font_color="green").print(f"Subordinate {role} ready at {url}")
            
            # Update agent context
            self.agent_context.add_a2a_peer(agent_id, {
                "role": role,
                "url": url,
                "capabilities": subordinate.capabilities,
                "type": "subordinate"
            })
            
            return subordinate
            
        except Exception as e:
            # Cleanup on failure
            if subordinate.process:
                try:
                    subordinate.process.terminate()
                except:
                    pass
            
            self.release_port(port)
            subordinate.status = 'error'
            
            PrintStyle(font_color="red").print(f"Failed to spawn subordinate {role}: {str(e)}")
            raise A2AError(
                A2AErrorType.INVALID_AGENT_RESPONSE,
                f"Failed to spawn subordinate {role}: {str(e)}"
            )
    
    def _create_subordinate_config(self, subordinate: SubordinateInfo, prompt_profile: str) -> Dict[str, Any]:
        """Create configuration for subordinate agent"""
        return {
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
            "a2a_auth_required": False,  # Simplified for subordinates
            "working_directory": os.getcwd()
        }
    
    async def _spawn_subordinate_process(self, config: Dict[str, Any]) -> subprocess.Popen:
        """Spawn subordinate as independent Python process"""
        # Create temporary config file
        config_file = f"/tmp/subordinate_config_{config['agent_id']}.json"
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        # Python command to spawn subordinate
        python_path = sys.executable
        script_path = os.path.join(os.path.dirname(__file__), "a2a_subordinate_runner.py")
        
        # Spawn process
        process = subprocess.Popen([
            python_path, script_path, config_file
        ], cwd=config["working_directory"],
           stdout=subprocess.PIPE,
           stderr=subprocess.PIPE,
           preexec_fn=os.setsid if os.name != 'nt' else None)
        
        PrintStyle(font_color="cyan").print(f"Spawned subordinate process PID: {process.pid}")
        
        return process
    
    async def _wait_for_subordinate_ready(self, subordinate: SubordinateInfo, timeout: int = 30):
        """Wait for subordinate to be ready for communication"""
        start_time = datetime.now()
        
        while (datetime.now() - start_time).seconds < timeout:
            try:
                # Try to ping subordinate
                agent_card = await self.a2a_client.discover_agent(subordinate.url)
                if agent_card and agent_card.get("name"):
                    PrintStyle(font_color="green").print(f"Subordinate {subordinate.role} is ready")
                    return
            except Exception:
                pass
            
            # Check if process is still running
            if subordinate.process and subordinate.process.poll() is not None:
                raise RuntimeError(f"Subordinate process {subordinate.role} exited prematurely")
            
            await asyncio.sleep(1)
        
        raise TimeoutError(f"Subordinate {subordinate.role} failed to start within {timeout} seconds")
    
    async def send_message_to_subordinate(
        self,
        role: str,
        message: str,
        context_data: Dict[str, Any] = None,
        timeout: int = 60
    ) -> str:
        """Send a message to a subordinate agent"""
        if role not in self.subordinate_registry:
            raise A2AError(
                A2AErrorType.TASK_NOT_FOUND,
                f"No subordinate found with role: {role}"
            )
        
        agent_id = self.subordinate_registry[role]
        subordinate = self.subordinates[agent_id]
        
        if subordinate.status not in ['ready', 'idle']:
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
            
            # Send task via A2A client
            response = await self.a2a_client.submit_task_with_sse(
                peer_url=subordinate.url,
                task_data=task_data,
                timeout=timeout
            )
            
            subordinate.status = 'idle'
            subordinate.last_contact = datetime.now(timezone.utc)
            
            # Extract response message
            if response.get("artifacts"):
                return response["artifacts"][0].get("content", "No response")
            else:
                return response.get("status", {}).get("result", "Task completed")
            
        except Exception as e:
            subordinate.status = 'error'
            PrintStyle(font_color="red").print(f"Error communicating with subordinate {role}: {str(e)}")
            raise
    
    def get_subordinate_by_role(self, role: str) -> Optional[SubordinateInfo]:
        """Get subordinate info by role"""
        if role in self.subordinate_registry:
            agent_id = self.subordinate_registry[role]
            return self.subordinates.get(agent_id)
        return None
    
    def get_all_subordinates(self) -> List[SubordinateInfo]:
        """Get all active subordinates"""
        return list(self.subordinates.values())
    
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
        del self.subordinates[agent_id]
        del self.subordinate_registry[role]
        self.agent_hierarchy.pop(agent_id, None)
        
        # Remove from agent context
        self.agent_context.remove_a2a_peer(agent_id)
        
        PrintStyle(font_color="green").print(f"Subordinate {role} shutdown complete")
        return True
    
    def cleanup_all_subordinates(self):
        """Cleanup all subordinates on exit"""
        if not self.subordinates:
            return
            
        PrintStyle(font_color="yellow").print("Cleaning up all subordinates...")
        
        for role in list(self.subordinate_registry.keys()):
            try:
                asyncio.run(self.shutdown_subordinate(role, force=True))
            except Exception as e:
                PrintStyle(font_color="red").print(f"Error cleaning up subordinate {role}: {str(e)}")
        
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