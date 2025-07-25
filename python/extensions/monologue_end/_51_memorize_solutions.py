import asyncio
from python.helpers import settings
from python.helpers.extension import Extension
from python.helpers.memory import Memory
from python.helpers.dirty_json import DirtyJson
from agent import LoopData
from python.helpers.log import LogItem
from python.tools.memory_load import DEFAULT_THRESHOLD as DEFAULT_MEMORY_THRESHOLD


class MemorizeSolutions(Extension):

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        # try:

        set = settings.get_settings()

        if not set["memory_memorize_enabled"]:
            return
 
        # show full util message
        log_item = self.agent.context.log.log(
            type="util",
            heading="Memorizing succesful solutions...",
        )

        # memorize in background
        task = asyncio.create_task(self.memorize(loop_data, log_item))
        return task

    async def memorize(self, loop_data: LoopData, log_item: LogItem, **kwargs):

        set = settings.get_settings()

        db = await Memory.get(self.agent)

        # get system message and chat history for util llm
        system = self.agent.read_prompt("memory.solutions_sum.sys.md")
        msgs_text = self.agent.concat_messages(self.agent.history)

        # log query streamed by LLM
        async def log_callback(content):
            log_item.stream(content=content)

        # call util llm to find solutions in history
        solutions_json = await self.agent.call_utility_model(
            system=system,
            message=msgs_text,
            callback=log_callback,
            background=True,
        )

        # Add validation and error handling for solutions_json
        if not solutions_json or not isinstance(solutions_json, str):
            log_item.update(heading="No response from utility model.")
            return

        # Strip any whitespace that might cause issues
        solutions_json = solutions_json.strip()

        if not solutions_json:
            log_item.update(heading="Empty response from utility model.")
            return

        try:
            solutions = DirtyJson.parse_string(solutions_json)
        except Exception as e:
            log_item.update(heading=f"Failed to parse solutions response: {str(e)}")
            return

        # Validate that solutions is a list or convertible to one
        if solutions is None:
            log_item.update(heading="No valid solutions found in response.")
            return

        # If solutions is not a list, try to make it one
        if not isinstance(solutions, list):
            if isinstance(solutions, (str, dict)):
                solutions = [solutions]
            else:
                log_item.update(heading="Invalid solutions format received.")
                return

        if not isinstance(solutions, list) or len(solutions) == 0:
            log_item.update(heading="No successful solutions to memorize.")
            return
        else:
            solutions_txt = "\n\n".join([str(solution) for solution in solutions]).strip()
            log_item.update(
                heading=f"{len(solutions)} successful solutions to memorize.", solutions=solutions_txt
            )

        # Process solutions with intelligent consolidation
        total_processed = 0
        total_consolidated = 0
        rem = []

        for solution in solutions:
            # Convert solution to structured text
            if isinstance(solution, dict):
                problem = solution.get('problem', 'Unknown problem')
                solution_text = solution.get('solution', 'Unknown solution')
                txt = f"# Problem\n {problem}\n# Solution\n {solution_text}"
            else:
                # If solution is not a dict, convert it to string
                txt = f"# Solution\n {str(solution)}"

            if set["memory_memorize_consolidation"]:
                try:
                    # Use intelligent consolidation system
                    from python.helpers.memory_consolidation import create_memory_consolidator
                    consolidator = create_memory_consolidator(
                        self.agent,
                        similarity_threshold=DEFAULT_MEMORY_THRESHOLD,  # More permissive for discovery
                        max_similar_memories=6,    # Fewer for solutions (more complex)
                        max_llm_context_memories=3
                    )

                    # Create solution-specific log for detailed tracking
                    solution_log = None # too many utility messages, skip log for now
                    # solution_log = self.agent.context.log.log(
                    #     type="util",
                    #     heading=f"Processing solution: {txt[:50]}...",
                    #     temp=False,
                    #     update_progress="none"  # Don't affect status bar
                    # )

                    # Process with intelligent consolidation
                    result_obj = await consolidator.process_new_memory(
                        new_memory=txt,
                        area=Memory.Area.SOLUTIONS.value,
                        metadata={"area": Memory.Area.SOLUTIONS.value},
                        log_item=solution_log
                    )

                    # Update the individual log item with completion status but keep it temporary
                    if result_obj.get("success"):
                        total_consolidated += 1
                        if solution_log:
                            solution_log.update(
                                result="Solution processed successfully",
                                heading=f"Solution completed: {txt[:50]}...",
                                temp=False,  # Show completion message
                                update_progress="none"  # Show briefly then disappear
                            )
                    else:
                        if solution_log:
                            solution_log.update(
                                result="Solution processing failed",
                                heading=f"Solution failed: {txt[:50]}...",
                                temp=False,  # Show completion message
                                update_progress="none"  # Show briefly then disappear
                            )
                    total_processed += 1

                except Exception as e:
                    # Log error but continue processing
                    log_item.update(consolidation_error=str(e))
                    total_processed += 1

                # Update final results with structured logging
                log_item.update(
                    heading=f"Solution memorization completed: {total_processed} solutions processed, {total_consolidated} intelligently consolidated",
                    solutions=solutions_txt,
                    result=f"{total_processed} solutions processed, {total_consolidated} intelligently consolidated",
                    solutions_processed=total_processed,
                    solutions_consolidated=total_consolidated,
                    update_progress="none"
                )
            else:
                # remove previous solutions too similiar to this one
                if set["memory_memorize_replace_threshold"] > 0:
                    rem += await db.delete_documents_by_query(
                        query=txt,
                        threshold=set["memory_memorize_replace_threshold"],
                        filter=f"area=='{Memory.Area.SOLUTIONS.value}'",
                    )
                    if rem:
                        rem_txt = "\n\n".join(Memory.format_docs_plain(rem))
                        log_item.update(replaced=rem_txt)

                # insert new solution
                await db.insert_text(text=txt, metadata={"area": Memory.Area.SOLUTIONS.value})

                log_item.update(
                    result=f"{len(solutions)} solutions memorized.",
                    heading=f"{len(solutions)} solutions memorized.",
                )
                if rem:
                    log_item.stream(result=f"\nReplaced {len(rem)} previous solutions.")


    # except Exception as e:
    #     err = errors.format_error(e)
    #     self.agent.context.log.log(
    #         type="error", heading="Memorize solutions extension error:", content=err
    #     )
