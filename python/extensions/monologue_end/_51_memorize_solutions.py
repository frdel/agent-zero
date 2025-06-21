import asyncio
from python.helpers.extension import Extension
from python.helpers.memory import Memory
from python.helpers.dirty_json import DirtyJson
from agent import LoopData
from python.helpers.log import LogItem


class MemorizeSolutions(Extension):

    REPLACE_THRESHOLD = 0.9
    # 优化：增加解决方案记忆间隔
    MEMORIZE_INTERVAL = 3  # 每3次对话才记忆一次解决方案
    MIN_CONVERSATION_LENGTH = 4  # 最少4轮对话才开始记忆解决方案

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        # 优化：检查是否需要记忆解决方案
        if not self._should_memorize_solutions(loop_data):
            return

        # show temp info message
        self.agent.context.log.log(
            type="info", content="Memorizing succesful solutions...", temp=True
        )

        # show full util message, this will hide temp message immediately if turned on
        log_item = self.agent.context.log.log(
            type="util",
            heading="Memorizing succesful solutions...",
        )

        # memorize in background
        asyncio.create_task(self.memorize(loop_data, log_item))

    def _should_memorize_solutions(self, loop_data: LoopData) -> bool:
        """检查是否应该记忆解决方案"""
        # 检查对话长度
        if len(self.agent.history.current.messages) < self.MIN_CONVERSATION_LENGTH:
            return False

        # 检查是否包含成功的解决方案标识
        recent_messages = self.agent.history.current.messages[-3:]  # 检查最近3条消息
        has_solution_indicators = any(
            any(keyword in str(msg.content).lower() for keyword in
                ['solved', 'success', 'completed', 'fixed', 'resolved', 'done'])
            for msg in recent_messages
        )

        if not has_solution_indicators:
            return False

        # 检查记忆间隔
        solution_count = getattr(self.agent, '_solution_memorize_count', 0)
        if solution_count % self.MEMORIZE_INTERVAL != 0:
            self.agent._solution_memorize_count = solution_count + 1
            return False

        self.agent._solution_memorize_count = solution_count + 1
        return True

    async def memorize(self, loop_data: LoopData, log_item: LogItem, **kwargs):
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
            log_item.update(
                heading=f"{len(solutions)} successful solutions to memorize."
            )

        # save chat history
        db = await Memory.get(self.agent)

        solutions_txt = ""
        rem = []
        for solution in solutions:
            # solution to plain text:
            if isinstance(solution, dict):
                problem = solution.get('problem', 'Unknown problem')
                solution_text = solution.get('solution', 'Unknown solution')
                txt = f"# Problem\n {problem}\n# Solution\n {solution_text}"
            else:
                # If solution is not a dict, convert it to string
                txt = f"# Solution\n {str(solution)}"
            solutions_txt += txt + "\n\n"

            # remove previous solutions too similiar to this one
            if self.REPLACE_THRESHOLD > 0:
                rem += await db.delete_documents_by_query(
                    query=txt,
                    threshold=self.REPLACE_THRESHOLD,
                    filter=f"area=='{Memory.Area.SOLUTIONS.value}'",
                )
                if rem:
                    rem_txt = "\n\n".join(Memory.format_docs_plain(rem))
                    log_item.update(replaced=rem_txt)

            # insert new solution
            await db.insert_text(text=txt, metadata={"area": Memory.Area.SOLUTIONS.value})

        solutions_txt = solutions_txt.strip()
        log_item.update(solutions=solutions_txt)
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
