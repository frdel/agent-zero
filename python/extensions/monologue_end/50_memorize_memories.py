from agent import Agent
from python.helpers.extension import Extension
import python.helpers.files as files
from python.helpers.vector_db import Area
import json
from python.helpers.dirty_json import DirtyJson
from python.helpers import errors
from python.tools.memory_tool import get_db

class MemorizeMemories(Extension):

    async def execute(self, loop_data={}, **kwargs):
        # try:
 
            # show temp info message
            self.agent.context.log.log(
                type="info", content="Memorizing new information...", temp=True
            )

            # show full util message, this will hide temp message immediately if turned on
            log_item = self.agent.context.log.log(
                type="util",
                heading="Memorizing new information...",
            )

            # get system message and chat history for util llm
            system = self.agent.read_prompt("memory.memories_sum.sys.md")
            msgs_text = self.agent.concat_messages(self.agent.history)

            # log query streamed by LLM
            def log_callback(content):
                log_item.stream(content=content)

            # call util llm to find info in history
            memories_json = await self.agent.call_utility_llm(
                system=system,
                msg=msgs_text,
                callback=log_callback,
            )

            memories = DirtyJson.parse_string(memories_json)

            if not isinstance(memories, list) or len(memories) == 0:
                log_item.update(heading="No useful information to memorize.")
                return
            else:
                log_item.update(
                    heading=f"{len(memories)} entries to memorize."
                )

            # save chat history
            vdb = get_db(self.agent)

            memories_txt = ""
            for memory in memories:
                # solution to plain text:
                txt = f"{memory}"
                memories_txt += txt + "\n\n"
                vdb.insert_text(
                    text=txt, metadata={"area": Area.MAIN.value}
                )

            memories_txt = memories_txt.strip()
            log_item.update(memories=memories_txt)
            log_item.update(
                result=f"{len(memories)} entries memorized.",
                heading=f"{len(memories)} entries memorized.",
            )

        # except Exception as e:
        #     err = errors.format_error(e)
        #     self.agent.context.log.log(
        #         type="error", heading="Memorize memories extension error:", content=err
        #     )
