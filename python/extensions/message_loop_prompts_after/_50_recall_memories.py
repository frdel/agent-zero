import asyncio
from python.helpers.extension import Extension
from python.helpers.memory import Memory
from agent import LoopData
from python.tools.memory_load import DEFAULT_THRESHOLD as DEFAULT_MEMORY_THRESHOLD
from python.helpers import dirty_json, errors, settings, log 


DATA_NAME_TASK = "_recall_memories_task"
DATA_NAME_ITER = "_recall_memories_iter"


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

        # turned off in settings?
        if not set["memory_recall_enabled"]:
            return

        # every X iterations (or the first one) recall memories
        if loop_data.iteration % set["memory_recall_interval"] == 0:

            # show util message right away
            log_item = self.agent.context.log.log(
                type="util",
                heading="Searching memories...",
            )

            task = asyncio.create_task(
                self.search_memories(loop_data=loop_data, log_item=log_item, **kwargs)
            )
        else:
            task = None

        # set to agent to be able to wait for it
        self.agent.set_data(DATA_NAME_TASK, task)
        self.agent.set_data(DATA_NAME_ITER, loop_data.iteration)

    async def search_memories(self, log_item: log.LogItem, loop_data: LoopData, **kwargs):

        # cleanup
        extras = loop_data.extras_persistent
        if "memories" in extras:
            del extras["memories"]
        if "solutions" in extras:
            del extras["solutions"]
        if "graph_knowledge" in extras:
            del extras["graph_knowledge"]


        set = settings.get_settings()
        # try:

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

        # if there is no query (or just dash by the LLM), do not continue
        if not query or len(query) <= 3:
            log_item.update(
                query="No relevant memory query generated, skipping search",
            )
            return

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

        # Query GraphRAG knowledge graph for additional insights
        # Query both the memory areas and main area for comprehensive results
        memory_context = {
            'memories': memories_txt if memories_txt else None,
            'solutions': solutions_txt if solutions_txt else None,
            'original_query': query
        }

        # Determine which areas to query based on what memories were found
        areas_to_query = ["main"]  # Always query main
        if memories_txt:
            areas_to_query.extend(["main", "fragments"])  # Main and fragments for general memories
        if solutions_txt:
            areas_to_query.append("solutions")  # Solutions area

        # Remove duplicates while preserving order
        areas_to_query = list(dict.fromkeys(areas_to_query))

        # Query GraphRAG only if enabled
        graph_knowledge_txt = ""
        try:
            set = settings.get_settings()
            if set.get("use_graphrag", True):
                # Enhanced query with memory context if available
                if memory_context and (memory_context.get('memories') or memory_context.get('solutions')):
                    context_info = []

                    if memory_context.get('memories'):
                        context_info.append(f"Related memories found:\n{memory_context['memories'][:500]}...")

                    if memory_context.get('solutions'):
                        context_info.append(f"Related solutions found:\n{memory_context['solutions'][:500]}...")

                    # Create context-enhanced query
                    enhanced_query = f"""Based on the following memory context, provide additional insights from the knowledge graph:

{chr(10).join(context_info)}

Original question: {query}

Focus on entities, relationships, or knowledge that complements the above memories and solutions."""

                    # Try the context-enhanced query first
                    try:
                        from python.helpers.graphrag_helper import GraphRAGHelper
                        helper = GraphRAGHelper.get_default()
                        result = helper.query_with_memory_context(enhanced_query, memory_context)
                        if result and "No relevant information" not in result:
                            log_item.update(graph_knowledge=result)
                            graph_knowledge_txt = result
                    except Exception:
                        pass  # Fall back to standard queries

                # Fallback to multiple query formulations for better coverage if no context result
                if not graph_knowledge_txt:
                    queries_to_try = [
                        query,  # Original query
                        f"What do you know about {query}?",  # More direct
                        f"Tell me about entities related to: {query}",  # Entity-focused
                    ]

                    results = []
                    for q in queries_to_try[:2]:  # Limit to 2 queries to avoid too much processing
                        try:
                            from python.helpers.graphrag_helper import GraphRAGHelper
                            helper = GraphRAGHelper.get_default()
                            result = helper.query(q)
                            if result and "No relevant information" not in result:
                                results.append(result)
                        except Exception:
                            continue

                    if results:
                        graph_knowledge_txt = "\n\n".join(results)
                        log_item.update(graph_knowledge=graph_knowledge_txt)
                    else:
                        # Final fallback to multi-area query
                        graph_knowledge_txt = await self._query_graphrag_multi_area(query, areas_to_query, log_item, memory_context)
                else:
                    # Also try multi-area query to get comprehensive results
                    multi_area_result = await self._query_graphrag_multi_area(query, areas_to_query, log_item, memory_context)
                    if multi_area_result and multi_area_result != graph_knowledge_txt:
                        graph_knowledge_txt = f"{graph_knowledge_txt}\n\n{multi_area_result}"
        except Exception:
            # GraphRAG failure shouldn't break memory recall
            pass

        # place to prompt
        if memories_txt:
            extras["memories"] = self.agent.parse_prompt(
                "agent.system.memories.md", memories=memories_txt
            )
        if solutions_txt:
            extras["solutions"] = self.agent.parse_prompt(
                "agent.system.solutions.md", solutions=solutions_txt
            )
        if graph_knowledge_txt:
            extras["graph_knowledge"] = self.agent.parse_prompt(
                "agent.system.graph_knowledge.md", graph_knowledge=graph_knowledge_txt
            )

    async def _query_graphrag_multi_area(self, query: str, areas: list[str], log_item, memory_context: dict = None) -> str:
        """Query multiple GraphRAG knowledge graph areas for comprehensive insights."""
        try:
            from python.helpers.graphrag_helper import GraphRAGHelper

            # Query multiple areas and combine results
            results = GraphRAGHelper.query_multi_area(query, areas, memory_context)

            if results:
                # Format results from multiple areas
                formatted_result = GraphRAGHelper.format_multi_area_results(results)
                log_item.update(graph_knowledge=formatted_result)
                return formatted_result
            else:
                return ""

        except Exception as e:
            # GraphRAG query failure shouldn't break memory recall
            return ""

    async def _query_graphrag(self, query: str, log_item, memory_context: dict = None) -> str:
        """Query GraphRAG knowledge graph for additional insights with memory context (legacy method)."""
        # Fallback to multi-area query with main area only for compatibility
        return await self._query_graphrag_multi_area(query, ["main"], log_item, memory_context)
