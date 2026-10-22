"""Synthetic loopback sidecar for real durability API and modal acceptance.

Run only from a sanitized source copy. It never starts Agent Zero's initializer,
connectors, background jobs, or a provider. The model raises if called.
"""
from __future__ import annotations

import asyncio
import os
import tempfile
import hashlib
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

if os.environ.get("A0_DURABILITY_UI_FIXTURE") != "isolated":
    raise RuntimeError("This synthetic fixture requires A0_DURABILITY_UI_FIXTURE=isolated and an isolated source copy")

from flask import Flask, Response, jsonify, redirect, request, send_from_directory, session

from agent import Agent, AgentConfig, AgentContext, LoopData, UserMessage
from helpers import extension, login, persist_chat
from helpers import runtime as framework_runtime
from helpers.api import csrf_protect, register_api_route, requires_auth
from helpers.durable import codec, documents, runtime
from helpers.llm_result import LLMResult
from helpers.tool import Tool
import helpers.log
import helpers.secrets
import helpers.state_monitor_integration


COUNTERS = {"provider_calls": 0, "tool_calls": 0}


class FrozenModel:
    model_name = "synthetic-ui-model"
    provider = "fixture"
    kwargs = {"a0_api_mode": "chat_completions"}

    async def unified_turn(self, **kwargs):
        COUNTERS["provider_calls"] += 1
        raise AssertionError("The UI fixture must never dispatch a model request")


class FixtureTool(Tool):
    async def execute(self, **kwargs):
        COUNTERS["tool_calls"] += 1
        raise AssertionError("The UI fixture must never dispatch a tool body")


extension._get_extension_classes = lambda *args, **kwargs: []
AgentContext._contexts = {}
Agent.get_chat_model = lambda self: FrozenModel()
Agent.get_tool = lambda self, name, method, args, message, loop_data, **kwargs: FixtureTool(
    self, name, method, args, message, loop_data)
manager = SimpleNamespace(mask_values=lambda value: value, replace_placeholders=lambda value: value)
helpers.secrets.get_secrets_manager = lambda context: manager
helpers.log.get_secrets_manager = lambda context: manager
helpers.state_monitor_integration.mark_dirty_all = lambda **kwargs: None
helpers.state_monitor_integration.mark_dirty_for_context = lambda *args, **kwargs: None
persist_chat.initialize_agent = lambda **kwargs: AgentConfig(mcp_servers="")
login.get_credentials_hash = lambda: "synthetic-authentication-fixture"
login.is_login_required = lambda: True
framework_runtime.runtime_id = "durability-ui-fixture"

state = Path(tempfile.mkdtemp(prefix="a0-durability-ui-"))
(ROOT / "usr").mkdir(mode=0o700, exist_ok=True)
persist_chat.CHATS_FOLDER = str(state / "chats")
source = runtime.RecoveryService(state / "source")
contexts, runs = {}, {}
terminal_seeded = False
for key, title in (("a", "Uncertain action A"), ("b", "Uncertain action B")):
    context = AgentContext(AgentConfig(mcp_servers=""), id="ui-chat-" + key, name=title)
    context.agent0.loop_data = LoopData()
    context.agent0.loop_data.iteration = 0
    result = LLMResult.from_chat(response=json.dumps({"tool_name": "fixture_tool", "tool_args": {"message": "synthetic"}}))
    checkpoint = codec.checkpoint(context.agent0, result=result)
    run = source.sync("admit", context.id, "ui-input-" + key, codec.message_payload(UserMessage("Synthetic work", id="ui-input-" + key)), checkpoint)
    source.sync("transition", run["run_id"], "tools", checkpoint=checkpoint)
    source.sync("start_call", run["run_id"], "tool:0:0", "tool", {
        "tool": codec.identity(FixtureTool), "name": "fixture_tool", "method": None,
        "args": {"message": "synthetic"},
    })
    source.sync("transition", run["run_id"], "needs_attention", status="attention", payload={"reason": "tool_outcome_unknown"})
    contexts[key], runs[key] = context, run["run_id"]
documents.update(source, contexts["a"], "todo", {"title": "Saved plan", "items": [
    {"id": "fixture-item", "text": "Original saved item", "done": False},
]}, 0, "fixture-initial-plan")
(state / "restored").mkdir(mode=0o700)
source.sync("backup", state / "restored" / "state.sqlite3")
source.close()
owner = runtime.RecoveryService(state / "restored")
runtime._service = owner

