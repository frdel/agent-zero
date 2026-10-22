"""Encrypted typed FAISS custody and atomic, idempotent shared memory patches."""
from __future__ import annotations

import copy
import hashlib
import json
import math

from helpers.durable.resources import cipher, ResourceHeld
from helpers.durable.store import ConflictError, IntegrityError

MAX_BYTES = 8 * 1024 * 1024
MAX_DOCUMENTS = 10000


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def key(scope):
    from pathlib import PurePosixPath
    if (not isinstance(scope, str) or not scope or len(scope) > 1000 or "\\" in scope or "\x00" in scope
            or PurePosixPath(scope).is_absolute() or any(item in {"", ".", ".."} for item in scope.split("/"))):
        raise ValueError("Invalid memory scope")
    return "memory:" + hashlib.sha256(scope.encode()).hexdigest()


def validate(value):
    identity, documents = value.get("identity"), value.get("documents")
    if (type(identity) is not dict or set(identity) != {"provider", "model", "dimension"}
            or not all(isinstance(identity[name], str) and len(identity[name]) <= 1000 for name in ("provider", "model"))
            or type(identity["dimension"]) is not int or not 0 <= identity["dimension"] <= 16384
            or type(documents) is not list or len(documents) > MAX_DOCUMENTS):
        raise ResourceHeld("shared_memory_snapshot_invalid")
    ids = set()
    knowledge = value.get("knowledge", {})
    if (type(knowledge) is not dict or len(knowledge) > MAX_DOCUMENTS
            or any(not isinstance(item, str) or len(item) != 64
                   or any(char not in "0123456789abcdef" for char in item)
                   for pair in knowledge.items() for item in pair)):
        raise ResourceHeld("shared_knowledge_manifest_invalid")
    for doc in documents:
        if (type(doc) is not dict or set(doc) != {"id", "text", "metadata", "vector"}
                or not isinstance(doc["id"], str) or not doc["id"] or len(doc["id"]) > 256 or doc["id"] in ids
                or not isinstance(doc["text"], str) or type(doc["metadata"]) is not dict
                or doc["metadata"].get("id") != doc["id"] or type(doc["vector"]) is not list
                or len(doc["vector"]) != identity["dimension"] or not identity["dimension"]
                or any(type(item) not in (int, float) or not math.isfinite(item) for item in doc["vector"])):
            raise ResourceHeld("shared_memory_document_invalid")
        ids.add(doc["id"])
    if len(encoded(value)) > MAX_BYTES:
        raise ResourceHeld("shared_memory_snapshot_exceeds_bound")
    return value


def seal(owner, scope, value, *, domain):
    epoch = owner.sync("get_restore_state")["epoch"]
    return {"schema": 1, "epoch": epoch, "domain": domain,
            "body": cipher().encrypt(encoded({"scope": scope, "epoch": epoch,
                "domain": domain, "value": value})).decode()}


def unseal(owner, scope, envelope, *, domain, expected_epoch=None):
    try:
        if (set(envelope) != {"schema", "epoch", "domain", "body"}
                or type(envelope["schema"]) is not int or envelope["schema"] != 1
                or envelope["domain"] != domain
                or expected_epoch is not None and envelope["epoch"] != expected_epoch):
            raise ValueError()
        data = json.loads(cipher().decrypt(envelope["body"].encode()))
        if (set(data) != {"scope", "epoch", "domain", "value"} or data["scope"] != scope
                or data["epoch"] != envelope["epoch"] or data["domain"] != domain):
            raise ValueError()
        return data["value"]
    except Exception:
        raise IntegrityError("Shared memory custody is unreadable or changed") from None


def get_snapshot(owner, scope):
    record = owner.sync("get_projection", key(scope))
    if record is None:
        return None
    value = validate(unseal(owner, scope, record["value"], domain=f"snapshot:{record['version']}"))
    return {**value, "revision": record["version"]}


