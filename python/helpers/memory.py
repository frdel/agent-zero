from datetime import datetime
from typing import Any, List, Sequence
from langchain.storage import InMemoryByteStore, LocalFileStore
from langchain.embeddings import CacheBackedEmbeddings

# from langchain_chroma import Chroma
from langchain_community.vectorstores import FAISS
import faiss
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.vectorstores.utils import (
    DistanceStrategy,
)
import os, json

import numpy as np
from . import files
from langchain_core.documents import Document
import uuid
from python.helpers import knowledge_import
from python.helpers.log import Log, LogItem
from enum import Enum
from agent import Agent


class MyFaiss(FAISS):
    # override aget_by_ids
    def get_by_ids(self, ids: Sequence[str], /) -> List[Document]:
        # return all self.docstore._dict[id] in ids
        return [self.docstore._dict[id] for id in ids if id in self.docstore._dict]  # type: ignore

    async def aget_by_ids(self, ids: Sequence[str], /) -> List[Document]:
        return self.get_by_ids(ids)


class Memory:

    class Area(Enum):
        MAIN = "main"
        FRAGMENTS = "fragments"
        SOLUTIONS = "solutions"
        INSTRUMENTS = "instruments"

    index: dict[str, "MyFaiss"] = {}

    @staticmethod
    async def get(agent: Agent):
        memory_subdir = agent.config.memory_subdir or "default"
        if Memory.index.get(memory_subdir) is None:
            log_item = agent.context.log.log(
                type="util",
                heading=f"Initializing VectorDB in '/{memory_subdir}'",
            )
            db = Memory.initialize(
                log_item,
                agent.config.embeddings_model,
                memory_subdir,
                False,
            )
            Memory.index[memory_subdir] = db
            wrap = Memory(agent, db, memory_subdir=memory_subdir)
            if agent.config.knowledge_subdirs:
                await wrap.preload_knowledge(
                    log_item, agent.config.knowledge_subdirs, memory_subdir
                )
            return wrap
        else:
            return Memory(
                agent=agent,
                db=Memory.index[memory_subdir],
                memory_subdir=memory_subdir,
            )

    @staticmethod
    def initialize(
        log_item: LogItem | None,
        embeddings_model,
        memory_subdir: str,
        in_memory=False,
    ) -> MyFaiss:

        print("Initializing VectorDB...")

        if log_item:
            log_item.stream(progress="\nInitializing VectorDB")

        em_dir = files.get_abs_path(
            "memory/embeddings"
        )  # just caching, no need to parameterize
        db_dir = Memory._abs_db_dir(memory_subdir)

        # make sure embeddings and database directories exist
        os.makedirs(db_dir, exist_ok=True)

        if in_memory:
            store = InMemoryByteStore()
        else:
            os.makedirs(em_dir, exist_ok=True)
            store = LocalFileStore(em_dir)

        # here we setup the embeddings model with the chosen cache storage
        embedder = CacheBackedEmbeddings.from_bytes_store(
            embeddings_model,
            store,
            namespace=getattr(
                embeddings_model,
                "model",
                getattr(embeddings_model, "model_name", "default"),
            ),
        )

        # self.db = Chroma(
        #     embedding_function=self.embedder,
        #     persist_directory=db_dir)

        # if db folder exists and is not empty:
        if os.path.exists(db_dir) and files.exists(db_dir, "index.faiss"):
            db = MyFaiss.load_local(
                folder_path=db_dir,
                embeddings=embedder,
                allow_dangerous_deserialization=True,
                distance_strategy=DistanceStrategy.COSINE,
                # normalize_L2=True,
                relevance_score_fn=Memory._cosine_normalizer,
            )
        else:
            index = faiss.IndexFlatIP(len(embedder.embed_query("example")))

            db = MyFaiss(
                embedding_function=embedder,
                index=index,
                docstore=InMemoryDocstore(),
                index_to_docstore_id={},
                distance_strategy=DistanceStrategy.COSINE,
                # normalize_L2=True,
                relevance_score_fn=Memory._cosine_normalizer,
            )
        return db  # type: ignore

    def __init__(
        self,
        agent: Agent,
        db: MyFaiss,
        memory_subdir: str,
    ):
        self.agent = agent
        self.db = db
        self.memory_subdir = memory_subdir

    async def preload_knowledge(
        self, log_item: LogItem | None, kn_dirs: list[str], memory_subdir: str
    ):
        # db abs path
        db_dir = Memory._abs_db_dir(memory_subdir)

        # Load the index file if it exists
        index_path = files.get_abs_path(db_dir, "knowledge_import.json")

        # make sure directory exists
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)

        index: dict[str, knowledge_import.KnowledgeImport] = {}
        if os.path.exists(index_path):
            with open(index_path, "r") as f:
                index = json.load(f)

        # preload knowledge folders
        index = self._preload_knowledge_folders(log_item, kn_dirs, index)

        for file in index:
            if index[file]["state"] in ["changed", "removed"] and index[file].get(
                "ids", []
            ):  # for knowledge files that have been changed or removed and have IDs
                await self.delete_documents_by_ids(
                    index[file]["ids"]
                )  # remove original version
            if index[file]["state"] == "changed":
                index[file]["ids"] = self.insert_documents(
                    index[file]["documents"]
                )  # insert new version

        # remove index where state="removed"
        index = {k: v for k, v in index.items() if v["state"] != "removed"}

        # strip state and documents from index and save it
        for file in index:
            if "documents" in index[file]:
                del index[file]["documents"]  # type: ignore
            if "state" in index[file]:
                del index[file]["state"]  # type: ignore
        with open(index_path, "w") as f:
            json.dump(index, f)

    def _preload_knowledge_folders(
        self,
        log_item: LogItem | None,
        kn_dirs: list[str],
        index: dict[str, knowledge_import.KnowledgeImport],
    ):
        # load knowledge folders, subfolders by area
        for kn_dir in kn_dirs:
            for area in Memory.Area:
                index = knowledge_import.load_knowledge(
                    log_item,
                    files.get_abs_path("knowledge", kn_dir, area.value),
                    index,
                    {"area": area.value},
                )

        # load instruments descriptions
        index = knowledge_import.load_knowledge(
            log_item,
            files.get_abs_path("instruments"),
            index,
            {"area": Memory.Area.INSTRUMENTS.value},
            filename_pattern="**/*.md",
        )

        return index

    async def search_similarity_threshold(
        self, query: str, limit: int, threshold: float, filter: str = ""
    ):
        comparator = Memory._get_comparator(filter) if filter else None
        return await self.db.asearch(
            query,
            search_type="similarity_score_threshold",
            k=limit,
            score_threshold=threshold,
            filter=comparator,
        )

    async def delete_documents_by_query(
        self, query: str, threshold: float, filter: str = ""
    ):
        k = 100
        tot = 0
        removed = []

        while True:
            # Perform similarity search with score
            docs = await self.search_similarity_threshold(
                query, limit=k, threshold=threshold, filter=filter
            )
            removed += docs

            # Extract document IDs and filter based on score
            # document_ids = [result[0].metadata["id"] for result in docs if result[1] < score_limit]
            document_ids = [result.metadata["id"] for result in docs]

            # Delete documents with IDs over the threshold score
            if document_ids:
                # fnd = self.db.get(where={"id": {"$in": document_ids}})
                # if fnd["ids"]: self.db.delete(ids=fnd["ids"])
                # tot += len(fnd["ids"])
                self.db.delete(ids=document_ids)
                tot += len(document_ids)

            # If fewer than K document IDs, break the loop
            if len(document_ids) < k:
                break

        if tot:
            self._save_db()  # persist
        return removed

    async def delete_documents_by_ids(self, ids: list[str]):
        # aget_by_ids is not yet implemented in faiss, need to do a workaround
        rem_docs = self.db.get_by_ids(ids)  # existing docs to remove (prevents error)
        if rem_docs:
            rem_ids = [doc.metadata["id"] for doc in rem_docs]  # ids to remove
            await self.db.adelete(ids=rem_ids)

        if rem_docs:
            self._save_db()  # persist
        return rem_docs

    def insert_text(self, text, metadata: dict = {}):
        id = str(uuid.uuid4())
        if not metadata.get("area", ""):
            metadata["area"] = Memory.Area.MAIN.value

        self.db.add_documents(
            documents=[
                Document(
                    text,
                    metadata={"id": id, "timestamp": self.get_timestamp(), **metadata},
                )
            ],
            ids=[id],
        )
        self._save_db()  # persist
        return id

    def insert_documents(self, docs: list[Document]):
        ids = [str(uuid.uuid4()) for _ in range(len(docs))]
        timestamp = self.get_timestamp()
        if ids:
            for doc, id in zip(docs, ids):
                doc.metadata["id"] = id  # add ids to documents metadata
                doc.metadata["timestamp"] = timestamp  # add timestamp
            self.db.add_documents(documents=docs, ids=ids)
            self._save_db()  # persist
        return ids

    def _save_db(self):
        self.db.save_local(folder_path=self._abs_db_dir(self.memory_subdir))

    @staticmethod
    def _get_comparator(condition: str):
        def comparator(data: dict[str, Any]):
            try:
                return eval(condition, {}, data)
            except Exception as e:
                # print(f"Error evaluating condition: {e}")
                return False

        return comparator

    @staticmethod
    def _score_normalizer(val: float) -> float:
        res = 1 - 1 / (1 + np.exp(val))
        return res

    @staticmethod
    def _cosine_normalizer(val: float) -> float:
        res = (1 + val) / 2
        res = max(
            0, min(1, res)
        )  # float precision can cause values like 1.0000000596046448
        return res

    @staticmethod
    def _abs_db_dir(memory_subdir: str) -> str:
        return files.get_abs_path("memory", memory_subdir)

    @staticmethod
    def format_docs_plain(docs: list[Document]) -> list[str]:
        result = []
        for doc in docs:
            text = ""
            for k, v in doc.metadata.items():
                text += f"{k}: {v}\n"
            text += f"Content: {doc.page_content}"
            result.append(text)
        return result

    @staticmethod
    def get_timestamp():
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
