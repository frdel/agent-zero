import re
from agent import Agent
from python.helpers.vector_db import VectorDB, Document
from python.helpers import files
import os, json
from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle
from chromadb.errors import InvalidDimensionException

# TODO multiple DBs at once
db: VectorDB | None= None

class Memory(Tool):
    def execute(self,**kwargs):
        result=""
        
        try:
            if "query" in kwargs:
                threshold = float(kwargs.get("threshold", 0.1))
                count = int(kwargs.get("count", 5))
                result = search(self.agent, kwargs["query"], count, threshold)
            elif "memorize" in kwargs:
                result = save(self.agent, kwargs["memorize"])
            elif "forget" in kwargs:
                result = forget(self.agent, kwargs["forget"])
            elif "delete" in kwargs:
                result = delete(self.agent, kwargs["delete"])
        except InvalidDimensionException as e:
            # hint about embedding change with existing database
            PrintStyle.hint("If you changed your embedding model, you will need to remove contents of /memory directory.")
            raise   
        
        # result = process_query(self.agent, self.args["memory"],self.args["action"], result_count=self.agent.config.auto_memory_count)
        return Response(message=result, break_loop=False)
            
def search(agent:Agent, query:str, count:int=5, threshold:float=0.1):
    initialize(agent)
    docs = db.search_similarity_threshold(query,count,threshold) # type: ignore
    if len(docs)==0: return files.read_file("./prompts/fw.memories_not_found.md", query=query)
    else: return str(docs)

def save(agent:Agent, text:str):
    initialize(agent)
    id = db.insert_document(text) # type: ignore
    return files.read_file("./prompts/fw.memory_saved.md", memory_id=id)

def delete(agent:Agent, ids_str:str):
    initialize(agent)
    ids = extract_guids(ids_str)
    deleted = db.delete_documents_by_ids(ids) # type: ignore
    return files.read_file("./prompts/fw.memories_deleted.md", memory_count=deleted)    

def forget(agent:Agent, query:str):
    initialize(agent)
    deleted = db.delete_documents_by_query(query) # type: ignore
    return files.read_file("./prompts/fw.memories_deleted.md", memory_count=deleted)

def initialize(agent:Agent):
    global db
    if not db:
        dir = os.path.join("memory",agent.config.memory_subdir)
        db = VectorDB(embeddings_model=agent.config.embeddings_model, in_memory=False, cache_dir=dir)

def extract_guids(text):
    pattern = r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b'
    return re.findall(pattern, text)