def scopes(owner):
    result = []
    for record in owner.sync("list_projections", "memory:"):
        try:
            data = json.loads(cipher().decrypt(record["value"]["body"].encode()))
            if key(data["scope"]) != record["key"]:
                raise ValueError()
            unseal(owner, data["scope"], record["value"], domain=f"snapshot:{record['version']}")
            result.append(data["scope"])
        except Exception:
            raise IntegrityError("Shared memory scope custody is unreadable") from None
    return sorted(set(result))


def operation(owner, scope, operation_id, fingerprint=None, *, allow_historical=False):
    name = "memory-op:" + key(scope)[7:] + ":" + hashlib.sha256(operation_id.encode()).hexdigest()
    prior = owner.sync("get_projection", name)
    if prior:
        if (not allow_historical and prior["value"]["epoch"] != owner.sync("get_restore_state")["epoch"]
                or fingerprint is not None and prior["value"]["fingerprint"] != fingerprint):
            raise ConflictError("Memory operation identity changed")
        return name, unseal(owner, scope, prior["value"]["receipt"],
            domain="operation:" + name + ":" + prior["value"]["fingerprint"], expected_epoch=prior["value"]["epoch"])
    return name, None


def apply_patch(owner, scope, expected_revision, operation_id, changes, *, run_id=None, job_id=None,
                job_token=None, identity=None, control=False, outcome=None, knowledge=None):
    """CAS a complete typed patch and its receipt; no delete/add intermediate state."""
    if (type(expected_revision) is not int or expected_revision < 0 or not isinstance(operation_id, str)
            or not operation_id or len(operation_id) > 1000 or type(changes) is not dict
            or set(changes) != {"upsert", "delete"} or type(changes["upsert"]) is not list
            or type(changes["delete"]) is not list or any(not isinstance(item, str) for item in changes["delete"])):
        raise ValueError("Invalid memory patch")
    fingerprint_fields = [expected_revision, identity, changes, outcome]
    if knowledge is not None:
        fingerprint_fields.append(knowledge)
    fingerprint = hashlib.sha256(encoded(fingerprint_fields)).hexdigest()
    operation_key, prior = operation(owner, scope, operation_id, fingerprint)
    if prior is not None:
        return prior
    saved = get_snapshot(owner, scope)
    if (saved["revision"] if saved else 0) != expected_revision:
        raise ConflictError("Shared memory revision changed")
    actual_identity = saved["identity"] if saved else identity
    if identity is not None and saved and identity != actual_identity:
        # An empty index acquires its dimension from its first real embedding.
        if actual_identity["dimension"] or saved["documents"] or any(identity[name] != actual_identity[name] for name in ("provider", "model")):
            raise ResourceHeld("shared_memory_embedding_identity_changed")
        actual_identity = identity
    docs = {doc["id"]: doc for doc in (saved["documents"] if saved else [])}
    removed = [item for item in dict.fromkeys(changes["delete"]) if item in docs]
    for item in changes["delete"]:
        docs.pop(item, None)
    for doc in changes["upsert"]:
        docs[doc["id"]] = copy.deepcopy(doc)
    value = {"identity": actual_identity, "documents": list(docs.values())}
    if knowledge is not None or saved and "knowledge" in saved:
        value["knowledge"] = copy.deepcopy(knowledge if knowledge is not None else saved["knowledge"])
    validate(value)
    receipt = {"revision": expected_revision + 1, "ids": [doc["id"] for doc in changes["upsert"]],
               "removed": removed, "removed_count": len(removed)}
    if outcome is not None:
        if type(outcome) is not dict or set(outcome) != {"message", "break_loop"} or not isinstance(outcome["message"], str) or type(outcome["break_loop"]) is not bool:
            raise ValueError("Invalid memory outcome")
        receipt["outcome"] = outcome
    role = "memory:" + key(scope)[7:]
    if control and not owner.sync("try_role", role):
        raise ConflictError("Shared memory is being maintained")
    try:
        domain = "operation:" + operation_key + ":" + fingerprint
        result = owner.sync("commit_memory_patch", key(scope), expected_revision, operation_key, fingerprint,
                            seal(owner, scope, value, domain=f"snapshot:{expected_revision + 1}"),
                            seal(owner, scope, receipt, domain=domain), run_id=run_id,
                            job_id=job_id, job_token=job_token, control_role=role if control else None)
        return unseal(owner, scope, result, domain=domain)
    finally:
        if control:
            owner.sync("release_role", role)


