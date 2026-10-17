from helpers.extension import Extension
from agent import LoopData, AgentContextType
from helpers import persist_chat


class SaveChat(Extension):
    """Persist the chat when the monologue ends.

    The regular save hook lives at message_loop_end (_90_save_chat), which
    runs before monologue_end extensions. Anything logged from monologue_end
    — the "Waiting for input" progress reset and post-turn utility items such
    as memory memorization — would otherwise only reach chat.json when the
    next turn happens to trigger a save, and is lost entirely if the server
    restarts in between. Background memorize tasks persist their terminal
    state separately when they complete.
    """

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        if not self.agent:
            return

        # Skip saving BACKGROUND contexts as they should be ephemeral
        if self.agent.context.type == AgentContextType.BACKGROUND:
            return

        persist_chat.save_tmp_chat(self.agent.context)
