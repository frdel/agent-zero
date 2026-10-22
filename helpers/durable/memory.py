"""Recover known memory mutations from the atomic shared index receipt."""
import hashlib
import inspect
from pathlib import Path


def source(name, digest):
    paths = {"MemorySave": "memory_save.py", "MemoryDelete": "memory_delete.py", "MemoryForget": "memory_forget.py"}
    path = Path(__file__).resolve().parents[2] / "plugins/_memory/tools" / paths[name] if name in paths else None
    return bool(path and hashlib.sha256(path.read_bytes()).hexdigest() == digest)


def supports(tool, args):
    from helpers.durable.codec import identity
    pin = identity(tool)
    execute = type(tool).__dict__.get("execute")
    return source(type(tool).__name__, pin["source"]) and bool(execute and inspect.getsourcefile(execute))


async def prepare(tool, args):
    from helpers.durable.resources import cipher
    cipher()


def recorded(owner, run, call):
    from plugins._memory.helpers.durable_memory import operation
    from plugins._memory.helpers.memory import get_agent_memory_subdir
    from types import SimpleNamespace
    payload = call.get("payload") or {}
    pin = payload.get("tool") or {}
    if not source(pin.get("class", "").rsplit(".", 1)[-1], pin.get("source")):
        return None
    saved = run["checkpoint"]["context"]
    proxy = SimpleNamespace(config=SimpleNamespace(profile=saved.get("agent_profile") or ""),
                            context=SimpleNamespace(get_data=lambda key: (saved.get("data") or {}).get(key)))
    scope = get_agent_memory_subdir(proxy)
    return operation(owner, scope, f"{run['run_id']}:{call['call_id']}:0",
                     allow_historical=owner.sync("can_resume", run["run_id"]))[1]


def can_resume(tool, args, call):
    return False  # Only a known mutation receipt can settle an interrupted write.


async def reconcile_unknown(tool, args, call):
    from helpers.durable.runtime import current
    from helpers.tool import Response
    turn = current(tool.agent)
    receipt = recorded(turn.owner, turn.owner.sync("get_run", turn.run_id), call)
    return Response(**receipt["outcome"]) if receipt and receipt.get("outcome") else None
