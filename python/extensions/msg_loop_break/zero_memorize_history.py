from agent import Agent
from python.helpers.extension import Extension
from python.helpers.files import read_file
from python.helpers.vector_db import VectorDB
import json

class MemorizeHistory(Extension):
    
    async def execute(self, **kwargs):
        if self.agent.number != 0: return #only agent 0 will memorize chat history with user
        
        self.agent.context.log.log(type="info", content="Memorizing chat history...", temp=True)

        #get system message and chat history for util llm
        system = self.agent.read_prompt("fw.memory.hist_sum.sys")
        msgs = []
        for msg in self.agent.history:
            content = msg.get("content", "")
            if content:
                msgs.append(content)
        msgs_json = json.dumps(msgs)

        #call util llm to summarize conversation
        summary = await self.agent.call_utility_llm(system=system,msg=msgs_json,output_label="")

        #save chat history
        vdb = VectorDB(
                logger=self.agent.context.log,
                embeddings_model=self.agent.config.embeddings_model,
                memory_dir="./memory/history",
                knowledge_dir=""
                )
        
        self.agent.context.log.log(type="info", content="Chat history memorized.", temp=True)
        