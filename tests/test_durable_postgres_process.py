"""Crash actual framework workers using PostgreSQL and disjoint host projections.

Set A0_TEST_DURABILITY_POSTGRES_DSN to an isolated disposable database. These
checks never select a developer's deployment DSN or inspect live user state.
"""
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import time
import uuid

import pytest

PROJECT = Path(__file__).resolve().parents[1]
DSN = os.environ.get("A0_TEST_DURABILITY_POSTGRES_DSN")


@pytest.mark.skipif(not DSN or os.name == "nt", reason="Requires explicit disposable PostgreSQL and POSIX kill")
@pytest.mark.parametrize("scenario,status,effects", [
    ("model_result", "completed", 0),
    ("model_intent", "attention", 0),
    ("never_body", "attention", 1),
    ("scheduler_projection", "completed", 0),
    ("parallel_join", "completed", 2),
    ("attachment_result", "completed", 0),
])
def test_postgres_framework_recovery_without_shared_chat_files(tmp_path, scenario, status, effects, monkeypatch):
    if scenario == "attachment_result":
        from cryptography.fernet import Fernet
        monkeypatch.setenv("A0_DURABILITY_RESOURCE_KEY", Fernet.generate_key().decode())
    namespace = "process_" + uuid.uuid4().hex
    args = [sys.executable, str(Path(__file__).resolve()), "--child", str(tmp_path), scenario, namespace]
    child = subprocess.Popen(args + ["crash"], cwd=PROJECT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        deadline = time.monotonic() + 30
        while not (tmp_path / "barrier").exists():
            if child.poll() is not None:
                out, err = child.communicate()
                pytest.fail(f"Worker exited before commit barrier: {out!r} {err!r}")
            if time.monotonic() > deadline:
                pytest.fail("Worker did not reach requested database commit boundary")
            if select.select([child.stdout], [], [], .05)[0]:
                os.read(child.stdout.fileno(), 65536)
        contender = subprocess.run(args + ["contender"], cwd=PROJECT, capture_output=True, timeout=15)
        assert contender.returncode == 0, contender.stderr.decode()
        ownership = json.loads((tmp_path / "contender.json").read_text())
        assert ownership == {"claimed": False}, "A live worker must retain sole run ownership"
        child.kill()
        child.communicate(timeout=5)
        if scenario == "attachment_result":
            import shutil
            shutil.rmtree(tmp_path / "host-crash")
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate(timeout=5)
    second = subprocess.run(args + ["recover"], cwd=PROJECT, capture_output=True, timeout=40)
    assert second.returncode == 0, second.stderr.decode()
    result = json.loads((tmp_path / "summary.json").read_text())
    if scenario == "attachment_result":
        assert result["attachment_bytes"] == "portable input bytes"
        assert result["recovered_file"] and "host-recover" in result["recovered_file"]
    assert result["status"] == status
    assert result["provider_calls"] == (0 if scenario == "model_intent" else 1)
    if scenario == "scheduler_projection":
        assert result["task_state"] == "idle" and result["task_result"] == "Done"
        assert result["plan_done"] == 1 and result["plan_todo"] == 1
    elif scenario == "parallel_join":
        assert result["effects"] == ["first", "second"]
        assert result["child_statuses"] == ["completed", "completed"]
    else:
        assert result["effects"] == effects
        if status == "completed":
            assert result["answer"] == "Done"


def child_main(root, scenario, namespace, action):
    import importlib.util
    sys.path.insert(0, str(PROJECT))
    if action == "contender":
        from helpers.durable.postgres import PostgresStore
        with PostgresStore(DSN, namespace=namespace) as store:
            run = next(row for row in store.list_run_headers() if row["context_id"] in ("process-test", "workflow-parent"))
            (Path(root) / "contender.json").write_text(json.dumps({"claimed": store.claim(run["run_id"])}))
        return
    from helpers.durable import runtime
    from helpers.durable.cluster import ClusterRecoveryService
    from helpers import persist_chat

    # Reuse the real loop/history/model/tool boundary harness. Only the store
    # factory changes; each worker's chat projection root is independent and
    # recovery must not consult either host's chat files.
    harness = "test_durable_workflow_process.py" if scenario in ("scheduler_projection", "parallel_join") else "test_durable_process_recovery.py"
    spec = importlib.util.spec_from_file_location("durability_process_harness", PROJECT / "tests" / harness)
    suite = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = suite
    spec.loader.exec_module(suite)

    def factory(_local_root):
        projection = Path(root) / ("host-" + action) / "chats"
        assert not projection.exists(), "Each worker starts with independent, empty chat projections"
        persist_chat.CHATS_FOLDER = str(projection)
        owner = ClusterRecoveryService(DSN, namespace=namespace, scan_interval=.05)
        if scenario == "attachment_result":
            from helpers import files
            from agent import Agent
            original_path = files.get_abs_path
            def host_path(*parts):
                if parts and str(parts[0]).startswith("usr/durability/resources"):
                    return str(Path(root) / ("host-" + action) / "materialized" / str(parts[0]).replace("/", "_") / Path(*parts[1:]))
                return original_path(*parts)
            files.get_abs_path = host_path
            Agent.parse_prompt = lambda self, name, **kwargs: kwargs.get("message", "") + " " + " ".join(kwargs.get("attachments", []))
            original_admit = owner.admit_from_context
            def attach(context, message, **kwargs):
                source = Path(root) / "host-crash" / "upload.txt"
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text("portable input bytes")
                message.attachments = [str(source)]
                return original_admit(context, message, **kwargs)
            owner.admit_from_context = attach
        return owner

    runtime.RecoveryService = factory
    suite.child_main(root, "model_result" if scenario == "attachment_result" else scenario, action)
    if scenario == "attachment_result" and action == "recover":
        from helpers.durable.resources import ResourceManager
        from helpers.durable.postgres import PostgresStore
        from types import SimpleNamespace
        with PostgresStore(DSN, namespace=namespace) as store:
            run = store.list_runs()[0]
            ref = run["checkpoint"]["resources"]["attachments"][0]
            manager = ResourceManager(SimpleNamespace(sync=lambda name, *args, **kwargs: getattr(store, name)(*args, **kwargs)), "process-test")
            path = manager.materialize(ref)
            summary_path = Path(root) / "summary.json"
            result = json.loads(summary_path.read_text())
            result.update(attachment_bytes=path.read_text(), recovered_file=str(path))
            summary_path.write_text(json.dumps(result))


if __name__ == "__main__":
    child_main(*sys.argv[2:])
