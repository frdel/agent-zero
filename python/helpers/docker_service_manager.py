import subprocess
import time
import logging
import os
import json
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from python.helpers.print_style import PrintStyle

class DockerServiceManager:
    """
    Manages Docker services automatically for Agent Zero
    Handles starting, stopping, and health checking of required services
    """
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.docker_compose_file = self.project_root / "docker-compose.yml"
        self.required_services = ["mem0_store", "neo4j"]
        self.optional_services = ["openmemory-mcp"]
        
    def is_docker_available(self) -> bool:
        """Check if Docker is installed and running"""
        try:
            result = subprocess.run(['docker', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                return False
                
            # Check if Docker daemon is running
            result = subprocess.run(['docker', 'info'], 
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
            
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    def is_docker_compose_available(self) -> bool:
        """Check if docker-compose is available"""
        try:
            # Try docker compose (newer syntax)
            result = subprocess.run(['docker', 'compose', 'version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return True
                
            # Try docker-compose (legacy)
            result = subprocess.run(['docker-compose', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
            
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    def get_compose_command(self) -> List[str]:
        """Get the appropriate docker compose command"""
        try:
            result = subprocess.run(['docker', 'compose', 'version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return ['docker', 'compose']
        except:
            pass
            
        return ['docker-compose']
    
    def get_service_status(self, service_name: str) -> Dict:
        """Get status of a specific service"""
        try:
            compose_cmd = self.get_compose_command()
            result = subprocess.run(
                compose_cmd + ['-f', str(self.docker_compose_file), 'ps', service_name, '--format', 'json'],
                capture_output=True, text=True, timeout=10,
                cwd=self.project_root
            )
            
            if result.returncode == 0 and result.stdout.strip():
                try:
                    # Handle both single service and multiple services output
                    lines = result.stdout.strip().split('\n')
                    for line in lines:
                        if line.strip():
                            service_info = json.loads(line)
                            if service_info.get('Service') == service_name:
                                return {
                                    'name': service_info.get('Service', service_name),
                                    'state': service_info.get('State', 'unknown'),
                                    'status': service_info.get('Status', 'unknown'),
                                    'ports': service_info.get('Publishers', []),
                                    'running': service_info.get('State', '').lower() == 'running'
                                }
                except json.JSONDecodeError:
                    pass
            
            return {
                'name': service_name,
                'state': 'not_found',
                'status': 'not_found',
                'ports': [],
                'running': False
            }
            
        except subprocess.TimeoutExpired:
            return {
                'name': service_name,
                'state': 'timeout',
                'status': 'timeout',
                'ports': [],
                'running': False
            }
        except Exception as e:
            return {
                'name': service_name,
                'state': 'error',
                'status': str(e),
                'ports': [],
                'running': False
            }
    
    def start_service(self, service_name: str, timeout: int = 60) -> Tuple[bool, str]:
        """Start a specific service"""
        try:
            PrintStyle.standard(f"Starting {service_name} service...")
            
            compose_cmd = self.get_compose_command()
            result = subprocess.run(
                compose_cmd + ['-f', str(self.docker_compose_file), 'up', '-d', service_name],
                capture_output=True, text=True, timeout=timeout,
                cwd=self.project_root
            )
            
            if result.returncode == 0:
                # Wait for service to be healthy
                if self.wait_for_service_health(service_name, timeout=30):
                    return True, f"Service {service_name} started successfully"
                else:
                    return False, f"Service {service_name} started but health check failed"
            else:
                error_msg = result.stderr or result.stdout or "Unknown error"
                return False, f"Failed to start {service_name}: {error_msg}"
                
        except subprocess.TimeoutExpired:
            return False, f"Timeout starting {service_name}"
        except Exception as e:
            return False, f"Error starting {service_name}: {str(e)}"
    
    def wait_for_service_health(self, service_name: str, timeout: int = 30) -> bool:
        """Wait for a service to become healthy"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = self.get_service_status(service_name)
            
            if status['running']:
                # Additional health checks for specific services
                if service_name == "neo4j":
                    if self.check_neo4j_health():
                        return True
                elif service_name == "mem0_store":
                    if self.check_qdrant_health():
                        return True
                else:
                    return True  # Generic service is running
            
            time.sleep(2)
        
        return False
    
    def check_neo4j_health(self) -> bool:
        """Check if Neo4j is responding"""
        try:
            import requests
            response = requests.get("http://localhost:7475", timeout=5)  # Updated port
            return response.status_code == 200
        except:
            return False
    
    def check_qdrant_health(self) -> bool:
        """Check if Qdrant is responding"""
        try:
            import requests
            response = requests.get("http://localhost:6333/collections", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def ensure_services_running(self, services: List[str] = None) -> Dict[str, bool]:
        """Ensure specified services are running, start them if needed"""
        if services is None:
            services = self.required_services
            
        results = {}
        
        # Check Docker availability first
        if not self.is_docker_available():
            PrintStyle.error("Docker is not available. Please install and start Docker.")
            return {service: False for service in services}
        
        if not self.is_docker_compose_available():
            PrintStyle.error("Docker Compose is not available. Please install Docker Compose.")
            return {service: False for service in services}
        
        if not self.docker_compose_file.exists():
            PrintStyle.error(f"Docker compose file not found: {self.docker_compose_file}")
            return {service: False for service in services}
        
        for service in services:
            PrintStyle.standard(f"Checking {service} service...")
            
            status = self.get_service_status(service)
            
            if status['running']:
                PrintStyle.standard(f"✅ {service} is already running")
                results[service] = True
            else:
                PrintStyle.standard(f"🔄 {service} is not running, starting...")
                success, message = self.start_service(service)
                
                if success:
                    PrintStyle.standard(f"✅ {message}")
                    results[service] = True
                else:
                    PrintStyle.error(f"❌ {message}")
                    results[service] = False
        
        return results
    
    def stop_services(self, services: List[str] = None) -> Dict[str, bool]:
        """Stop specified services"""
        if services is None:
            services = self.required_services + self.optional_services
            
        results = {}
        
        if not self.is_docker_compose_available():
            return {service: False for service in services}
        
        for service in services:
            try:
                compose_cmd = self.get_compose_command()
                result = subprocess.run(
                    compose_cmd + ['-f', str(self.docker_compose_file), 'stop', service],
                    capture_output=True, text=True, timeout=30,
                    cwd=self.project_root
                )
                
                results[service] = result.returncode == 0
                
            except Exception as e:
                PrintStyle.error(f"Error stopping {service}: {str(e)}")
                results[service] = False
        
        return results
    
    def get_services_info(self) -> Dict:
        """Get comprehensive information about all services"""
        info = {
            'docker_available': self.is_docker_available(),
            'compose_available': self.is_docker_compose_available(),
            'services': {}
        }
        
        all_services = self.required_services + self.optional_services
        
        for service in all_services:
            info['services'][service] = self.get_service_status(service)
        
        return info
    
    def auto_setup_services(self) -> bool:
        """Automatically set up required services for mem0 Graph Memory"""
        PrintStyle.standard("🚀 Setting up mem0 Graph Memory services...")
        
        # Check prerequisites
        if not self.is_docker_available():
            PrintStyle.error("❌ Docker is required but not available")
            PrintStyle.standard("Please install Docker: https://docs.docker.com/get-docker/")
            return False
        
        if not self.is_docker_compose_available():
            PrintStyle.error("❌ Docker Compose is required but not available")
            PrintStyle.standard("Please install Docker Compose: https://docs.docker.com/compose/install/")
            return False
        
        # Start required services
        results = self.ensure_services_running(self.required_services)
        
        success_count = sum(1 for success in results.values() if success)
        total_count = len(results)
        
        if success_count == total_count:
            PrintStyle.standard(f"✅ All {total_count} services started successfully!")
            PrintStyle.standard("🎉 mem0 Graph Memory is ready to use")
            return True
        else:
            PrintStyle.error(f"❌ {success_count}/{total_count} services started successfully")
            PrintStyle.standard("Some services may not be available. Agent Zero will use fallback options.")
            return success_count > 0

# Global instance for easy access
docker_service_manager = DockerServiceManager()