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


class Memory:

    class Area(Enum):
        MAIN = "main"
        FRAGMENTS = "fragments"
        SOLUTIONS = "solutions"

    index: dict[str, "MyFaiss"] = {}

    # Name (without extension) of the on-disk checkpoint a reindex writes
    # after every batch, so an interrupted rebuild can resume instead of
    # re-embedding everything from scratch.
    _REBUILD_INDEX_NAME = "index.rebuilding"
    # Documents embedded per batch during a reindex. Keeping this modest
    # bounds how much work a crash mid-batch can lose, and how large a single
    # embeddings-API call gets (a large batch of long documents can make one
    # call take a very long time on a slow/shared backend).
    _REBUILD_BATCH_SIZE = 20

    @staticmethod
    def _rebuild_meta_path(db_dir: str) -> str:
        return files.get_abs_path(db_dir, f"{Memory._REBUILD_INDEX_NAME}.json")

    @staticmethod
    def _rebuild_model_signature(model_config: "models.ModelConfig") -> dict:
        """Everything about model_config that can change what the embedder
        actually produces, excluding secrets. provider/name alone aren't
        enough: some providers accept kwargs (e.g. an OpenAI `dimensions`
        override, or an `api_base` pointed at a different backend/model
        version) that change the output dimension/semantics without
        changing provider or name. api_key is deliberately excluded --
        this signature is persisted to disk in the memory dir, and a
        credential rotation alone must not be treated as "a different
        model"."""
        kwargs = {
            k: v for k, v in model_config.build_kwargs().items() if k != "api_key"
        }
        return {
            "model_provider": model_config.provider,
            "model_name": model_config.name,
            "model_kwargs": kwargs,
        }

    @staticmethod
    def _load_rebuild_checkpoint(
        db_dir: str,
        model_config: "models.ModelConfig",
        embedder: Any,
    ) -> tuple["MyFaiss | None", set[str]]:
        """Load a partially-rebuilt index left behind by an interrupted
        reindex, but only if it was built under the SAME effective embedding
        configuration as the one we're about to (re)index with.

        A stale checkpoint left over from a *different* configuration (the
        model was switched again, or a dimension-affecting kwarg changed,
        while the previous rebuild was interrupted) holds vectors of a
        possibly different dimension/semantics and must not be reused:
        resuming into it would raise a FAISS dimension assertion the moment
        a new document is added, rather than making progress. Returns (db,
        resumed_ids); db is None (and resumed_ids empty) if there is
        nothing usable to resume from.
        """
        name = Memory._REBUILD_INDEX_NAME
        if not (
            files.exists(db_dir, f"{name}.faiss") and files.exists(db_dir, f"{name}.pkl")
        ):
            return None, set()

        meta_path = Memory._rebuild_meta_path(db_dir)
        if not os.path.exists(meta_path):
            PrintStyle.standard(
                "Found a partial memory rebuild with no model marker -- discarding it and starting fresh"
            )
            return None, set()
        try:
            meta = json.loads(files.read_file(meta_path))
        except Exception:
            PrintStyle.standard(
                "Partial memory rebuild marker is unreadable -- discarding it and starting fresh"
            )
            return None, set()

        if meta != Memory._rebuild_model_signature(model_config):
            PrintStyle.standard(
                "Partial memory rebuild was for a different embedding configuration "
                f"({meta.get('model_provider')}/{meta.get('model_name')}) -- "
                "discarding it and starting fresh"
            )
            return None, set()

        try:
            db = MyFaiss.load_local(
                folder_path=db_dir,
                index_name=name,
                embeddings=embedder,
                allow_dangerous_deserialization=True,
                distance_strategy=DistanceStrategy.COSINE,
                relevance_score_fn=Memory._cosine_normalizer,
            )
        except Exception as e:
            PrintStyle.standard(
                f"Could not load partial memory rebuild ({e}) -- starting fresh"
            )
            return None, set()

        return db, set(db.get_all_docs().keys())

    @staticmethod
    def _write_rebuild_checkpoint(
        db: "MyFaiss", db_dir: str, model_config: "models.ModelConfig"
    ) -> None:
        name = Memory._REBUILD_INDEX_NAME
        db.save_local(folder_path=db_dir, index_name=name)
        files.write_file(
            Memory._rebuild_meta_path(db_dir),
            json.dumps(Memory._rebuild_model_signature(model_config)),
        )

    @staticmethod
    def _clear_rebuild_checkpoint(db_dir: str) -> None:
        name = Memory._REBUILD_INDEX_NAME
        for ext in ("faiss", "pkl", "json"):
            path = files.get_abs_path(db_dir, f"{name}.{ext}")
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass

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
            resumed_db: MyFaiss | None = None
            resumed_ids: set[str] = set()
            if docs:
                resumed_db, resumed_ids = Memory._load_rebuild_checkpoint(
                    db_dir, model_config, embedder
                )

            if resumed_ids:
                db = resumed_db  # type: ignore
                PrintStyle.standard(
                    f"Resuming memory rebuild: {len(resumed_ids)}/{len(docs)} already embedded"
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

            # insert docs if reindexing
            if docs:
                PrintStyle.standard("Indexing memories...")
                if log_item:
                    log_item.stream(progress="\nIndexing memories")

                # Embed in small batches, checkpointing to disk after each
                # one, so an interrupted rebuild (crash, restart, a slow/
                # shared embeddings backend timing out) resumes from where
                # it left off instead of re-embedding everything -- which,
                # for a large memory store on a slow backend, can otherwise
                # cost hours of redone work every time it's interrupted.
                remaining = [(k, v) for k, v in docs.items() if k not in resumed_ids]
                batch_size = Memory._REBUILD_BATCH_SIZE
                done = len(resumed_ids)
                total = len(docs)
                for i in range(0, len(remaining), batch_size):
                    chunk = remaining[i : i + batch_size]
                    db.add_documents(
                        documents=[d for _, d in chunk],
                        ids=[k for k, _ in chunk],
                    )
                    done += len(chunk)
                    PrintStyle.standard(f"Indexed {done}/{total} memories...")
                    Memory._write_rebuild_checkpoint(db, db_dir, model_config)

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

            # Only drop the rebuild checkpoint once the final index and meta
            # file are durably written. Clearing it any earlier (e.g. right
            # after the batch loop) leaves a window where a crash between
            # "checkpoint cleared" and "final save complete" loses BOTH the
            # resumable checkpoint and the persisted index -- reintroducing
            # the full re-embed-from-scratch failure mode this exists to fix.
            if docs:
                Memory._clear_rebuild_checkpoint(db_dir)

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
            with open(hash_path, "w") as f:
                f.write(h.hexdigest())
        except Exception as e:
            PrintStyle(font_color="yellow").print(f"Warning: could not write FAISS hash: {e}")

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
