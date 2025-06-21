import asyncio
from python.helpers.extension import Extension
from python.helpers.memory import Memory
from python.helpers.dirty_json import DirtyJson
from agent import LoopData
from python.helpers.log import LogItem


class MemorizeMemories(Extension):

    REPLACE_THRESHOLD = 0.9
    # 优化：增加记忆间隔，减少API调用频率
    MEMORIZE_INTERVAL = 5  # 每5次对话才记忆一次
    MIN_CONVERSATION_LENGTH = 3  # 最少3轮对话才开始记忆

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        # 优化：检查是否需要记忆
        if not self._should_memorize(loop_data):
            return

        # show temp info message
        self.agent.context.log.log(
            type="info", content="Memorizing new information...", temp=True
        )

        # show full util message, this will hide temp message immediately if turned on
        log_item = self.agent.context.log.log(
            type="util",
            heading="Memorizing new information...",
        )

        # memorize in background
        asyncio.create_task(self.memorize(loop_data, log_item))

    def _should_memorize(self, loop_data: LoopData) -> bool:
        """检查是否应该进行记忆操作"""
        # 检查对话长度
        if len(self.agent.history.current.messages) < self.MIN_CONVERSATION_LENGTH:
            return False

        # 检查记忆间隔
        memorize_count = getattr(self.agent, '_memorize_count', 0)
        if memorize_count % self.MEMORIZE_INTERVAL != 0:
            self.agent._memorize_count = memorize_count + 1
            return False

        self.agent._memorize_count = memorize_count + 1
        return True

    async def memorize(self, loop_data: LoopData, log_item: LogItem, **kwargs):

        # 优化：限制历史长度，减少token使用
        max_history_tokens = 4000  # 限制历史记录的token数量
        msgs_text = self._get_limited_history(max_history_tokens)

        # 如果历史太短，跳过记忆
        if len(msgs_text.strip()) < 100:
            log_item.update(heading="History too short, skipping memorization.")
            return

        # get system message and chat history for util llm
        system = self.agent.read_prompt("memory.memories_sum.sys.md")

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

    def _get_limited_history(self, max_tokens: int) -> str:
        """获取限制长度的历史记录"""
        from python.helpers import tokens

        full_history = self.agent.concat_messages(self.agent.history)

        # 如果历史记录不超过限制，直接返回
        if tokens.approximate_tokens(full_history) <= max_tokens:
            return full_history

        # 否则截取最近的对话
        return tokens.trim_to_tokens(full_history, max_tokens, "end")

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
