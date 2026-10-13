from helpers.extension import Extension


class CheckChatModel(Extension):
    async def execute(self, data=None, **kwargs):
        agent = self.agent
        if not agent or not isinstance(data, dict) or data.get("model_not_configured"):
            return
        try:
            from plugins._model_config.helpers import model_config
        except Exception:
            return
        if model_config.is_chat_model_configured(model_config.get_effective_config(agent)):
            return
        data["model_not_configured"] = True