def capture(db, identity):
    documents = []
    for position, identifier in sorted(db.index_to_docstore_id.items()):
        doc = db.get_by_ids([identifier])[0]
        documents.append({"id": identifier, "text": doc.page_content, "metadata": copy.deepcopy(doc.metadata),
                          "vector": db.index.reconstruct(position).tolist()})
    return validate({"identity": {**identity, "dimension": db.index.d}, "documents": documents})


def rebuild(value, embedder):
    import faiss
    import numpy as np
    from langchain_core.documents import Document
    from langchain_community.docstore.in_memory import InMemoryDocstore
    from langchain_community.vectorstores.utils import DistanceStrategy
    from plugins._memory.helpers.memory import Memory, MyFaiss
    validate(value)
    documents = value["documents"]
    index = faiss.IndexFlatIP(value["identity"]["dimension"])
    if documents:
        index.add(np.asarray([doc["vector"] for doc in documents], dtype="float32"))
    return MyFaiss(embedding_function=embedder, index=index,
        docstore=InMemoryDocstore({doc["id"]: Document(doc["text"], metadata=copy.deepcopy(doc["metadata"])) for doc in documents}),
        index_to_docstore_id={position: doc["id"] for position, doc in enumerate(documents)},
        distance_strategy=DistanceStrategy.COSINE, relevance_score_fn=Memory._cosine_normalizer)


async def get(agent=None, *, scope=None, preload_knowledge=True, force_knowledge=False):
    from helpers.durable.runtime import service
    from plugins._memory.helpers.memory import Memory, get_agent_memory_subdir
    from langchain.embeddings import CacheBackedEmbeddings
    from langchain.storage import InMemoryByteStore
    import models
    owner = service()
    if not owner or not getattr(owner, "distributed", False):
        return None
    scope = scope if scope is not None else get_agent_memory_subdir(agent)
    config = Memory._get_embedding_config(agent)
    identity = {"provider": str(config.provider), "model": str(config.name), "dimension": 0}
    saved = get_snapshot(owner, scope)
    if saved and any(saved["identity"][name] != identity[name] for name in ("provider", "model")):
        raise ResourceHeld("shared_memory_embedding_identity_changed")
    model = models.get_embedding_model(config.provider, config.name, **config.build_kwargs())
    embedder = CacheBackedEmbeddings.from_bytes_store(model, InMemoryByteStore(), namespace=identity["provider"] + ":" + identity["model"])
    value = saved or {"identity": identity, "documents": []}
    if saved is None:
        from pathlib import Path
        from plugins._memory.helpers.memory import abs_db_dir
        legacy = Memory.index.get(scope)
        if legacy is None and Path(abs_db_dir(scope), "index.faiss").is_file():
            legacy, _ = Memory.initialize(None, config, scope, False)
        if legacy is not None:
            from helpers.durable.runtime import current
            turn = current(agent) if agent else None
            if agent is not None and turn is None and not force_knowledge:
                raise ResourceHeld("shared_memory_requires_claim")
            initial = capture(legacy, identity)
            receipt = apply_patch(owner, scope, 0, "legacy-import", {"upsert": initial["documents"], "delete": []},
                                  identity=initial["identity"], run_id=turn.run_id if turn else None, control=turn is None)
            value = {**initial, "revision": receipt["revision"]}
    wrap = Memory(rebuild(value, embedder), scope)
    wrap._durable_memory = {"owner": owner, "agent": agent, "snapshot": value, "sequence": 0}
    if preload_knowledge:
        if agent is None:
            import initialize
            knowledge = initialize.initialize_agent().knowledge_subdirs or []
        else:
            knowledge = agent.config.knowledge_subdirs or []
        from plugins._memory.helpers.memory import get_knowledge_subdirs_by_memory_subdir
        directories = get_knowledge_subdirs_by_memory_subdir(scope, list(knowledge))
        if directories:
            await preload(wrap, None, directories, force_knowledge=force_knowledge)
    return wrap


