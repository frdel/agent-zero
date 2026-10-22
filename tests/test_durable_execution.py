"""Real detached commands and shared receipts; no provider or deployment state."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time
import uuid
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent import LoopData, UserMessage
from helpers.durable import codec, execution, runtime
from helpers.durable.resources import ResourceManager
from helpers.durable.store import OwnershipError
from plugins._code_execution.tools.code_execution_tool import CodeExecution
from plugins._code_execution.tools.input import Input
from test_durable_cluster import nodes, rig

PROJECT = Path(__file__).resolve().parents[1]
DSN = os.environ.get("A0_TEST_DURABILITY_POSTGRES_DSN")


@pytest.fixture
def shell(nodes, monkeypatch, tmp_path):
    from cryptography.fernet import Fernet
    monkeypatch.setenv("A0_DURABILITY_RESOURCE_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("A0_DURABILITY_POSTGRES_DSN", DSN)
    monkeypatch.setenv("A0_DURABILITY_EXECUTION_ROOT", str(tmp_path / "jobs"))
    work = tmp_path / "work"
    work.mkdir()
    config = {"ssh_enabled": False, "durability_interactive": False,
              "code_exec_timeouts": {"max_exec_timeout": 5},
              "output_timeouts": {"max_exec_timeout": .1}, "ssh_pass": ""}
    monkeypatch.setattr("plugins._code_execution.tools.code_execution_tool._get_config", lambda agent: config)
    monkeypatch.setattr(CodeExecution, "ensure_cwd", AsyncMock(return_value=str(work)))
    context = nodes.rig.context
    context.agent0.loop_data = LoopData(iteration=0)
    message = UserMessage("Synthetic command", id="command-input")
    run = nodes.first.sync("admit", context.id, message.id, codec.message_payload(message), codec.checkpoint(context.agent0))
    assert nodes.first.sync("claim", run["run_id"])
    turn = runtime.Turn(nodes.first, context.agent0, run)
    turn.active_call_id = "tool:0:0"
    context._durable_turn = turn
    nodes.first.contexts[run["run_id"]] = context
    def tool(args):
        value = CodeExecution(context.agent0, "code_execution_tool", None, args, "", context.agent0.loop_data)
        value.log = None
        return value
    return nodes, turn, tool, config, work


@pytest.mark.asyncio
async def test_code_tool_reuses_shared_outcome_and_restores_cwd_exports(shell, monkeypatch):
    nodes, turn, tool, cfg, work = shell
    turn.agent.context._durable_workspace_origin = {"project_name": "managed-test"}
    turn.agent.context._durable_workspace_path = work
    counter = work / "effects"
    subdir = work / "next"
    subdir.mkdir()
    args = {"runtime": "terminal", "code": f"printf once >> {shlex.quote(str(counter))}; cd {shlex.quote(str(subdir))}; export DURABLE_EXPORTED='saved value'; export DURABLE_PATH=\"$PWD\"; printf first"}
    from helpers.modules import load_classes_from_file
    from helpers.tool import Tool
    loaded, = load_classes_from_file(str(PROJECT / "plugins/_code_execution/tools/code_execution_tool.py"), Tool)
    monkeypatch.setattr(loaded, "ensure_cwd", CodeExecution.ensure_cwd)
    actual = loaded(turn.agent, "code_execution_tool", None, args, "", turn.agent.loop_data)
    actual.log = None
    first = json.loads((await actual.execute(**args)).message)
    assert first["status"] == "completed" and first["exit_code"] == 0 and first["output"] == "first"
    assert counter.read_text() == "once"
    deadline = time.monotonic() + 10
    while nodes.first.sync("get_resource_job", first["job_id"])["status"] != "completed":
        assert time.monotonic() < deadline
        await asyncio.sleep(.05)
    # A different host identity can retrieve the completed shared result. It
    # must not need the first host's receipt directory or relaunch the command.
    monkeypatch.setenv("A0_DURABILITY_EXECUTION_HOST_ID", "another-host")
    assert json.loads((await tool(args).execute(**args)).message) == first
    assert counter.read_text() == "once"
    new_workspace = work.parent / "materialized-on-another-host"
    (new_workspace / "next").mkdir(parents=True)
    turn.agent.context._durable_workspace_path = new_workspace
    turn.active_call_id = "tool:0:1"
    followup = {"runtime": "terminal", "code": "printf '%s\\n' \"$DURABLE_EXPORTED\" \"$DURABLE_PATH\"; pwd"}
    result = json.loads((await tool(followup).execute(**followup)).message)
    assert result["output"] == f"saved value\n{new_workspace / 'next'}\n{new_workspace / 'next'}\n"
    assert counter.read_text() == "once"


@pytest.mark.asyncio
async def test_unknown_submission_and_stale_owner_never_spawn_a_command(shell, monkeypatch):
    nodes, turn, tool, cfg, work = shell
    marker = work / "must-not-exist"
    args = {"runtime": "terminal", "code": "touch " + shlex.quote(str(marker))}
    target = execution._target(cfg)
    fingerprint = execution._digest({"schema": 1, "args": args, "target": target})
    identifier = execution._job_id(turn)
    manager = ResourceManager(nodes.first, turn.agent.context.id, turn.run_id)
    manager.publish_manifest("execution-job-" + identifier,
                             {"schema": 1, "id": identifier, "fingerprint": fingerprint, "target": target,
                              "root": str(work / "never-launched"), "status": "submitted"}, 0)
    with pytest.raises(runtime.RecoveryHeld, match="execution_submission_outcome_unknown"):
        await tool(args).execute(**args)
    assert not marker.exists()
    turn.active_call_id = "tool:0:1"
    nodes.first.sync("release", turn.run_id)
    assert nodes.second.sync("claim", turn.run_id)
    with pytest.raises(OwnershipError):
        await tool(args).execute(**args)
    assert not marker.exists()
    # Mere ownership movement is not cancellation. A real running command
    # receives a stop signal only after the authoritative cancelled decision.
    turn.owner = nodes.second
    nodes.second.contexts[turn.run_id] = turn.agent.context
    turn.active_call_id = "tool:0:2"
    cfg["code_exec_timeouts"]["max_exec_timeout"] = .1
    command = {"runtime": "terminal", "code": "while :; do sleep .05; done"}
    running = json.loads((await tool(command).execute(**command)).message)
    assert running["status"] == "running"
    assert await execution.cancel_sessions(turn.agent.context, turn.run_id) == []
    nodes.second.sync("control", turn.agent.context.id, "cancel")
    requested = await execution.cancel_sessions(turn.agent.context, turn.run_id)
    assert requested == [{"job_id": running["job_id"], "status": "cancellation_requested"}]
    deadline = time.monotonic() + 10
    while nodes.second.sync("get_resource_job", running["job_id"])["status"] != "completed":
        assert time.monotonic() < deadline
        await asyncio.sleep(.05)
    assert nodes.second.sync("get_resource_job", running["job_id"])["result"]["cancelled"]
    nodes.second.sync("control", turn.agent.context.id, "reset")
    assert await execution.cancel_sessions(turn.agent.context, turn.run_id) == []


def _wait(path, process=None, seconds=15):
    deadline = time.monotonic() + seconds
    while not path.exists():
        if process and process.poll() is not None:
            raise AssertionError(process.communicate()[1].decode())
        if time.monotonic() >= deadline:
            raise AssertionError("Detached execution did not reach its durable receipt")
        time.sleep(.02)


def _stop_pty_processes(root):
    """Only terminate processes whose private test receipts identify them."""
    import signal
    for receipt in Path(root).glob("relay-*/broker.json"):
        try:
            os.kill(json.loads(receipt.read_bytes())["pid"], signal.SIGTERM)
        except ProcessLookupError:
            pass
    for receipt in Path(root).glob("pty-*/ready.json"):
        value = json.loads(receipt.read_bytes())
        for pid, group in ((value["pid"], False), (value["shell_pid"], True)):
            try:
                (os.killpg if group else os.kill)(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


@pytest.mark.asyncio
async def test_live_pty_preserves_functions_aliases_and_stdin_across_framework_hosts(shell, monkeypatch):
    from helpers.durable import workspaces, resources
    nodes, turn, tool, cfg, work = shell
    cfg["durability_interactive"] = True
    root = Path(os.environ["A0_DURABILITY_EXECUTION_ROOT"])
    (work / "baseline").write_text("owner source")
    manager = ResourceManager(turn.owner, turn.agent.context.id, turn.run_id)
    with workspaces.project_override("pty-project", work):
        original = workspaces.capture(manager, work)
    execution_root = work.parent / "execution-host-A"
    workspaces.restore(manager, original, execution_root)
    scope = workspaces.project_override("pty-project", execution_root, manifest=original)
    scope.__enter__()
    turn.agent.context.set_data("project", "pty-project")
    turn.agent.context._durable_workspace_path = execution_root
    turn.agent.context._durable_workspace_origin = original
    turn.agent.context._durable_resources = {"version": 1, "workspace": original}
    monkeypatch.setattr(CodeExecution, "ensure_cwd", AsyncMock(return_value=str(execution_root)))
    async def execute(args):
        return json.loads((await tool(args).execute(**args)).message)
    try:
        first = await execute({"runtime": "terminal", "code": "alias hello='printf hello'; speak() { printf function; }; value=saved; printf ready"})
        assert first["status"] == "completed" and first["output"] == "ready"
        nodes.first.sync("release", turn.run_id)
        assert nodes.second.sync("claim", turn.run_id)
        turn.owner = nodes.second
        nodes.second.contexts[turn.run_id] = turn.agent.context
        monkeypatch.setenv("A0_DURABILITY_EXECUTION_HOST_ID", "framework-host-B")
        # A separate adapter edits B's imported tree. The next PTY command
        # must stage those changes to A and preserve the settled shell state.
        (turn.agent.context._durable_workspace_path / "from-B").write_text("worker-B")
        resources.snapshot_context(turn.owner, turn.agent.context, turn.run_id)
        turn.active_call_id = "tool:0:1"
        second = await execute({"runtime": "terminal", "code": "cat from-B; hello; speak; printf \"$value\""})
        assert second["output"] == "worker-Bhellofunctionsaved"
        # A foreground read owns the actual terminal. Timeout must leave it
        # alive, and the audited Input tool sends into that same shell.
        cfg["code_exec_timeouts"]["max_exec_timeout"] = .1
        turn.active_call_id = "tool:0:2"
        running = await execute({"runtime": "terminal", "code": "printf once >> effects; read -r answer; printf 'got:%s' \"$answer\""})
        assert running["status"] == "running"
        turn.active_call_id = "tool:0:3"
        cfg["code_exec_timeouts"]["max_exec_timeout"] = 5
        args = {"keyboard": "synthetic answer", "session": 0}
        value = Input(turn.agent, "input", None, args, "", turn.agent.loop_data)
        value.log = None
        assert execution.supports(value, args)
        result = json.loads((await value.execute(**args)).message)
        assert result["status"] == "completed" and result["output"] == "got:synthetic answer"
        assert json.loads((await value.execute(**args)).message) == result
        assert not (work / "effects").exists()
        checkpoint = codec.checkpoint(turn.agent)
        effect = next(row for row in checkpoint["resources"]["workspace"]["files"] if row["path"] == "effects")
        assert manager.get_bytes(effect["ref"]) == b"once"
        assert (turn.agent.context._durable_workspace_path / "effects").read_text() == "once"
        turn.active_call_id = "tool:0:4"
        output = await execute({"runtime": "output"})
        assert output["output"] == "got:synthetic answer"
        turn.active_call_id = "tool:0:5"
        reset = await execute({"runtime": "reset"})
        assert reset["status"] == "completed"
        turn.active_call_id = "tool:0:6"
        clean = await execute({"runtime": "terminal", "code": "printf '%s' \"${value-unset}\"; type hello 2>/dev/null || :"})
        assert clean["output"] == "unset"
        turn.active_call_id = "tool:0:7"
        cfg["code_exec_timeouts"]["max_exec_timeout"] = .1
        pending = await execute({"runtime": "terminal", "code": "while :; do sleep .05; done"})
        assert pending["status"] == "running"
        assert await execution.cancel_sessions(turn.agent.context, turn.run_id) == []
        turn.owner.sync("control", turn.agent.context.id, "cancel")
        assert await execution.cancel_sessions(turn.agent.context, turn.run_id) == [
            {"job_id": pending["job_id"], "status": "cancellation_requested"}]
        deadline = time.monotonic() + 10
        while turn.owner.sync("get_resource_job", pending["job_id"])["status"] != "completed":
            assert time.monotonic() < deadline
            await asyncio.sleep(.05)
        assert turn.owner.sync("get_resource_job", pending["job_id"])["result"]["cancelled"]
    finally:
        scope.__exit__(None, None, None)
        _stop_pty_processes(root)


@pytest.mark.asyncio
async def test_pty_reconstructs_settled_shell_but_never_repeats_unknown_send(shell, monkeypatch):
    import signal
    nodes, turn, tool, cfg, work = shell
    cfg["durability_interactive"] = True
    root = Path(os.environ["A0_DURABILITY_EXECUTION_ROOT"])
    new_root = root.parent / "host-B-jobs"
    turn.agent.context._durable_workspace_origin = {"project_name": "pty-project"}
    turn.agent.context._durable_workspace_path = work
    try:
        args = {"runtime": "terminal", "code": "alias hi='printf alias'; func() { printf function; }; value=state; printf settled"}
        assert json.loads((await tool(args).execute(**args)).message)["output"] == "settled"
        receipt_path, = root.glob("pty-*/ready.json")
        old = json.loads(receipt_path.read_bytes())
        os.kill(old["pid"], signal.SIGKILL)
        os.killpg(old["shell_pid"], signal.SIGKILL)
        turn.active_call_id = "tool:0:1"
        next_args = {"runtime": "terminal", "code": "hi; func; printf \"$value\""}
        result = json.loads((await tool(next_args).execute(**next_args)).message)
        assert result["output"] == "aliasfunctionstate"
        # Lose the relay and shell host at a known prompt, then restore the
        # authenticated declarations into a different managed materialization.
        current = json.loads(receipt_path.read_bytes())
        broker_pid = json.loads(next(root.glob("relay-*/broker.json")).read_bytes())["pid"]
        os.kill(broker_pid, signal.SIGKILL)
        os.kill(current["pid"], signal.SIGKILL)
        os.killpg(current["shell_pid"], signal.SIGKILL)
        from helpers.durable.interactive import manifest_kind
        manager = ResourceManager(turn.owner, turn.agent.context.id, turn.run_id)
        role = "pty:" + manager.get_manifest(manifest_kind(0))["value"]["id"]
        deadline = time.monotonic() + 5
        while not turn.owner.sync("try_role", role):
            assert time.monotonic() < deadline
            await asyncio.sleep(.02)
        turn.owner.sync("release_role", role)
        moved = work.parent / "host-B-workspace"
        moved.mkdir()
        turn.agent.context._durable_workspace_path = moved
        monkeypatch.setenv("A0_DURABILITY_EXECUTION_ROOT", str(new_root))
        monkeypatch.setenv("A0_DURABILITY_EXECUTION_HOST_ID", "new-execution-host")
        turn.active_call_id = "tool:0:2"
        moved_args = {"runtime": "terminal", "code": "hi; func; printf \"$value\"; pwd"}
        restored = json.loads((await tool(moved_args).execute(**moved_args)).message)
        assert restored["output"] == f"aliasfunctionstate{moved}\n"
        receipt_path, = new_root.glob("pty-*/ready.json")
        turn.active_call_id = "tool:0:3"
        cfg["code_exec_timeouts"]["max_exec_timeout"] = .1
        unknown = {"runtime": "terminal", "code": "printf once >> effects; read -r answer; printf finished"}
        assert json.loads((await tool(unknown).execute(**unknown)).message)["status"] == "running"
        current = json.loads(receipt_path.read_bytes())
        os.kill(current["pid"], signal.SIGKILL)
        os.killpg(current["shell_pid"], signal.SIGKILL)
        # A replacement daemon sees fsynced intent and refuses to resend. The
        # original call reuses only a known preview, then later reads hold.
        turn.active_call_id = "tool:0:4"
        with pytest.raises(runtime.RecoveryHeld, match="pty_broker_or_delivery_outcome_unavailable"):
            await tool({"runtime": "output"}).execute(runtime="output")
        assert (moved / "effects").read_text() == "once"
    finally:
        _stop_pty_processes(root)
        _stop_pty_processes(new_root)


@pytest.mark.skipif(not DSN or os.name != "posix", reason="Requires disposable PostgreSQL and POSIX process groups")
def test_supervisor_publishes_after_worker_sigkill_and_never_relaunches(tmp_path, monkeypatch):
    from cryptography.fernet import Fernet
    from helpers.durable.postgres import PostgresStore
    monkeypatch.setenv("A0_DURABILITY_RESOURCE_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("A0_DURABILITY_POSTGRES_DSN", DSN)
    namespace = "execution_" + uuid.uuid4().hex
    environment = dict(os.environ, A0_DURABILITY_JOB_NAMESPACE=namespace)
    worker = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--worker", str(tmp_path)],
                              cwd=PROJECT, env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        _wait(tmp_path / "effect", worker)
        worker.kill(); worker.communicate(timeout=5)
        (tmp_path / "release").touch()
        with PostgresStore(DSN, namespace=namespace) as store:
            deadline = time.monotonic() + 20
            while True:
                row = store.get_resource_job("detached-job")
                if row["status"] == "completed":
                    break
                assert time.monotonic() < deadline
                time.sleep(.05)
            class Owner:
                def sync(self, method, *args, **kwargs):
                    return getattr(store, method)(*args, **kwargs)
            result = row["result"]
            assert ResourceManager(Owner(), "detached-context").get_bytes(result["output"]) == b"finished"
            assert result["exit_code"] == 0
        second = subprocess.run([sys.executable, "-m", "helpers.durable.execution", "--supervise", str(tmp_path / "job")],
                                cwd=PROJECT, env=environment, capture_output=True, timeout=5)
        assert second.returncode == 0, second.stderr.decode()
        assert (tmp_path / "effect").read_text() == "once"
    finally:
        (tmp_path / "release").touch()
        if worker.poll() is None:
            worker.kill(); worker.communicate(timeout=5)


def worker_main(root):
    from helpers.durable.postgres import PostgresStore
    root = Path(root)
    token = "synthetic-append-only-job-token"
    environment = dict(os.environ, A0_DURABILITY_JOB_TOKEN=token)
    with PostgresStore(os.environ["A0_DURABILITY_POSTGRES_DSN"], namespace=environment["A0_DURABILITY_JOB_NAMESPACE"]) as store:
        run = store.admit("detached-context", "detached-input", {}, {"context": {"id": "detached-context"}})
        assert store.claim(run["run_id"])
        fingerprint = hashlib.sha256(b"synthetic-execution").hexdigest()
        store.register_resource_job(run["run_id"], "detached-job", fingerprint, hashlib.sha256(token.encode()).hexdigest())
        directory = execution._private(root / "job")
        spec = {"schema": 1, "job_id": "detached-job", "fingerprint": fingerprint,
                "command": f"printf once >> {shlex.quote(str(root / 'effect'))}; while [ ! -e {shlex.quote(str(root / 'release'))} ]; do sleep .02; done; printf finished",
                "cwd": str(root), "environment": {}, "publish": True, "context_id": "detached-context", "run_id": run["run_id"]}
        execution._write(directory / "spec.json", execution._encoded(spec))
        subprocess.Popen([sys.executable, "-m", "helpers.durable.execution", "--supervise", str(directory)],
                         cwd=PROJECT, env=environment, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
        while True:
            time.sleep(1)


def pty_worker_main(root):
    from types import SimpleNamespace
    from helpers.durable.postgres import PostgresStore
    from helpers.durable import interactive
    root = Path(root)
    with PostgresStore(os.environ["A0_DURABILITY_POSTGRES_DSN"], namespace=os.environ["A0_DURABILITY_JOB_NAMESPACE"]) as store:
        class Owner:
            def __init__(self):
                self.store = store
            def sync(self, method, *args, **kwargs):
                return getattr(store, method)(*args, **kwargs)
        owner = Owner()
        run = store.admit("pty-context", "input", {}, {"context": {"id": "pty-context"}})
        assert store.claim(run["run_id"])
        context = SimpleNamespace(id="pty-context")
        turn = SimpleNamespace(owner=owner, run_id=run["run_id"], agent=SimpleNamespace(context=context))
        manager = ResourceManager(owner, context.id, run["run_id"])
        identifier = hashlib.sha256(store.namespace.encode()).hexdigest()
        spec = {"id": identifier, "cwd": str(root), "host": execution._host_id(), "target": execution._target({"ssh_enabled": False})}
        ref = manager.put_bytes("pty-session", identifier, execution._encoded(spec), sensitive=True)
        session = manager.publish_manifest("execution-pty-0", {"version": 1, "id": identifier,
            "kind": "execution-pty-0", "target": spec["target"], "spec": ref, "queue": [], "sequence": 0}, 0)
        session = interactive._enqueue(turn, manager, session, "pty-command", "command", hashlib.sha256(b"command").hexdigest(),
            "alias hi='printf hi'; fn() { printf fn; }; value=saved; printf once >> effect; read -r answer\nhi; fn; printf \"$value:$answer\"")
        interactive._spawn(turn, manager, session, {"ssh_enabled": False})
        execution._write(root / "run.json", execution._encoded({"run_id": run["run_id"]}))
        while True:
            time.sleep(1)


if __name__ == "__main__":
    (pty_worker_main if sys.argv[1] == "--pty-worker" else worker_main)(sys.argv[2])


@pytest.mark.skipif(not DSN or os.name != "posix", reason="Requires disposable PostgreSQL and POSIX PTY")
def test_shared_pty_continues_stdin_after_actual_framework_worker_sigkill(tmp_path, monkeypatch):
    from cryptography.fernet import Fernet
    from types import SimpleNamespace
    from helpers.durable import interactive
    from helpers.durable.postgres import PostgresStore
    monkeypatch.setenv("A0_DURABILITY_RESOURCE_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("A0_DURABILITY_POSTGRES_DSN", DSN)
    monkeypatch.setenv("A0_DURABILITY_EXECUTION_ROOT", str(tmp_path / "jobs"))
    namespace = "pty_" + uuid.uuid4().hex
    environment = dict(os.environ, A0_DURABILITY_JOB_NAMESPACE=namespace)
    worker = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--pty-worker", str(tmp_path)],
        cwd=PROJECT, env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        _wait(tmp_path / "effect", worker)
        worker.kill(); worker.communicate(timeout=5)
        monkeypatch.setenv("A0_DURABILITY_EXECUTION_HOST_ID", "successor-framework-host")
        with PostgresStore(DSN, namespace=namespace) as store:
            run_id = json.loads((tmp_path / "run.json").read_bytes())["run_id"]
            assert store.claim(run_id)
            class Owner:
                def sync(self, method, *args, **kwargs):
                    return getattr(store, method)(*args, **kwargs)
            owner = Owner()
            manager = ResourceManager(owner, "pty-context", run_id)
            turn = SimpleNamespace(owner=owner, run_id=run_id)
            session = manager.get_manifest("execution-pty-0")
            interactive._enqueue(turn, manager, session, "pty-input", "input", hashlib.sha256(b"input").hexdigest(), "answer")
            deadline = time.monotonic() + 15
            while store.get_resource_job("pty-input")["status"] != "completed":
                assert time.monotonic() < deadline
                time.sleep(.05)
            for identity in ("pty-command", "pty-input"):
                result = store.get_resource_job(identity)["result"]
                assert manager.get_bytes(result["output"]) == b"hifnsaved:answer"
            assert (tmp_path / "effect").read_text() == "once"
            # Repeating admission with the same ID cannot inject input twice.
            interactive._enqueue(turn, manager, manager.get_manifest("execution-pty-0"), "pty-input", "input", hashlib.sha256(b"input").hexdigest(), "answer")
            assert (tmp_path / "effect").read_text() == "once"
    finally:
        if worker.poll() is None:
            worker.kill(); worker.communicate(timeout=5)
        _stop_pty_processes(tmp_path / "jobs")


@pytest.fixture
def ssh_server(tmp_path):
    """An actual authenticated SSH/SFTP target, confined to one temporary home."""
    import socket
    import threading
    import paramiko
    root = tmp_path / "ssh-home"
    root.mkdir()
    key = paramiko.RSAKey.generate(2048)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0)); listener.listen(8); listener.settimeout(.1)
    port = listener.getsockname()[1]
    transports, stopped = [], threading.Event()
    class Files(paramiko.SFTPServerInterface):
        def path(self, path):
            value = Path(path) if path.startswith("/") else root / path
            value = value.resolve()
            if value != root and root not in value.parents:
                raise PermissionError()
            return value
        def canonicalize(self, path):
            return str(self.path(path))
        def stat(self, path):
            try:
                return paramiko.SFTPAttributes.from_stat(self.path(path).stat())
            except OSError as exc:
                return paramiko.SFTPServer.convert_errno(exc.errno)
        lstat = stat
        def list_folder(self, path):
            entries = []
            for item in self.path(path).iterdir():
                attr = paramiko.SFTPAttributes.from_stat(item.lstat())
                attr.filename = item.name
                entries.append(attr)
            return entries
        def mkdir(self, path, attr):
            try:
                self.path(path).mkdir(mode=attr.st_mode or 0o700)
                return paramiko.SFTP_OK
            except OSError as exc:
                return paramiko.SFTPServer.convert_errno(exc.errno)
        def chattr(self, path, attr):
            os.chmod(self.path(path), attr.st_mode)
            return paramiko.SFTP_OK
        def posix_rename(self, oldpath, newpath):
            os.replace(self.path(oldpath), self.path(newpath))
            return paramiko.SFTP_OK
        def open(self, path, flags, attr):
            try:
                descriptor = os.open(self.path(path), flags, attr.st_mode or 0o600)
                mode = "r+b" if flags & os.O_RDWR else "wb" if flags & os.O_WRONLY else "rb"
                stream = os.fdopen(descriptor, mode)
                handle = paramiko.SFTPHandle(flags)
                handle.readfile = stream; handle.writefile = stream
                return handle
            except OSError as exc:
                return paramiko.SFTPServer.convert_errno(exc.errno)
    class Server(paramiko.ServerInterface):
        def check_auth_password(self, username, password):
            return paramiko.AUTH_SUCCESSFUL if (username, password) == ("synthetic", "fixture-only") else paramiko.AUTH_FAILED
        def get_allowed_auths(self, username):
            return "password"
        def check_channel_request(self, kind, channel_id):
            return paramiko.OPEN_SUCCEEDED if kind == "session" else paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED
        def check_channel_exec_request(self, channel, command):
            def run():
                result = subprocess.run(command.decode(), shell=True, cwd=root, capture_output=True)
                channel.sendall(result.stdout); channel.sendall_stderr(result.stderr)
                channel.send_exit_status(result.returncode); channel.close()
            threading.Thread(target=run, daemon=True).start()
            return True
    def accept():
        while not stopped.is_set():
            try:
                connection, _ = listener.accept()
            except (TimeoutError, OSError):
                continue
            transport = paramiko.Transport(connection)
            transport.add_server_key(key)
            transport.set_subsystem_handler("sftp", paramiko.SFTPServer, Files)
            transports.append(transport)
            try:
                transport.start_server(server=Server())
            except (EOFError, OSError, paramiko.SSHException):
                transport.close()  # expected when a killed relay was handshaking
    thread = threading.Thread(target=accept, daemon=True)
    thread.start()
    known = tmp_path / "known_hosts"
    known.write_text(f"[127.0.0.1]:{port} {key.get_name()} {key.get_base64()}\n")
    yield root, port, known
    stopped.set(); listener.close()
    for transport in transports:
        transport.close()
    thread.join(timeout=2)


@pytest.mark.asyncio
async def test_ssh_reconnect_reads_existing_receipt_and_rejects_unknown_host_key(shell, ssh_server, monkeypatch):
    nodes, turn, tool, cfg, work = shell
    remote, port, known = ssh_server
    cfg.update(ssh_enabled=True, ssh_addr="127.0.0.1", ssh_port=port, ssh_user="synthetic",
               ssh_pass="fixture-only", durability_ssh_known_hosts=str(known),
               code_exec_timeouts={"max_exec_timeout": 10})
    monkeypatch.setattr(CodeExecution, "ensure_cwd", AsyncMock(return_value=str(remote)))
    args = {"runtime": "terminal", "code": "printf once >> ssh-effect; printf remote-result"}
    original = ResourceManager.publish_manifest
    def lose_receipt_ack(manager, kind, value, version):
        if kind.startswith("execution-job-") and value.get("status") == "completed":
            raise RuntimeError("Synthetic worker lost the remote receipt acknowledgement")
        return original(manager, kind, value, version)
    with monkeypatch.context() as cut:
        cut.setattr(ResourceManager, "publish_manifest", lose_receipt_ack)
        with pytest.raises(RuntimeError, match="Synthetic worker lost"):
            await tool(args).execute(**args)
    assert (remote / "ssh-effect").read_text() == "once"

    nodes.first.sync("release", turn.run_id)
    assert nodes.second.sync("claim", turn.run_id)
    turn.owner = nodes.second
    nodes.second.contexts[turn.run_id] = turn.agent.context
    result = json.loads((await tool(args).execute(**args)).message)
    assert result["status"] == "completed" and result["output"] == "remote-result"
    assert (remote / "ssh-effect").read_text() == "once"
    turn.active_call_id = "tool:0:1"
    missing = work / "no-known-hosts"
    missing.touch()
    cfg["durability_ssh_known_hosts"] = str(missing)
    with pytest.raises(Exception, match="known_hosts"):
        await tool({"runtime": "terminal", "code": "printf must-not-run >> ssh-effect"}).execute(
            runtime="terminal", code="printf must-not-run >> ssh-effect")
    assert (remote / "ssh-effect").read_text() == "once"


@pytest.mark.asyncio
async def test_ssh_pty_relay_survives_framework_relay_loss_without_forwarding_database_secrets(shell, ssh_server, monkeypatch):
    import signal
    from helpers.durable import workspaces
    nodes, turn, tool, cfg, work = shell
    remote, port, known = ssh_server
    root = Path(os.environ["A0_DURABILITY_EXECUTION_ROOT"])
    cfg.update(ssh_enabled=True, ssh_addr="127.0.0.1", ssh_port=port, ssh_user="synthetic",
        ssh_pass="fixture-only", durability_ssh_known_hosts=str(known), durability_interactive=True,
        code_exec_timeouts={"max_exec_timeout": 15})
    monkeypatch.setattr(CodeExecution, "ensure_cwd", AsyncMock(return_value=str(remote)))
    (work / "base").write_text("owner project")
    manager = ResourceManager(turn.owner, turn.agent.context.id, turn.run_id)
    with workspaces.project_override("ssh-project", work):
        manifest = workspaces.capture(manager, work)
    scope = workspaces.project_override("ssh-project", work, manifest=manifest)
    scope.__enter__()
    turn.agent.context.set_data("project", "ssh-project")
    turn.agent.context._durable_workspace_path = work
    turn.agent.context._durable_workspace_origin = manifest
    turn.agent.context._durable_resources = {"version": 1, "workspace": manifest}
    try:
        attachment = manager.put_bytes("attachment", "synthetic-input", b" shared-input", sensitive=True)
        args = {"runtime": "terminal", "code": "alias hi='printf remote'; function fn() { printf function; }; value=saved; printf settled; cat a0-resource://" + attachment["id"]}
        first = json.loads((await tool(args).execute(**args)).message)
        assert first["output"] == "settled shared-input"
        pid = json.loads(next(root.glob("relay-*/broker.json")).read_bytes())["pid"]
        os.kill(pid, signal.SIGKILL)
        nodes.first.sync("release", turn.run_id)
        assert nodes.second.sync("claim", turn.run_id)
        turn.owner = nodes.second
        nodes.second.contexts[turn.run_id] = turn.agent.context
        turn.active_call_id = "tool:0:1"
        second_args = {"runtime": "terminal", "code": "hi; fn; printf \"$value\"; printf once >> ssh-pty-effect; pwd; env | grep '^A0_DURABILITY_' || :"}
        second = json.loads((await tool(second_args).execute(**second_args)).message)
        assert second["status"] == "completed" and second["output"] == f"remotefunctionsaved{turn.agent.context._durable_workspace_path}\n"
        assert (turn.agent.context._durable_workspace_path / "ssh-pty-effect").read_text() == "once"
        assert not (work / "ssh-pty-effect").exists()
        repeated = json.loads((await tool(second_args).execute(**second_args)).message)
        assert repeated["output"] == f"remotefunctionsaved{turn.agent.context._durable_workspace_path}\n"
        assert (turn.agent.context._durable_workspace_path / "ssh-pty-effect").read_text() == "once"
        # Uploaded daemon/requests contain no database DSN, key, or append-only
        # capability; SSH credentials remain on the framework relay too.
        for path in (remote / ".a0-durable-pty").rglob("*.json"):
            content = path.read_text()
            assert DSN not in content and os.environ["A0_DURABILITY_RESOURCE_KEY"] not in content
            assert "fixture-only" not in content and '"token"' not in content
        # Loss of all target receipts cannot make a replacement's empty PTY
        # look like successful completion of an earlier foreground operation.
        import shutil
        turn.active_call_id = "tool:0:2"
        cfg["code_exec_timeouts"]["max_exec_timeout"] = .1
        outside = remote / "unknown-effects"
        uncertain = {"runtime": "terminal", "code": "printf once >> " + shlex.quote(str(outside)) + "; read -r answer"}
        assert json.loads((await tool(uncertain).execute(**uncertain)).message)["status"] == "running"
        daemon_receipt, = (remote / ".a0-durable-pty").glob("*/ready.json")
        daemon = json.loads(daemon_receipt.read_bytes())
        os.kill(daemon["pid"], signal.SIGKILL)
        os.killpg(daemon["shell_pid"], signal.SIGKILL)
        os.kill(json.loads(next(root.glob("relay-*/broker.json")).read_bytes())["pid"], signal.SIGKILL)
        shutil.rmtree(daemon_receipt.parent)
        turn.active_call_id = "tool:0:3"
        with pytest.raises(runtime.RecoveryHeld, match="pty_broker_or_delivery_outcome_unavailable"):
            await tool({"runtime": "output"}).execute(runtime="output")
        assert outside.read_text() == "once"
    finally:
        scope.__exit__(None, None, None)
        _stop_pty_processes(root)
        for receipt in (remote / ".a0-durable-pty").glob("*/ready.json"):
            value = json.loads(receipt.read_bytes())
            for pid, group in ((value["pid"], False), (value["shell_pid"], True)):
                try:
                    (os.killpg if group else os.kill)(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass


@pytest.mark.parametrize("override", ["builtin_function", "set_alias", "prompt_array"])
def test_pty_restore_rejects_framing_overrides_before_repeating_effects(tmp_path, override):
    from plugins._code_execution.helpers.durable_pty import Shell
    root = tmp_path / "pty"
    root.mkdir(mode=0o700)
    marker = root / "effects"
    quoted = shlex.quote(str(marker))
    if override == "builtin_function":
        code = 'builtin() { if [[ "$1" == printf ]]; then command printf x >> ' + quoted + '; fi; command builtin "$@"; }\n'
    elif override == "set_alias":
        code = "alias set=" + shlex.quote("printf x >> " + quoted + "; builtin set") + "\n"
    else:
        code = "PROMPT_COMMAND=(__a0_capture " + shlex.quote("command printf x >> " + quoted) + ")\n"
    script = root / "define.sh"
    script.write_text(code)
    shell = Shell(root, {"id": "framing-review", "cwd": str(root)})
    try:
        shell.ready = False
        shell.send(("builtin source -- " + shlex.quote(str(script)) + "\n").encode())
        shell.wait_ready(10)
        state = shell.state
        assert not state["portable"]
    finally:
        shell.close()
    before = marker.read_bytes() if marker.exists() else b""
    # Compatibility with old or tampered receipts must not trust the former
    # portable flag. The actual saved declarations are checked before spawn.
    with pytest.raises(ValueError, match="overrides framing"):
        Shell(root, {"id": "framing-review", "cwd": str(root), "restore": dict(state, portable=True)})
    assert (marker.read_bytes() if marker.exists() else b"") == before
