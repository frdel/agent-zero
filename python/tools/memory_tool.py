from agent import Agent
from python.helpers.vector_db import VectorDB, Document
from python.helpers import files
import os, json
from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle

db: VectorDB | None = None

class Memory(Tool):
    def execute(self,**kwargs):
        result=[]
        
        if "query" in kwargs:
            if "threshold" in kwargs: threshold = float(kwargs["threshold"]) 
            else: threshold = 0.1
            result = process_query(self.agent, kwargs["query"], action="load", threshold=threshold, result_count=3)
        elif "memorize" in kwargs:
            result = process_query(self.agent, kwargs["memorize"], action="save")
        elif "forget" in kwargs:
            result = process_query(self.agent, kwargs["forget"], action="delete")

        # result = process_query(self.agent, self.args["memory"],self.args["action"], result_count=self.agent.config.auto_memory_count)
        return Response(message="\n\n".join(result), break_loop=False)
            

def initialize(embeddings_model, subdir=""):
    global db
    dir = os.path.join("memory",subdir)
    db = VectorDB(embeddings_model=embeddings_model, in_memory=False, cache_dir=dir)


def process_query(agent:Agent, message: str, action: str = "load", result_count: int = 3, threshold: float = 0.1, **kwargs):
    if not db: initialize(agent.config.embeddings_model, subdir=agent.config.memory_subdir)
    
    if action.strip().lower() == "save":
        id = db.insert_document(str(message)) # type: ignore
        return [files.read_file("./prompts/fw.memory_saved.md")]

    elif action.strip().lower() == "delete":
        deleted = db.delete_documents(message) # type: ignore
        return [files.read_file("./prompts/fw.memories_deleted.md", count=deleted)]

    else:
        results=[]
        docs = db.search_similarity_threshold(message,result_count,threshold) # type: ignore
        if len(docs)==0: return [files.read_file("./prompts/fw.memories_not_found.md", query=message)]
        for doc in docs:
            results.append(doc.page_content)
        return results
        # return "\n\n".join(results)
            

