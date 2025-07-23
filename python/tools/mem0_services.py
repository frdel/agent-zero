from python.helpers.tool import Tool, Response
from python.helpers.settings import get_settings
from python.helpers.print_style import PrintStyle

class Mem0Services(Tool):
    """
    Manage mem0 Graph Memory Docker services - check status, start, stop, or restart services
    """
    
    async def execute(self, action="status", service="", **kwargs):
        """
        Manage mem0 services
        
        Args:
            action: Action to perform - 'status', 'start', 'stop', 'restart', or 'setup'
            service: Specific service name (optional) - 'neo4j', 'mem0_store', or 'openmemory-mcp'
        """
        try:
            from python.helpers.docker_service_manager import docker_service_manager
        except ImportError:
            return Response(
                message="Docker service manager not available. Please ensure Docker is installed.",
                break_loop=False
            )
        
        action = action.lower().strip()
        service = service.lower().strip() if service else ""
        
        if action == "status":
            return await self._show_status(docker_service_manager, service)
        elif action == "start":
            return await self._start_services(docker_service_manager, service)
        elif action == "stop":
            return await self._stop_services(docker_service_manager, service)
        elif action == "restart":
            return await self._restart_services(docker_service_manager, service)
        elif action == "setup":
            return await self._setup_services(docker_service_manager)
        else:
            return Response(
                message="Invalid action. Use: 'status', 'start', 'stop', 'restart', or 'setup'",
                break_loop=False
            )
    
    async def _show_status(self, manager, service_filter=""):
        """Show status of mem0 services"""
        info = manager.get_services_info()
        
        response_parts = [
            "**mem0 Graph Memory Services Status**",
            "=" * 40,
            ""
        ]
        
        # Docker availability
        if info['docker_available']:
            response_parts.append("🐳 Docker: ✅ Available")
        else:
            response_parts.append("🐳 Docker: ❌ Not available")
            response_parts.append("   Please install Docker: https://docs.docker.com/get-docker/")
        
        if info['compose_available']:
            response_parts.append("🐙 Docker Compose: ✅ Available")
        else:
            response_parts.append("🐙 Docker Compose: ❌ Not available")
            response_parts.append("   Please install Docker Compose: https://docs.docker.com/compose/install/")
        
        response_parts.append("")
        
        # Service status
        if not info['docker_available'] or not info['compose_available']:
            response_parts.append("Cannot check service status without Docker and Docker Compose.")
            return Response(message="\n".join(response_parts), break_loop=False)
        
        response_parts.append("**Service Status:**")
        response_parts.append("")
        
        for service_name, status in info['services'].items():
            # Filter by service if specified
            if service_filter and service_filter not in service_name.lower():
                continue
            
            if status['running']:
                status_icon = "✅"
                status_text = f"Running ({status['status']})"
            elif status['state'] == 'not_found':
                status_icon = "⚫"
                status_text = "Not created"
            else:
                status_icon = "❌"
                status_text = f"Stopped ({status['state']})"
            
            response_parts.append(f"{status_icon} **{service_name}**: {status_text}")
            
            # Show port mappings if available
            if status['ports']:
                port_info = []
                for port in status['ports']:
                    if isinstance(port, dict):
                        published = port.get('PublishedPort', '')
                        target = port.get('TargetPort', '')
                        if published and target:
                            port_info.append(f"{published}:{target}")
                if port_info:
                    response_parts.append(f"   Ports: {', '.join(port_info)}")
            
            response_parts.append("")
        
        # Add usage instructions
        settings = get_settings()
        response_parts.extend([
            "**Quick Actions:**",
            "• `mem0_services start` - Start all required services",
            "• `mem0_services setup` - Auto-setup all services",
            "• `mem0_services stop` - Stop all services",
            ""
        ])
        
        # Show configuration status
        deployment_mode = settings.get("mem0_deployment", "local")
        graph_enabled = settings.get("mem0_enable_graph_memory", False)
        auto_start = settings.get("mem0_auto_start_services", True)
        
        response_parts.extend([
            "**Configuration:**",
            f"• Deployment mode: {deployment_mode}",
            f"• Graph memory: {'✅ Enabled' if graph_enabled else '❌ Disabled'}",
            f"• Auto-start services: {'✅ Enabled' if auto_start else '❌ Disabled'}",
        ])
        
        return Response(message="\n".join(response_parts), break_loop=False)
    
    async def _start_services(self, manager, service_filter=""):
        """Start mem0 services"""
        settings = get_settings()
        
        if service_filter:
            # Start specific service
            services = [service_filter] if service_filter in ["neo4j", "mem0_store", "openmemory-mcp"] else []
            if not services:
                return Response(
                    message=f"Invalid service name: {service_filter}. Use: neo4j, mem0_store, or openmemory-mcp",
                    break_loop=False
                )
        else:
            # Start required services based on configuration
            services = ["mem0_store"]  # Always need Qdrant
            if settings.get("mem0_enable_graph_memory", False):
                services.append("neo4j")
        
        PrintStyle.standard(f"Starting services: {', '.join(services)}")
        results = manager.ensure_services_running(services)
        
        response_parts = ["**Service Start Results:**", ""]
        
        for service, success in results.items():
            if success:
                response_parts.append(f"✅ {service}: Started successfully")
            else:
                response_parts.append(f"❌ {service}: Failed to start")
        
        success_count = sum(1 for success in results.values() if success)
        total_count = len(results)
        
        response_parts.extend([
            "",
            f"**Summary:** {success_count}/{total_count} services started successfully"
        ])
        
        if success_count == total_count:
            response_parts.append("🎉 All services are ready!")
        else:
            response_parts.append("⚠️ Some services failed to start. Check Docker logs for details.")
        
        return Response(message="\n".join(response_parts), break_loop=False)
    
    async def _stop_services(self, manager, service_filter=""):
        """Stop mem0 services"""
        if service_filter:
            services = [service_filter] if service_filter in ["neo4j", "mem0_store", "openmemory-mcp"] else []
            if not services:
                return Response(
                    message=f"Invalid service name: {service_filter}. Use: neo4j, mem0_store, or openmemory-mcp",
                    break_loop=False
                )
        else:
            services = ["neo4j", "mem0_store", "openmemory-mcp"]
        
        PrintStyle.standard(f"Stopping services: {', '.join(services)}")
        results = manager.stop_services(services)
        
        response_parts = ["**Service Stop Results:**", ""]
        
        for service, success in results.items():
            if success:
                response_parts.append(f"✅ {service}: Stopped successfully")
            else:
                response_parts.append(f"❌ {service}: Failed to stop")
        
        return Response(message="\n".join(response_parts), break_loop=False)
    
    async def _restart_services(self, manager, service_filter=""):
        """Restart mem0 services"""
        # Stop first
        stop_response = await self._stop_services(manager, service_filter)
        
        # Wait a moment
        import asyncio
        await asyncio.sleep(2)
        
        # Start again
        start_response = await self._start_services(manager, service_filter)
        
        return Response(
            message=f"{stop_response.message}\n\n{start_response.message}",
            break_loop=False
        )
    
    async def _setup_services(self, manager):
        """Auto-setup all required services"""
        PrintStyle.standard("🚀 Setting up mem0 Graph Memory services...")
        
        success = manager.auto_setup_services()
        
        if success:
            return Response(
                message="✅ mem0 Graph Memory services setup completed successfully!\n\n"
                       "You can now use mem0 with Graph Memory features.\n"
                       "Use `mem0_services status` to check service status.",
                break_loop=False
            )
        else:
            return Response(
                message="⚠️ Service setup completed with some issues.\n\n"
                       "Some services may not be available, but Agent Zero will use fallback options.\n"
                       "Use `mem0_services status` to see detailed status.",
                break_loop=False
            )