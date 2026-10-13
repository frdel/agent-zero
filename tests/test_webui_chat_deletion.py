import base64
from pathlib import Path
import shutil
import subprocess

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHATS_STORE_JS = (
    PROJECT_ROOT / "webui" / "components" / "sidebar" / "chats" / "chats-store.js"
)


def test_chat_deletion_is_optimistic_and_rejects_stale_snapshots() -> None:
    if not shutil.which("node"):
        pytest.skip("Node.js is required to execute the chat-deletion regression.")

    source = CHATS_STORE_JS.read_text(encoding="utf-8")
    model_start = source.index("const model =")
    store_start = source.index('const store = createStore("chats", model);')
    model_source = source[model_start:store_start] + "\nexport { model };\n"
    stubs = """
const callJsonApi = (...args) => globalThis.__callJsonApi(...args);
const sendJsonData = (...args) => globalThis.__sendJsonData(...args);
const getContext = () => globalThis.__context;
const setContext = (id) => { globalThis.__context = id; };
const toastFetchError = (...args) => globalThis.__toastFetchError(...args);
const toast = () => {};
const justToast = (...args) => globalThis.__justToast(...args);
const getConnectionStatus = () => true;
const notificationStore = {};
const sidebarStore = { sortRows: (_kind, rows) => [...rows] };
const tasksStore = { tasks: [] };
const syncStore = { mode: "HEALTHY" };
const chatInputStore = {};
"""
    module_url = "data:text/javascript;base64," + base64.b64encode(
        (stubs + model_source).encode("utf-8")
    ).decode("ascii")
    script = f"""
globalThis.sessionStorage = {{
  values: new Map(),
  getItem(key) {{ return this.values.get(key) ?? null; }},
  setItem(key, value) {{ this.values.set(key, String(value)); }},
  removeItem(key) {{ this.values.delete(key); }},
}};
globalThis.__callJsonApi = async () => ({{}});
globalThis.__toastFetchError = () => {{}};
globalThis.__justToast = () => {{}};

const {{ model }} = await import({module_url!r});

function assert(condition, message) {{
  if (!condition) throw new Error(message);
}}

function reset(contexts, selected) {{
  model.contexts = contexts.map((context) => ({{ ...context }}));
  model.contextsJson = "";
  model.selected = selected;
  model.selectedContext = model.contexts.find((context) => context.id === selected);
  model.deletedContextIds = {{}};
  globalThis.__context = selected;
}}

const chats = [
  {{ id: "a", created_at: 30 }},
  {{ id: "b", created_at: 20 }},
  {{ id: "c", created_at: 10 }},
];

reset(chats, "");
model.applyContexts(chats);
const unchangedContexts = model.contexts;
model.applyContexts(chats.map((context) => ({{ ...context }})));
assert(
  model.contexts === unchangedContexts,
  "unchanged snapshots must preserve the Alpine contexts array",
);
const unchangedFirstRow = model.contexts[0];
model.applyContexts([{{ ...chats[0], name: "Renamed" }}, ...chats.slice(1)]);
assert(
  model.contexts === unchangedContexts &&
    model.contexts[0] === unchangedFirstRow &&
    model.contexts[0].name === "Renamed",
  "changed context metadata must update its existing row in place",
);
model.applyContexts([...chats, {{ id: "d", created_at: 40 }}]);
assert(
  model.contexts !== unchangedContexts && model.contexts[0].id === "d",
  "structural context changes must replace and reorder the contexts array",
);

const tree = [
  {{ id: "parent", created_at: 20 }},
  {{ id: "child", parent_context_id: "parent", created_at: 10 }},
  {{ id: "grandchild", parent_context_id: "child", created_at: 5 }},
  {{ id: "greatgrandchild", parent_context_id: "grandchild", created_at: 1 }},
];
reset(tree, "");
model.applyContexts(tree);
const unchangedTree = model.contexts;
model.selected = "parent";
model.expandedParents = {{}};
model.applyContexts(tree.map((context) => ({{ ...context }})));
assert(model.contexts === unchangedTree, "unchanged chat trees must preserve identity");
assert(
  model.expandedParents.parent === true,
  "selection synchronization must still run for unchanged contexts",
);
for (const selected of ["parent", "child", "grandchild"]) {{
  model.expandedParents = {{}};
  reset(tree.slice(0, tree.findIndex(context => context.id === selected) + 1), selected);
  assert(!model.isExpanded(selected), "a chat without children remains collapsed");
  model.applyContexts(tree);
  assert(
    model.isExpanded(selected),
    "a selected agent must reveal its children at every depth",
  );
  const expanded = model.expandedParents;
  model.applyContexts(tree);
  assert(model.expandedParents === expanded, "unchanged expansion preserves identity");
  model.toggleChildren(selected);
  model.applyContexts(tree);
  assert(
    !model.isExpanded(selected),
    "snapshot refresh must preserve manually collapsed children",
  );
}}
model.expandedParents = {{}};
model.setSelected("greatgrandchild");
assert(
  ["parent", "child", "grandchild"].every(id => model.isExpanded(id)),
  "selecting a deep worker opens every ancestor",
);
model.expandedParents = {{}};
model.applyContexts(tree);
assert(
  ["parent", "child", "grandchild"].every(id => model.isExpanded(id)),
  "restoring a deep selection opens every ancestor",
);
const expanded = model.expandedParents;
model.applyContexts(tree);
assert(model.expandedParents === expanded, "unchanged expansion does not republish state");

reset(chats, "b");
globalThis.__context = "a";
await model.selectChat("a");
assert(
  model.selected === "a" && model.selectedContext?.id === "a",
  "selection state must catch up when the low-level context already switched",
);

let resolveDelete;
globalThis.__sendJsonData = () => new Promise((resolve) => {{ resolveDelete = resolve; }});
reset(chats, "a");
const deletion = model.killChat("a");

assert(
  model.contexts.map((context) => context.id).join(",") === "b,c",
  "the deleted row must disappear before the request completes",
);
assert(model.selected === "b", "fallback selection must happen in the same turn");
assert(model.deletedContextIds.a === true, "the in-flight delete needs a tombstone");
await model.selectChat("a");
assert(
  model.selected === "b" && globalThis.__context === "b",
  "a queued click must not navigate back to a context being deleted",
);

model.applyContexts(chats);
assert(
  model.contexts.map((context) => context.id).join(",") === "b,c",
  "an in-flight stale snapshot must not restore the deleted row",
);

await new Promise((resolve) => setTimeout(resolve, 0));
assert(typeof resolveDelete === "function", "the delete request should be in flight");
resolveDelete({{ message: "Context removed." }});
await deletion;
assert(model.deletedContextIds.a === true, "the tombstone must survive the HTTP acknowledgement");

model.applyContexts(chats);
assert(
  model.contexts.map((context) => context.id).join(",") === "b,c",
  "a stale post-acknowledgement snapshot must remain filtered",
);
model.applyContexts(chats.slice(1));
assert(
  model.deletedContextIds.a === true,
  "an absent snapshot must not retire the tombstone while older polls can still arrive",
);
model.applyContexts(chats);
assert(
  model.contexts.map((context) => context.id).join(",") === "b,c",
  "an older present snapshot arriving after an absent one must remain filtered",
);

const rapidDeleteResolvers = {{}};
globalThis.__sendJsonData = (_url, payload) => new Promise((resolve) => {{
  rapidDeleteResolvers[payload.context] = resolve;
}});
reset(chats, "a");
const deleteA = model.killChat("a");
await new Promise((resolve) => setTimeout(resolve, 0));
const deleteB = model.killChat("b");
assert(
  model.contexts.map((context) => context.id).join(",") === "c",
  "rapid deletes must remove every pending row immediately",
);
assert(model.selected === "c", "rapid selected-chat deletes must advance without a stale row");
model.applyContexts(chats);
assert(
  model.contexts.map((context) => context.id).join(",") === "c",
  "one stale snapshot must not reinsert any concurrently deleted row",
);
await new Promise((resolve) => setTimeout(resolve, 0));
rapidDeleteResolvers.b({{ message: "Context removed." }});
rapidDeleteResolvers.a({{ message: "Context removed." }});
await Promise.all([deleteA, deleteB]);
model.applyContexts(chats.slice(2));
assert(
  model.deletedContextIds.a === true && model.deletedContextIds.b === true,
  "rapid-delete tombstones must survive an absent snapshot",
);
model.applyContexts(chats);
assert(
  model.contexts.map((context) => context.id).join(",") === "c",
  "late snapshots must not reinsert any rapidly deleted row",
);

globalThis.__sendJsonData = async () => {{ throw new Error("delete failed"); }};
reset(chats, "a");
const originalConsoleError = console.error;
console.error = () => {{}};
await model.killChat("a");
console.error = originalConsoleError;
assert(
  model.contexts.map((context) => context.id).join(",") === "a,b,c",
  "a failed delete must restore the optimistically removed row",
);
assert(!model.deletedContextIds.a, "a failed delete must clear its tombstone");
assert(model.selected === "b", "rollback must not override the fallback or a later user selection");
"""

    subprocess.run(
        ["node", "--input-type=module", "-e", script],
        check=True,
        text=True,
    )


