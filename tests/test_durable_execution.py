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
    config = {"ssh_enabled": False, "code_exec_timeouts": {"max_exec_timeout": 5}, "ssh_pass": ""}
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


if __name__ == "__main__":
    worker_main(sys.argv[2])


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
        def mkdir(self, path, attr):
            try:
                self.path(path).mkdir(mode=attr.st_mode or 0o700)
                return paramiko.SFTP_OK
            except OSError as exc:
                return paramiko.SFTPServer.convert_errno(exc.errno)
        def chattr(self, path, attr):
            os.chmod(self.path(path), attr.st_mode)
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
            transport.start_server(server=Server())
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