app = Flask("durability-browser-fixture", static_folder=None)
app.secret_key = "synthetic-session-key-used-only-in-ephemeral-test-sidecar"
register_api_route(app, threading.RLock())


@app.route("/login")
def login_handler():
    return Response("Fixture authentication required", 401)


@app.route("/fixture/login")
def fixture_login():
    session["authentication"] = login.get_credentials_hash()
    return redirect("/")


@app.route("/fixture/control", methods=["POST"])
@requires_auth
@csrf_protect
async def fixture_control():
    global terminal_seeded
    payload = request.get_json() or {}
    action = payload.get("action")
    if action == "seed_terminal_rows":
        if not terminal_seeded:
            for index in range(55):
                context_id = f"ui-terminal-{index:02d}"
                terminal = owner.sync("admit", context_id, f"terminal-input-{index:02d}", {}, {})
                owner.sync("transition", terminal["run_id"], "completed", status="completed")
            terminal_seeded = True
    elif action == "bump_a":
        owner.sync("transition", runs["a"], "needs_attention", status="attention", payload={"reason": "fixture_concurrent_review"})
    elif action == "document_race":
        current = documents.read(owner, contexts["a"], "todo")
        documents.update(owner, contexts["a"], "todo", {"title": "Concurrent saved plan", "items": [
            {"id": "fixture-item", "text": "Concurrent saved item", "done": False},
        ]}, current["revision"], "fixture-concurrent-plan")
    elif action == "disable":
        owner.enabled = False
    elif action == "enable":
        owner.enabled = True
    else:
        return jsonify({"error": "Unknown fixture control"}), 400
    return jsonify({"ok": True})


@app.route("/fixture/audit")
@requires_auth
async def fixture_audit():
    source_hashes = dict(owner.sync("get_run", runs["a"])["checkpoint"]["environment"]["runtime_sources"])
    for name in ("api/durability.py", "helpers/durable/review.py", "helpers/durable/retry.py",
                 "webui/components/durability/durability.html", "webui/components/durability/durability-state.js",
                 "webui/components/durability/durability-store.js", "webui/js/api.js", "webui/js/modals.js"):
        source_hashes[name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    return jsonify({"counters": COUNTERS, "run_ids": runs, "source_hashes": source_hashes, "runs": {
        key: {"status": owner.sync("get_run", run_id)["status"],
              "calls": [{"call_id": call["call_id"], "status": call["status"]}
                        for call in owner.sync("calls", run_id)]}
        for key, run_id in runs.items()
    }})


@app.route("/", endpoint="serve_index")
@requires_auth
async def fixture_index():
    return Response(INDEX, mimetype="text/html")


@app.route("/fixture/chats-store.js")
def fixture_chats_store():
    return Response('import {createStore} from "/js/AlpineStore.js"; export const store=createStore("chats",{selected:"ui-chat-a"});', mimetype="text/javascript")


@app.route("/<path:path>")
def static(path):
    return send_from_directory(ROOT / "webui", path)


INDEX = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Durability acceptance fixture</title>
<link rel="icon" href="data:,"><link rel="stylesheet" href="/index.css"><link rel="stylesheet" href="/css/modals.css"><link rel="stylesheet" href="/css/buttons.css"><link rel="stylesheet" href="/vendor/google/google-icons.css">
<script type="importmap">{"imports":{"/components/sidebar/chats/chats-store.js":"/fixture/chats-store.js"}}</script>
<script>globalThis.runtimeInfo={id:"durability-ui-fixture",loggedIn:true,webuiExtensions:{js:new Proxy({},{get:()=>[]}),html:new Proxy({},{get:()=>[]})}};</script>
<script>document.fonts.load('24px "Material Symbols Outlined"').then(()=>document.documentElement.classList.add('material-icons-ready'));</script>
<script type="module" src="/js/icons.js"></script><script type="module" src="/js/initFw.js"></script>
</head><body class="dark-mode device-pointer" x-data style="padding:24px">
<h1>Agent Zero recovery acceptance</h1><p>Synthetic private ledger. External execution is disabled.</p>
<button class="button" id="open-durability" onclick="void window.openModal('durability/durability.html')">Open recovery and documents</button>
</body></html>"""

if __name__ == "__main__":
    print(json.dumps({"fixture": "ready", "internal_port": 8619}), flush=True)
    try:
        app.run(host="0.0.0.0", port=8619, debug=False, use_reloader=False, threaded=True)
    finally:
        owner.close()
