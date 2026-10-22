"""Shared, claim-fenced PTY queue and detached local/SSH receipt relay.

Only workflow owners append requests. A relay holds a pinned database role and
consumes one-use job capabilities before delivery. It never owns a workflow or
replays a request whose delivery intent already exists.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import signal
import stat
import subprocess
import sys
import time
from types import SimpleNamespace

from helpers.durable import execution as batch

VERSION = 1
QUEUE_LIMIT = 128
PTY_SOURCE = Path(__file__).resolve().parents[2] / "plugins/_code_execution/helpers/durable_pty.py"


def _context(workspace):
    return SimpleNamespace(_durable_workspace_path=workspace["root"] if workspace else None,
        _durable_workspace_origin={"project_name": workspace["project"]} if workspace else None)


def _canonical(value, workspace):
    from helpers.durable.resources import canonical_value
    return canonical_value(_context(workspace), value)


def _state(value, workspace, paths=None):
    state = _canonical(value, workspace)
    if paths:
        from helpers.durable.resources import _replace
        state = _replace(state, paths)
    if state:
        text = json.dumps([state.get("variables", {}), state.get("functions", ""), state.get("aliases", "")])
        text = re.sub(r"a0-workspace://[^\s\\\"']+", "WORKSPACE", text)
        if re.search(r"(?:=|[\s\"'])/(?!/)", text):
            state["portable"] = False
    return state


def _localized(value, workspace, manager, paths=None):
    from helpers.durable.resources import local_value, _replace
    value = local_value(_context(workspace), value)
    uris = set(re.findall(r"a0-resource://[a-f0-9]{64}", json.dumps(value)))
    replacements = {uri: str(manager.materialize(manager.reference(uri))) for uri in uris}
    if paths is not None:
        paths.update({path: uri for uri, path in replacements.items()})
    return _replace(value, replacements)


def _cfg(tool):
    from plugins._code_execution.tools.code_execution_tool import _get_config
    return _get_config(tool.agent)


def _kind(args):
    return "input" if "keyboard" in args else str(args["runtime"]).strip().lower()


def manifest_kind(session):
    return "execution-pty-" + str(session)


def can_resume(tool, args, call):
    from helpers.durable.runtime import current
    turn = current(tool.agent)
    if not turn or not getattr(turn.owner, "distributed", False):
        return False
    manager = batch._manager(turn)
    identifier = batch._job_id(turn, call["call_id"])
    if manager.get_manifest("execution-pty-job-" + identifier):
        return True
    # No queue consumer can see this call before its operation manifest and
    # capability exist. This is proven non-dispatch, rather than permission to
    # repeat an operation with an unknown outcome.
    return (not turn.owner.sync("get_resource_job", identifier)
            and not manager.get_manifest("execution-job-" + identifier)
            and not manager.get_manifest("execution-session-" + str(args.get("session", 0)))
            and _cfg(tool).get("durability_interactive", True))


def _enqueue(turn, manager, session, identifier, operation, fingerprint, data=""):
    existing = turn.owner.sync("get_resource_job", identifier)
    if existing:
        if existing["fingerprint"] != fingerprint or existing["run_id"] != turn.run_id:
            batch._held("pty_operation_identity_changed")
    # Publish the encrypted capability descriptor only after the matching job
    # exists. Crash gaps here contain no delivery permission and are safe to
    # complete from the recorded descriptor, never from freshly changed args.
    envelope_kind = "execution-pty-request-" + identifier
    envelope = manager.get_manifest(envelope_kind)
    if not envelope:
        context = getattr(getattr(turn, "agent", None), "context", None)
        workspace = (getattr(context, "_durable_resources", {}) or {}).get("workspace")
        token = secrets.token_urlsafe(32)
        descriptor = {"id": identifier, "run_id": turn.run_id, "kind": operation,
                      "fingerprint": fingerprint, "data": data, "token": token, "workspace": workspace}
        ref = manager.put_bytes("pty-request", identifier, batch._encoded(descriptor), sensitive=True)
        envelope = manager.publish_manifest(envelope_kind, {"request": ref}, 0)
    ref = envelope["value"]["request"]
    descriptor = json.loads(manager.get_bytes(ref))
    if (descriptor["id"] != identifier or descriptor["run_id"] != turn.run_id
            or descriptor["fingerprint"] != fingerprint or descriptor["kind"] != operation
            or descriptor["data"] != data):
        batch._held("pty_operation_identity_changed")
    turn.owner.sync("register_resource_job", turn.run_id, identifier, fingerprint,
                    hashlib.sha256(descriptor["token"].encode()).hexdigest())
    value = dict(session["value"])
    queue = []
    for item in value.get("queue", []):
        if item["id"] == identifier:
            return session
        row = turn.owner.sync("get_resource_job", item["id"])
        if row and row["status"] != "completed":
            queue.append(item)
    # Keep the latest terminal snapshot reachable for a broker replacement.
    for item in reversed(value.get("queue", [])):
        row = turn.owner.sync("get_resource_job", item["id"])
        if row and row["status"] == "completed" and (row.get("result") or {}).get("state"):
            value["last_state"] = row["result"]["state"]
            if row["result"].get("workspace"):
                value["last_workspace"] = row["result"]["workspace"]
            break
    if len(queue) >= QUEUE_LIMIT:
        batch._held("pty_queue_capacity_reached")
    sequence = value.get("sequence", 0) + 1
    queue.append({"id": identifier, "request": ref, "sequence": sequence, "workspace": descriptor.get("workspace")})
    value.update(queue=queue, sequence=sequence, latest=identifier)
    return manager.publish_manifest(value["kind"], value, session["version"])


def _spawn(turn, manager, session, cfg):
    # The contender acquires the pinned session role BEFORE touching any shell.
    # Starting two contenders is harmless; a failed role acquisition exits.
    root = batch._private(batch._local_root() / ("relay-" + session["value"]["id"]))
    launch = {"context_id": turn.agent.context.id, "kind": session["value"]["kind"],
              "session_id": session["value"]["id"], "workspace": batch._workspace(turn),
              "host": batch._host_id()}
    path = root / (secrets.token_hex(16) + ".json")
    batch._write(path, batch._encoded(launch))
    environment = dict(os.environ)
    environment["A0_DURABILITY_JOB_NAMESPACE"] = turn.owner.store.namespace
    # SSH credentials live only in the relay environment, never a manifest or
    # target. The command daemon on that target has no database capability.
    if cfg["ssh_enabled"]:
        environment["A0_DURABILITY_PTY_SSH_CONFIG"] = json.dumps({key: cfg[key] for key in (
            "ssh_enabled", "ssh_addr", "ssh_port", "ssh_user", "ssh_pass", "durability_ssh_known_hosts", "durability_ssh_host_key")})
    subprocess.Popen([sys.executable, "-m", "helpers.durable.interactive", str(path)],
        cwd=str(Path(__file__).resolve().parents[2]), env=environment,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True, close_fds=True)


def _response(tool, manager, result):
    if result.get("workspace_error"):
        batch._held("execution_workspace_requires_reconciliation")
    if result.get("workspace"):
        from helpers.durable.resources import adopt_workspace_result
        context = tool.agent.context
        if context.get_data("project") != result["workspace"]["project_name"]:
            batch._held("execution_workspace_project_changed")
        present = (getattr(context, "_durable_resources", {}) or {}).get("workspace")
        if not present or present["digest"] != result["workspace"]["digest"]:
            adopt_workspace_result(manager, context, result["workspace"])
    from helpers.durable.resources import local_value
    response = batch._response(tool, manager, result)
    response.message = local_value(tool.agent.context, response.message)
    workspace = batch._workspace(SimpleNamespace(agent=tool.agent, owner=manager.owner, run_id=manager.run_id))
    if workspace:
        data = json.loads(response.message)
        data["output"] = data["output"].replace("a0-workspace://" + workspace["project"], workspace["root"])
        for path, uri in getattr(tool.agent.context, "_durable_resource_paths", {}).items():
            data["output"] = data["output"].replace(uri, path)
        response.message = json.dumps(data, ensure_ascii=False)
    return response


async def reconcile(tool, args):
    from helpers.durable.runtime import current
    from helpers.tool import Response
    from plugins._code_execution.tools.code_execution_tool import _resolve_ssh_pass
    turn = current(tool.agent)
    if not turn or not turn.active_call_id or not getattr(turn.owner, "distributed", False):
        batch._held("execution_shared_resources_required")
    turn.owner.sync("assert_owner", turn.run_id)
    manager = batch._manager(turn)
    identifier = batch._job_id(turn)
    job_kind = "execution-pty-job-" + identifier
    job = manager.get_manifest(job_kind)
    fingerprint = batch._digest({"version": VERSION, "args": batch._arguments(tool, args)})
    if job:
        if job["value"]["fingerprint"] != fingerprint:
            batch._held("pty_operation_identity_changed")
        result = turn.owner.sync("get_resource_job", identifier)
        if result and result["status"] == "completed":
            return _response(tool, manager, result["result"])
    cfg = _cfg(tool)
    if cfg["ssh_enabled"]:
        cfg["ssh_pass"] = await _resolve_ssh_pass(cfg["ssh_pass"])
        cfg["durability_ssh_host_key"] = await asyncio.to_thread(batch._ssh_identity, cfg)
    kind = manifest_kind(args.get("session", 0))
    session = manager.get_manifest(kind)
    mode = _kind(args)
    if not session:
        if mode in {"output", "input"}:
            return Response("No durable PTY session is recorded.", False)
        cwd = await tool.ensure_cwd()
        target = batch._target(cfg)
        session_id = batch._digest([turn.owner.store.namespace, tool.agent.context.id,
                                   turn.owner.sync("document_generation", tool.agent.context.id), kind])
        spec = {"id": session_id, "cwd": _canonical(cwd, batch._workspace(turn)),
                "host": batch._host_id(), "target": target}
        project = (getattr(turn.agent.context, "_durable_resources", {}) or {}).get("workspace")
        ref = manager.put_bytes("pty-session", session_id, batch._encoded(spec), sensitive=True)
        session = manager.publish_manifest(kind, {"version": VERSION, "id": session_id, "kind": kind,
            "target": target, "spec": ref, "workspace": project, "queue": [], "sequence": 0}, 0)
    value = session["value"]
    if value["target"]["mode"] == "ssh" and batch._target(cfg) != value["target"]:
        batch._held("execution_target_changed")
    if not job:
        operation = {"output": "read", "reset": "reset", "input": "input"}.get(mode, "command")
        if operation == "command" and not args.get("reset"):
            for item in value["queue"]:
                row = turn.owner.sync("get_resource_job", item["id"])
                if row and row["status"] != "completed":
                    old = json.loads(manager.get_bytes(item["request"]))
                    if old["kind"] in {"command", "input"}:
                        operation = "read"  # preserve the busy-session guard
                        break
        data = ""
        if operation == "command":
            data = args["code"] if mode == "terminal" else batch._command(mode, args["code"])
        elif operation == "input":
            data = args["keyboard"].rstrip()
        from helpers.durable.resources import canonical_value
        data = canonical_value(turn.agent.context, data)
        # The manifest records the complete request before queue publication;
        # recovery uses this descriptor, never regenerated input bytes.
        job = manager.publish_manifest(job_kind, {"version": VERSION, "id": identifier,
            "fingerprint": fingerprint, "kind": kind, "operation": operation,
            "data": manager.put_bytes("pty-command", identifier, data.encode(), sensitive=True)}, 0)
    else:
        operation = job["value"]["operation"]
        data = manager.get_bytes(job["value"]["data"]).decode()
    # If a process died after registration but before queue CAS, retain its
    # original capability in the job manifest rather than generating another.
    if not any(item["id"] == identifier for item in session["value"]["queue"]):
        if args.get("reset") and operation == "command":
            session = _enqueue(turn, manager, session, identifier + ":reset", "reset",
                               batch._digest([fingerprint, "reset"]))
        session = _enqueue(turn, manager, session, identifier, operation, fingerprint, data)
    await turn.owner.wait_for_ancestors(turn.run_id, getattr(turn.agent.context, "_durable_origin", None))
    _spawn(turn, manager, session, cfg)
    timeout = cfg.get("output_timeouts" if mode == "output" else "code_exec_timeouts", {}).get("max_exec_timeout", 240)
    deadline = time.monotonic() + max(.1, min(600, timeout))
    while True:
        row = await turn.owner.io("get_resource_job", identifier)
        if row["status"] == "completed":
            return _response(tool, manager, row["result"])
        if time.monotonic() >= deadline:
            break
        await asyncio.sleep(.05)
    # Output snapshots are read-only jobs. They may settle independently while
    # the original command still owns the foreground PTY.
    preview = identifier + ":preview"
    latest = manager.get_manifest(kind)
    _enqueue(turn, manager, latest, preview, "read", batch._digest([fingerprint, "preview"]))
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        row = await turn.owner.io("get_resource_job", preview)
        if row and row["status"] == "completed":
            result = dict(row["result"], job_id=identifier)
            original = turn.owner.sync("get_resource_job", identifier)
            if original and original["status"] != "completed":
                result["status"] = "running"
            return _response(tool, manager, result)
        await asyncio.sleep(.05)
    batch._held("pty_broker_or_delivery_outcome_unavailable")


async def cancel_sessions(context, owner, run_id):
    """Best-effort wakeup; only an authoritative Stop can cancel PTY sends."""
    from helpers.durable.resources import ResourceManager
    manager = ResourceManager(owner, context.id)
    results = []
    for index in range(64):
        session = manager.get_manifest(manifest_kind(index))
        if not session:
            continue
        cancelled = []
        for item in session["value"].get("queue", []):
            row = owner.sync("get_resource_job", item["id"])
            if row and row["run_id"] == run_id and row["status"] != "completed":
                cancelled.append(item["id"])
        if not cancelled:
            continue
        run = owner.sync("get_run", run_id)
        if (run["status"] != "cancelled" or run["generation"] != owner.sync("document_generation", context.id)):
            continue
        target = session["value"]["target"]
        if target == {"mode": "local", "host": batch._host_id()}:
            root = batch._local_root() / ("pty-" + session["value"]["id"])
            if root.exists() and batch._read(root / "session.json")["id"] == session["value"]["id"]:
                batch._write(root / "cancel.json", batch._encoded(cancelled))
        # Cross-host/SSH relays also poll this shared Stop. No loss of a worker
        # or claim is interpreted as cancellation, and no terminal is invented.
        results.extend({"job_id": identity, "status": "cancellation_requested"} for identity in cancelled)
    return results


class LocalTransport:
    def __init__(self, root, spec):
        from plugins._code_execution.helpers import durable_pty
        self.root = batch._private(root)
        for name in ("queue", "receipts"):
            batch._private(self.root / name)
        if not (self.root / "session.json").exists():
            durable_pty.write(self.root / "session.json", spec)
        elif durable_pty.read(self.root / "session.json")["id"] != spec["id"]:
            raise ValueError("PTY session identity changed")
        self.workspace = durable_pty.read(self.root / "session.json").get("workspace")
        self.resource_paths = self.read("resources.json") or {}
        self.ensure()

    def ensure(self):
        import fcntl
        if (self.root / "blocked.json").exists():
            return False
        fd = os.open(self.root / "daemon.lock", os.O_CREAT | os.O_RDWR, 0o600)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return (self.root / "ready.json").exists()
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
        subprocess.Popen([sys.executable, str(PTY_SOURCE), str(self.root)],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True, close_fds=True)
        return False

    def read(self, name):
        path = self.root / name
        return batch._read(path) if path.exists() else None

    def put(self, name, value):
        from plugins._code_execution.helpers import durable_pty
        path = self.root / name
        if path.exists() and name.startswith("queue/"):
            if durable_pty.read(path) != value:
                raise ValueError("PTY request identity changed")
            return
        durable_pty.write(path, value)

    def stage(self, manager, manifest, identifier):
        from helpers.durable import workspaces
        path = self.root / ("workspace-" + identifier)
        workspaces.restore_for_job(manager, manifest, path)
        return {"root": str(path), "project": manifest["project_name"]}

    def localize(self, value, workspace, manager):
        value = _localized(value, workspace, manager, self.resource_paths)
        self.put("resources.json", self.resource_paths)
        return value

    def export(self, workspace, manifest, identifier):
        return Path(workspace["root"])


class SSHTransport:
    """Receipt relay to a private persistent daemon, with pinned SSH identity."""
    def __init__(self, cfg, spec, project=None):
        self.cfg = cfg
        with batch._ssh(cfg) as client:
            sftp = client.open_sftp()
            try:
                base = sftp.normalize(".").rstrip("/") + "/.a0-durable-pty"
                self.root = base + "/" + spec["id"]
                if project:
                    spec = dict(spec, cwd=self.root, workspace=None, restore=None)
                for path in (base, self.root, self.root + "/queue", self.root + "/receipts"):
                    try:
                        info = sftp.lstat(path)
                        if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077:
                            raise ValueError("Unsafe remote PTY directory")
                    except FileNotFoundError:
                        sftp.mkdir(path, mode=0o700)
                for name, data in (("daemon.py", PTY_SOURCE.read_bytes()), ("session.json", batch._encoded(spec))):
                    try:
                        sftp.lstat(self.root + "/" + name)
                    except FileNotFoundError:
                        with sftp.open(self.root + "/" + name, "wx") as out:
                            out.write(data)
                        sftp.chmod(self.root + "/" + name, 0o600)
                with sftp.open(self.root + "/session.json", "rb") as inp:
                    stored = json.loads(inp.read(batch.MAX_OUTPUT))
                    if stored["id"] != spec["id"]:
                        raise ValueError("Remote PTY session identity changed")
                    self.workspace = stored.get("workspace")
                try:
                    with sftp.open(self.root + "/resources.json", "rb") as inp:
                        self.resource_paths = json.loads(inp.read(batch.MAX_OUTPUT))
                except FileNotFoundError:
                    self.resource_paths = {}
                command = "nohup python3 " + shlex.quote(self.root + "/daemon.py") + " " + shlex.quote(self.root) + " </dev/null >/dev/null 2>&1 &"
                _, output, _ = client.exec_command(command, timeout=10)
                if output.channel.recv_exit_status() != 0:
                    raise RuntimeError("Remote PTY daemon launch unacknowledged")
                self.last_start = time.monotonic()
            finally:
                sftp.close()

    def ensure(self):
        if self.read("blocked.json"):
            return False
        if time.monotonic() - self.last_start > 1:
            with batch._ssh(self.cfg) as client:
                command = "nohup python3 " + shlex.quote(self.root + "/daemon.py") + " " + shlex.quote(self.root) + " </dev/null >/dev/null 2>&1 &"
                _, output, _ = client.exec_command(command, timeout=10)
                if output.channel.recv_exit_status() != 0:
                    return False
            self.last_start = time.monotonic()
        return bool(self.read("ready.json"))

    def read(self, name):
        with batch._ssh(self.cfg) as client:
            with client.open_sftp() as sftp:
                try:
                    with sftp.open(self.root + "/" + name, "rb") as inp:
                        return json.loads(inp.read(batch.MAX_OUTPUT))
                except FileNotFoundError:
                    return None

    def put(self, name, value):
        with batch._ssh(self.cfg) as client:
            with client.open_sftp() as sftp:
                path = self.root + "/" + name
                try:
                    with sftp.open(path, "rb") as inp:
                        old = json.loads(inp.read(batch.MAX_OUTPUT))
                    if name.startswith("queue/"):
                        if old != value:
                            raise ValueError("Remote PTY request identity changed")
                        return
                except FileNotFoundError:
                    pass
                temporary = path + "." + secrets.token_hex(8)
                with sftp.open(temporary, "wx") as out:
                    out.write(batch._encoded(value))
                sftp.chmod(temporary, 0o600)
                sftp.posix_rename(temporary, path)

    @staticmethod
    def _directory(sftp, path):
        try:
            info = sftp.lstat(path)
            if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077:
                raise ValueError("Remote project directory is unsafe")
        except FileNotFoundError:
            sftp.mkdir(path, mode=0o700)

    def stage(self, manager, manifest, identifier):
        from helpers.durable import workspaces
        workspaces._validate(manifest)
        manager.owner.sync("assert_resource_job", manager.job_id, manager.job_token)
        root = self.root + "/workspace-" + identifier
        with batch._ssh(self.cfg) as client:
            with client.open_sftp() as sftp:
                try:
                    sftp.lstat(root)
                except FileNotFoundError:
                    sftp.mkdir(root, mode=0o700)
                else:
                    raise ValueError("Remote staged project identity already exists")
                for name in manifest["directories"]:
                    self._directory(sftp, root + "/" + name)
                for row in manifest["files"]:
                    name = root + "/" + row["path"]
                    # File paths and parent order were validated by the shared
                    # workspace codec; no archive or target symlink is followed.
                    parent = str(Path(row["path"]).parent)
                    if parent != ".":
                        for part in reversed(Path(parent).parents):
                            if str(part) != ".":
                                self._directory(sftp, root + "/" + str(part))
                        self._directory(sftp, root + "/" + parent)
                    with sftp.open(name, "wx") as out:
                        out.write(manager.get_bytes(row["ref"]))
                    sftp.chmod(name, 0o700 if row["executable"] else 0o600)
        return {"root": root, "project": manifest["project_name"]}

    def localize(self, value, workspace, manager):
        from helpers.durable.resources import local_value, _replace
        value = local_value(_context(workspace), value)
        uris = set(re.findall(r"a0-resource://[a-f0-9]{64}", json.dumps(value)))
        replacements = {}
        if uris:
            with batch._ssh(self.cfg) as client:
                with client.open_sftp() as sftp:
                    self._directory(sftp, self.root + "/resources")
                    for uri in uris:
                        ref = manager.reference(uri)
                        path = self.root + "/resources/" + ref["id"]
                        data = manager.get_bytes(ref)
                        try:
                            info = sftp.lstat(path)
                            if not stat.S_ISREG(info.st_mode):
                                raise ValueError("Remote resource path is unsafe")
                            with sftp.open(path, "rb") as inp:
                                if inp.read(batch.MAX_OUTPUT + 1) != data:
                                    raise ValueError("Remote resource identity changed")
                        except FileNotFoundError:
                            with sftp.open(path, "wx") as out:
                                out.write(data)
                            sftp.chmod(path, 0o600)
                        replacements[uri] = path
                        self.resource_paths[path] = uri
            self.put("resources.json", self.resource_paths)
        return _replace(value, replacements)

    def export(self, workspace, manifest, identifier):
        from helpers.durable import workspaces
        mirror = batch._private(batch._local_root() / ("remote-tree-" + identifier + "-" + secrets.token_hex(8)))
        with batch._ssh(self.cfg) as client:
            with client.open_sftp() as sftp:
                def inventory():
                    found = {}
                    def visit(relative=""):
                        if len(Path(relative).parts) > workspaces.MAX_DEPTH:
                            raise workspaces.WorkspaceHeld("workspace_depth_limit")
                        for entry in sftp.listdir_attr(workspace["root"] + ("/" + relative if relative else "")):
                            if entry.filename in workspaces._EXCLUDED:
                                continue
                            name = relative + "/" + entry.filename if relative else entry.filename
                            workspaces._path(name)
                            if stat.S_ISLNK(entry.st_mode) or not (stat.S_ISREG(entry.st_mode) or stat.S_ISDIR(entry.st_mode)):
                                raise workspaces.WorkspaceHeld("workspace_links_or_special_files_unsupported")
                            found[name] = (entry.st_mode, entry.st_size, entry.st_mtime)
                            if len(found) > workspaces.MAX_FILES:
                                raise workspaces.WorkspaceHeld("workspace_file_count_limit")
                            if stat.S_ISDIR(entry.st_mode):
                                visit(name)
                    visit()
                    return found
                before = inventory()
                total, hashes = 0, {}
                for name, (mode, size, _) in sorted(before.items()):
                    path = mirror / name
                    if stat.S_ISDIR(mode):
                        batch._private(path)
                        continue
                    if size > workspaces.MAX_FILE_BYTES:
                        raise workspaces.WorkspaceHeld("workspace_file_size_limit")
                    total += size
                    if total > workspaces.MAX_TOTAL_BYTES:
                        raise workspaces.WorkspaceHeld("workspace_total_size_limit")
                    batch._private(path.parent)
                    with sftp.open(workspace["root"] + "/" + name, "rb") as inp:
                        data = inp.read(workspaces.MAX_FILE_BYTES + 1)
                    workspaces._check_content(Path(name), data)
                    if len(data) != size:
                        raise workspaces.WorkspaceHeld("workspace_changed_during_capture")
                    batch._write(path, data)
                    path.chmod(0o700 if mode & 0o111 else 0o600)
                    hashes[name] = hashlib.sha256(data).hexdigest()
                if inventory() != before:
                    raise workspaces.WorkspaceHeld("workspace_changed_during_capture")
                # SFTP timestamps have coarse precision. Verify file bytes a
                # second time so same-size writes cannot pass on mtime alone.
                for name, digest in hashes.items():
                    with sftp.open(workspace["root"] + "/" + name, "rb") as inp:
                        if hashlib.sha256(inp.read(workspaces.MAX_FILE_BYTES + 1)).hexdigest() != digest:
                            raise workspaces.WorkspaceHeld("workspace_changed_during_capture")
        return mirror


def _result(store, owner, context_id, descriptor, receipt, workspace, *, tree=None, tree_manifest=None, paths=None):
    from helpers.durable.resources import ResourceManager
    manager = ResourceManager(owner, context_id, job_id=descriptor["id"], job_token=descriptor["token"])
    rendered = receipt["output"]
    if workspace:
        # stdout is display text, so concatenated `printf` output can put a
        # path after an ordinary letter. Unlike executable arguments, it must
        # not retain a previous host's root merely for lacking a word boundary.
        rendered = rendered.replace(workspace["root"], "a0-workspace://" + workspace["project"])
    for path, uri in (paths or {}).items():
        rendered = rendered.replace(path, uri)
    output = manager.put_bytes("execution-output", descriptor["id"], rendered.encode()[:batch.MAX_OUTPUT], sensitive=True)
    state = _state(receipt.get("state"), workspace, paths)
    ref = manager.put_bytes("pty-state", descriptor["id"], batch._encoded(state), sensitive=True) if state else None
    result = {"job_id": descriptor["id"], "fingerprint": descriptor["fingerprint"],
        "status": receipt["status"], "exit_code": receipt.get("exit_code"), "output": output,
        "state": ref, "cancelled": bool(receipt.get("cancelled")), "truncated": False}
    if receipt.get("workspace_error"):
        result["workspace_error"] = "workspace_capture_requires_reconciliation"
    if tree and tree_manifest:
        from helpers.durable import workspaces
        try:
            with workspaces.project_override(tree_manifest["project_name"], tree, manifest=tree_manifest):
                result["workspace"] = workspaces.capture(manager, tree)
        except workspaces.WorkspaceHeld:
            # The command outcome remains known even if coherent, safe file
            # capture is unavailable. Never re-execute it to rebuild the tree.
            result["workspace_error"] = "workspace_capture_requires_reconciliation"
    store.finish_resource_job(descriptor["id"], descriptor["token"], result)
    return result


def broker(path):
    from helpers.durable.postgres import PostgresStore
    from helpers.durable.resources import ResourceManager
    launch = batch._read(path)
    Path(path).unlink()
    namespace = os.environ["A0_DURABILITY_JOB_NAMESPACE"]
    role = "pty:" + launch["session_id"]
    with PostgresStore(os.environ["A0_DURABILITY_POSTGRES_DSN"], namespace=namespace) as store:
        if not store.try_role(role):
            return
        batch._write(Path(path).parent / "broker.json", batch._encoded({"pid": os.getpid(), "session": launch["session_id"], "host": launch["host"]}))
        class Owner:
            def sync(self, method, *args, **kwargs):
                return getattr(store, method)(*args, **kwargs)
        owner = Owner()
        manager = ResourceManager(owner, launch["context_id"])
        session = manager.get_manifest(launch["kind"])
        if not session or session["value"]["id"] != launch["session_id"]:
            return
        value = session["value"]
        spec = json.loads(manager.get_bytes(value["spec"]))
        workspace = launch.get("workspace")
        startup_paths = {}
        project = value.get("last_workspace") or value.get("workspace")
        if spec["target"]["mode"] == "local":
            spec = _localized(spec, workspace, manager)
            spec["workspace"] = workspace
        if spec["target"]["mode"] == "local" and spec["host"] != launch["host"]:
            if not workspace or not value.get("last_state"):
                return  # an absolute old-host cwd is never new-host authority
            # A new shell can restore only a demonstrably settled prompt.
            if any(store.get_resource_job(item["id"])["status"] == "running" for item in value["queue"]):
                return
            state = json.loads(manager.get_bytes(value["last_state"]))
            if not state or not state.get("portable") or not str(state["cwd"]).startswith("a0-workspace://"):
                return
            spec["restore"] = _localized(state, workspace, manager, startup_paths)
            spec["cwd"] = spec["restore"]["cwd"]
        if spec["target"]["mode"] == "ssh":
            cfg = json.loads(os.environ["A0_DURABILITY_PTY_SSH_CONFIG"])
            if batch._target(cfg) != spec["target"]:
                return
            transport = SSHTransport(cfg, spec, project)
            workspace = transport.workspace
            if workspace is None:
                project = None
        else:
            transport = LocalTransport(batch._local_root() / ("pty-" + launch["session_id"]), spec)
            workspace = transport.workspace
        if startup_paths:
            transport.resource_paths.update(startup_paths)
            transport.put("resources.json", transport.resource_paths)
        idle = time.monotonic()
        while store.try_role(role):  # same pinned session; no reconnect path
            session = manager.get_manifest(launch["kind"])
            if not session or session["value"]["id"] != launch["session_id"]:
                return
            pending, cancelled = False, []
            ready = transport.ensure()
            unknown_delivery = False
            for item in session["value"].get("queue", []):
                row = store.get_resource_job(item["id"])
                if row and row["status"] == "running":
                    descriptor = json.loads(manager.get_bytes(item["request"]))
                    if (descriptor["kind"] in ("command", "input", "reset")
                            and not transport.read("receipts/" + item["id"] + ".intent")
                            and not transport.read("receipts/" + item["id"] + ".result")):
                        unknown_delivery = True
            for item in session["value"].get("queue", []):
                row = store.get_resource_job(item["id"])
                if not row or row["status"] == "completed":
                    continue
                pending = True
                descriptor = json.loads(manager.get_bytes(item["request"]))
                if (descriptor["id"] != item["id"] or descriptor["fingerprint"] != row["fingerprint"]
                        or descriptor.get("workspace") != item.get("workspace")):
                    raise ValueError("PTY capability identity changed")
                receipt = transport.read("receipts/" + item["id"] + ".result")
                if receipt:
                    if receipt["id"] != item["id"] or receipt["fingerprint"] != row["fingerprint"]:
                        raise ValueError("PTY receipt identity changed")
                    current = transport.read("workspace.json")
                    if current:
                        workspace = current["workspace"]
                    tree = None
                    if workspace and project:
                        from helpers.durable.workspaces import WorkspaceHeld
                        try:
                            tree = transport.export(workspace, project, item["id"])
                        except (WorkspaceHeld, OSError, ValueError):
                            receipt = dict(receipt, workspace_error=True)
                    result = _result(store, owner, launch["context_id"], descriptor, receipt, workspace,
                                     tree=tree, tree_manifest=project, paths=transport.read("resources.json"))
                    if result.get("workspace"):
                        project = result["workspace"]
                    continue
                run = store.get_run(descriptor["run_id"])
                if run["status"] == "cancelled":
                    if row["status"] == "submitted":
                        _result(store, owner, launch["context_id"], descriptor, {
                            "status": "completed", "output": "Cancelled before PTY delivery.",
                            "exit_code": None, "state": None, "cancelled": True}, workspace)
                        continue
                    cancelled.append(item["id"])
                    continue
                if run["status"] != "running" or run["checkpoint"].get("paused"):
                    continue
                if row["status"] == "submitted":
                    if not ready or unknown_delivery:
                        continue
                    # Atomic one-use external delivery intent. If anything
                    # fails after this point, no broker may resend the bytes.
                    from helpers.durable.store import OwnershipError
                    try:
                        begun = store.begin_resource_job(item["id"], descriptor["token"], role)
                    except OwnershipError:
                        # Pause/control can race the preceding projection read.
                        # An unconsumed grant waits; lost roles/sessions stop.
                        if not store.try_role(role):
                            return
                        continue
                    if begun:
                        from helpers.durable.resources import ResourceManager
                        job_manager = ResourceManager(owner, launch["context_id"], job_id=item["id"], job_token=descriptor["token"])
                        request = {key: child for key, child in descriptor.items() if key != "token"}
                        request.pop("workspace", None)  # refs/capabilities stay on the relay
                        desired = item.get("workspace")
                        if desired and descriptor["kind"] in ("command", "input") and (not project or desired["digest"] != project["digest"]):
                            if descriptor["kind"] != "command":
                                _result(store, owner, launch["context_id"], descriptor, {
                                    "status": "completed", "output": "", "state": None, "workspace_error": True}, workspace)
                                continue
                            prompt = transport.read("prompt.json")
                            if workspace is None and session["value"].get("last_state"):
                                restored = json.loads(manager.get_bytes(session["value"]["last_state"]))
                                prompt = {"state": restored} if restored and restored.get("portable") else None
                            if not prompt or not prompt["state"].get("portable"):
                                _result(store, owner, launch["context_id"], descriptor, {
                                    "status": "completed", "output": "", "state": None, "workspace_error": True}, workspace)
                                continue
                            state = _state(prompt["state"], workspace, transport.read("resources.json"))
                            if not state.get("portable"):
                                _result(store, owner, launch["context_id"], descriptor, {
                                    "status": "completed", "output": "", "state": None, "workspace_error": True}, workspace)
                                continue
                            staged = transport.stage(job_manager, desired, item["id"])
                            if workspace is None:
                                state["cwd"] = "a0-workspace://" + desired["project_name"]
                            elif not str(state["cwd"]).startswith("a0-workspace://"):
                                _result(store, owner, launch["context_id"], descriptor, {
                                    "status": "completed", "output": "", "state": None, "workspace_error": True}, workspace)
                                continue
                            state = transport.localize(state, staged, job_manager)
                            request["rebind"] = {"workspace": staged, "restore": state}
                            workspace, project = staged, desired
                        request["data"] = transport.localize(request["data"], workspace, job_manager)
                        transport.put("queue/" + f'{item["sequence"]:020d}-' + item["id"] + ".json", request)
            if cancelled:
                transport.put("cancel.json", cancelled)
            if pending:
                idle = time.monotonic()
            elif time.monotonic() - idle > 300:
                return
            time.sleep(.1)


if __name__ == "__main__":
    broker(sys.argv[1])