async def preload(memory, log_item, directories, *, force_knowledge=False):
    """Parse/embed first, then CAS one typed patch; absence never authorizes erasure."""
    from pathlib import Path
    from glob import escape
    from plugins._memory.helpers import knowledge_import
    from plugins._memory.helpers.memory import Memory, abs_knowledge_dir
    from helpers.durable.runtime import current
    state = memory._durable_memory
    owner, scope = state["owner"], memory.memory_subdir
    previous = state["snapshot"]
    parser = hashlib.sha256(Path(knowledge_import.__file__).read_bytes()).hexdigest()
    known = {}
    for doc in previous["documents"]:
        metadata = doc["metadata"]
        source = metadata.get("durable_knowledge_source")
        if source:
            known.setdefault(source, set()).add(metadata.get("durable_knowledge_version"))
    known.update({source: {version} for source, version in previous.get("knowledge", {}).items()})
    imported, versions, checks = [], {}, []
    total = document_bytes = 0
    for directory in dict.fromkeys(directories):
        root = Path(abs_knowledge_dir(directory))
        # A joining worker may not have this host's knowledge files. Never create
        # missing directories or infer deletions from its partial filesystem.
        if not root.is_dir():
            continue
        logical = ("project:" + scope[9:] if scope.startswith("projects/") and root.is_absolute()
                   and str(directory).endswith("/knowledge") else str(directory))
        for area, folder, recursive in [(Memory.Area.MAIN.value, root, False),
                *[(item.value, root / item.value, True) for item in Memory.Area]]:
            if not folder.is_dir():
                continue
            selected = {}
            for path in folder.glob("**/*" if recursive else "*"):
                if (not path.is_file() or path.name.startswith(".")
                        or path.suffix.lower() not in {".txt", ".pdf", ".csv", ".html", ".json", ".md"}):
                    continue
                source = hashlib.sha256(encoded([scope, logical, path.relative_to(root).as_posix()])).hexdigest()
                if source in known and not force_knowledge:
                    continue
                if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
                    raise ResourceHeld("shared_knowledge_link_not_supported")
                total += path.stat().st_size
                if total > MAX_BYTES or len(checks) >= MAX_DOCUMENTS:
                    raise ResourceHeld("shared_knowledge_exceeds_bound")
                body = path.read_bytes()
                if len(body) > MAX_BYTES:
                    raise ResourceHeld("shared_knowledge_exceeds_bound")
                digest = hashlib.sha256(body).hexdigest()
                version = hashlib.sha256(encoded([digest, parser])).hexdigest()
                checks.append((path, digest))
                if known.get(source) == {version}:
                    continue
                versions[source] = version
                selected[str(path)] = (source, version, logical + "/" + path.relative_to(root).as_posix())
            if not selected:
                continue
            parsed = {}
            for name in selected:
                path = Path(name)
                parsed.update(knowledge_import.load_knowledge(log_item, str(path.parent), {}, {"area": area},
                    filename_pattern=escape(path.name), recursive=False))
            if not selected.keys() <= parsed.keys():
                raise ResourceHeld("shared_knowledge_parse_failed")
            for path, (source, version, logical_path) in sorted(selected.items()):
                for chunk, doc in enumerate(parsed[path]["documents"]):
                    identifier = "knowledge:" + hashlib.sha256(encoded([scope, source, version, chunk])).hexdigest()
                    metadata = {**doc.metadata, "id": identifier, "source_path": logical_path,
                        "durable_knowledge_source": source, "durable_knowledge_version": version,
                        "durable_knowledge_chunk": chunk}
                    if "source" in metadata:
                        metadata["source"] = logical_path
                    imported.append({"id": identifier, "text": doc.page_content, "metadata": metadata})
                    document_bytes += len(encoded(imported[-1]))
                    if len(imported) > MAX_DOCUMENTS or document_bytes > MAX_BYTES:
                        raise ResourceHeld("shared_knowledge_exceeds_bound")
    if not versions:
        return
    turn = current(state["agent"]) if state["agent"] else None
    if state["agent"] is not None and turn is None and not force_knowledge:
        raise ResourceHeld("shared_knowledge_requires_claim")
    vectors = await memory.db.embedding_function.aembed_documents([doc["text"] for doc in imported]) if imported else []
    if len(vectors) != len(imported):
        raise ResourceHeld("shared_knowledge_embedding_invalid")
    for doc, vector in zip(imported, vectors):
        doc["vector"] = list(vector)
    identity = dict(previous["identity"])
    if imported and not identity["dimension"]:
        identity["dimension"] = len(imported[0]["vector"])
    for path, digest in checks:
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ResourceHeld("shared_knowledge_changed_during_import")
    revision = previous.get("revision", 0)
    changes = {"upsert": imported, "delete": [doc["id"] for doc in previous["documents"]
        if doc["metadata"].get("durable_knowledge_source") in versions]}
    operation_id = "knowledge-import:" + hashlib.sha256(encoded([revision, sorted(versions.items())])).hexdigest()
    apply_patch(owner, scope, revision, operation_id, changes, identity=identity,
                run_id=turn.run_id if turn else None, control=turn is None,
                knowledge={**previous.get("knowledge", {}), **versions})
    value = get_snapshot(owner, scope)
    memory.db = rebuild(value, memory.db.embedding_function)
    state["snapshot"] = value


