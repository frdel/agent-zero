from flask import Request, Response
from python.helpers.api import ApiHandler
from python.helpers.tunnel_manager import TunnelManager

class Tunnel(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        action = input.get("action", "get")
        
        tunnel_manager = TunnelManager.get_instance()
        
        if action == "create":
            # Get the port from the request or use default
            port = input.get("port", 5000)
            tunnel_url = tunnel_manager.start_tunnel(port)
            if tunnel_url is None:
                # Add a little delay and check again - tunnel might be starting
                import time
                time.sleep(2)
                tunnel_url = tunnel_manager.get_tunnel_url()
            
            return {
                "success": tunnel_url is not None,
                "tunnel_url": tunnel_url,
                "message": "Tunnel creation in progress" if tunnel_url is None else "Tunnel created successfully"
            }
        
        elif action == "stop":
            success = tunnel_manager.stop_tunnel()
            return {
                "success": success
            }
        
        elif action == "get":
            tunnel_url = tunnel_manager.get_tunnel_url()
            return {
                "success": tunnel_url is not None,
                "tunnel_url": tunnel_url,
                "is_running": tunnel_manager.is_running
            }
        
        return {
            "success": False,
            "error": "Invalid action. Use 'create', 'stop', or 'get'."
        } 
