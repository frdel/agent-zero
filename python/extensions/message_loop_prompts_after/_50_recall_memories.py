import asyncio
from python.helpers.extension import Extension
from python.helpers.memory import Memory
from agent import LoopData
from python.tools.memory_load import DEFAULT_THRESHOLD as DEFAULT_MEMORY_THRESHOLD
from python.helpers import dirty_json, errors, settings

DATA_NAME_TASK = "_recall_memories_task"


class RecallMemories(Extension):

    # INTERVAL = 3
    # HISTORY = 10000
    # MEMORIES_MAX_SEARCH = 12
    # SOLUTIONS_MAX_SEARCH = 8
    # MEMORIES_MAX_RESULT = 5
    # SOLUTIONS_MAX_RESULT = 3
    # THRESHOLD = DEFAULT_MEMORY_THRESHOLD

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):

        set = settings.get_settings()

        # every 3 iterations (or the first one) recall memories
        if loop_data.iteration % set["memory_recall_interval"] == 0:
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
        if "solutions" in extras:
            del extras["solutions"]


        set = settings.get_settings()
        # try:

        # if recall is disabled, return
        if not set["memory_recall_enabled"]:
            return

        # show full util message
        log_item = self.agent.context.log.log(
            type="util",
            heading="Searching memories...",
        )

        # get system message and chat history for util llm
        system = self.agent.read_prompt("memory.memories_query.sys.md")

        # log query streamed by LLM
        async def log_callback(content):
            log_item.stream(query=content)

        # call util llm to summarize conversation
        user_instruction = (
            loop_data.user_message.output_text() if loop_data.user_message else "None"
        )
        history = self.agent.history.output_text()[-set["memory_recall_history_len"]:]
        message = self.agent.read_prompt(
            "memory.memories_query.msg.md", history=history, message=user_instruction
        )

        # if query preparation by AI is enabled
        if set["memory_recall_query_prep"]:
            try:
                # call util llm to generate search query from the conversation
                query = await self.agent.call_utility_model(
                    system=system,
                    message=message,
                    callback=log_callback,
                )
                query = query.strip()
            except Exception as e:
                err = errors.format_error(e)
                self.agent.context.log.log(
                    type="error", heading="Recall memories extension error:", content=err
                )
                query = ""

            # no query, no search
            if not query:
                log_item.update(
                    heading="Failed to generate memory query",
                )
                return
        
        # otherwise use the message and history as query
        else:
            query = user_instruction + "\n\n" + history

        # get memory database
        db = await Memory.get(self.agent)

        # search for general memories and fragments
        memories = await db.search_similarity_threshold(
            query=query,
            limit=set["memory_recall_memories_max_search"],
            threshold=set["memory_recall_similarity_threshold"],
            filter=f"area == '{Memory.Area.MAIN.value}' or area == '{Memory.Area.FRAGMENTS.value}'",  # exclude solutions
        )

        # search for solutions
        solutions = await db.search_similarity_threshold(
            query=query,
            limit=set["memory_recall_solutions_max_search"],
            threshold=set["memory_recall_similarity_threshold"],
            filter=f"area == '{Memory.Area.SOLUTIONS.value}'",  # exclude solutions
        )

        if not memories and not solutions:
            log_item.update(
                heading="No memories or solutions found",
            )
            return

        # if post filtering is enabled
        if set["memory_recall_post_filter"]:
            # assemble an enumerated dict of memories and solutions for AI validation
            mems_list = {i: memory.page_content for i, memory in enumerate(memories + solutions)}

            # call AI to validate the memories
            try:
                filter = await self.agent.call_utility_model(
                    system=self.agent.read_prompt("memory.memories_filter.sys.md"),
                    message=self.agent.read_prompt(
                        "memory.memories_filter.msg.md",
                        memories=mems_list,
                        history=history,
                        message=user_instruction,
                    ),
                )
                filter_inds = dirty_json.try_parse(filter)

                # filter memories and solutions based on filter_inds
                filtered_memories = []
                filtered_solutions = []
                mem_len = len(memories)

                # process each index in filter_inds
                # make sure filter_inds is a list and contains valid integers
                if isinstance(filter_inds, list):
                    for idx in filter_inds:
                        if isinstance(idx, int):
                            if idx < mem_len:
                                # this is a memory
                                filtered_memories.append(memories[idx])
                            else:
                                # this is a solution, adjust index
                                sol_idx = idx - mem_len
                                if sol_idx < len(solutions):
                                    filtered_solutions.append(solutions[sol_idx])

                # replace original lists with filtered ones
                memories = filtered_memories
                solutions = filtered_solutions

            except Exception as e:
                err = errors.format_error(e)
                self.agent.context.log.log(
                    type="error", heading="Failed to filter relevant memories", content=err
                )
                filter_inds = []


        # limit the number of memories and solutions
        memories = memories[: set["memory_recall_memories_max_result"]]
        solutions = solutions[: set["memory_recall_solutions_max_result"]]

        # log the search result
        log_item.update(
            heading=f"{len(memories)} memories and {len(solutions)} relevant solutions found",
        )

        memories_txt = "\n\n".join([mem.page_content for mem in memories]) if memories else ""
        solutions_txt = "\n\n".join([sol.page_content for sol in solutions]) if solutions else ""

        # log the full results
        if memories_txt:
            log_item.update(memories=memories_txt)
        if solutions_txt:
            log_item.update(solutions=solutions_txt)

        # place to prompt
        if memories_txt:
            extras["memories"] = self.agent.parse_prompt(
                "agent.system.memories.md", memories=memories_txt
            )
        if solutions_txt:
            extras["solutions"] = self.agent.parse_prompt(
                "agent.system.solutions.md", solutions=solutions_txt
            )
