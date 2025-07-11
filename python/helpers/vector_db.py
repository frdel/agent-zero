from typing import Any, List, Sequence
import uuid
from langchain_community.vectorstores import FAISS

# faiss needs to be patched for python 3.12 on arm #TODO remove once not needed
from python.helpers import faiss_monkey_patch
import faiss


from langchain_core.documents import Document
from langchain.storage import InMemoryByteStore
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.vectorstores.utils import (
    DistanceStrategy,
)
from langchain.embeddings import CacheBackedEmbeddings

from agent import Agent
from python.helpers.settings import get_settings

# Conditional import to avoid errors if mem0 not installed or disabled
try:
    from python.helpers.memory_mem0 import Mem0Memory  # type: ignore
except Exception:
    Mem0Memory = None  # type: ignore


class MyFaiss(FAISS):
    # override aget_by_ids
    def get_by_ids(self, ids: Sequence[str], /) -> List[Document]:
        # return all self.docstore._dict[id] in ids
        return [self.docstore._dict[id] for id in (ids if isinstance(ids, list) else [ids]) if id in self.docstore._dict]  # type: ignore

    async def aget_by_ids(self, ids: Sequence[str], /) -> List[Document]:
        return self.get_by_ids(ids)

    def get_all_docs(self) -> dict[str, Document]:
        return self.docstore._dict  # type: ignore


class VectorDB:

    _cached_embeddings: dict[str, CacheBackedEmbeddings] = {}

    @staticmethod
    def _get_embeddings(agent: Agent, cache: bool = True):
        model = agent.get_embedding_model()
        if not cache:
            return model  # return raw embeddings if cache is False
        namespace = getattr(
            model,
            "model_name",
            "default",
        )
        if namespace not in VectorDB._cached_embeddings:
            store = InMemoryByteStore()
            VectorDB._cached_embeddings[namespace] = (
                CacheBackedEmbeddings.from_bytes_store(
                    model,
                    store,
                    namespace=namespace,
                )
            )
        return VectorDB._cached_embeddings[namespace]

    def __init__(self, agent: Agent, cache: bool = True):
        self.agent = agent

        # Determine if we should use mem0 backend
        settings = get_settings()
        self._use_mem0: bool = (
            settings.get("memory_backend") == "mem0" and settings.get("mem0_enabled", False)
        )

        # Initialize FAISS backend only if mem0 is not used
        if not self._use_mem0:
            self.cache = cache  # store cache preference
            self.embeddings = self._get_embeddings(agent, cache=cache)
            self.index = faiss.IndexFlatIP(len(self.embeddings.embed_query("example")))

            self.db = MyFaiss(
                embedding_function=self.embeddings,
                index=self.index,
                docstore=InMemoryDocstore(),
                index_to_docstore_id={},
                distance_strategy=DistanceStrategy.COSINE,
                # normalize_L2=True,
                relevance_score_fn=cosine_normalizer,
            )
        else:
            # For mem0 we lazily obtain the Mem0Memory instance when needed
            self.cache = False
            self.embeddings = None  # type: ignore
            self.index = None  # type: ignore
            self.db = None  # type: ignore

    async def search_by_similarity_threshold(
        self, query: str, limit: int, threshold: float, filter: str = ""
    ):
        # If mem0 backend is active, delegate to Mem0Memory
        if self._use_mem0 and Mem0Memory:
            mem0_db = await Mem0Memory.get(self.agent)
            return await mem0_db.search_similarity_threshold(
                query=query,
                limit=limit,
                threshold=threshold,
                filter=filter,
            )

        # FAISS backend (original behavior)
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

    async def search_by_metadata(self, filter: str, limit: int = 0) -> list[Document]:
        # If mem0 backend is active, approximate metadata search using similarity threshold with low threshold
        if self._use_mem0 and Mem0Memory:
            mem0_db = await Mem0Memory.get(self.agent)
            # mem0 supports filter in search function; use an empty query and rely on filter
            results = await mem0_db.search_similarity_threshold(
                query="", limit=limit or 100, threshold=0.0, filter=filter
            )
            # If limit == 0, return all results else sliced
            return results if limit == 0 else results[:limit]

        # FAISS backend
        comparator = get_comparator(filter)
        all_docs = self.db.get_all_docs()
        result = []
        for doc in all_docs.values():
            if comparator(doc.metadata):
                result.append(doc)
                # stop if limit reached and limit > 0
                if limit > 0 and len(result) >= limit:
                    break
        return result

    async def insert_documents(self, docs: list[Document]):
        # If mem0 backend is active, delegate to Mem0Memory
        if self._use_mem0 and Mem0Memory:
            mem0_db = await Mem0Memory.get(self.agent)
            return await mem0_db.insert_documents(docs)

        # FAISS backend
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

    async def delete_documents_by_ids(self, ids: list[str]):
        # If mem0 backend is active, delegate to Mem0Memory
        if self._use_mem0 and Mem0Memory:
            mem0_db = await Mem0Memory.get(self.agent)
            return await mem0_db.delete_documents_by_ids(ids)

        # FAISS backend
        rem_docs = await self.db.aget_by_ids(ids)  # type: ignore
        if rem_docs:
            rem_ids = [doc.metadata["id"] for doc in rem_docs]
            await self.db.adelete(ids=rem_ids)  # type: ignore
        return rem_docs


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
            result = eval(condition, {}, data)
            return result
        except Exception as e:
            # PrintStyle.error(f"Error evaluating condition: {e}")
            return False

    return comparator
