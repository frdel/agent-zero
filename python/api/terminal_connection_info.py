from python.helpers.api import ApiHandler, Request, Response
from python.helpers.webssh_manager import webssh_manager
from python.helpers import rfc_exchange
from agent import AgentContext


class TerminalConnectionInfo(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        """Get terminal connection details for WebSSH integration"""
        try:
            # Get context_id and session from input
            context_id = input.get("context_id", "")
            session = int(input.get("session", 0))

            if not context_id:
                return {"error": "Missing context_id parameter"}

            # Get agent context
            context = AgentContext.get(context_id)
            if not context:
                return {"error": f"Context not found: {context_id}"}

            # Get agent from context
            agent = context.get_agent()
            if not agent:
                return {"error": "No agent found in context"}

            # Check if WebSSH server is running
            if not webssh_manager.is_running:
                return {"error": "WebSSH server is not running"}

            # Get SSH connection details from agent config
            if not agent.config.code_exec_ssh_enabled:
                return {"error": "SSH execution is not enabled"}

            # Get SSH connection parameters
            ssh_host = agent.config.code_exec_ssh_addr
            ssh_port = agent.config.code_exec_ssh_port
            ssh_user = agent.config.code_exec_ssh_user

            # Get SSH password (try config first, then RFC exchange)
            ssh_password = agent.config.code_exec_ssh_pass
            if not ssh_password:
                ssh_password = await rfc_exchange.get_root_password()

            if not ssh_password:
                return {"error": "SSH password not available"}

            # Generate WebSSH connection URL
            webssh_url = webssh_manager.get_connection_url(
                hostname=ssh_host,
                port=ssh_port,
                username=ssh_user,
                password=ssh_password,
                session_id=session  # Pass session ID for tmux session matching
            )

            if not webssh_url:
                return {"error": "Failed to generate WebSSH URL"}

            # Return connection details
            return {
                "success": True,
                "webssh_url": webssh_url,
                "session": session,
                "ssh_host": ssh_host,
                "ssh_port": ssh_port,
                "ssh_user": ssh_user,
                "webssh_server": webssh_manager.get_connection_details()
            }

        except Exception as e:
            return {"error": f"Failed to get terminal connection info: {str(e)}"}
