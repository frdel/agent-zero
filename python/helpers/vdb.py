from langchain.storage import InMemoryByteStore, LocalFileStore
from langchain.embeddings import CacheBackedEmbeddings
from langchain_core.embeddings import Embeddings

from langchain_chroma import Chroma
import chromadb
from chromadb.config import Settings

from . import files
from langchain_core.documents import Document
import uuid


class VectorDB:

    def __init__(self, embeddings_model:Embeddings, in_memory=False, cache_dir="./cache"):
        print("Initializing VectorDB...")
        self.embeddings_model = embeddings_model

        db_cache = files.get_abs_path(cache_dir,"database")

        self.client =chromadb.PersistentClient(path=db_cache)
        self.collection = self.client.create_collection("my_collection")
        self.collection

        
    def search(self, query:str, results=2):
        emb = self.embeddings_model.embed_query(query)
        res = self.collection.query(query_embeddings=[emb],n_results=results)
        best = res["documents"][0][0] # type: ignore
        
    # def delete_documents(self, query):
    #     score_limit = 1
    #     k = 2
    #     tot = 0
    #     while True:
    #         # Perform similarity search with score
    #         docs = self.db.similarity_search_with_score(query, k=k)

    #         # Extract document IDs and filter based on score
    #         document_ids = [result[0].metadata["id"] for result in docs if result[1] < score_limit]

    #         # Delete documents with IDs over the threshold score
    #         if document_ids:
    #             fnd = self.db.get(where={"id": {"$in": document_ids}})
    #             if fnd["ids"]: self.db.delete(ids=fnd["ids"])
    #             tot += len(fnd["ids"])
            
    #         # If fewer than K document IDs, break the loop
    #         if len(document_ids) < k:
    #             break
        
    #     return tot

    def insert(self, data:str):
        
        id = str(uuid.uuid4())
        emb = self.embeddings_model.embed_documents([data])[0]

        self.collection.add(
            ids=[id],
            embeddings=[emb],
            documents=[data],
            )

        return id
        


