from agent import Agent
from tools.helpers.vector_db import VectorDB, Document
from tools.helpers import files
import os, json
from tools.helpers.tool import Tool, Response
from tools.helpers.print_style import PrintStyle

db: VectorDB
result_count = 3 #TODO parametrize better


class Memory(Tool):
    def execute(self):
        result = process_query(self.agent, self.args["memory"],self.args["action"])
        return Response(message=result, break_loop=False)
            

def initialize(embeddings_model,messages_returned=3, subdir=""):
    global db, result_count
    dir = os.path.join("memory",subdir)
    db = VectorDB(embeddings_model=embeddings_model, in_memory=False, cache_dir=dir)
    result_count = messages_returned


def process_query(agent:Agent, message: str, action: str = "load", **kwargs):
    if action.strip().lower() == "save":
        id = db.insert_document(str(message))
        return files.read_file("./prompts/fw.memory_saved.md")

    elif action.strip().lower() == "delete":
        deleted = db.delete_documents(message)
        return files.read_file("./prompts/fw.memories_deleted.md", count=deleted)

    else:
        results=[]
        docs = db.search_max_rel(message,result_count)
        if len(docs)==0: return files.read_file("./prompts/fw.memories_not_found.md", query=message)
        for doc in docs:
            results.append(doc.page_content)
        return "\n\n".join(results)
            

