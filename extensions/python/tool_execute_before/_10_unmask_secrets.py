from typing import Any

from helpers.extension import Extension
from helpers.secrets import get_secrets_manager


def _replace_secret_placeholders(value: Any, secrets_mgr: Any) -> Any:
    if isinstance(value, str):
        return secrets_mgr.replace_placeholders(value)
    if isinstance(value, dict):
        return {
            key: _replace_secret_placeholders(item, secrets_mgr)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_replace_secret_placeholders(item, secrets_mgr) for item in value]
    if isinstance(value, tuple):
        return tuple(_replace_secret_placeholders(item, secrets_mgr) for item in value)
    return value


class UnmaskToolSecrets(Extension):

    async def execute(self, **kwargs):
        if not self.agent:
            return

        # Get tool args from kwargs
        tool_args = kwargs.get("tool_args")
        if not tool_args:
            return

        secrets_mgr = get_secrets_manager(self.agent.context)

        # Unmask placeholders recursively in arguments for actual tool execution
        for key, value in tool_args.items():
            tool_args[key] = _replace_secret_placeholders(value, secrets_mgr)
