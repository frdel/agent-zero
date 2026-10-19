import asyncio
from helpers.extension import Extension
from agent import LoopData
from helpers import cache, dirty_json, errors, log, plugins

# Direct import - this extension lives inside the memory plugin
from plugins._memory.helpers.memory import Memory, get_agent_memory_subdir
from plugins._memory.tools.memory import DEFAULT_THRESHOLD as DEFAULT_MEMORY_THRESHOLD


DATA_NAME_TASK = "_recall_memories_task"
DATA_NAME_ITER = "_recall_memories_iter"
DATA_NAME_LOOP = "_recall_memories_loop"
DATA_NAME_RESULT = "_recall_memories_result"
DATA_NAME_RESULT_SCOPE = "_recall_memories_result_scope"
SEARCH_TIMEOUT = 30


def apply_recall_result(loop_data: LoopData, result: dict | None):
    extras = loop_data.extras_persistent
    extras.pop("memories", None)
    extras.pop("solutions", None)
    if not isinstance(result, dict):
        return
    for key in ("memories", "solutions"):
        if result.get(key):
            extras[key] = result[key]


def get_recall_scope(agent):
    memory_subdir = get_agent_memory_subdir(agent)
    return cache.determine_cache_key(agent, memory_subdir)


class RecallMemories(Extension):

    # INTERVAL = 3
    # HISTORY = 10000
    # MEMORIES_MAX_SEARCH = 12
    # SOLUTIONS_MAX_SEARCH = 8
    # MEMORIES_MAX_RESULT = 5
    # SOLUTIONS_MAX_RESULT = 3
    # THRESHOLD = DEFAULT_MEMORY_THRESHOLD

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        if not self.agent:
            return

        set = plugins.get_plugin_config("_memory", self.agent)
        if not set:
            return None

        # turned off in settings?
        if not set["memory_recall_enabled"]:
            return None

        recall_scope = get_recall_scope(self.agent)
        cached_result = self.agent.get_data(DATA_NAME_RESULT)
        if cached_result is not None:
            if self.agent.get_data(DATA_NAME_RESULT_SCOPE) == recall_scope:
                apply_recall_result(loop_data, cached_result)
            else:
                cached_result = None
            self.agent.set_data(DATA_NAME_RESULT, None)
            self.agent.set_data(DATA_NAME_RESULT_SCOPE, None)

        # every X iterations (or the first one) recall memories
        if loop_data.iteration % set["memory_recall_interval"] != 0:
            return

        previous_task = self.agent.get_data(DATA_NAME_TASK)
        previous_loop = self.agent.get_data(DATA_NAME_LOOP)
        if previous_task and not previous_task.done():
            if previous_loop is loop_data:
                return
            previous_task.cancel()

        if cached_result is None:
            apply_recall_result(loop_data, {})

        # show util message right away
        log_item = self.agent.context.log.log(
            type="util",
            heading="Searching memories...",
        )

        task = asyncio.create_task(
            self.search_and_cache(
                loop_data=loop_data,
                log_item=log_item,
                recall_scope=recall_scope,
                **kwargs,
            )
        )

        # set to agent to be able to wait for it
        self.agent.set_data(DATA_NAME_TASK, task)
        self.agent.set_data(DATA_NAME_ITER, loop_data.iteration)
        self.agent.set_data(DATA_NAME_LOOP, loop_data)

    async def search_and_cache(
        self, log_item: log.LogItem, loop_data: LoopData, recall_scope, **kwargs
    ):
        if not self.agent:
            return {}
        try:
            result = await asyncio.wait_for(
                self.search_memories(
                    loop_data=loop_data,
                    log_item=log_item,
                    memory_subdir=recall_scope[-1],
                    **kwargs,
                ),
                timeout=SEARCH_TIMEOUT,
            )
        except TimeoutError:
            log_item.update(heading="Memory recall timed out")
            result = {}
        except Exception as e:
            self.agent.context.log.log(
                type="warning",
                heading="Memory recall error",
                content=errors.format_error(e),
            )
            result = {}
        if get_recall_scope(self.agent) == recall_scope:
            self.agent.set_data(DATA_NAME_RESULT, result)
            self.agent.set_data(DATA_NAME_RESULT_SCOPE, recall_scope)
        else:
            result = {}
            self.agent.set_data(DATA_NAME_RESULT, None)
            self.agent.set_data(DATA_NAME_RESULT_SCOPE, None)
        return result

    async def search_memories(
        self,
        log_item: log.LogItem,
        loop_data: LoopData,
        memory_subdir: str = "",
        **kwargs,
    ):
        if not self.agent:
            return {}

        set = plugins.get_plugin_config("_memory", self.agent)
        if not set:
            return {}
        # try:

        # get system message and chat history for util llm
        system = self.agent.read_prompt("memory.memories_query.sys.md")

        # # log query streamed by LLM
        # async def log_callback(content):
        #     log_item.stream(query=content)

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
                    # callback=log_callback,
                )
                query = query.strip()
                log_item.update(query=query) # no need for streaming here
            except Exception as e:
                err = errors.format_error(e)
                self.agent.context.log.log(
                    type="warning", heading="Recall memories extension error:", content=err
                )
                query = ""

            # no query, no search
            if not query:
                log_item.update(
                    heading="Failed to generate memory query",
                )
                return {}
        
        # otherwise use the message and history as query
        else:
            query = user_instruction + "\n\n" + history

        # if there is no query (or just dash by the LLM), do not continue
        if not query or len(query) <= 3:
            log_item.update(
                query="No relevant memory query generated, skipping search",
            )
            return {}

        # get memory database
        if memory_subdir and get_agent_memory_subdir(self.agent) != memory_subdir:
            return {}
        db = await Memory.get(self.agent)
        if memory_subdir and db.memory_subdir != memory_subdir:
            return {}

        embedding = await db.embed_query(query)

        # search for general memories and fragments
        memories = await db.search_similarity_threshold(
            query=query,
            limit=set["memory_recall_memories_max_search"],
            threshold=set["memory_recall_similarity_threshold"],
            filter=f"area == '{Memory.Area.MAIN.value}' or area == '{Memory.Area.FRAGMENTS.value}'",  # exclude solutions
            embedding=embedding,
        )

        # search for solutions
        solutions = await db.search_similarity_threshold(
            query=query,
            limit=set["memory_recall_solutions_max_search"],
            threshold=set["memory_recall_similarity_threshold"],
            filter=f"area == '{Memory.Area.SOLUTIONS.value}'",  # exclude solutions
            embedding=embedding,
        )

        if not memories and not solutions:
            log_item.update(
                heading="No memories or solutions found",
            )
            return {}

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
                    type="warning", heading="Failed to filter relevant memories", content=err
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

        result = {}
        if memories_txt:
            result["memories"] = self.agent.parse_prompt(
                "agent.system.memories.md", memories=memories_txt
            )
        if solutions_txt:
            result["solutions"] = self.agent.parse_prompt(
                "agent.system.solutions.md", solutions=solutions_txt
            )
        return result
