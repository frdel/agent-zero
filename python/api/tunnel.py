from python.helpers.api import ApiHandler, Request, Response
from python.helpers import runtime
from python.helpers.tunnel_manager import TunnelManager

class Tunnel(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        action = input.get("action", "get")
        
        tunnel_manager = TunnelManager.get_instance()

        if action == "health":
            return {"success": True}
        
        if action == "create":
            port = runtime.get_web_ui_port()
            provider = input.get("provider", "serveo")  # Default to serveo
            tunnel_url = tunnel_manager.start_tunnel(port, provider)
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
            return self.stop()
        
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

    def stop(self):
        tunnel_manager = TunnelManager.get_instance()
        tunnel_manager.stop_tunnel()
        return {
            "success": True
        }
