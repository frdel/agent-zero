import asyncio
from helpers import errors, plugins
from helpers.extension import Extension
from helpers.dirty_json import DirtyJson
from agent import LoopData
from helpers.log import LogItem
from helpers.defer import DeferredTask, THREAD_BACKGROUND

# Direct import - this extension lives inside the memory plugin
from plugins._memory.helpers.memory import Memory
from plugins._memory.helpers.memory_quality import filter_auto_memory_fragments
from plugins._memory.tools.memory import DEFAULT_THRESHOLD as DEFAULT_MEMORY_THRESHOLD


class MemorizeMemories(Extension):

    def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        # try:
        if not self.agent:
            return

        set = plugins.get_plugin_config("_memory", self.agent)
        if not set:
            return None

        if not set["memory_memorize_enabled"]:
            return

        # show full util message
        log_item = self.agent.context.log.log(
            type="util",
            heading="Memorizing new information...",
        )

        # memorize in background
        task = DeferredTask(thread_name=THREAD_BACKGROUND)
        task.start_task(self.memorize, loop_data, log_item)
        # task = asyncio.create_task(self.memorize(loop_data, log_item))

    async def memorize(self, loop_data: LoopData, log_item: LogItem, **kwargs):
        if not self.agent:
            return

        try:
            set = plugins.get_plugin_config("_memory", self.agent)
            if not set:
                return None

            db = await Memory.get(self.agent)

            # get system message and chat history for util llm
            system = self.agent.read_prompt("memory.memories_sum.sys.md")
            msgs_text = self.agent.concat_messages(self.agent.history)
            # Keep only recent context to avoid utility-model context-window overflow.
            MAX_MSGS_CHARS = 80000
            if len(msgs_text) > MAX_MSGS_CHARS:
                msgs_text = msgs_text[-MAX_MSGS_CHARS:]

            # # log query streamed by LLM
            # async def log_callback(content):
            #     log_item.stream(content=content)

            # call util llm to find info in history
            memories_json = await self.agent.call_utility_model(
                system=system,
                message=msgs_text,
                # callback=log_callback,
                background=True,
            )

            # log data < no need for streaming utility messages
            log_item.update(content=memories_json)

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

            raw_memories_count = len(memories)
            memories = filter_auto_memory_fragments(memories)
            filtered_memories_count = raw_memories_count - len(memories)

            if not memories:
                log_item.update(
                    heading="No durable information to memorize.",
                    filtered_memories_count=filtered_memories_count,
                )
                return

            memories_txt = "\n\n".join(memories).strip()
            log_item.update(
                heading=f"{len(memories)} durable entries to memorize.",
                memories=memories_txt,
                filtered_memories_count=filtered_memories_count,
            )

            # Process memories with intelligent consolidation
            total_processed = 0
            total_consolidated = 0
            rem = []

            for memory in memories:
                # Convert memory to plain text
                txt = f"{memory}"

                if set["memory_memorize_consolidation"]:
                    
                    try:
                        # Use intelligent consolidation system
                        from plugins._memory.helpers.memory_consolidation import create_memory_consolidator
                        consolidator = create_memory_consolidator(
                            self.agent,
                            similarity_threshold=DEFAULT_MEMORY_THRESHOLD,  # More permissive for discovery
                            max_similar_memories=8,
                            max_llm_context_memories=4
                        )

                        # Create memory item-specific log for detailed tracking
                        memory_log = None # too many utility messages, skip log for now
                        # memory_log = self.agent.context.log.log(
                        #     type="util",
                        #     heading=f"Processing memory fragment: {txt[:50]}...",
                        #     update_progress="none"  # Don't affect status bar
                        # )

                        # Process with intelligent consolidation
                        result_obj = await consolidator.process_new_memory(
                            new_memory=txt,
                            area=Memory.Area.FRAGMENTS.value,
                            metadata={"area": Memory.Area.FRAGMENTS.value},
                            log_item=memory_log
                        )

                        # Update the individual log item with completion status but keep it temporary
                        if result_obj.get("success"):
                            total_consolidated += 1
                            if memory_log:
                                memory_log.update(
                                    result="Fragment processed successfully",
                                    heading=f"Memory fragment completed: {txt[:50]}...",
                                    update_progress="none"  # Show briefly then disappear
                                )
                        else:
                            if memory_log:
                                memory_log.update(
                                    result="Fragment processing failed",
                                    heading=f"Memory fragment failed: {txt[:50]}...",
                                    update_progress="none"  # Show briefly then disappear
                                )
                        total_processed += 1

                    except Exception as e:
                        # Log error but continue processing
                        log_item.update(consolidation_error=str(e))
                        total_processed += 1

                    # Update final results with structured logging
                    log_item.update(
                        heading=f"Memorization completed: {total_processed} memories processed, {total_consolidated} intelligently consolidated",
                        memories=memories_txt,
                        result=f"{total_processed} memories processed, {total_consolidated} intelligently consolidated",
                        memories_processed=total_processed,
                        memories_consolidated=total_consolidated,
                        update_progress="none"
                    )

                else:

                    # remove previous fragments too similiar to this one
                    if set["memory_memorize_replace_threshold"] > 0:
                        rem += await db.delete_documents_by_query(
                            query=txt,
                            threshold=set["memory_memorize_replace_threshold"],
                            filter=f"area=='{Memory.Area.FRAGMENTS.value}'",
                        )
                        if rem:
                            rem_txt = "\n\n".join(Memory.format_docs_plain(rem))
                            log_item.update(replaced=rem_txt)

                    # insert new memory
                    await db.insert_text(text=txt, metadata={"area": Memory.Area.FRAGMENTS.value})

                    log_item.update(
                        result=f"{len(memories)} entries memorized.",
                        heading=f"{len(memories)} entries memorized.",
                    )
                    if rem:
                        log_item.stream(result=f"\nReplaced {len(rem)} previous memories.")
                


        except Exception as e:
            err = errors.format_error(e)
            self.agent.context.log.log(
                type="warning", heading="Memorize memories extension error", content=err
            )
