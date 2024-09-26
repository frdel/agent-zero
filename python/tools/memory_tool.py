import re
from agent import Agent
from python.helpers.vector_db import get_or_create_db
import os
from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle
from python.helpers.errors import handle_error
from python.helpers import files

class Memory(Tool):
    async def execute(self,**kwargs):
        result=""

        area = kwargs.get("area", "manual") # when called by agent, it will always be manual
    
        try:
            if "query" in kwargs:
                threshold = float(kwargs.get("threshold", 0.1))
                count = int(kwargs.get("count", 5))
                result = search(self.agent, kwargs["query"], count, threshold)
            elif "memorize" in kwargs:
                result = save(self.agent, kwargs["memorize"])
            elif "forget" in kwargs:
                result = forget(self.agent, kwargs["forget"])
            # elif "delete" in kwargs
                result = delete(self.agent, kwargs["delete"])
        except Exception as e:
            handle_error(e)
            # hint about embedding change with existing database
            PrintStyle.hint("If you changed your embedding model, you will need to remove contents of /memory directory.")
            self.agent.context.log.log(type="hint", content="If you changed your embedding model, you will need to remove contents of /memory directory.")
            raise   
        
        # result = process_query(self.agent, self.args["memory"],self.args["action"], result_count=self.agent.config.auto_memory_count)
        return Response(message=result, break_loop=False)
            
def search(agent:Agent, query:str, count:int=5, threshold:float=0.1):
    db = get_db(agent)
    # docs = db.search_similarity(query,count) # type: ignore
    docs = db.search_similarity_threshold(query,count,threshold) # type: ignore
    if len(docs)==0: return agent.read_prompt("fw.memories_not_found.md", query=query)
    else: return str(docs)

def save(agent:Agent, text:str):
    db = get_db(agent)
    id = db.insert_text(text) # type: ignore
    return agent.read_prompt("fw.memory_saved.md", memory_id=id)

def delete(agent:Agent, ids_str:str):
    db = get_db(agent)
    ids = extract_guids(ids_str)
    deleted = db.delete_documents_by_ids(ids) # type: ignore
    return agent.read_prompt("fw.memories_deleted.md", memory_count=deleted)    

def forget(agent:Agent, query:str):
    db = get_db(agent)
    deleted = db.delete_documents_by_query(query) # type: ignore
    return agent.read_prompt("fw.memories_deleted.md", memory_count=deleted)

def get_db(agent: Agent):
    mem_dir = files.get_abs_path("memory", agent.config.memory_subdir or "default")
    kn_dirs = [files.get_abs_path("knowledge", d) for d in agent.config.knowledge_subdirs or []]

    db = get_or_create_db(
        agent.context.log,
        embeddings_model=agent.config.embeddings_model, 
        in_memory=False, 
        memory_dir=mem_dir,
        knowledge_dirs=kn_dirs)    

    return db
        
def extract_guids(text):
    pattern = r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b'
    return re.findall(pattern, text)