from agent import Agent
from python.helpers.extension import Extension
from python.helpers.files import read_file
from python.helpers.vector_db import get_or_create
import json
from python.helpers.dirty_json import DirtyJson
from python.helpers import errors


class MemorizeSolutions(Extension):

    async def execute(self, loop_data={}, **kwargs):
        try:
            self.agent.context.log.log(
                type="info", content="Memorizing succesful solutions...", temp=True
            )

            # get system message and chat history for util llm
            system = self.agent.read_prompt("memory.solutions_sum.sys.md")
            msgs_text = self.agent.concat_messages(self.agent.history)

            # call util llm to find solutions in history
            solutions_json = await self.agent.call_utility_llm(
                system=system,
                msg=msgs_text,
                log_type="util",
            )

            solutions = DirtyJson.parse_string(solutions_json)

            if not isinstance(solutions, list) or len(solutions) == 0:
                self.agent.context.log.log(
                    type="info", content="No succesful solutions found.", temp=False
                )
                return
            else:
                self.agent.context.log.log(
                    type="info",
                    content=f"{len(solutions)} succesful solutions found.",
                    temp=True,
                )

            # save chat history
            vdb = get_or_create(
                logger=self.agent.context.log,
                embeddings_model=self.agent.config.embeddings_model,
                memory_dir="./memory/solutions",
                knowledge_dir="",
            )

            for solution in solutions:
                # solution to plain text:
                txt = (
                    f"Problem: {solution['problem']}\nSolution: {solution['solution']}"
                )
                vdb.insert_text(
                    text=txt,
                )  # metadata={"full": msgs_text})

            self.agent.context.log.log(
                type="info",
                content=f"{len(solutions)} solutions memorized.",
                temp=False,
            )

        except Exception as e:
            err = errors.format_error(e)
            self.agent.context.log.log(
                type="error", heading="Memorize solutions extension error:", content=err
            )
