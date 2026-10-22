"""Explicit built-in execution adapters; unknown effects never gain replay rights."""
from helpers.durable import execution, sessions, computer, memory


def implementation(tool, args):
    for module in (execution, sessions, computer, memory):
        if module.supports(tool, args):
            return module
    return None


def recorded_adapter(owner, run, call):
    """Inspect a pinned built-in receipt without constructing an executable tool."""
    import hashlib
    from pathlib import Path
    from helpers.durable.resources import ResourceManager
    root = Path(__file__).resolve().parents[2]
    identity = (call.get("payload") or {}).get("tool") or {}
    name = identity.get("class", "").rsplit(".", 1)[-1]
    if getattr(owner, "distributed", False) and memory.source(name, identity.get("source")):
        return call["status"] == "completed" or bool((memory.recorded(owner, run, call) or {}).get("outcome"))
    source = {"Browser": "plugins/_browser/tools/browser.py", "MCPTool": "helpers/mcp_handler.py",
              "ComputerUseRemote": "plugins/_a0_connector/tools/computer_use_remote.py",
              "CodeExecution": "plugins/_code_execution/tools/code_execution_tool.py",
              "Input": "plugins/_code_execution/tools/input.py"}.get(name)
    if not getattr(owner, "distributed", False) or not source or identity.get("source") != hashlib.sha256((root / source).read_bytes()).hexdigest():
        return False
    manager = ResourceManager(owner, run["context_id"], run["run_id"])
    if call["status"] == "completed":
        return True  # Only finalization of the retained body result is eligible.
    if name == "Browser":
        from plugins._browser.helpers.session_broker import _key
        from plugins._browser.helpers.durable_connector import operation_key
        kinds = ["browser-op-" + _key(run["context_id"], run["run_id"], call["call_id"], 0),
                 "host-browser-op-" + operation_key(run["context_id"], run["run_id"], call["call_id"], 0)]
    elif name == "ComputerUseRemote":
        kinds = ["computer-op-" + computer.operation_key(run["context_id"], run["run_id"], call["call_id"], 0)]
    elif name == "MCPTool":
        from helpers.durable.mcp_broker import key
        kinds = ["mcp-op-" + key(run["context_id"], run["run_id"], call["call_id"])]
    else:
        identifier = hashlib.sha256(f"{run['context_id']}:{run['run_id']}:{call['call_id']}".encode()).hexdigest()
        kinds = ["execution-pty-job-" + identifier, "execution-job-" + identifier]
    return any(manager.get_manifest(kind) for kind in kinds)
