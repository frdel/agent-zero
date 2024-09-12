from typing import Any, List
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import asyncio

class EmbeddingMemory:
    def __init__(self, embedding_model):
        self.embedding_model = embedding_model
        self.memories = []
        self.embeddings = []

    async def store(self, text: str, data: Any):
        embedding = await self._embed(text)
        self.memories.append((text, data))
        self.embeddings.append(embedding)

    async def get_relevant_context(self, query: str, top_k: int = 3) -> List[Any]:
        if not self.embeddings:
            return []  # Return an empty list if there are no stored embeddings

        query_embedding = await self._embed(query)
        
        # Ensure embeddings is a 2D array
        embeddings_array = np.array(self.embeddings)
        if embeddings_array.ndim == 1:
            embeddings_array = embeddings_array.reshape(1, -1)

        similarities = cosine_similarity([query_embedding], embeddings_array)[0]
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        return [self.memories[i][1] for i in top_indices]

    async def _embed(self, text: str) -> List[float]:
        # Use the model synchronously within an asyncio thread
        return await asyncio.to_thread(self.embedding_model.embed_query, text)