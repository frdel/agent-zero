from langchain.storage import InMemoryByteStore, LocalFileStore
from langchain.embeddings import CacheBackedEmbeddings
from langchain_chroma import Chroma
from . import files
from langchain_core.documents import Document
import uuid


class VectorDB:

    def __init__(self, embeddings_model, in_memory=False, cache_dir="./cache"):
        print("Initializing VectorDB...")
        self.embeddings_model = embeddings_model

        em_cache = files.get_abs_path(cache_dir,"embeddings")
        db_cache = files.get_abs_path(cache_dir,"database")
        
        if in_memory:
            self.store = InMemoryByteStore()
        else:
            self.store = LocalFileStore(em_cache)


        #here we setup the embeddings model with the chosen cache storage
        self.embedder = CacheBackedEmbeddings.from_bytes_store(
            embeddings_model, 
            self.store, 
            namespace=getattr(embeddings_model, 'model', getattr(embeddings_model, 'model_name', "default")) )

        self.db = Chroma(embedding_function=self.embedder,persist_directory=db_cache)
        
    def search_similarity(self, query, results=3):
        return self.db.similarity_search(query,results)

    def search_max_rel(self, query, results=3):
        return self.db.max_marginal_relevance_search(query,results)

    def delete_documents(self, query):
        score_limit = 1
        k = 2
        tot = 0
        while True:
            # Perform similarity search with score
            docs = self.db.similarity_search_with_score(query, k=k)

            # Extract document IDs and filter based on score
            document_ids = [result[0].metadata["id"] for result in docs if result[1] < score_limit]

            # Delete documents with IDs over the threshold score
            if document_ids:
                fnd = self.db.get(where={"id": {"$in": document_ids}})
                if fnd["ids"]: self.db.delete(ids=fnd["ids"])
                tot += len(fnd["ids"])
            
            # If fewer than K document IDs, break the loop
            if len(document_ids) < k:
                break
        
        return tot

    def insert_document(self, data):
        id = str(uuid.uuid4())
        self.db.add_documents(documents=[ Document(data, metadata={"id": id}) ])
        return id
        


