from agent import Agent
from tools.helpers.vector_db import VectorDB, Document
from tools.helpers import files
import os, json

db: VectorDB
result_count = 3

def initialize(embeddings_model,messages_returned=3, subdir=""):
    global db, result_count
    dir = os.path.join("memory",subdir)
    db = VectorDB(embeddings_model=embeddings_model, in_memory=False, cache_dir=dir)
    result_count = messages_returned

def execute(agent:Agent, message: str, action: str = "load", **kwargs):
    if action.strip().lower() == "save":
        id = db.insert_document(message)
        return files.read_file("./prompts/fw.memory_saved.md")

    elif action.strip().lower() == "delete":
        deleted = db.delete_documents(message)
        return files.read_file("./prompts/fw.memories_deleted.md", count=deleted)

    else:
        results=[]
        docs = db.search_max_rel(message,result_count)
        if len(docs)==0: return files.read_file("./prompts/fw.memories_not_found.md", query=message)
        for doc in docs:
            results.append({ "meta": doc.metadata, "content": doc.page_content })
        return json.dumps(results)
            

