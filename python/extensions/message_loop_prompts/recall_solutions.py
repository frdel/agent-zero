from agent import Agent
from python.helpers.extension import Extension
from python.helpers.files import read_file
from python.helpers.vector_db import get_or_create
import json


class RecallSolutions(Extension):

    INTERVAL = 3
    HISTORY = 5
    RESULTS = 3
    THRESHOLD = 0.1

    async def execute(self, loop_data={}, **kwargs):

        iter = loop_data.get("iteration", 0)
        if iter % RecallSolutions.INTERVAL == 0:  # every 3 iterations (or the first one) recall solution memories
            await self.search_solutions(loop_data=loop_data, **kwargs)


    async def search_solutions(self, loop_data={}, **kwargs):
        self.agent.context.log.log(
            type="info", content="Searching memory for solutions...", temp=False
        )

        # get system message and chat history for util llm
        msgs_text = self.agent.concat_messages(
            self.agent.history[-RecallSolutions.HISTORY:]
        )  # only last X messages
        system = self.agent.read_prompt(
            "memory.solutions_query.sys.md", history=msgs_text
        )

        # call util llm to summarize conversation
        query = await self.agent.call_utility_llm(
            system=system, msg=loop_data["message"]
        )

        # get solutions database
        vdb = get_or_create(
            logger=self.agent.context.log,
            embeddings_model=self.agent.config.embeddings_model,
            memory_dir="./memory/solutions",
            knowledge_dir="",
        )

        solutions = vdb.search_similarity_threshold(
            query=query, results=RecallSolutions.RESULTS, threshold=RecallSolutions.THRESHOLD
        )

        if not isinstance(solutions, list) or len(solutions) == 0:
            self.agent.context.log.log(
                type="info", content="No successful solution memories found.", temp=False
            )
            return
        else:
            self.agent.context.log.log(
                type="info",
                content=f"{len(solutions)} successful solution memories found.",
                temp=False,
            )

       # concatenate solution.page_content in solutions:
        solutions_text = ""
        for solution in solutions:
            solutions_text += solution.page_content + "\n\n"

        # place to prompt
        solutions_prompt = self.agent.read_prompt("agent.system.solutions.md", solutions=solutions_text)

        # append to system message
        loop_data["system"] += solutions_prompt
