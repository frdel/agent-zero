"""Detached read-only inference and frozen-memory recall receipts.

Task handles are inert JSON references. Model requests are prepared immutably,
then consume one-use phase grants. Neither worker nor broker recovery repeats
an inference with a running, unknown outcome.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
from types import SimpleNamespace

from helpers.durable import execution

VERSION = 1


def _sources():
    root = Path(__file__).resolve().parents[2]
    names = ("helpers/durable/background.py", "helpers/durable/memorization.py", "helpers/durable/history.py",
             "helpers/history.py", "models.py", "plugins/_infection_check/helpers/checker.py",
             "plugins/_memory/helpers/memory_quality.py", "plugins/_memory/helpers/durable_memory.py")
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names}


def _resource_roots(value, manager):
    """Expose authenticated refs for GC without exposing encrypted inputs."""
    roots = {}
    def visit(item):
        if type(item) is dict:
            if set(item) == {"id", "kind", "name", "digest", "size"}:
                try:
                    stored = manager.owner.sync("get_resource", manager.context_id, item["id"])
                    if stored["metadata"] == item:
                        roots[item["id"]] = item
                except (ValueError, KeyError):
                    pass
            for child in item.values():
                visit(child)
        elif type(item) is list:
            for child in item:
                visit(child)
    visit(value)
    return list(roots.values())


def enabled(agent):
    from helpers.durable.runtime import current
    turn = current(agent)
    return bool(turn and getattr(turn.owner, "distributed", False))


def _owner(agent):
    from helpers.durable.runtime import current, service
    turn = current(agent)
    owner = turn.owner if turn else getattr(agent.context, "_durable_recovery_owner", None) or service()
    if owner is None or not getattr(owner, "distributed", False):
        execution._held("background_shared_owner_unavailable")
    return owner


def _model(model, *, embedding=False):
    import models
    from helpers.durable import codec, retry
    conf_override = None
    if embedding and type(model) is tuple and len(model) == 2 and type(model[1]) is models.ModelConfig:
        model, conf_override = model
    if embedding:
        from langchain.embeddings import CacheBackedEmbeddings
        if type(model) is CacheBackedEmbeddings:
            if model.query_embedding_store is not None:
                execution._held("background_query_cache_adapter_required")
            model = model.underlying_embeddings
    allowed = (models.LiteLLMEmbeddingWrapper, models.LocalSentenceTransformerWrapper) if embedding else (models.LiteLLMChatWrapper,)
    if type(model) not in allowed:
        execution._held("background_model_adapter_required")
    local = type(model) is models.LocalSentenceTransformerWrapper
    options = dict(getattr(model, "kwargs", {}) or {})
    key = options.pop("api_key", "")
    if not isinstance(key, str):
        execution._held("background_credential_adapter_required")
    if not local and set(options) - (set(retry.MODEL_KEYS) - {"api_key"}):
        execution._held("background_model_options_adapter_required")
    conf = conf_override or getattr(model, "a0_model_conf", None)
    if local:
        options = dict(conf.kwargs if conf else {})
        if options.get("trust_remote_code") or set(options) - {"device", "cache_folder", "revision", "trust_remote_code"}:
            execution._held("background_local_embedding_adapter_required")
    provider = getattr(model, "provider", None) or model.model_name.split("/", 1)[0]
    configured = models.get_api_key_raw(provider)
    portable_key = not key or key == "None" or key in [item.strip() for item in configured.split(",")]
    return {"kind": "local_embedding" if local else "embedding" if embedding else "chat",
            "name": model.model_name, "provider": getattr(model, "provider", None),
            "implementation": codec.identity(model), "options": options,
            "credential_source": "provider" if local or portable_key else "worker"}, key


def _audit(agent, utility=False):
    from helpers import extension
    from helpers.durable import codec
    points = [f"_functions/models/LiteLLMChatWrapper/unified_call/{when}" for when in ("start", "end")]
    if utility:
        points += ["util_model_call_before", "util_model_call_after"]
        points += [f"_functions/agent/Agent/call_utility_model/{when}" for when in ("start", "end")]
    for point in points:
        for hook in extension._get_extension_classes(point, agent=agent):
            identity = codec.identity(hook)
            if not (point == "util_model_call_before" and identity["class"].split(".")[-1] == "MaskToolSecrets"
                    and identity["source"] == "d65b2c486d010f8e43c30abd1029a502520a04a899c64a6902b9e373f73d2bbf"):
                execution._held("background_inference_hook_adapter_required")


def messages(values):
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
    roles = {SystemMessage: "system", HumanMessage: "human", AIMessage: "ai"}
    result = []
    for value in values:
        if (type(value) not in roles or type(value.content) is not str
                or any(getattr(value, name, None) for name in ("additional_kwargs", "response_metadata", "name", "id", "tool_calls"))):
            execution._held("background_message_adapter_required")
        result.append({"role": roles[type(value)], "content": value.content})
    return result


def _identity(agent, name):
    from helpers.durable.runtime import current
    turn = current(agent)
    if not turn:
        execution._held("background_call_identity_missing")
    identifier = execution._digest([agent.context.id, turn.run_id, agent.number, name])
    return turn, identifier


def _launch(owner, reference, credentials):
    root = execution._private(execution._local_root() / "background")
    path = root / (secrets.token_hex(16) + ".json")
    execution._write(path, execution._encoded(reference))
    environment = dict(os.environ, A0_DURABILITY_JOB_NAMESPACE=owner.store.namespace,
                       A0_DURABILITY_BACKGROUND_KEYS=json.dumps(credentials))
    subprocess.Popen([sys.executable, "-m", "helpers.durable.background", str(path)],
        cwd=str(Path(__file__).resolve().parents[2]), env=environment,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True, close_fds=True)


def start(agent, name, spec, model_objects):
    from helpers.durable.resources import ResourceManager
    from helpers.durable import codec
    spec = codec.masked(agent, spec)
    turn, identifier = _identity(agent, name)
    turn.owner.sync("assert_owner", turn.run_id)
    manager = ResourceManager(turn.owner, agent.context.id, turn.run_id)
    kind = "background-" + identifier
    existing = manager.get_manifest(kind)
    descriptions, credentials = {}, {}
    for key, model in model_objects.items():
        descriptions[key], credentials[key] = _model(model, embedding=key == "embedding")
    if existing:
        saved = json.loads(manager.get_bytes(existing["value"]["request"]))
        if saved["models"] != descriptions or saved["spec"] != spec:
            execution._held("background_request_identity_changed")
    else:
        phases = (("query", "embedding", "filter") if spec["kind"] == "recall" else
                  ("summary", "consolidation", "embedding") if spec["kind"] == "memorize" else ("model",))
        grants = {}
        for phase in (*phases, "final"):
            for suffix in (("prepare", "effect") if phase != "final" else ("result",)):
                label = phase + ":" + suffix
                grants[label] = {"id": identifier + ":" + label, "token": secrets.token_urlsafe(32)}
        if spec["kind"] == "memorize":
            grants["commit:result"] = {"id": identifier + ":commit", "token": secrets.token_urlsafe(32)}
        request = {"version": VERSION, "id": identifier, "context": agent.context.id, "sources": _sources(),
                   "run_id": turn.run_id, "spec": spec, "models": descriptions, "grants": grants}
        ref = manager.put_bytes("background-request", identifier, execution._encoded(request), sensitive=True)
        jobs = [{"id": grant["id"], "fingerprint": execution._digest([identifier, label, ref["digest"]]),
                 "token_digest": hashlib.sha256(grant["token"].encode()).hexdigest(), "allow_completed": True}
                for label, grant in grants.items()]
        existing = turn.owner.sync("publish_resource_outbox", agent.context.id, kind,
            {"request": ref, "roots": _resource_roots(spec, manager), "id": identifier, "run_id": turn.run_id},
            0, turn.run_id, jobs)
    request = json.loads(manager.get_bytes(existing["value"]["request"]))
    reference = {"version": VERSION, "id": identifier, "context": agent.context.id,
                 "run_id": turn.run_id, "kind": spec["kind"], "request": existing["value"]["request"]}
    _launch(turn.owner, reference, credentials)
    return TaskHandle(agent, reference)


class TaskHandle:
    def __init__(self, agent, reference):
        validate_reference(reference)
        self.agent, self.reference = agent, dict(reference)
        self._last_spawn = time.monotonic()

    def _row(self):
        return _owner(self.agent).sync("get_resource_job", self.reference["id"] + ":final:result")

    def done(self):
        row = self._row()
        return bool(row and row["status"] == "completed")

    def cancel(self):
        return False  # cancelling an observer never cancels or repeats inference

    def result(self):
        row = self._row()
        if not row or row["status"] != "completed":
            raise asyncio.InvalidStateError("Background result is not committed")
        from helpers.durable.resources import ResourceManager
        manager = ResourceManager(_owner(self.agent), self.reference["context"])
        value = json.loads(manager.get_bytes(row["result"]["value"]))
        if self.reference["kind"] == "checker":
            return tuple(value)
        return value

    async def wait(self):
        from helpers.durable.runtime import current
        owner = _owner(self.agent)
        turn = current(self.agent)
        if not turn or self.reference["context"] != self.agent.context.id:
            execution._held("background_execution_claim_required")
        owner.sync("assert_owner", turn.run_id)
        deadline = time.monotonic() + 120
        role = "background:" + self.reference["id"]
        while not self.done():
            if time.monotonic() - self._last_spawn >= 1 and owner.sync("try_role", role):
                owner.sync("release_role", role)
                # A missing broker can resume only unsent phases. Credentials
                # are obtained from this worker, never from stored envelopes.
                from helpers.durable.resources import ResourceManager
                manager = ResourceManager(owner, self.reference["context"])
                request = json.loads(manager.get_bytes(self.reference["request"]))
                if request["sources"] != _sources():
                    execution._held("background_adapter_source_changed")
                origin = owner.sync("get_run", self.reference["run_id"])
                if origin["generation"] != owner.sync("document_generation", self.reference["context"]) or origin["status"] == "cancelled":
                    execution._held("background_origin_stopped")
                if any(owner.sync("get_resource_job", value["id"])["status"] == "running"
                       for key, value in request["grants"].items() if key.endswith(":effect")):
                    execution._held("background_inference_outcome_unknown")
                credentials = {}
                for key, expected in request["models"].items():
                    if key == "embedding":
                        from plugins._memory.helpers.memory import Memory
                        db = await Memory.get(self.agent)
                        model = (db.db.embedding_function, Memory._get_embedding_config(self.agent))
                    else:
                        model = self.agent.get_chat_model() if key == "main" else self.agent.get_utility_model()
                    actual, credentials[key] = _model(model, embedding=key == "embedding")
                    if actual != expected:
                        execution._held("background_model_configuration_changed")
                _launch(owner, self.reference, credentials)
                self._last_spawn = time.monotonic()
            if time.monotonic() >= deadline:
                execution._held("background_result_unavailable")
            await asyncio.sleep(.05)
        return self.result()

    def __await__(self):
        return self.wait().__await__()


def validate_reference(value):
    from helpers.durable.store import _identity
    if type(value) is not dict or set(value) != {"version", "id", "context", "run_id", "kind", "request"} or value["version"] != VERSION:
        raise ValueError("Invalid background task reference")
    for key in ("id", "context", "run_id"):
        _identity(value[key], "background " + key)
    if value["kind"] not in ("recall", "checker", "text", "memorize", "history") or type(value["request"]) is not dict:
        raise ValueError("Invalid background task kind")
    execution._encoded(value)


def recover_pending(owner):
    """Bounded orphan-outbox scan; no workflow ownership or live Agent created."""
    from helpers.durable.resources import ResourceManager
    from helpers.durable.store import IntegrityError, OwnershipError
    from helpers.durable.runtime import RecoveryHeld
    import models
    after = getattr(owner, "_background_cursor", None)
    rows = owner.sync("list_resource_manifests", "background-", limit=50, after=after)
    owner._background_cursor = [rows[-1]["context_id"], rows[-1]["kind"]] if len(rows) == 50 else None
    now = time.monotonic()
    retries = getattr(owner, "_background_retries", {})
    owner._background_retries = {key: value for key, value in retries.items() if now - value < 120}
    for row in rows:
        identifier = row["value"]["id"]
        if now - retries.get(identifier, -1000) < 5:
            continue
        try:
            final = owner.sync("get_resource_job", identifier + ":final:result")
            if final and final["status"] == "completed":
                continue
            manager = ResourceManager(owner, row["context_id"])
            request = json.loads(manager.get_bytes(row["value"]["request"]))
            if request["sources"] != _sources():
                continue
            origin = owner.sync("get_run", request["run_id"])
            if origin["status"] not in ("running", "completed") or (origin.get("checkpoint") or {}).get("paused"):
                continue
            role = "background:" + identifier
            if not owner.sync("try_role", role):
                continue
            owner.sync("release_role", role)
            grants = request["grants"]
            # A one-use effect grant cannot be replayed after broker loss.
            if any((owner.sync("get_resource_job", value["id"]) or {}).get("status") == "running"
                   for name, value in grants.items() if name.endswith(":effect")):
                continue
            credentials, supported = {}, True
            for slot, model in request["models"].items():
                if model["credential_source"] != "provider":
                    supported = False
                    break
                provider = model["provider"] or model["name"].split("/", 1)[0]
                credentials[slot] = "" if model["kind"] == "local_embedding" else models.get_api_key(provider)
                _construct(model, credentials[slot])  # Verify source before launch.
            if supported:
                reference = {"version": VERSION, "id": identifier, "context": row["context_id"],
                    "run_id": request["run_id"], "kind": request["spec"]["kind"], "request": row["value"]["request"]}
                _launch(owner, reference, credentials)
                owner._background_retries[identifier] = now
        except (ValueError, KeyError, IntegrityError, OwnershipError, RecoveryHeld):
            # An unreadable/cancelled outbox must not block healthy contexts.
            continue


def inference(agent, name, model, values, *, checker=False, utility=False):
    _audit(agent, utility=utility)
    slot = "main" if model is agent.get_chat_model() else "utility"
    # Model factories often return fresh wrappers. Compare their request shape
    # instead of object identity to preserve the configured credential slot.
    if not utility and _model(model)[0] == _model(agent.get_chat_model())[0]:
        slot = "main"
    return start(agent, name, {"kind": "checker" if checker else "text", "model": slot,
                             "messages": messages(values)}, {slot: model})


async def recall(agent, loop_data, scope):
    from plugins._memory.helpers.memory import Memory
    from helpers import plugins
    from helpers.durable.resources import ResourceManager
    import faiss
    import numpy as np
    _audit(agent, utility=True)
    turn, _ = _identity(agent, "recall")
    manager = ResourceManager(turn.owner, agent.context.id, turn.run_id)
    settings = plugins.get_plugin_config("_memory", agent)
    memory = await Memory.get(agent)
    db = memory.db
    if type(db.index) is not faiss.IndexFlatIP or db.index.ntotal > 10000:
        execution._held("memory_snapshot_index_adapter_required")
    mapping = dict(db.index_to_docstore_id)
    vectors = np.asarray(db.index.reconstruct_n(0, db.index.ntotal), dtype="float32")
    vector_bytes = vectors.tobytes()
    if len(vector_bytes) > 64 * 1024 * 1024 or len(mapping) != len(vectors):
        execution._held("memory_snapshot_capacity_exceeded")
    docs = [{"id": mapping[index], "text": db.docstore.search(mapping[index]).page_content,
             "metadata": dict(db.docstore.search(mapping[index]).metadata)} for index in range(len(vectors))]
    check_docs = [{"id": mapping[index], "text": db.docstore.search(mapping[index]).page_content,
                   "metadata": dict(db.docstore.search(mapping[index]).metadata)} for index in range(len(vectors))]
    if (mapping != db.index_to_docstore_id or execution._encoded(docs) != execution._encoded(check_docs)
            or vector_bytes != np.asarray(db.index.reconstruct_n(0, db.index.ntotal), dtype="float32").tobytes()):
        execution._held("memory_snapshot_changed_during_capture")
    refs = [manager.put_bytes("memory-vectors", hashlib.sha256(chunk).hexdigest(), chunk, sensitive=True)
            for offset in range(0, len(vector_bytes), 4 * 1024 * 1024)
            for chunk in [vector_bytes[offset:offset + 4 * 1024 * 1024]]]
    documents = manager.put_bytes("memory-corpus", hashlib.sha256(execution._encoded(docs)).hexdigest(), execution._encoded(docs), sensitive=True)
    user = loop_data.user_message.output_text() if loop_data.user_message else "None"
    history = agent.history.output_text()[-settings["memory_recall_history_len"]:]
    marker = "A0_RECALL_CONTENT_" + execution._digest([agent.context.id, turn.run_id, loop_data.iteration])[:32]
    spec = {"kind": "recall", "scope": list(scope), "vectors": refs, "dimension": db.index.d, "documents": documents, "count": len(docs),
        "settings": {key: settings[key] for key in ("memory_recall_query_prep", "memory_recall_post_filter", "memory_recall_memories_max_search", "memory_recall_solutions_max_search", "memory_recall_similarity_threshold", "memory_recall_memories_max_result", "memory_recall_solutions_max_result")},
        "query_messages": [{"role": "system", "content": agent.read_prompt("memory.memories_query.sys.md")},
                           {"role": "human", "content": agent.read_prompt("memory.memories_query.msg.md", history=history, message=user)}],
        "plain_query": user + "\n\n" + history, "marker": marker,
        "filter_system": agent.read_prompt("memory.memories_filter.sys.md"),
        "filter_template": agent.read_prompt("memory.memories_filter.msg.md", memories=marker, history=history, message=user),
        "memories_template": agent.parse_prompt("agent.system.memories.md", memories=marker),
        "solutions_template": agent.parse_prompt("agent.system.solutions.md", solutions=marker)}
    name = f"recall:{loop_data.iteration}"
    return start(agent, name, spec, {"utility": agent.get_utility_model(),
                                   "embedding": (db.embedding_function, Memory._get_embedding_config(agent))})


def _construct(description, key):
    import models
    from helpers.durable import codec
    kind = description["kind"]
    expected = models.LocalSentenceTransformerWrapper if kind == "local_embedding" else models.LiteLLMEmbeddingWrapper if kind == "embedding" else models.LiteLLMChatWrapper
    if codec.identity(expected) != description["implementation"]:
        execution._held("background_model_source_changed")
    options = dict(description["options"])
    if key:
        options["api_key"] = key
    if kind == "local_embedding":
        return models.LocalSentenceTransformerWrapper("huggingface", description["name"], **options)
    provider = description["provider"] or description["name"].split("/", 1)[0]
    name = description["name"].removeprefix(provider + "/")
    return expected(name, provider, **options)


def broker(path):
    from helpers.durable.postgres import PostgresStore
    from helpers.durable.resources import ResourceManager
    reference = execution._read(path)
    Path(path).unlink()
    validate_reference(reference)
    keys = json.loads(os.environ["A0_DURABILITY_BACKGROUND_KEYS"])
    with PostgresStore(os.environ["A0_DURABILITY_POSTGRES_DSN"], namespace=os.environ["A0_DURABILITY_JOB_NAMESPACE"]) as store:
        role = "background:" + reference["id"]
        if not store.try_role(role):
            return
        execution._write(execution._private(execution._local_root() / "background") / (reference["id"] + ".broker.json"),
                         execution._encoded({"id": reference["id"], "pid": os.getpid()}))
        class Owner:
            def sync(self, method, *args, **kwargs):
                return getattr(store, method)(*args, **kwargs)
        owner = Owner()
        manager = ResourceManager(owner, reference["context"])
        request = json.loads(manager.get_bytes(reference["request"]))
        if request["sources"] != _sources():
            execution._held("background_adapter_source_changed")
        def grant(label):
            value = request["grants"][label]
            return value, ResourceManager(owner, reference["context"], job_id=value["id"], job_token=value["token"])
        async def phase(label, prepared, action):
            prepare, pm = grant(label + ":prepare")
            row = store.get_resource_job(prepare["id"])
            if row["status"] != "completed":
                ref = pm.put_bytes("background-prepared", prepare["id"], execution._encoded(prepared), sensitive=True)
                store.finish_resource_job(prepare["id"], prepare["token"], {"request": ref})
                row = store.get_resource_job(prepare["id"])
            prepared = json.loads(pm.get_bytes(row["result"]["request"]))
            prepared_ref = row["result"]["request"]
            effect, em = grant(label + ":effect")
            row = store.get_resource_job(effect["id"])
            if row["status"] == "completed":
                if row["result"].get("prepared") != prepared_ref:
                    execution._held("background_prepared_request_changed")
                return json.loads(em.get_bytes(row["result"]["value"]))
            if not store.begin_resource_job(effect["id"], effect["token"], role):
                execution._held("background_inference_outcome_unknown")
            result = await action(prepared)
            ref = em.put_bytes("background-phase", effect["id"], execution._encoded(result), sensitive=True)
            store.finish_resource_job(effect["id"], effect["token"], {"value": ref, "prepared": prepared_ref})
            return result
        async def infer(values, slot):
            from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
            classes = {"system": SystemMessage, "human": HumanMessage, "ai": AIMessage}
            model = _construct(request["models"][slot], keys.get(slot, ""))
            # The submitting agent already audited these function hooks as
            # empty. A detached process has no agent/profile and must not
            # discover a different global hook set at delivery time.
            response, _ = await type(model).unified_call.__wrapped__(model,
                messages=[classes[item["role"]](content=item["content"]) for item in values], a0_retry_attempts=0)
            return response
        async def execute():
            final, fm = grant("final:result")
            if store.get_resource_job(final["id"])["status"] == "completed":
                return
            spec = request["spec"]
            if spec["kind"] == "memorize":
                from helpers.durable import memorization
                async def embed_many(values):
                    model = _construct(request["models"]["embedding"], keys.get("embedding", ""))
                    return await model.aembed_documents(values)
                result = await memorization.execute(owner, request, phase, infer, embed_many)
            elif spec["kind"] != "recall":
                result = await phase("model", spec["messages"], lambda values: infer(values, spec["model"]))
                if spec["kind"] == "history":
                    from helpers.durable import history
                    result = history.project(spec, result)
                if spec["kind"] == "checker":
                    from plugins._infection_check.helpers.checker import parse_result
                    action, detail = parse_result(result)
                    result = [action, detail, result]
            else:
                from helpers import faiss_monkey_patch
                import faiss
                import numpy as np
                from helpers import dirty_json
                settings = spec["settings"]
                query = ((await phase("query", spec["query_messages"], lambda values: infer(values, "utility"))).strip()
                         if settings["memory_recall_query_prep"] else spec["plain_query"]) if spec["count"] else ""
                result = {}
                if len(query) > 3:
                    async def embed(value):
                        model = _construct(request["models"]["embedding"], keys.get("embedding", ""))
                        return await model.aembed_query(value)
                    vector = await phase("embedding", query, embed)
                    data = b"".join(manager.get_bytes(ref) for ref in spec["vectors"])
                    vectors = np.frombuffer(data, dtype="float32").reshape((-1, spec["dimension"]))
                    docs = json.loads(manager.get_bytes(spec["documents"]))
                    index = faiss.IndexFlatIP(spec["dimension"])
                    index.add(vectors)
                    scores, indices = index.search(np.asarray([vector], dtype="float32"), 20)
                    def search(areas, limit):
                        return [docs[int(i)] for score, i in zip(scores[0], indices[0]) if i >= 0 and docs[int(i)]["metadata"].get("area") in areas and max(0, min(1, (1 + float(score)) / 2)) >= settings["memory_recall_similarity_threshold"]][:limit]
                    memories = search({"main", "fragments"}, settings["memory_recall_memories_max_search"])
                    solutions = search({"solutions"}, settings["memory_recall_solutions_max_search"])
                    if settings["memory_recall_post_filter"] and (memories or solutions):
                        text = str({i: doc["text"] for i, doc in enumerate(memories + solutions)})
                        values = [{"role": "system", "content": spec["filter_system"]}, {"role": "human", "content": spec["filter_template"].replace(spec["marker"], text)}]
                        selected = dirty_json.try_parse(await phase("filter", values, lambda values: infer(values, "utility")))
                        if isinstance(selected, list):
                            all_docs, count = memories + solutions, len(memories)
                            memories = [all_docs[i] for i in selected if type(i) is int and 0 <= i < count]
                            solutions = [all_docs[i] for i in selected if type(i) is int and count <= i < len(all_docs)]
                    for key, values, count in (("memories", memories, settings["memory_recall_memories_max_result"]), ("solutions", solutions, settings["memory_recall_solutions_max_result"])):
                        if values[:count]:
                            result[key] = spec[key + "_template"].replace(spec["marker"], "\n\n".join(doc["text"] for doc in values[:count]))
            ref = fm.put_bytes("background-result", final["id"], execution._encoded(result), sensitive=True)
            store.finish_resource_job(final["id"], final["token"], {"value": ref})
            for label, value in request["grants"].items():
                if label != "final:result" and store.get_resource_job(value["id"])["status"] == "submitted":
                    store.finish_resource_job(value["id"], value["token"], {"skipped": True})
        asyncio.run(execute())


if __name__ == "__main__":
    broker(sys.argv[1])