def test_snapshot_cannot_reconcile_another_chat_after_an_async_context_switch():
    if not shutil.which("node"):
        pytest.skip("Node.js is required for the snapshot race regression.")
    source = (PROJECT_ROOT / "webui/index.js").read_text(encoding="utf-8")
    source = source[source.index("export async function applySnapshot("):source.index("export async function poll(")]
    source = source.replace("export async", "async", 1)
    import json

    script = f"""
import assert from 'node:assert/strict';
import vm from 'node:vm';
for (const phase of ['extension', 'messages']) {{
  const sandbox = {{
    context: 'old', lastLogGuid: '', lastLogVersion: 0,
    chatsStore: {{ applyContexts() {{ assert.fail('stale sidebar reconciliation'); }} }},
    tasksStore: {{}},
    msgs: {{ resetMessageRenderState() {{}} }},
    modelGateStore: {{ mergeSyntheticMessages: logs => logs }},
    afterMessagesUpdate() {{ assert.fail('stale message completion'); }},
  }};
  sandbox.callJsExtensions = async () => {{ if (phase === 'extension') sandbox.context = 'new'; }};
  sandbox.setMessages = async () => {{
    assert.notEqual(phase, 'extension', 'stale snapshot reached message rendering');
    sandbox.context = 'new';
  }};
  vm.createContext(sandbox);
  vm.runInContext({json.dumps(source)}, sandbox);
  const result = await sandbox.applySnapshot({{context:'old', contexts:[], tasks:[], logs:[], log_version:1, log_guid:'guid'}});
  assert.equal(result.updated, false);
  assert.equal(sandbox.context, 'new');
}}
"""
    subprocess.run(["node", "--input-type=module", "-e", script], check=True, capture_output=True, text=True)
