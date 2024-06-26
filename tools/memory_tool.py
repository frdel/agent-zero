from agent import Agent
from tools.helpers.vector_db import VectorDB, Document
from tools.helpers import files
import os, json
from tools.helpers.tool import Tool, Response
from tools.helpers.print_style import PrintStyle

db: VectorDB | None = None

class Memory(Tool):
    def execute(self,**kwargs):
        #TODO separate param for memory tool result count
        result = process_query(self.agent, self.args["memory"],self.args["action"], result_count=self.agent.auto_memory_count)
        return Response(message="\n\n".join(result), break_loop=False)
            

def initialize(embeddings_model, subdir=""):
    global db
    dir = os.path.join("memory",subdir)
    db = VectorDB(embeddings_model=embeddings_model, in_memory=False, cache_dir=dir)


def process_query(agent:Agent, message: str, action: str = "load", result_count: int = 3, **kwargs):
    if not db: initialize(agent.embeddings_model, subdir=agent.memory_subdir)
    
    if action.strip().lower() == "save":
        id = db.insert_document(str(message)) # type: ignore
        return files.read_file("./prompts/fw.memory_saved.md")

    elif action.strip().lower() == "delete":
        deleted = db.delete_documents(message) # type: ignore
        return files.read_file("./prompts/fw.memories_deleted.md", count=deleted)

    else:
        results=[]
        docs = db.search_max_rel(message,result_count) # type: ignore
        if len(docs)==0: return files.read_file("./prompts/fw.memories_not_found.md", query=message)
        for doc in docs:
            results.append(doc.page_content)
        return results
        # return "\n\n".join(results)
            

