from datetime import datetime
from typing import Any, List, Sequence
from langchain.storage import InMemoryByteStore, LocalFileStore
from langchain.embeddings import CacheBackedEmbeddings

# from langchain_chroma import Chroma
from langchain_community.vectorstores import FAISS

# faiss needs to be patched for python 3.12 on arm #TODO remove once not needed
from python.helpers import faiss_monkey_patch
import faiss


from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.vectorstores.utils import (
    DistanceStrategy,
)
from langchain_core.embeddings import Embeddings

import os, json

import numpy as np

from python.helpers.print_style import PrintStyle
from . import files
from langchain_core.documents import Document
import uuid
from python.helpers import knowledge_import
from python.helpers.log import Log, LogItem
from enum import Enum
from agent import Agent
import models
import logging
from simpleeval import simple_eval


# Raise the log level so WARNING messages aren't shown
logging.getLogger("langchain_core.vectorstores.base").setLevel(logging.ERROR)


class MyFaiss(FAISS):
    # override aget_by_ids
    def get_by_ids(self, ids: Sequence[str], /) -> List[Document]:
        # return all self.docstore._dict[id] in ids
        return [self.docstore._dict[id] for id in (ids if isinstance(ids, list) else [ids]) if id in self.docstore._dict]  # type: ignore

    async def aget_by_ids(self, ids: Sequence[str], /) -> List[Document]:
        return self.get_by_ids(ids)

    def get_all_docs(self):
        return self.docstore._dict  # type: ignore


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
            db, created = Memory.initialize(
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
    async def reload(agent: Agent):
        memory_subdir = agent.config.memory_subdir or "default"
        if Memory.index.get(memory_subdir):
            del Memory.index[memory_subdir]
        return await Memory.get(agent)

    @staticmethod
    def initialize(
        log_item: LogItem | None,
        model_config: models.ModelConfig,
        memory_subdir: str,
        in_memory=False,
    ) -> tuple[MyFaiss, bool]:

        PrintStyle.standard("Initializing VectorDB...")

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

        embeddings_model = models.get_embedding_model(
            model_config.provider,
            model_config.name,
            **model_config.build_kwargs(),
        )
        embeddings_model_id = files.safe_file_name(
            model_config.provider + "_" + model_config.name
        )

        # here we setup the embeddings model with the chosen cache storage
        embedder = CacheBackedEmbeddings.from_bytes_store(
            embeddings_model, store, namespace=embeddings_model_id
        )

        # initial DB and docs variables
        db: MyFaiss | None = None
        docs: dict[str, Document] | None = None

        created = False

        # if db folder exists and is not empty:
        if os.path.exists(db_dir) and files.exists(db_dir, "index.faiss"):
            db = MyFaiss.load_local(
                folder_path=db_dir,
                embeddings=embedder,
                allow_dangerous_deserialization=True,
                distance_strategy=DistanceStrategy.COSINE,
                # normalize_L2=True,
                relevance_score_fn=Memory._cosine_normalizer,
            )  # type: ignore

            # if there is a mismatch in embeddings used, re-index the whole DB
            emb_ok = False
            emb_set_file = files.get_abs_path(db_dir, "embedding.json")
            if files.exists(emb_set_file):
                embedding_set = json.loads(files.read_file(emb_set_file))
                if (
                    embedding_set["model_provider"] == model_config.provider
                    and embedding_set["model_name"] == model_config.name
                ):
                    # model matches
                    emb_ok = True

            # re-index -  create new DB and insert existing docs
            if db and not emb_ok:
                docs = db.get_all_docs()
                db = None

        # DB not loaded, create one
        if not db:
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

            # insert docs if reindexing
            if docs:
                PrintStyle.standard("Indexing memories...")
                if log_item:
                    log_item.stream(progress="\nIndexing memories")
                db.add_documents(documents=list(docs.values()), ids=list(docs.keys()))

            # save DB
            Memory._save_db_file(db, memory_subdir)
            # save meta file
            meta_file_path = files.get_abs_path(db_dir, "embedding.json")
            files.write_file(
                meta_file_path,
                json.dumps(
                    {
                        "model_provider": model_config.provider,
                        "model_name": model_config.name,
                    }
                ),
            )

            created = True

        return db, created

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
        if log_item:
            log_item.update(heading="Preloading knowledge...")

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
                # Also remove from GraphRAG if it exists
                await self._remove_from_graphrag(index[file]["documents"])

            if index[file]["state"] == "changed":
                index[file]["ids"] = await self.insert_documents(
                    index[file]["documents"]
                )  # insert new version
                # Also ingest into GraphRAG
                await self._ingest_to_graphrag(index[file]["documents"], log_item)

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
                await self.db.adelete(ids=document_ids)
                tot += len(document_ids)

            # If fewer than K document IDs, break the loop
            if len(document_ids) < k:
                break

        if tot:
            self._save_db()  # persist
        return removed

    async def delete_documents_by_ids(self, ids: list[str]):
        # aget_by_ids is not yet implemented in faiss, need to do a workaround
        rem_docs = await self.db.aget_by_ids(
            ids
        )  # existing docs to remove (prevents error)
        if rem_docs:
            rem_ids = [doc.metadata["id"] for doc in rem_docs]  # ids to remove
            await self.db.adelete(ids=rem_ids)

        if rem_docs:
            self._save_db()  # persist
        return rem_docs

    async def insert_text(self, text, metadata: dict = {}):
        doc = Document(text, metadata=metadata)
        ids = await self.insert_documents([doc])
        return ids[0]

    async def insert_documents(self, docs: list[Document]):
        ids = [str(uuid.uuid4()) for _ in range(len(docs))]
        timestamp = self.get_timestamp()

        if ids:
            for doc, id in zip(docs, ids):
                doc.metadata["id"] = id  # add ids to documents metadata
                doc.metadata["timestamp"] = timestamp  # add timestamp
                if not doc.metadata.get("area", ""):
                    doc.metadata["area"] = Memory.Area.MAIN.value

            await self.db.aadd_documents(documents=docs, ids=ids)
            self._save_db()  # persist
        return ids

    def _save_db(self):
        Memory._save_db_file(self.db, self.memory_subdir)

    @staticmethod
    def _save_db_file(db: MyFaiss, memory_subdir: str):
        abs_dir = Memory._abs_db_dir(memory_subdir)
        db.save_local(folder_path=abs_dir)

    @staticmethod
    def _get_comparator(condition: str):
        def comparator(data: dict[str, Any]):
            try:
                result = simple_eval(condition, names=data)
                return result
            except Exception as e:
                PrintStyle.error(f"Error evaluating condition: {e}")
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

    async def _ingest_to_graphrag(self, documents: list, log_item=None):
        """Ingest knowledge documents into GraphRAG knowledge graph."""
        try:
            # Check if GraphRAG knowledge ingestion is enabled
            from python.helpers import settings
            set = settings.get_settings()

            # Check if GraphRAG is enabled (defaults to True for enabled)
            if not set.get("use_graphrag", True):
                return

            from python.helpers.graphrag_helper import GraphRAGHelper

            if not documents:
                return

            # Track ingestion for logging
            ingested_count = 0

            for doc in documents:
                # Get metadata for context
                metadata = doc.metadata
                area = metadata.get('area', 'main')
                source_file = metadata.get('source_file', 'unknown')

                # Create area-specific extraction instructions
                area_instructions = {
                    'main': "Extract key concepts, entities, facts, and relationships from this knowledge document",
                    'solutions': "Extract problem-solving approaches, methods, solutions, and their relationships",
                    'instruments': "Extract tools, technologies, capabilities, and their usage patterns",
                    'fragments': "Extract entities, facts, and relationships from this document fragment"
                }

                instruction = area_instructions.get(area, "Extract entities, relationships, and key information")
                instruction += f" from {source_file}"

                                # Ingest the document content with metadata
                if doc.page_content and doc.page_content.strip():
                    # Get area-specific GraphRAG helper
                    helper = GraphRAGHelper.get_for_area(area)

                    # Create metadata for knowledge source tracking
                    source_metadata = {
                        "source_type": "knowledge_file",
                        "source_id": source_file,
                        "filename": source_file,
                        "area": area,
                        "file_path": metadata.get('source_path', ''),
                        "file_type": metadata.get('file_type', ''),
                        "knowledge_source": True
                    }

                    helper.ingest_text(doc.page_content, instruction, source_metadata)
                    ingested_count += 1

                    if log_item:
                        log_item.stream(progress=f"\n  GraphRAG: Ingested {source_file} ({area}) with metadata")

            if ingested_count > 0 and log_item:
                log_item.stream(progress=f"\n  GraphRAG: Successfully ingested {ingested_count} knowledge documents")

        except Exception as e:
            # Knowledge ingestion failure shouldn't break the startup process
            if log_item:
                log_item.stream(progress=f"\n  GraphRAG ingestion warning: {e}")
            pass

    async def _remove_from_graphrag(self, documents: list):
        """Remove knowledge from GraphRAG knowledge graph."""
        try:
            from python.helpers.graphrag_helper import GraphRAGHelper

            if not documents:
                return

            # Extract potential entity names from documents for deletion
            import re
            entities_by_area = {}

            for doc in documents:
                content = doc.page_content
                source_file = doc.metadata.get('source_file', '')
                area = doc.metadata.get('area', 'main')

                # Extract capitalized terms, quoted terms, and file-based entities
                capitalized_words = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', content)
                quoted_terms = re.findall(r'"([^"]+)"', content)

                if area not in entities_by_area:
                    entities_by_area[area] = []

                entities_by_area[area].extend(capitalized_words)
                entities_by_area[area].extend(quoted_terms)

                # Also try to delete based on source file name
                if source_file:
                    file_stem = source_file.split('.')[0]
                    entities_by_area[area].append(file_stem)

            # Remove duplicates and attempt deletion for each area
            for area, entities_list in entities_by_area.items():
                entities_to_delete = list(set([entity.strip() for entity in entities_list if entity.strip()]))

                if entities_to_delete:
                    # Get area-specific helper
                    helper = GraphRAGHelper.get_for_area(area)

                    # Create query string for deletion
                    entities_query = " OR ".join(entities_to_delete[:10])  # Limit to avoid very long queries
                    helper.delete_knowledge(entities_query)

        except Exception:
            # GraphRAG deletion failure shouldn't break the process
            pass


def get_memory_subdir_abs(agent: Agent) -> str:
    return files.get_abs_path("memory", agent.config.memory_subdir or "default")


def get_custom_knowledge_subdir_abs(agent: Agent) -> str:
    for dir in agent.config.knowledge_subdirs:
        if dir != "default":
            return files.get_abs_path("knowledge", dir)
    raise Exception("No custom knowledge subdir set")


def reload():
    # clear the memory index, this will force all DBs to reload
    Memory.index = {}
