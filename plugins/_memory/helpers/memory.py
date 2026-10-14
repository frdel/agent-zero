from typing import Any, List, Sequence
from langchain.storage import InMemoryByteStore, LocalFileStore
from langchain.embeddings import CacheBackedEmbeddings
from helpers import guids

# from langchain_chroma import Chroma
from langchain_community.vectorstores import FAISS

# faiss needs to be patched for python 3.12 on arm #TODO remove once not needed
from helpers import faiss_monkey_patch
import faiss


from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.vectorstores.utils import (
    DistanceStrategy,
)
from langchain_core.embeddings import Embeddings

import os, json, hashlib, re

import numpy as np

from helpers.print_style import PrintStyle
from helpers import files, plugins, projects
from helpers.localization import Localization
from langchain_core.documents import Document
from . import knowledge_import
from helpers.log import Log, LogItem
from enum import Enum
from agent import Agent, AgentContext
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

    def similarity_search_with_score_by_vector(self, embedding, k, filter=None, **kwargs):
        """Override to gracefully handle orphaned IDs in the docstore (desync resilience).

        If the parent method raises ValueError for an ID that exists in
        index_to_docstore_id but not in the docstore, we remove the orphaned
        entry from the in-memory index and retry. If the retry still fails,
        we return empty results instead of crashing.
        """
        import logging
        _log = logging.getLogger("plugins._memory")
        try:
            return super().similarity_search_with_score_by_vector(
                embedding, k, filter=filter, **kwargs
            )
        except ValueError as e:
            if "Could not find document for id" not in str(e):
                raise
            _log.warning(f"FAISS docstore desync detected: {e}. Attempting repair.")
            # Identify and remove orphaned IDs from index_to_docstore_id
            docstore_ids = set(self.docstore._dict.keys())
            orphaned_positions = [
                pos for pos, doc_id in self.index_to_docstore_id.items()
                if str(doc_id) not in docstore_ids
            ]
            if orphaned_positions:
                import numpy as np
                _log.warning(
                    f"Removing {len(orphaned_positions)} orphaned entries from FAISS index: "
                    f"{[self.index_to_docstore_id[p] for p in orphaned_positions]}"
                )
                # Remove orphaned vectors from the FAISS index
                self.index.remove_ids(
                    np.fromiter(orphaned_positions, dtype=np.int64)
                )
                # Rebuild index_to_docstore_id with remaining entries
                remaining = [
                    doc_id for i, doc_id in sorted(self.index_to_docstore_id.items())
                    if i not in set(orphaned_positions)
                ]
                self.index_to_docstore_id = {
                    i: doc_id for i, doc_id in enumerate(remaining)
                }
            # Retry search after repair
            try:
                return super().similarity_search_with_score_by_vector(
                    embedding, k, filter=filter, **kwargs
                )
            except ValueError:
                _log.error("FAISS search still failing after orphan removal. Returning empty results.")
                return []

    def save_local(self, folder_path: str, index_name: str = "index") -> None:
        """Atomic save: write to temp files, fsync, then os.replace.

        Prevents FAISS index/docstore desync by ensuring both files are
        fully written to temp paths before either becomes visible to
        readers via os.replace (atomic on POSIX).
        """
        from pathlib import Path
        import pickle as _pickle

        path = Path(folder_path)
        path.mkdir(exist_ok=True, parents=True)

        faiss_path = str(path / f"{index_name}.faiss")
        pkl_path = str(path / f"{index_name}.pkl")
        tmp_faiss = faiss_path + ".tmp"
        tmp_pkl = pkl_path + ".tmp"

        try:
            # Step 1: Write index.faiss to temp file
            faiss.write_index(self.index, tmp_faiss)

            # Step 2: Write index.pkl to temp file with fsync
            with open(tmp_pkl, "wb") as f:
                _pickle.dump((self.docstore, self.index_to_docstore_id), f)
                f.flush()
                os.fsync(f.fileno())

            # Step 3: Atomically replace both files (POSIX rename is atomic)
            os.replace(tmp_faiss, faiss_path)
            os.replace(tmp_pkl, pkl_path)

        except Exception:
            # Clean up temp files on failure - originals remain untouched
            for tmp in [tmp_faiss, tmp_pkl]:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
            raise