def save(memory):
    from helpers.durable.runtime import current
    state = memory._durable_memory
    previous = state["snapshot"]
    value = capture(memory.db, previous["identity"])
    if "knowledge" in previous:
        value["knowledge"] = copy.deepcopy(previous["knowledge"])
    old = {doc["id"]: doc for doc in previous["documents"]}
    actual = {doc["id"]: doc for doc in value["documents"]}
    changes = {"upsert": [doc for identifier, doc in actual.items() if old.get(identifier) != doc],
               "delete": [identifier for identifier in old if identifier not in actual]}
    if not changes["upsert"] and not changes["delete"]:
        return
    turn = current(state["agent"]) if state["agent"] else None
    import uuid
    operation_id = (f"{turn.run_id}:{turn.active_call_id}:{state['sequence']}" if turn and turn.active_call_id else uuid.uuid4().hex)
    outcome = None
    if turn and turn.active_call_id:
        tool = getattr(turn.agent.loop_data, "current_tool", None)
        from helpers.durable.memory import supports
        if tool is not None and supports(tool, {}):
            message = (turn.agent.read_prompt("fw.memory_saved.md", memory_id=changes["upsert"][0]["id"])
                       if type(tool).__name__ == "MemorySave" else
                       turn.agent.read_prompt("fw.memories_deleted.md", memory_count=len(changes["delete"])))
            from helpers.durable.codec import masked
            outcome = {"message": masked(turn.agent, message), "break_loop": False}
    receipt = apply_patch(state["owner"], memory.memory_subdir, previous.get("revision", 0), operation_id, changes,
                          identity=value["identity"], run_id=turn.run_id if turn else None, control=turn is None, outcome=outcome)
    state["sequence"] += 1
    state["snapshot"] = {**value, "revision": receipt["revision"]}
