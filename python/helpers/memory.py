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
from agent import Agent, ModelConfig
import models


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
        RESEARCH = "research"

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
        model_config: ModelConfig,
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

        embeddings_model = models.get_model(
            models.ModelType.EMBEDDING,
            model_config.provider,
            model_config.name,
            **model_config.kwargs,
        )
        embeddings_model_id = files.safe_file_name(
            model_config.provider.name + "_" + model_config.name
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
                    embedding_set["model_provider"] == model_config.provider.name
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
                        "model_provider": model_config.provider.name,
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
            if index[file]["state"] == "changed":
                index[file]["ids"] = await self.insert_documents(
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
        rem_docs = await self.db.aget_by_ids(ids)  # existing docs to remove (prevents error)
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

            # rate limiter
            docs_txt = "".join(self.format_docs_plain(docs))
            await self.agent.rate_limiter(
                model_config=self.agent.config.embeddings_model, input=docs_txt
            )

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
                return eval(condition, {}, data)
            except Exception as e:
                # PrintStyle.error(f"Error evaluating condition: {e}")
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

    # Research-specific methods for SakanaAI integration
    async def insert(self, text: str, area: "Memory.Area" = None, metadata: dict = None):
        """Enhanced insert method with area specification for research artifacts"""
        if area is None:
            area = Memory.Area.MAIN
        if metadata is None:
            metadata = {}
        
        metadata["area"] = area.value
        return await self.insert_text(text, metadata)

    async def search_research_artifacts(self, query: str, artifact_type: str = None, 
                                      limit: int = 10, threshold: float = 0.7):
        """Search for research artifacts with optional type filtering"""
        filter_condition = f"area == '{Memory.Area.RESEARCH.value}'"
        if artifact_type:
            filter_condition += f" and type == '{artifact_type}'"
        
        return await self.search_similarity_threshold(
            query, limit=limit, threshold=threshold, filter=filter_condition
        )

    async def get_research_papers(self, limit: int = 20, threshold: float = 0.5):
        """Get all research papers stored in memory"""
        return await self.search_similarity_threshold(
            "research paper academic", 
            limit=limit, 
            threshold=threshold,
            filter=f"area == '{Memory.Area.RESEARCH.value}' and type == 'academic_paper'"
        )

    async def get_experiment_designs(self, limit: int = 10, threshold: float = 0.5):
        """Get all experiment designs stored in memory"""
        return await self.search_similarity_threshold(
            "experiment design methodology", 
            limit=limit, 
            threshold=threshold,
            filter=f"area == '{Memory.Area.RESEARCH.value}' and type == 'experiment_design'"
        )

    async def get_peer_reviews(self, limit: int = 10, threshold: float = 0.5):
        """Get all peer reviews stored in memory"""
        return await self.search_similarity_threshold(
            "peer review evaluation", 
            limit=limit, 
            threshold=threshold,
            filter=f"area == '{Memory.Area.RESEARCH.value}' and type == 'peer_review'"
        )

    async def get_research_findings(self, query: str = "", limit: int = 15, threshold: float = 0.6):
        """Get research findings with optional query filtering"""
        search_query = f"research findings results {query}".strip()
        return await self.search_similarity_threshold(
            search_query, 
            limit=limit, 
            threshold=threshold,
            filter=f"area == '{Memory.Area.RESEARCH.value}' and type == 'research_findings'"
        )

    async def delete_research_artifacts(self, artifact_type: str = None, threshold: float = 0.5):
        """Delete research artifacts by type"""
        if artifact_type:
            filter_condition = f"area == '{Memory.Area.RESEARCH.value}' and type == '{artifact_type}'"
            query = f"research {artifact_type}"
        else:
            filter_condition = f"area == '{Memory.Area.RESEARCH.value}'"
            query = "research artifacts"
            
        return await self.delete_documents_by_query(query, threshold, filter_condition)

    async def get_research_timeline(self, days_back: int = 30):
        """Get research artifacts from recent timeline"""
        from datetime import datetime, timedelta
        cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        
        # This would require timestamp comparison, simplified implementation
        return await self.search_similarity_threshold(
            "recent research", 
            limit=50, 
            threshold=0.3,
            filter=f"area == '{Memory.Area.RESEARCH.value}'"
        )

    async def save_research_session(self, session_data: dict):
        """Save complete research session with metadata"""
        metadata = {
            "type": "research_session",
            "session_id": session_data.get("session_id", "unknown"),
            "research_topic": session_data.get("topic", ""),
            "agent": self.agent.agent_name,
            "area": Memory.Area.RESEARCH.value
        }
        
        session_summary = f"""Research Session Summary:
Topic: {session_data.get('topic', 'Unknown')}
Duration: {session_data.get('duration', 'Unknown')}
Artifacts Created: {session_data.get('artifacts_count', 0)}
Key Findings: {session_data.get('key_findings', 'None recorded')}
Next Steps: {session_data.get('next_steps', 'None specified')}
"""
        
        return await self.insert_text(session_summary, metadata)

    @staticmethod
    def format_research_docs(docs: list[Document]) -> str:
        """Format research documents for display with enhanced metadata"""
        if not docs:
            return "No research documents found."
        
        result = []
        for i, doc in enumerate(docs, 1):
            text = f"\n--- Research Document {i} ---\n"
            
            # Extract key metadata
            doc_type = doc.metadata.get('type', 'Unknown')
            timestamp = doc.metadata.get('timestamp', 'Unknown')
            agent = doc.metadata.get('agent', 'Unknown')
            
            text += f"Type: {doc_type}\n"
            text += f"Timestamp: {timestamp}\n"
            text += f"Agent: {agent}\n"
            
            # Add specific metadata based on type
            if doc_type == "research_findings":
                research_type = doc.metadata.get('research_type', 'Unknown')
                query = doc.metadata.get('query', 'Unknown')
                text += f"Research Type: {research_type}\n"
                text += f"Query: {query}\n"
            elif doc_type == "experiment_design":
                experiment_type = doc.metadata.get('experiment_type', 'Unknown')
                research_question = doc.metadata.get('research_question', 'Unknown')
                text += f"Experiment Type: {experiment_type}\n"
                text += f"Research Question: {research_question}\n"
            elif doc_type == "academic_paper":
                paper_type = doc.metadata.get('paper_type', 'Unknown')
                research_topic = doc.metadata.get('research_topic', 'Unknown')
                text += f"Paper Type: {paper_type}\n"
                text += f"Topic: {research_topic}\n"
            elif doc_type == "peer_review":
                review_type = doc.metadata.get('review_type', 'Unknown')
                paper_url = doc.metadata.get('paper_url', 'Unknown')
                text += f"Review Type: {review_type}\n"
                text += f"Paper URL: {paper_url}\n"
            
            text += f"\nContent Preview:\n{doc.page_content[:300]}..."
            text += "\n" + "="*50
            result.append(text)
        
        return "\n".join(result)


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