class Memory:

    class Area(Enum):
        MAIN = "main"
        FRAGMENTS = "fragments"
        SOLUTIONS = "solutions"

    index: dict[str, "MyFaiss"] = {}

    @staticmethod
    def _get_embedding_config(agent=None):
        from plugins._model_config.helpers.model_config import get_embedding_model_config_object
        return get_embedding_model_config_object(agent)

    @staticmethod
    async def get(agent: Agent):
        memory_subdir = get_agent_memory_subdir(agent)
        if Memory.index.get(memory_subdir) is None:
            log_item = agent.context.log.log(
                type="util",
                heading=f"Initializing VectorDB in '/{memory_subdir}'",
            )
            db, created = Memory.initialize(
                log_item,
                Memory._get_embedding_config(agent),
                memory_subdir,
                False,
            )
            Memory.index[memory_subdir] = db
            wrap = Memory(db, memory_subdir=memory_subdir)
            knowledge_subdirs = get_knowledge_subdirs_by_memory_subdir(
                memory_subdir, agent.config.knowledge_subdirs or []
            )
            if knowledge_subdirs:
                await wrap.preload_knowledge(log_item, knowledge_subdirs, memory_subdir)
            return wrap
        else:
            return Memory(
                db=Memory.index[memory_subdir],
                memory_subdir=memory_subdir,
            )

    @staticmethod
    async def get_by_subdir(
        memory_subdir: str,
        log_item: LogItem | None = None,
        preload_knowledge: bool = True,
    ):
        if not Memory.index.get(memory_subdir):
            import initialize

            agent_config = initialize.initialize_agent()
            model_config = Memory._get_embedding_config()
            db, _created = Memory.initialize(
                log_item=log_item,
                model_config=model_config,
                memory_subdir=memory_subdir,
                in_memory=False,
            )
            wrap = Memory(db, memory_subdir=memory_subdir)
            if preload_knowledge:
                knowledge_subdirs = get_knowledge_subdirs_by_memory_subdir(
                    memory_subdir, agent_config.knowledge_subdirs or []
                )
                if knowledge_subdirs:
                    await wrap.preload_knowledge(
                        log_item, knowledge_subdirs, memory_subdir
                    )
            Memory.index[memory_subdir] = db
        return Memory(db=Memory.index[memory_subdir], memory_subdir=memory_subdir)

    @staticmethod
    async def reload(agent: Agent):
        memory_subdir = get_agent_memory_subdir(agent)
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
            "tmp/memory/embeddings"
        )  # just caching, no need to parameterize
        db_dir = abs_db_dir(memory_subdir)

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
            if not Memory._verify_index_hash(db_dir):
                PrintStyle(font_color="yellow").print(
                    f"FAISS index hash mismatch in '{db_dir}' — index will be rebuilt."
                )
            else:
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
        db: MyFaiss,
        memory_subdir: str,
    ):
        self.db = db
        self.memory_subdir = memory_subdir

    async def preload_knowledge(
        self, log_item: LogItem | None, kn_dirs: list[str], memory_subdir: str
    ):
        if log_item:
            log_item.update(heading="Preloading knowledge...")

        # db abs path
        db_dir = abs_db_dir(memory_subdir)

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
            # everything in the root of the knowledge goes to main
            index = knowledge_import.load_knowledge(
                log_item,
                abs_knowledge_dir(kn_dir),
                index,
                {"area": Memory.Area.MAIN.value},
                filename_pattern="*",
                recursive=False,
            )
            # subdirectories go to their folders
            for area in Memory.Area:
                index = knowledge_import.load_knowledge(
                    log_item,
                    # files.get_abs_path("knowledge", kn_dir, area.value),
                    abs_knowledge_dir(kn_dir, area.value),
                    index,
                    {"area": area.value},
                    recursive=True,
                )

        return index

    def get_document_by_id(self, id: str) -> Document | None:
        return self.db.get_by_ids(id)[0]

    async def embed_query(self, query: str) -> list[float]:
        return await self.db.embedding_function.aembed_query(query)

    async def search_similarity_threshold(
        self,
        query: str,
        limit: int,
        threshold: float,
        filter: str = "",
        embedding: list[float] | None = None,
    ):
        comparator = Memory._get_comparator(filter) if filter else None

        if embedding is not None:
            docs_and_scores = await self.db.asimilarity_search_with_score_by_vector(
                embedding,
                k=limit,
                filter=comparator,
            )
            return [
                doc
                for doc, score in docs_and_scores
                if Memory._cosine_normalizer(score) >= threshold
            ]

        return await self.db.asearch(
            query,
            search_type="similarity_score_threshold",
            k=limit,
            score_threshold=threshold,
            filter=comparator,
        )

    async def search_similarity_threshold_with_scores(
        self, query: str, limit: int, threshold: float, filter: str = ""
    ) -> list[tuple[Document, float]]:
        comparator = Memory._get_comparator(filter) if filter else None

        return await self.db.asimilarity_search_with_relevance_scores(
            query,
            k=limit,
            score_threshold=threshold,
            filter=comparator,
        )

    async def delete_documents_by_query(
        self,
        query: str,
        threshold: float,
        filter: str = "",
        *,
        include_exact: bool = False,
        cascade: bool = False,
    ):
        k = 100
        tot = 0
        removed = []
        removed_ids: set[str] = set()

        while True:
            # Perform similarity search with score
            docs = await self.search_similarity_threshold(
                query, limit=k, threshold=threshold, filter=filter
            )
            removed += docs

            # Extract document IDs and filter based on score
            # document_ids = [result[0].metadata["id"] for result in docs if result[1] < score_limit]
            document_ids = [result.metadata["id"] for result in docs]
            removed_ids.update(str(doc_id) for doc_id in document_ids)

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

        if include_exact:
            exact_docs = self._find_exact_query_docs(query, filter, removed_ids)
            if exact_docs:
                exact_ids = [doc.metadata["id"] for doc in exact_docs]
                await self.db.adelete(ids=exact_ids)
                removed += exact_docs
                removed_ids.update(str(doc_id) for doc_id in exact_ids)
                tot += len(exact_ids)

        if cascade and removed_ids:
            related_docs = self._find_related_docs_by_ids(removed_ids)
            if related_docs:
                related_ids = [doc.metadata["id"] for doc in related_docs]
                await self.db.adelete(ids=related_ids)
                removed += related_docs
                removed_ids.update(str(doc_id) for doc_id in related_ids)
                tot += len(related_ids)

        if tot:
            self._save_db()  # persist
        return removed

    async def delete_documents_by_ids(
        self, ids: list[str], *, cascade: bool = False, filter: str = ""
    ):
        # aget_by_ids is not yet implemented in faiss, need to do a workaround
        rem_docs = await self.db.aget_by_ids(
            ids
        )  # existing docs to remove (prevents error)
        rem_ids = [doc.metadata["id"] for doc in rem_docs]

        if cascade:
            related_docs = self._find_related_docs_by_ids(set(ids) | set(rem_ids))
            if related_docs:
                existing = {doc.metadata["id"] for doc in rem_docs}
                rem_docs.extend(
                    doc for doc in related_docs if doc.metadata["id"] not in existing
                )

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
        ids = [self._generate_doc_id() for _ in range(len(docs))]
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

    async def update_documents(self, docs: list[Document]):
        ids = [doc.metadata["id"] for doc in docs]
        await self.db.adelete(ids=ids)  # delete originals
        ins = await self.db.aadd_documents(documents=docs, ids=ids)  # add updated
        self._save_db()  # persist
        return ins

    def _save_db(self):
        Memory._save_db_file(self.db, self.memory_subdir)

    def _generate_doc_id(self):
        while True:
            doc_id = guids.generate_id(10)  # random ID
            if not self.db.get_by_ids(doc_id):  # check if exists
                return doc_id

    def _find_exact_query_docs(
        self, query: str, filter: str, skip_ids: set[str]
    ) -> list[Document]:
        needle = _normalize_memory_match_text(query)
        if len(needle) < 3:
            return []

        docs: list[Document] = []
        comparator = Memory._get_comparator(filter) if filter else None
        for doc in self.db.get_all_docs().values():
            doc_id = str(doc.metadata.get("id", ""))
            if not doc_id or doc_id in skip_ids:
                continue
            if comparator and not comparator(doc.metadata):
                continue
            haystack = _normalize_memory_match_text(
                f"{doc.page_content}\n{json.dumps(doc.metadata, sort_keys=True, default=str)}"
            )
            if needle in haystack:
                docs.append(doc)
        return docs

    def _find_related_docs_by_ids(
        self, ids: set[str], filter: str = ""
    ) -> list[Document]:
        ids = {str(doc_id) for doc_id in ids if str(doc_id)}
        if not ids:
            return []

        docs: list[Document] = []
        comparator = Memory._get_comparator(filter) if filter else None
        for doc in self.db.get_all_docs().values():
            doc_id = str(doc.metadata.get("id", ""))
            if not doc_id or doc_id in ids:
                continue
            if comparator and not comparator(doc.metadata):
                continue
            if _metadata_references_any(doc.metadata, ids):
                docs.append(doc)
        return docs

    @staticmethod
    def _save_db_file(db: MyFaiss, memory_subdir: str):
        abs_dir = abs_db_dir(memory_subdir)
        db.save_local(folder_path=abs_dir)
        Memory._write_index_hash(abs_dir)

    @staticmethod
    def _write_index_hash(abs_dir: str) -> None:
        faiss_path = os.path.join(abs_dir, "index.faiss")
        hash_path = os.path.join(abs_dir, "index.faiss.sha256")
        try:
            h = hashlib.sha256()
            with open(faiss_path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            tmp_hash = hash_path + ".tmp"
            with open(tmp_hash, "w") as f:
                f.write(h.hexdigest())
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_hash, hash_path)
        except Exception as e:
            PrintStyle(font_color="yellow").print(f"Warning: could not write FAISS hash: {e}")
            try:
                os.unlink(tmp_hash)
            except OSError:
                pass

    @staticmethod
    def _verify_index_hash(abs_dir: str) -> bool:
        faiss_path = os.path.join(abs_dir, "index.faiss")
        hash_path = os.path.join(abs_dir, "index.faiss.sha256")
        if not os.path.exists(hash_path):
            return True
        try:
            with open(hash_path, "r") as f:
                stored = f.read().strip()
            h = hashlib.sha256()
            with open(faiss_path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            return h.hexdigest() == stored
        except Exception as e:
            PrintStyle(font_color="yellow").print(f"Warning: FAISS hash check failed: {e}")
            return True

    @staticmethod
    def _get_comparator(condition: str):
        _FILTER_SAFE = re.compile(
            r"^[a-zA-Z0-9_\-\.\ \t'\"=<>!()\[\],:\+]+$"
        )
        if len(condition) > 512 or not _FILTER_SAFE.match(condition):
            PrintStyle.error(
                f"Memory filter rejected (unsafe characters or too long): {condition!r}"
            )
            return lambda _data: False

        def comparator(data: dict[str, Any]):
            try:
                result = simple_eval(condition, names=data, functions={})
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
        return float(res)  # native float, not numpy scalar (JSON serializable)

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
        return Localization.get().now_iso(timespec="seconds")


def get_custom_knowledge_subdir_abs(agent: Agent) -> str:
    for dir in agent.config.knowledge_subdirs:
        if dir != "default":
            if dir == "custom":
                return files.get_abs_path("usr/knowledge")
            return files.get_abs_path("usr/knowledge", dir)
    raise Exception("No custom knowledge subdir set")


def reload():
    # clear the memory index, this will force all DBs to reload
    Memory.index = {}


def _normalize_memory_match_text(value: str) -> str:
    return " ".join(str(value or "").casefold().split())


def _metadata_references_any(value: Any, ids: set[str]) -> bool:
    if isinstance(value, dict):
        return any(_metadata_references_any(item, ids) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_metadata_references_any(item, ids) for item in value)
    text = str(value or "").strip()
    if not text:
        return False
    if text in ids:
        return True
    return any(doc_id in text.split(",") for doc_id in ids)


def abs_db_dir(memory_subdir: str) -> str:
    # patch for projects, this way we don't need to re-work the structure of memory subdirs
    if memory_subdir.startswith("projects/"):
        from helpers.projects import get_project_meta

        return files.get_abs_path(get_project_meta(memory_subdir[9:]), "memory")
    # standard subdirs
    return files.get_abs_path("usr/memory", memory_subdir)


def abs_knowledge_dir(knowledge_subdir: str, *sub_dirs: str) -> str:
    # patch for projects, this way we don't need to re-work the structure of knowledge subdirs
    if knowledge_subdir.startswith("projects/"):
        from helpers.projects import get_project_meta

        return files.get_abs_path(
            get_project_meta(knowledge_subdir[9:]), "knowledge", *sub_dirs
        )
    # standard subdirs
    if knowledge_subdir == "default":
        return files.get_abs_path("knowledge", *sub_dirs)
    if knowledge_subdir == "custom":
        return files.get_abs_path("usr/knowledge", *sub_dirs)
    return files.get_abs_path("usr/knowledge", knowledge_subdir, *sub_dirs)


def get_memory_subdir_abs(agent: Agent) -> str:
    subdir = get_agent_memory_subdir(agent)
    return abs_db_dir(subdir)


def get_agent_memory_subdir(agent: Agent) -> str:
    config = plugins.get_plugin_config("_memory", agent)

    if not config:
        return "default"
    
    # Check if project isolation is enabled and we are in a project
    if config.get("project_memory_isolation", True):
        project_name = projects.get_context_project_name(agent.context)
        if project_name:
            return "projects/" + project_name

    # Fallback to configured subdir or default
    return config.get("agent_memory_subdir", "") or "default"


def get_context_memory_subdir(context: AgentContext) -> str:
    agent = context.get_agent()
    return get_agent_memory_subdir(agent)


def get_existing_memory_subdirs() -> list[str]:
    try:
        from helpers.projects import (
            get_project_meta,
            get_projects_parent_folder,
        )

        # Get subdirectories from memory folder
        subdirs = files.get_subdirectories("usr/memory")

        project_subdirs = files.get_subdirectories(get_projects_parent_folder())
        for project_subdir in project_subdirs:
            if files.exists(
                get_project_meta(project_subdir), "memory", "index.faiss"
            ):
                subdirs.append(f"projects/{project_subdir}")

        # Ensure 'default' is always available
        if "default" not in subdirs:
            subdirs.insert(0, "default")

        return subdirs
    except Exception as e:
        PrintStyle.error(f"Failed to get memory subdirectories: {str(e)}")
        return ["default"]


def get_knowledge_subdirs_by_memory_subdir(
    memory_subdir: str, default: list[str]
) -> list[str]:
    if memory_subdir.startswith("projects/"):
        from helpers.projects import get_project_meta

        default.append(get_project_meta(memory_subdir[9:], "knowledge"))
    return default
