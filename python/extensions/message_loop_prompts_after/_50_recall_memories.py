import asyncio
from python.helpers.extension import Extension
from python.helpers.memory import Memory
from agent import LoopData

DATA_NAME_TASK = "_recall_memories_task"


class RecallMemories(Extension):

    INTERVAL = 3
    HISTORY = 10000
    RESULTS = 3
    THRESHOLD = 0.6

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):

        # every 3 iterations (or the first one) recall memories
        if loop_data.iteration % RecallMemories.INTERVAL == 0:
            task = asyncio.create_task(
                self.search_memories(loop_data=loop_data, **kwargs)
            )
        else:
            task = None

        # set to agent to be able to wait for it
        self.agent.set_data(DATA_NAME_TASK, task)

    async def search_memories(self, loop_data: LoopData, **kwargs):

        # cleanup
        extras = loop_data.extras_persistent
        if "memories" in extras:
            del extras["memories"]

        # try:
        
        # show full util message
        log_item = self.agent.context.log.log(
            type="util",
            heading="Searching memories...",
        )

        # get system message and chat history for util llm
        # msgs_text = self.agent.concat_messages(
        #     self.agent.history[-RecallMemories.HISTORY :]
        # )  # only last X messages
        msgs_text = self.agent.history.output_text()[-RecallMemories.HISTORY :]
        system = self.agent.read_prompt(
            "memory.memories_query.sys.md", history=msgs_text
        )

        # log query streamed by LLM
        async def log_callback(content):
            log_item.stream(query=content)

        # call util llm to summarize conversation
        query = await self.agent.call_utility_model(
            system=system,
            message=(
                loop_data.user_message.output_text() if loop_data.user_message else "None"
            ),
            callback=log_callback,
        )

        # get solutions database
        db = await Memory.get(self.agent)

        memories = await db.search_similarity_threshold(
            query=query,
            limit=RecallMemories.RESULTS,
            threshold=RecallMemories.THRESHOLD,
            filter=f"area == '{Memory.Area.MAIN.value}' or area == '{Memory.Area.FRAGMENTS.value}'",  # exclude solutions
        )

        # log the short result
        if not isinstance(memories, list) or len(memories) == 0:
            log_item.update(
                heading="No useful memories found",
            )
            return
        else:
            log_item.update(
                heading=f"{len(memories)} memories found",
            )

        # concatenate memory.page_content in memories:
        memories_text = ""
        for memory in memories:
            memories_text += memory.page_content + "\n\n"
        memories_text = memories_text.strip()

        # log the full results
        log_item.update(memories=memories_text)

        # place to prompt
        memories_prompt = self.agent.parse_prompt(
            "agent.system.memories.md", memories=memories_text
        )

        # append to prompt
        extras["memories"] = memories_prompt

    # except Exception as e:čč
    #     err = errors.format_error(e)
    #     self.agent.context.log.log(
    #         type="error", heading="Recall memories extension error:", content=err
    #     )
