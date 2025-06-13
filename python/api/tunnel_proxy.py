from flask import Request, Response
from python.helpers import dotenv, runtime
from python.helpers.api import ApiHandler
from python.helpers.tunnel_manager import TunnelManager
import requests


class TunnelProxy(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        # Get configuration from environment
        tunnel_api_port = (
            runtime.get_arg("tunnel_api_port")
            or int(dotenv.get_dotenv_value("TUNNEL_API_PORT", 0))
            or 55520
        )

        # first verify the service is running:
        service_ok = False
        try:
            response = requests.post(f"http://localhost:{tunnel_api_port}/", json={"action": "health"})
            if response.status_code == 200:
                service_ok = True
        except Exception as e:
            service_ok = False

        # forward this request to the tunnel service if OK
        if service_ok:
            try:
                response = requests.post(f"http://localhost:{tunnel_api_port}/", json=input)
                return response.json()
            except Exception as e:
                return {"error": str(e)}
        else:
            # forward to API handler directly
            from python.api.tunnel import Tunnel
            return await Tunnel(self.app, self.thread_lock).process(input, request)
