from typing import Any, List, Sequence
import uuid
from langchain_community.vectorstores import FAISS
import faiss
from langchain_core.documents import Document
from langchain.storage import InMemoryByteStore
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.vectorstores.utils import (
    DistanceStrategy,
)
from langchain.embeddings import CacheBackedEmbeddings

from agent import Agent


class MyFaiss(FAISS):
    # override aget_by_ids
    def get_by_ids(self, ids: Sequence[str], /) -> List[Document]:
        # return all self.docstore._dict[id] in ids
        return [self.docstore._dict[id] for id in (ids if isinstance(ids, list) else [ids]) if id in self.docstore._dict]  # type: ignore

    async def aget_by_ids(self, ids: Sequence[str], /) -> List[Document]:
        return self.get_by_ids(ids)


class VectorDB:
    def __init__(self, agent: Agent):
        self.agent = agent
        self.store = InMemoryByteStore()
        self.model = agent.get_embedding_model()

        self.embedder = CacheBackedEmbeddings.from_bytes_store(
            self.model,
            self.store,
            namespace=getattr(
                self.model,
                "model",
                getattr(self.model, "model_name", "default"),
            ),
        )

        self.index = faiss.IndexFlatIP(len(self.embedder.embed_query("example")))

        self.db = MyFaiss(
            embedding_function=self.embedder,
            index=self.index,
            docstore=InMemoryDocstore(),
            index_to_docstore_id={},
            distance_strategy=DistanceStrategy.COSINE,
            # normalize_L2=True,
            relevance_score_fn=cosine_normalizer,
        )

    async def search_similarity_threshold(
        self, query: str, limit: int, threshold: float, filter: str = ""
    ):
        comparator = get_comparator(filter) if filter else None

        # rate limiter
        await self.agent.rate_limiter(
            model_config=self.agent.config.embeddings_model, input=query
        )

        return await self.db.asearch(
            query,
            search_type="similarity_score_threshold",
            k=limit,
            score_threshold=threshold,
            filter=comparator,
        )

    async def insert_documents(self, docs: list[Document]):
        ids = [str(uuid.uuid4()) for _ in range(len(docs))]

        if ids:
            for doc, id in zip(docs, ids):
                doc.metadata["id"] = id  # add ids to documents metadata

            # rate limiter
            docs_txt = "".join(format_docs_plain(docs))
            await self.agent.rate_limiter(
                model_config=self.agent.config.embeddings_model, input=docs_txt
            )

            self.db.add_documents(documents=docs, ids=ids)
        return ids


def format_docs_plain(docs: list[Document]) -> list[str]:
    result = []
    for doc in docs:
        text = ""
        for k, v in doc.metadata.items():
            text += f"{k}: {v}\n"
        text += f"Content: {doc.page_content}"
        result.append(text)
    return result


def cosine_normalizer(val: float) -> float:
    res = (1 + val) / 2
    res = max(
        0, min(1, res)
    )  # float precision can cause values like 1.0000000596046448
    return res


def get_comparator(condition: str):
    def comparator(data: dict[str, Any]):
        try:
            return eval(condition, {}, data)
        except Exception as e:
            # PrintStyle.error(f"Error evaluating condition: {e}")
            return False

    return comparator
