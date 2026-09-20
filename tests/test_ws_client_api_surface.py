import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _get_named_exports(source: str) -> set[str]:
    exports: set[str] = set()

    exports.update(re.findall(r"^export\s+function\s+([A-Za-z0-9_]+)\s*\(", source, flags=re.M))
    exports.update(re.findall(r"^export\s+const\s+([A-Za-z0-9_]+)\s*=", source, flags=re.M))
    exports.update(re.findall(r"^export\s+class\s+([A-Za-z0-9_]+)\s*[\{:]", source, flags=re.M))

    for m in re.findall(r"^export\s*\{([^}]+)\}\s*;?", source, flags=re.M):
        for item in m.split(","):
            item = item.strip()
            if not item:
                continue
            # Handle: `foo as bar`
            parts = item.split()
            if len(parts) >= 3 and parts[-2] == "as":
                exports.add(parts[-1])
            else:
                exports.add(parts[0])

    return exports


def test_websocket_js_exports_minimal_namespaced_api_surface() -> None:
    source = (PROJECT_ROOT / "webui" / "js" / "websocket.js").read_text(encoding="utf-8")
    exports = _get_named_exports(source)

    assert "createNamespacedClient" in exports
    assert "getNamespacedClient" in exports

    assert "broadcast" not in exports
    assert "requestAll" not in exports


def test_completed_state_push_cannot_overwrite_disconnected_mode() -> None:
    source = (
        PROJECT_ROOT / "webui" / "components" / "sync" / "sync-store.js"
    ).read_text(encoding="utf-8")

    apply_end = source.split("await applySnapshot(data.snapshot", 1)[1].split(
        'this._setMode(SYNC_MODES.HEALTHY, "push applied");', 1
    )[0]
    assert "if (!stateSocket.isConnected()) return;" in apply_end


def test_state_pushes_coalesce_without_losing_deltas_or_sequence_checks() -> None:
    if not shutil.which("node"):
        pytest.skip("Node.js is required for the state-push regression.")
    source = (
        PROJECT_ROOT / "webui" / "components" / "sync" / "sync-store.js"
    ).read_text(encoding="utf-8")
    source = re.sub(r"^import .*\n", "", source, flags=re.M)
    source = source.replace("export { store, SYNC_MODES };", "")
    message_window = (PROJECT_ROOT / "webui/js/message-window.js").read_text()
    notifications = (
        PROJECT_ROOT / "webui/components/notifications/notification-store.js"
    ).read_text()
    notifications = re.sub(r"^import .*\n", "", notifications, flags=re.M)
    notifications = (
        "const createStore = (_name, model) => model;\n"
        "const API = {callJsonApi: async () => ({success: true})};\n"
        + notifications
    )
    script = """
const { default: assert } = await import('node:assert/strict');
const handlers = new Map();
let connected = true;
const socket = {
  addHandlers() {}, onConnect() {}, onDisconnect() {},
  on(name, handler) { handlers.set(name, handler); },
  isConnected: () => connected,
  request: async () => ({results: [{ok: true, data: {runtime_epoch: 'epoch', seq_base: 100}}]}),
};
const getNamespacedClient = () => socket;
// Alpine wraps nested plain objects on read; identity checks must use that wrapper.
const proxies = new WeakMap();
function reactive(value) {
  if (!value || Object.getPrototypeOf(value) !== Object.prototype) return value;
  if (!proxies.has(value)) proxies.set(value, new Proxy(value, {
    get(target, key) { return reactive(Reflect.get(target, key)); },
  }));
  return proxies.get(value);
}
const createStore = (_name, model) => reactive(model);
const chatTopStore = {};
const notificationStore = { toastStack: [] };
const buildStateRequestPayload = () => ({});
const Extensions = {};
const applied = [];
let release;
let applying = 0;
let notificationSink = null;
const applySnapshot = async (snapshot) => {
  assert.equal(++applying, 1, 'renders must remain serial');
  applied.push(snapshot);
  if (applied.length === 1) await new Promise(resolve => { release = resolve; });
  notificationSink?.updateFromPoll(snapshot);
  applying--;
};
"""
    script += "\nconst { getMessageCacheKey } = await import('data:text/javascript,' + encodeURIComponent(" + json.dumps(message_window) + "));\n"
    script += "\nconst { store: notificationConsumer } = await import('data:text/javascript,' + encodeURIComponent(" + json.dumps(notifications) + "));\n"
    script += source
    script += """
await store.init();
const push = handlers.get('state_push');
function envelope(seq, overrides = {}, epoch = 'epoch') {
  return {data: {seq, runtime_epoch: epoch, snapshot: {
    context: 'chat', log_guid: 'log', log_version: seq,
    logs: [{no: 1, id: 'stream', type: 'agent', content: String(seq)}],
    contexts: null, tasks: null, notifications: [], notifications_guid: 'notifications',
    log_progress_active: true, ...overrides,
  }}};
}
push(envelope(101));
while (!release) await Promise.resolve();
const original = envelope(102, {
  logs: [{no: 2, id: 'tool', type: 'code_exe', content: 'done'}],
  contexts: [{id: 'chat'}, {id: 'other-agent', running: true}], tasks: [{id: 'task'}],
  notifications: [{id: 'n1', message: 'old'}, {id: 'n2', message: 'keep'}],
});
push(original);
for (let seq = 103; seq <= 200; seq++) push(envelope(seq));
push(envelope(201, {
  logs: [{no: 3, id: 'stream', type: 'response', content: 'finished'}],
  notifications: [{id: 'n1', message: 'new'}], log_progress_active: false,
}));
release();
await store._pushQueue;
assert.equal(applied.length, 2, 'resume must render one catch-up, not 100 obsolete states');
const latest = applied[1];
assert.equal(latest.log_version, 201);
assert.equal(latest.log_progress_active, false);
assert.deepEqual(latest.logs.map(log => [log.type, log.content]), [
  ['code_exe', 'done'], ['agent', '200'], ['response', 'finished'],
]);
assert.deepEqual(latest.contexts, original.data.snapshot.contexts);
assert.deepEqual(latest.tasks, [{id: 'task'}]);
assert.deepEqual(latest.notifications, [
  {id: 'n1', message: 'old'}, {id: 'n2', message: 'keep'}, {id: 'n1', message: 'new'},
]);
assert.equal(original.data.seq, 102, 'extension envelopes must not be mutated');
assert.equal(original.data.snapshot.logs.length, 1);
assert.equal(store.lastSeq, 201);
assert.equal(store._pendingPush, null, 'finished batches must leave no reactive pending envelope');

// A full log snapshot supersedes pending records; notification GUIDs reset independently.
push(envelope(202));
push(envelope(203, {logs: [{no: 0, type: 'user', content: 'full'}],
  notifications_guid: 'new-notifications', notifications: []}));
await store._pushQueue;
assert.deepEqual(applied.at(-1).logs, [{no: 0, type: 'user', content: 'full'}]);
assert.deepEqual(applied.at(-1).notifications, []);

// Context and log resets remain separate applications, with their original ordering.
push(envelope(204));
push(envelope(205, {context: 'other', log_guid: 'other-log'}));
push(envelope(206, {context: 'other', log_guid: 'reset-log'}));
await store._pushQueue;
assert.deepEqual(applied.slice(-3).map(s => [s.context, s.log_guid]),
  [['chat', 'log'], ['other', 'other-log'], ['other', 'reset-log']]);

let resyncs = 0;
store.sendStateRequest = async options => { assert.equal(options.forceFull, true); resyncs++; };
const count = applied.length;
push(envelope(208)); // Missing 207 must not be hidden by coalescing 208 and 209.
push(envelope(209));
await store._pushQueue;
assert.equal(resyncs, 1);
assert.equal(applied.length, count);
push(envelope(207, {}, 'restarted'));
await store._pushQueue;
assert.equal(resyncs, 2);
assert.equal(applied.length, count);

connected = false;
store.mode = SYNC_MODES.DISCONNECTED;
push(envelope(207));
await store._pushQueue;
assert.equal(store.mode, SYNC_MODES.DISCONNECTED);

// Notification order has side effects: replacing a grouped toast marks it read.
connected = true;
notificationSink = notificationConsumer;
const notification = (id, message, timestamp) => ({
  id, message, timestamp, group: 'job-status', read: false, display_time: 0, priority: 10,
});
const updates = [
  notification('job-a', 'A running', 1),
  notification('job-b', 'B running', 2),
  notification('job-a', 'A completed', 3),
];
for (const item of updates) notificationConsumer.updateFromPoll({
  notifications_guid: 'notifications', notifications: [{...item}],
});
const expectedToast = notificationConsumer.toastStack.map(item => item.message);
const expectedRead = notificationConsumer.notifications.map(item => [item.id, item.read]);
notificationConsumer.notifications = [];
notificationConsumer.toastStack = [];
for (let i = 0; i < updates.length; i++) {
  push(envelope(208 + i, {notifications: [{...updates[i]}]}));
}
await store._pushQueue;
assert.deepEqual(notificationConsumer.toastStack.map(item => item.message), expectedToast);
assert.deepEqual(notificationConsumer.notifications.map(item => [item.id, item.read]), expectedRead);
assert.deepEqual(expectedToast, ['A completed']);
assert.equal(notificationConsumer.notifications.find(item => item.id === 'job-a').read, false);
"""
    subprocess.run(["node", "--input-type=module", "-e", script], check=True, timeout=15)


