import asyncio
from python.helpers.extension import Extension
from python.helpers.memory import Memory
from python.helpers.dirty_json import DirtyJson
from agent import LoopData
from python.helpers.log import LogItem


class MemorizeSolutions(Extension):

    REPLACE_THRESHOLD = 0.9

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        # try:

        # show temp info message
        self.agent.context.log.log(
            type="info", content="Memorizing succesful solutions...", temp=True
        )

        # show full util message, this will hide temp message immediately if turned on
        log_item = self.agent.context.log.log(
            type="util",
            heading="Memorizing succesful solutions...",
        )

        #memorize in background
        asyncio.create_task(self.memorize(loop_data, log_item))        

    async def memorize(self, loop_data: LoopData, log_item: LogItem, **kwargs):
        # get system message and chat history for util llm
        system = self.agent.read_prompt("memory.solutions_sum.sys.md")
        msgs_text = self.agent.concat_messages(self.agent.history)

        # log query streamed by LLM
        def log_callback(content):
            log_item.stream(content=content)

        # call util llm to find solutions in history
        solutions_json = await self.agent.call_utility_llm(
            system=system,
            msg=msgs_text,
            callback=log_callback,
        )

        solutions = DirtyJson.parse_string(solutions_json)

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
            txt = f"# Problem\n {solution['problem']}\n# Solution\n {solution['solution']}"
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
            db.insert_text(text=txt, metadata={"area": Memory.Area.SOLUTIONS.value})

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
