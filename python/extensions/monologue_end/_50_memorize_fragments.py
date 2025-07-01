import asyncio
from python.helpers.extension import Extension
from python.helpers.memory import Memory
from python.helpers.dirty_json import DirtyJson
from agent import LoopData
from python.helpers.log import LogItem


class MemorizeMemories(Extension):

    REPLACE_THRESHOLD = 0.9

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        # try:

        # show full util message
        log_item = self.agent.context.log.log(
            type="util",
            heading="Memorizing new information...",
        )

        # memorize in background
        asyncio.create_task(self.memorize(loop_data, log_item))

    async def memorize(self, loop_data: LoopData, log_item: LogItem, **kwargs):

        # get system message and chat history for util llm
        system = self.agent.read_prompt("memory.memories_sum.sys.md")
        msgs_text = self.agent.concat_messages(self.agent.history)

        # log query streamed by LLM
        async def log_callback(content):
            log_item.stream(content=content)

        # call util llm to find info in history
        memories_json = await self.agent.call_utility_model(
            system=system,
            message=msgs_text,
            callback=log_callback,
            background=True,
        )

        # Add validation and error handling for memories_json
        if not memories_json or not isinstance(memories_json, str):
            log_item.update(heading="No response from utility model.")
            return

        # Strip any whitespace that might cause issues
        memories_json = memories_json.strip()

        if not memories_json:
            log_item.update(heading="Empty response from utility model.")
            return

        try:
            memories = DirtyJson.parse_string(memories_json)
        except Exception as e:
            log_item.update(heading=f"Failed to parse memories response: {str(e)}")
            return

        # Validate that memories is a list or convertible to one
        if memories is None:
            log_item.update(heading="No valid memories found in response.")
            return

        # If memories is not a list, try to make it one
        if not isinstance(memories, list):
            if isinstance(memories, (str, dict)):
                memories = [memories]
            else:
                log_item.update(heading="Invalid memories format received.")
                return

        if not isinstance(memories, list) or len(memories) == 0:
            log_item.update(heading="No useful information to memorize.")
            return
        else:
            log_item.update(heading=f"{len(memories)} entries to memorize.")

        # save chat history
        db = await Memory.get(self.agent)

        memories_txt = ""
        rem = []
        for memory in memories:
            # solution to plain text:
            txt = f"{memory}"
            memories_txt += "\n\n" + txt
            log_item.update(memories=memories_txt.strip())

            # remove previous fragments too similiar to this one
            if self.REPLACE_THRESHOLD > 0:
                rem += await db.delete_documents_by_query(
                    query=txt,
                    threshold=self.REPLACE_THRESHOLD,
                    filter=f"area=='{Memory.Area.FRAGMENTS.value}'",
                )
                if rem:
                    rem_txt = "\n\n".join(Memory.format_docs_plain(rem))
                    log_item.update(replaced=rem_txt)

            # insert new solution
            await db.insert_text(text=txt, metadata={"area": Memory.Area.FRAGMENTS.value})

        log_item.update(
            result=f"{len(memories)} entries memorized.",
            heading=f"{len(memories)} entries memorized.",
        )
        if rem:
            log_item.stream(result=f"\nReplaced {len(rem)} previous memories.")

    # except Exception as e:
    #     err = errors.format_error(e)
    #     self.agent.context.log.log(
    #         type="error", heading="Memorize memories extension error:", content=err
    #     )
