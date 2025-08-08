from python.helpers.extension import Extension
from agent import LoopData


class IncludeSudoCommands(Extension):
    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        """Inject current user's sudo commands into prompt extras"""
        try:
            from python.helpers.user_management import get_current_user
            current_user = get_current_user()

            # Format sudo commands for prompt injection
            sudo_prompt = self._format_sudo_commands(current_user)
            loop_data.extras_temporary["sudo_commands"] = sudo_prompt

        except Exception:
            # Graceful fallback if no user context available
            # Default behavior for non-authenticated contexts
            pass

    def _format_sudo_commands(self, user):
        """Format the sudo commands for the system prompt"""
        if user.is_admin:
            return self.agent.read_prompt(
                "agent.extras.sudo_commands_admin.md",
                username=user.username
            )
        else:
            # Regular user with sudo whitelist
            sudo_commands_text = "\n".join([f"- {cmd}" for cmd in user.sudo_commands])
            return self.agent.read_prompt(
                "agent.extras.sudo_commands_user.md",
                username=user.username,
                system_username=user.system_username,
                sudo_commands=sudo_commands_text,
                command_count=len(user.sudo_commands)
            )
