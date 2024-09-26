from agent import Agent
from python.helpers.extension import Extension
import python.helpers.files as files
from python.helpers.vector_db import Area
import json
from python.helpers.dirty_json import DirtyJson
from python.helpers import errors
from python.tools.memory_tool import get_db

class MemorizeSolutions(Extension):

    async def execute(self, loop_data={}, **kwargs):
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
            vdb = get_db(self.agent)

            solutions_txt = ""
            for solution in solutions:
                # solution to plain text:
                txt = f"# Problem\n {solution['problem']}\n# Solution\n {solution['solution']}"
                solutions_txt += txt + "\n\n"
                vdb.insert_text(
                    text=txt, metadata={"area": Area.SOLUTIONS.value}
                )

            solutions_txt = solutions_txt.strip()
            log_item.update(solutions=solutions_txt)
            log_item.update(
                result=f"{len(solutions)} solutions memorized.",
                heading=f"{len(solutions)} solutions memorized.",
            )

        # except Exception as e:
        #     err = errors.format_error(e)
        #     self.agent.context.log.log(
        #         type="error", heading="Memorize solutions extension error:", content=err
        #     )