def test_message_layout_yield_finishes_when_browser_stops_animation_frames() -> None:
    if not shutil.which("node"):
        pytest.skip("Node.js is required for the layout-yield regression.")
    source = (PROJECT_ROOT / "webui/js/messages.js").read_text()
    helper = source[source.index("function nextAnimationFrame() {"):source.index("function appendToMessageGroup(")]
    script = """
import assert from 'node:assert/strict';
let frame, timer;
globalThis.requestAnimationFrame = callback => { frame = callback; return 1; };
globalThis.cancelAnimationFrame = id => { assert.equal(id, 1); frame = null; };
globalThis.setTimeout = callback => { timer = callback; return 2; };
globalThis.clearTimeout = id => { assert.equal(id, 2); timer = null; };
""" + helper + """
const background = nextAnimationFrame();
assert.equal(typeof timer, 'function', 'layout cannot depend on paint alone');
timer();
await background;
assert.equal(frame, null);
assert.equal(timer, null);
const foreground = nextAnimationFrame();
frame();
await foreground;
assert.equal(frame, null);
assert.equal(timer, null);
"""
    subprocess.run(["node", "--input-type=module", "-e", script], check=True, timeout=15)


def test_partial_snapshot_retains_sidebar_collections_and_extension_shape() -> None:
    source = (PROJECT_ROOT / "webui" / "index.js").read_text(encoding="utf-8")
    request_builder = source.split(
        "export function buildStateRequestPayload", 1
    )[1].split("export async function applySnapshot", 1)[0]

    assert "collections_delta: true" in request_builder
    assert "const hasCollections =" in source
    assert "Array.isArray(snapshot.contexts) && Array.isArray(snapshot.tasks)" in source
    assert "snapshot: extensionSnapshot" in source
    assert "contexts: chatsStore.contexts" in source
    assert "tasks: getStore(\"tasks\")?.tasks" in source
    assert "if (hasCollections)" in source
    assert "snapshot.contexts || []" not in source
