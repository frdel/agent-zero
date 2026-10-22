"""Durable execution policy and compatibility receipts.

Local POSIX supervisors survive their framework worker and publish encrypted
results using an append-only resource capability. New sessions use the detached
PTY broker in interactive.py; legacy batch receipts remain readable and are
never converted into fresh command submissions.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import secrets
import shlex
import signal
import stat
import subprocess
import sys
import time
import types

MAX_OUTPUT = 8 * 1024 * 1024
PUBLIC_OUTPUT = 64 * 1024
SCHEMA = 1


def _held(reason):
    from helpers.durable.runtime import RecoveryHeld
    raise RecoveryHeld(reason)


def _encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _digest(value):
    return hashlib.sha256(_encoded(value)).hexdigest()


def _core_class(tool, expected):
    cls = type(tool)
    if cls.__qualname__ != expected.__qualname__ or cls.__bases__ != expected.__bases__:
        return False
    methods = {name for name, value in expected.__dict__.items() if callable(value)}
    if ({name for name, value in cls.__dict__.items() if callable(value)} != methods
            or any(name in tool.__dict__ for name in methods)):
        return False
    # Core tools are executed by helpers.modules under a short module name.
    # Python class identity differs; source plus code identity must not.
    for name, method in expected.__dict__.items():
        expected_code = getattr(method, "__code__", None)
        if type(expected_code) is not types.CodeType:
            continue
        actual_code = getattr(cls.__dict__.get(name), "__code__", None)
        if (type(actual_code) is not types.CodeType or Path(actual_code.co_filename).resolve() != Path(expected_code.co_filename).resolve()
                or actual_code.co_qualname != expected_code.co_qualname
                or actual_code.co_code != expected_code.co_code or actual_code.co_consts != expected_code.co_consts):
            return False
    execute = getattr(cls.__dict__.get("execute"), "__code__", None)
    expected_execute = expected.__dict__["execute"].__code__
    return type(execute) is types.CodeType and Path(execute.co_filename).resolve() == Path(expected_execute.co_filename).resolve()


def supports(tool, args):
    from plugins._code_execution.tools.code_execution_tool import CodeExecution
    from plugins._code_execution.tools.input import Input
    if not isinstance(args, dict):
        return False
    if _core_class(tool, Input):
        return (not set(args) - {"keyboard", "session"}
                and isinstance(args.get("keyboard", ""), str)
                and len(args.get("keyboard", "").encode()) <= 1024 * 1024
                and type(args.get("session", 0)) is int and 0 <= args.get("session", 0) <= 63)
    if not _core_class(tool, CodeExecution):
        return False
    if set(args) - {"runtime", "code", "session", "reset"}:
        return False
    mode = str(args.get("runtime", "")).strip().lower()
    session = args.get("session", 0)
    if type(session) is not int or not 0 <= session <= 63 or type(args.get("reset", False)) is not bool:
        return False
    return (mode in {"output", "reset"} or mode in {"terminal", "python", "nodejs"}
            and isinstance(args.get("code"), str) and len(args["code"].encode()) <= 1024 * 1024)


def _arguments(tool, args):
    from helpers.durable.codec import masked
    from helpers.durable.resources import canonical_value
    return canonical_value(tool.agent.context, masked(tool.agent, args))


def _job_id(turn, call_id=None):
    call_id = call_id or turn.active_call_id
    if not call_id:
        _held("execution_call_identity_missing")
    return hashlib.sha256(f"{turn.agent.context.id}:{turn.run_id}:{call_id}".encode()).hexdigest()


def _manager(turn, **kwargs):
    from helpers.durable.resources import ResourceManager
    return ResourceManager(turn.owner, turn.agent.context.id, run_id=turn.run_id, **kwargs)


def can_resume(tool, args, call):
    """An unresolved body is resumable only through its committed job manifest."""
    if not supports(tool, args):
        return False
    from helpers.durable.runtime import current
    turn = current(tool.agent)
    if not turn or not getattr(turn.owner, "distributed", False):
        return False
    from helpers.durable import interactive
    if interactive.can_resume(tool, args, call):
        return True
    if "keyboard" in args:
        return False
    mode = str(args["runtime"]).strip().lower()
    if mode in {"output", "reset"}:
        return True  # read-only polling or idempotent reset of one receipt owner
    return bool(_manager(turn).get_manifest("execution-job-" + _job_id(turn, call["call_id"])))


def _private(directory):
    directory = Path(directory)
    if directory.is_symlink():
        raise ValueError("Execution directory cannot be a symlink")
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    for path in [directory, *directory.parents]:
        if path.is_symlink():
            raise ValueError("Execution path cannot contain a symlink")
    os.chmod(directory, 0o700)
    return directory


def _write(path, data):
    path = Path(path)
    temporary = path.with_name(path.name + "." + secrets.token_hex(8))
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _read(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Execution receipt is missing or unsafe")
    return json.loads(path.read_bytes())


def _host_id():
    configured = os.environ.get("A0_DURABILITY_EXECUTION_HOST_ID")
    if configured:
        return hashlib.sha256(configured.encode()).hexdigest()
    return hashlib.sha256(os.uname().nodename.encode()).hexdigest()


def _local_root():
    from helpers import files
    return _private(os.environ.get("A0_DURABILITY_EXECUTION_ROOT") or files.get_abs_path("usr/durability/execution"))


def _target(cfg):
    if cfg["ssh_enabled"]:
        return {"mode": "ssh", "host": cfg["ssh_addr"], "port": cfg["ssh_port"], "user": cfg["ssh_user"],
                "host_key": cfg["durability_ssh_host_key"]}
    if os.name != "posix":
        _held("durable_execution_requires_posix")
    return {"mode": "local", "host": _host_id()}


def _command(mode, code):
    if mode == "terminal":
        return code
    if mode == "python":
        return "ipython -c " + shlex.quote(code)
    if mode == "nodejs":
        return "node /exe/node_eval.js " + shlex.quote(code)
    _held("unsupported_execution_runtime")


def _workspace(turn):
    context = turn.agent.context
    origin = getattr(context, "_durable_workspace_origin", None)
    path = getattr(context, "_durable_workspace_path", None)
    if not origin:
        origin = (turn.owner.sync("get_run", turn.run_id).get("checkpoint", {}).get("resources") or {}).get("workspace")
    if origin and not path:
        from helpers import projects
        path = projects.get_project_folder(origin["project_name"])
    return {"root": str(Path(path).resolve()), "project": origin["project_name"]} if origin and path else None


def _portable_shell_state(state, workspace):
    if not state or not workspace:
        return state
    root = workspace["root"].rstrip("/")
    prefix = "a0-workspace://" + workspace["project"]
    from helpers.durable.resources import canonical_value
    context = types.SimpleNamespace(_durable_workspace_path=root,
                                    _durable_workspace_origin={"project_name": workspace["project"]})
    cwd = state["cwd"]
    within = cwd == root or cwd.startswith(root + "/")
    value = dict(state, portable=within)
    if within:
        value["cwd"] = prefix + cwd[len(root):]
    exported, mapped_keys = {}, []
    for key, item in state["set"].items():
        # Map session state only. Commands arrive localized by the tool boundary
        # and retain their canonical argument fingerprint.
        mapped = canonical_value(context, item)
        if mapped != item:
            mapped_keys.append(key)
        exported[key] = mapped
        remainder = mapped.replace(prefix, "WORKSPACE")
        if remainder.startswith("/") or ":/" in remainder or " /" in remainder:
            value["portable"] = False
    value["set"] = exported
    value["workspace_exports"] = mapped_keys
    return value


def _restore_shell_state(turn, state, moved):
    if state is None:
        _held("execution_shell_state_unavailable_reset_required")
    value = dict(state)
    if str(value.get("cwd", "")).startswith("a0-workspace://"):
        workspace = _workspace(turn)
        if not workspace:
            _held("execution_workspace_unavailable")
        prefix = "a0-workspace://" + workspace["project"]
        if value["cwd"] != prefix and not value["cwd"].startswith(prefix + "/"):
            _held("execution_workspace_changed")
        if moved and not value.get("portable"):
            _held("execution_environment_host_adapter_required")
        value["cwd"] = workspace["root"] + value["cwd"][len(prefix):]
        from helpers.durable.resources import local_value
        context = types.SimpleNamespace(_durable_workspace_path=workspace["root"],
                                        _durable_workspace_origin={"project_name": workspace["project"]})
        value["set"] = {key: local_value(context, item) if key in value.get("workspace_exports", []) else item
                        for key, item in value["set"].items()}
    elif moved:
        _held("execution_cwd_host_adapter_required")
    return value


def _snapshot_env():
    # Capability/database/encryption credentials belong to the supervisor only.
    return {key: value for key, value in os.environ.items()
            if not key.startswith("A0_DURABILITY_") and key not in {"SHLVL", "PWD", "OLDPWD", "_"}}


def _ssh(cfg):
    import paramiko
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    known_hosts = cfg.get("durability_ssh_known_hosts")
    if known_hosts:
        client.load_host_keys(known_hosts)
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    client.connect(cfg["ssh_addr"], cfg["ssh_port"], cfg["ssh_user"], cfg["ssh_pass"],
                   allow_agent=False, look_for_keys=False, timeout=10, auth_timeout=10, banner_timeout=10)
    actual = hashlib.sha256(client.get_transport().get_remote_server_key().asbytes()).hexdigest()
    if cfg.get("durability_ssh_host_key") and cfg["durability_ssh_host_key"] != actual:
        client.close()
        raise ValueError("SSH target identity changed")
    return client


def _ssh_identity(cfg):
    with _ssh(cfg) as client:
        return hashlib.sha256(client.get_transport().get_remote_server_key().asbytes()).hexdigest()


def _remote(cfg, operation, job_id, spec=None):
    """Each reconnect fetches an existing identity; read/reset never submit it."""
    with _ssh(cfg) as client:
        sftp = client.open_sftp()
        try:
            base = sftp.normalize(".").rstrip("/") + "/.a0-durable-jobs"
            root = base + "/" + job_id
            if operation == "submit":
                for directory in (base, root):
                    try:
                        info = sftp.lstat(directory)
                        if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077:
                            raise ValueError("Remote execution directory is unsafe")
                    except FileNotFoundError:
                        sftp.mkdir(directory, mode=0o700)
                # A remote identity with any launch evidence cannot be replaced.
                for name in ("spec.json", "started.json", "result.json"):
                    try:
                        sftp.lstat(root + "/" + name)
                    except FileNotFoundError:
                        continue
                    raise ValueError("Remote job identity already exists")
                for name, data in (("supervisor.py", Path(__file__).read_bytes()), ("spec.json", _encoded(spec))):
                    with sftp.open(root + "/" + name, "wx") as stream:
                        stream.write(data)
                    sftp.chmod(root + "/" + name, 0o600)
                command = "nohup python3 " + shlex.quote(root + "/supervisor.py") + " --supervise " + shlex.quote(root) + " </dev/null >/dev/null 2>&1 &"
                _, output, error = client.exec_command(command, timeout=10)
                if output.channel.recv_exit_status() != 0:
                    raise RuntimeError("Remote supervisor submission was not acknowledged")
                return {"root": root}
            if operation == "cancel":
                with sftp.open(root + "/spec.json", "rb") as stream:
                    original = json.loads(stream.read(MAX_OUTPUT))
                if not spec or original.get("job_id") != job_id or original.get("fingerprint") != spec.get("fingerprint"):
                    raise ValueError("Remote execution identity changed")
                with sftp.open(root + "/cancel", "w") as stream:
                    stream.write(b"cancel")
                sftp.chmod(root + "/cancel", 0o600)
            receipt = None
            try:
                with sftp.open(root + "/result.json", "rb") as stream:
                    receipt = json.loads(stream.read(MAX_OUTPUT))
            except FileNotFoundError:
                pass
            try:
                with sftp.open(root + "/output", "rb") as stream:
                    output = stream.read(MAX_OUTPUT)
            except FileNotFoundError:
                output = b""
            started = False
            try:
                sftp.lstat(root + "/started.json")
                started = True
            except FileNotFoundError:
                pass
            return {"receipt": receipt, "output": output, "started": started}
        finally:
            sftp.close()


def _local_read(job):
    if job["target"] != {"mode": "local", "host": _host_id()}:
        _held("local_execution_host_unavailable")
    root = Path(job["root"])
    if root.is_symlink() or not root.is_dir():
        _held("execution_submission_outcome_unknown")
    spec = _read(root / "spec.json")
    if spec.get("job_id") != job["id"] or spec.get("fingerprint") != job["fingerprint"]:
        _held("execution_result_fingerprint_changed")
    receipt = _read(root / "result.json") if (root / "result.json").exists() else None
    output_path = root / "output"
    if output_path.is_symlink():
        _held("execution_output_integrity")
    output = output_path.read_bytes()[:MAX_OUTPUT] if output_path.exists() else b""
    started = _read(root / "started.json") if (root / "started.json").exists() else None
    if started and (started.get("job_id") != job["id"] or started.get("fingerprint") != job["fingerprint"]):
        _held("execution_result_fingerprint_changed")
    return {"receipt": receipt, "output": output, "started": bool(started)}


async def _observe(turn, manager, job, cfg):
    if getattr(turn.owner, "distributed", False) and job["target"]["mode"] == "local":
        row = await turn.owner.io("get_resource_job", job["id"])
        if row and row.get("status") == "completed":
            value = row["result"]
            if value["fingerprint"] != job["fingerprint"]:
                _held("execution_result_fingerprint_changed")
            return value
    try:
        observed = await asyncio.to_thread(_remote, cfg, "read", job["id"]) if job["target"]["mode"] == "ssh" else _local_read(job)
    except (OSError, ValueError):
        _held("execution_receipt_unreachable")
    receipt = observed["receipt"]
    if receipt:
        if receipt.get("fingerprint") != job["fingerprint"] or receipt.get("job_id") != job["id"]:
            _held("execution_result_fingerprint_changed")
        output = manager.put_bytes("execution-output", job["id"], observed["output"], sensitive=True)
        state = manager.put_bytes("execution-state", job["id"], _encoded(receipt.get("state")), sensitive=True)
        return {"job_id": job["id"], "fingerprint": job["fingerprint"], "status": "completed",
                "exit_code": receipt["exit_code"], "output": output, "state": state,
                "cancelled": bool(receipt.get("cancelled")), "truncated": bool(receipt.get("truncated"))}
    if not observed["started"]:
        _held("execution_submission_outcome_unknown")
    return {"job_id": job["id"], "status": "running", "output_bytes": observed["output"]}


async def reconcile(tool, args):
    from helpers.durable.runtime import current
    from helpers.durable import codec
    from helpers.tool import Response
    from plugins._code_execution.tools.code_execution_tool import _get_config, _resolve_ssh_pass
    if not supports(tool, args):
        _held("durable_execution_mode_requires_adapter")
    turn = current(tool.agent)
    if not turn or not turn.active_call_id:
        _held("execution_call_identity_missing")
    if not getattr(turn.owner, "distributed", False):
        _held("execution_shared_resources_required")
    manager = _manager(turn)
    identifier = _job_id(turn)
    from helpers.durable import interactive
    # Old journal identities retain their original execution protocol. All
    # newly configured sessions use the persistent interactive broker.
    prior_batch = manager.get_manifest("execution-session-" + str(args.get("session", 0)))
    if ("keyboard" in args or manager.get_manifest(interactive.manifest_kind(args.get("session", 0)))
            or _get_config(tool.agent).get("durability_interactive", True)
            and not prior_batch and not manager.get_manifest("execution-job-" + identifier)):
        return await interactive.reconcile(tool, args)
    kind = "execution-job-" + identifier
    saved = manager.get_manifest(kind)
    job = saved["value"] if saved else None
    if job and job.get("result"):
        expected = _digest({"schema": SCHEMA, "args": _arguments(tool, args), "target": job["target"]})
        if expected != job["fingerprint"]:
            _held("execution_command_fingerprint_changed")
        return _response(tool, manager, job["result"])
    cfg = _get_config(tool.agent)
    if cfg["ssh_enabled"]:
        cfg["ssh_pass"] = await _resolve_ssh_pass(cfg["ssh_pass"])
        cfg["durability_ssh_host_key"] = await asyncio.to_thread(_ssh_identity, cfg)
    target = _target(cfg)
    session_id = args.get("session", 0)
    session_kind = "execution-session-" + str(session_id)
    session = manager.get_manifest(session_kind)
    previous = session["value"] if session else {}
    mode = str(args["runtime"]).strip().lower()
    if previous and previous.get("target") != target:
        local_reader = previous["target"]["mode"] == target["mode"] == "local"
        if not local_reader:
            _held("execution_target_changed")
    state = None
    created = job is None
    if previous.get("job_id") and job is None:
        old = manager.get_manifest("execution-job-" + previous["job_id"])
        if not old:
            _held("execution_session_receipt_missing")
        old_job = old["value"]
        old_result = old_job.get("result") or await _observe(turn, manager, old_job, cfg)
        if mode == "reset" or args.get("reset"):
            if old_result["status"] != "completed":
                if target["mode"] == "ssh":
                    await asyncio.to_thread(_remote, cfg, "cancel", old_job["id"], {"fingerprint": old_job["fingerprint"]})
                else:
                    _local_read(old_job)
                    _write(Path(old_job["root"]) / "cancel", b"cancel")
                deadline = time.monotonic() + 10
                while old_result["status"] != "completed" and time.monotonic() < deadline:
                    await asyncio.sleep(.1)
                    old_result = await _observe(turn, manager, old_job, cfg)
                if old_result["status"] != "completed":
                    _held("execution_cancel_outcome_unknown")
            manager.publish_manifest(session_kind, {"schema": SCHEMA, "target": target}, session["version"])
            if mode == "reset":
                return Response("Durable execution session reset. Existing effects were not undone.", False)
            previous, session = {}, manager.get_manifest(session_kind)
        elif old_result["status"] != "completed" and old_job["id"] != identifier:
            text = codec.masked(tool.agent, old_result.get("output_bytes", b"").decode(errors="replace"))
            return Response(json.dumps({"job_id": old_job["id"], "status": "running", "output": text[-PUBLIC_OUTPUT:]}), False)
        elif mode == "output":
            return _response(tool, manager, old_result)
        elif old_result["status"] == "completed" and old_result.get("state"):
            state = _restore_shell_state(turn, json.loads(manager.get_bytes(old_result["state"])), previous["target"] != target)
    if mode == "reset":
        manager.publish_manifest(session_kind, {"schema": SCHEMA, "target": target}, session["version"] if session else 0)
        return Response("Durable execution session reset.", False)
    if mode == "output":
        return Response("No durable execution job is recorded for this session.", False)
    fingerprint = _digest({"schema": SCHEMA, "args": _arguments(tool, args), "target": job["target"] if job else target})
    if job:
        if job["fingerprint"] != fingerprint or (job["target"] != target and not job["target"]["mode"] == target["mode"] == "local"):
            _held("execution_command_fingerprint_changed")
    else:
        cwd = state["cwd"] if state else await tool.ensure_cwd()
        spec = {"schema": SCHEMA, "job_id": identifier, "fingerprint": fingerprint,
                "command": _command(mode, args["code"]), "cwd": cwd,
                "environment": state or {}, "publish": bool(getattr(turn.owner, "distributed", False) and target["mode"] == "local"),
                "context_id": tool.agent.context.id, "run_id": turn.run_id,
                "workspace": _workspace(turn) if target["mode"] == "local" else None}
        # Resolved commands and exported variables are private resource bytes.
        private_spec = manager.put_bytes("execution-spec", identifier, _encoded(spec), sensitive=True)
        token = secrets.token_urlsafe(32)
        if spec["publish"]:
            turn.owner.sync("register_resource_job", turn.run_id, identifier, fingerprint, hashlib.sha256(token.encode()).hexdigest())
        root = str(_local_root() / identifier) if target["mode"] == "local" else None
        job = {"schema": SCHEMA, "id": identifier, "run_id": turn.run_id, "call_id": turn.active_call_id,
               "fingerprint": fingerprint, "target": target,
               "spec": private_spec, "root": root, "status": "submitted"}
        # This is the one-way submission boundary. A missing launch/receipt after
        # this commit is uncertainty, never permission for a replacement command.
        saved = manager.publish_manifest(kind, job, 0)
        manager.publish_manifest(session_kind, {"schema": SCHEMA, "target": target, "job_id": identifier}, session["version"] if session else 0)
        await turn.owner.wait_for_ancestors(turn.run_id, getattr(tool.agent.context, "_durable_origin", None))
        if target["mode"] == "ssh":
            await asyncio.to_thread(_remote, cfg, "submit", identifier, spec)
        else:
            directory = _private(root)
            _write(directory / "spec.json", _encoded(spec))
            environment = dict(os.environ)
            environment["A0_DURABILITY_JOB_TOKEN"] = token
            environment["A0_DURABILITY_JOB_NAMESPACE"] = getattr(turn.owner.store, "namespace", "agent_zero")
            subprocess.Popen([sys.executable, "-m", "helpers.durable.execution", "--supervise", str(directory)],
                             cwd=str(Path(__file__).resolve().parents[2]), env=environment,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True, close_fds=True)
    deadline = time.monotonic() + max(0.1, min(600, cfg["code_exec_timeouts"].get("max_exec_timeout", 240)))
    startup_deadline = time.monotonic() + 5
    result = job.get("result")
    while result is None or result["status"] != "completed":
        try:
            result = await _observe(turn, manager, job, cfg)
        except BaseException as exc:
            from helpers.durable.runtime import RecoveryHeld
            if (created and isinstance(exc, RecoveryHeld) and str(exc) == "execution_submission_outcome_unknown"
                    and time.monotonic() < startup_deadline):
                await asyncio.sleep(.05)
                continue
            raise
        if result["status"] == "completed" or time.monotonic() >= deadline:
            break
        await asyncio.sleep(.1)
    if result["status"] == "completed" and not job.get("result"):
        job = dict(job, status="completed", result=result)
        manager.publish_manifest(kind, job, saved["version"])
    return _response(tool, manager, result)


async def cancel_sessions(context, run_id=None):
    """Signal matching jobs only for a recorded Stop, never worker disappearance.

    Signalling is best effort and cannot retract effects already dispatched.
    A request acknowledgement is not a terminal command receipt.
    """
    from types import SimpleNamespace
    from helpers.durable.runtime import current, service, RecoveryHeld
    from helpers.durable.store import StaleRunError
    from helpers.durable.resources import ResourceManager
    from plugins._code_execution.tools.code_execution_tool import _get_config, _resolve_ssh_pass
    turn = current(context.agent0)
    owner = turn.owner if turn else service()
    run_id = run_id or (turn.run_id if turn else None)
    if owner is None or not getattr(owner, "distributed", False) or not run_id:
        return []
    try:
        run = await owner.io("get_run", run_id)
        generation = owner.sync("document_generation", context.id)
    except (StaleRunError, KeyError):
        return []
    if (run["context_id"] != context.id or run["status"] != "cancelled"
            or run["generation"] != generation):
        return []
    manager = ResourceManager(owner, context.id)
    from helpers.durable import interactive
    results, cfg = await interactive.cancel_sessions(context, owner, run_id), None
    for index in range(64):
        session = manager.get_manifest("execution-session-" + str(index))
        if not session or not session["value"].get("job_id"):
            continue
        recorded = manager.get_manifest("execution-job-" + session["value"]["job_id"])
        if not recorded:
            continue
        job = recorded["value"]
        if job.get("run_id") != run_id or job.get("status") == "completed":
            continue
        try:
            identity = SimpleNamespace(run_id=run_id, agent=context.agent0, active_call_id=job.get("call_id"))
            if job["id"] != _job_id(identity):
                _held("execution_job_identity_changed")
            spec = json.loads(manager.get_bytes(job["spec"]))
            if (spec["job_id"] != job["id"] or spec["run_id"] != run_id
                    or spec["context_id"] != context.id or spec["fingerprint"] != job["fingerprint"]):
                _held("execution_job_identity_changed")
            # Reset/delete between inventory and signalling revokes this scope.
            fresh = await owner.io("get_run", run_id)
            if fresh["status"] != "cancelled" or fresh["generation"] != owner.sync("document_generation", context.id):
                continue
            if job["target"]["mode"] == "local":
                row = await owner.io("get_resource_job", job["id"])
                if row and row["status"] == "completed":
                    continue
                _local_read(job)  # identity, host and regular-file checks
                _write(Path(job["root"]) / "cancel", b"cancel")
            else:
                if cfg is None:
                    cfg = _get_config(context.agent0)
                    if not cfg["ssh_enabled"]:
                        _held("execution_target_changed")
                    cfg["ssh_pass"] = await _resolve_ssh_pass(cfg["ssh_pass"])
                    cfg["durability_ssh_host_key"] = await asyncio.to_thread(_ssh_identity, cfg)
                if _target(cfg) != job["target"]:
                    _held("execution_target_changed")
                await asyncio.to_thread(_remote, cfg, "cancel", job["id"], {"fingerprint": job["fingerprint"]})
            results.append({"job_id": job["id"], "status": "cancellation_requested"})
        except (Exception, RecoveryHeld):
            results.append({"job_id": job["id"], "status": "cancellation_unknown"})
    return results


def _response(tool, manager, result):
    from helpers.durable import codec
    from helpers.tool import Response
    output = manager.get_bytes(result["output"]) if result.get("output") else result.get("output_bytes", b"")
    text = codec.masked(tool.agent, output.decode("utf-8", errors="replace"))
    message = {"job_id": result["job_id"], "status": result["status"], "output": text[-PUBLIC_OUTPUT:]}
    for key in ("exit_code", "cancelled", "truncated"):
        if key in result:
            message[key] = result[key]
    if getattr(tool, "log", None):
        tool.log.update(content=json.dumps(message, ensure_ascii=False))
    return Response(json.dumps(message, ensure_ascii=False), False)


def _capture(path, exit_code):
    _write(Path(path), _encoded({"cwd": os.getcwd(), "environment": _snapshot_env(), "exit_code": int(exit_code)}))


def _supervise(directory):
    import fcntl
    import selectors
    directory = _private(directory)
    descriptor = os.open(directory / "supervisor.lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return
    spec = _read(directory / "spec.json")
    if (directory / "result.json").exists() or (directory / "started.json").exists():
        return  # A second controller invocation never replays an uncertain job.
    _write(directory / "started.json", _encoded({"job_id": spec["job_id"], "fingerprint": spec["fingerprint"]}))
    environment = _snapshot_env()
    base = dict(environment)
    snapshot = spec.get("environment") or {}
    environment.update(snapshot.get("set", {}))
    for name in snapshot.get("unset", []):
        environment.pop(name, None)
    environment.update(PAGER="cat", GIT_PAGER="cat")
    capture = directory / "shell-state.json"
    script = directory / "command.sh"
    _write(script, spec["command"].encode())
    capture_command = " ".join(shlex.quote(item) for item in [sys.executable, str(Path(__file__).resolve()), "--capture", str(capture)])
    trap = shlex.quote(capture_command + ' "$?"')
    command = f"trap {trap} EXIT\nsource {shlex.quote(str(script))}\n"
    cancelled, truncated, output_size = False, False, 0
    if (directory / "cancel").exists():
        _write(directory / "output", b"")
        receipt = {"schema": SCHEMA, "job_id": spec["job_id"], "fingerprint": spec["fingerprint"],
                   "exit_code": -9, "state": None, "cancelled": True, "truncated": False}
        _write(directory / "result.json", _encoded(receipt))
        if spec.get("publish"):
            _publish_result(spec, receipt, directory)
        return
    process = subprocess.Popen(["/bin/bash", "--noprofile", "--norc", "-c", command], cwd=spec.get("cwd") or None,
                               env=environment, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, start_new_session=True)
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    with (directory / "output").open("wb") as stream:
        os.chmod(directory / "output", 0o600)
        while selector.get_map():
            if (directory / "cancel").exists() and process.poll() is None:
                cancelled = True
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            for key, _ in selector.select(.1):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                allowed = max(0, MAX_OUTPUT - output_size)
                stream.write(chunk[:allowed]); stream.flush()
                output_size += min(allowed, len(chunk))
                truncated |= len(chunk) > allowed
        os.fsync(stream.fileno())
    exit_code = process.wait()
    state = None
    if capture.exists():
        captured = _read(capture)
        final = captured["environment"]
        state = {"cwd": captured["cwd"], "set": {key: value for key, value in final.items() if base.get(key) != value},
                 "unset": [key for key in base if key not in final]}
        capture.unlink()
    state = _portable_shell_state(state, spec.get("workspace"))
    receipt = {"schema": SCHEMA, "job_id": spec["job_id"], "fingerprint": spec["fingerprint"],
               "exit_code": exit_code, "state": state, "cancelled": cancelled, "truncated": truncated}
    _write(directory / "result.json", _encoded(receipt))
    if spec.get("publish"):
        _publish_result(spec, receipt, directory)


def _publish_result(spec, receipt, directory):
    # This process has no workflow claim. Its capability can append private bytes
    # and one matching result, never start calls, change history or resume work.
    from helpers.durable.postgres import PostgresStore
    from helpers.durable.resources import ResourceManager
    token = os.environ["A0_DURABILITY_JOB_TOKEN"]
    with PostgresStore(os.environ["A0_DURABILITY_POSTGRES_DSN"], namespace=os.environ["A0_DURABILITY_JOB_NAMESPACE"]) as store:
        class Owner:
            def sync(self, method, *args, **kwargs):
                return getattr(store, method)(*args, **kwargs)
        manager = ResourceManager(Owner(), spec["context_id"], job_id=spec["job_id"], job_token=token)
        output = manager.put_bytes("execution-output", spec["job_id"], (directory / "output").read_bytes(), sensitive=True)
        state = manager.put_bytes("execution-state", spec["job_id"], _encoded(receipt["state"]), sensitive=True)
        result = {"job_id": spec["job_id"], "fingerprint": spec["fingerprint"], "status": "completed",
                  "exit_code": receipt["exit_code"], "state": state, "output": output,
                  "cancelled": receipt["cancelled"], "truncated": receipt["truncated"]}
        store.finish_resource_job(spec["job_id"], token, result)


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--capture":
        _capture(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 3 and sys.argv[1] == "--supervise":
        _supervise(sys.argv[2])
    else:
        raise SystemExit("Expected --supervise JOB_DIRECTORY")
