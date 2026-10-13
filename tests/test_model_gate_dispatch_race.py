import re
import shutil
from pathlib import Path

import pytest

from test_chat_loading_refresh import run_module

STORE = Path("webui/components/chat/model-gate-store.js").read_text(encoding="utf-8")


def _function_source(name: str) -> str:
    start = STORE.index(f"  async {name}(")
    end = STORE.index("\n  },", start)
    return STORE[start:end]


def test_dispatch_captures_pending_before_await():
    body = _function_source("dispatchPendingIfConfigured")
    capture_at = body.index("const pending = this.pending;")
    latch_at = body.index("this.dispatching = true;")
    await_at = body.index("await this.canSendToModel(pending.context);")
    assert capture_at < await_at
    assert latch_at < await_at


def test_dispatch_rechecks_pending_identity_after_await():
    body = _function_source("dispatchPendingIfConfigured")
    await_at = body.index("await this.canSendToModel(pending.context);")
    recheck_at = body.index("this.pending !== pending")
    assert await_at < recheck_at


def test_dispatch_never_reads_message_without_pending_guard():
    body = _function_source("dispatchPendingIfConfigured")
    assert "!pending" in body
    # message is only read from the captured local, never from this.pending
    assert "pending.message" in body
    assert not re.search(r"this\.pending\.message", body)


def test_open_advanced_catch_reports_readable_message():
    body = _function_source("openAdvancedModelConfiguration")
    assert "error?.message" in body


GATE_HARNESS = """
const saved = new Map();
const sessionStorage = {setItem: (key, value) => saved.set(key, value),
  getItem: key => saved.get(key) || null, removeItem: key => saved.delete(key)};
const document = {addEventListener() {}};
const createStore = (_name, model) => model;
const modelConfigStore = {}, onboardingStore = {};
const requests = [];
const callJsonApi = async (endpoint, data) => {
  requests.push({endpoint, data});
  return {model_configured: true};
};
"""


@pytest.mark.skipif(not shutil.which("node"), reason="Node.js is required")
@pytest.mark.parametrize("operation", ["selectPresetSwitch", "clearOverrideSwitch"])
@pytest.mark.parametrize("switch_chat", [False, True])
def test_preset_changes_retry_setup_prompt_only_after_success(operation, switch_chat):
    switcher = Path("plugins/_model_config/webui/switcher-mixin.js").read_text()
    switcher = re.sub(r"^import .*?;\n", "", switcher, flags=re.MULTILINE)
    harness = GATE_HARNESS.replace(
        "const document = {addEventListener() {}};", "const document = new EventTarget();"
    ) + f"const operation = {operation!r};\nconst switchChat = {str(switch_chat).lower()};\n" + """
let selected = 'chat-a', saveOk = false;
globalThis.window = {Alpine: {store: () => ({selected})}};
const overrides = [];
const fetchApi = async (_url, options) => {
  overrides.push(JSON.parse(options.body));
  return {json: async () => ({ok: saveOk, preset_name: 'Ready', effective_preset: 'Ready'})};
};
"""
    run_module("webui/components/chat/model-gate-store.js", harness, switcher + """
store.start({message: 'Original setup prompt', attachments: [], messageId: 'pending-id', context: 'chat-a'});
const pending = store.pending;
const sends = [];
globalThis.sendMessage = async options => { sends.push(options); return true; };
const switcher = {...switcherState, ...switcherMethods};
if (switchChat) selected = 'chat-b';
assert.equal(await switcher[operation]('chat-a', 'Ready'), false);
await new Promise(setImmediate);
assert.equal(requests.length, 0, 'failed preset save notified the gate');
assert.equal(store.pending, pending);
assert.equal(saved.size, 1);
saveOk = true;
assert.equal(await switcher[operation]('chat-a', 'Ready'), true);
await new Promise(setImmediate);
assert.equal(requests.length, 1);
assert.equal(requests[0].data.context_id, 'chat-a', 'readiness used the selected chat instead of the pending chat');
assert.equal(sends.length, 1);
assert.equal(sends[0].context, 'chat-a');
assert.equal(sends[0].message, 'Original setup prompt');
assert.equal(sends[0].preserveInput, true);
assert.equal(store.pending, null);
assert.equal(saved.size, 0);
assert.deepEqual(overrides.map(data => data.context_id), ['chat-a', 'chat-a']);
assert.equal(switcher.switcherEffectivePreset, switchChat ? 'Default' : 'Ready');
""")


@pytest.mark.skipif(not shutil.which("node"), reason="Node.js is required")
def test_gate_keeps_saved_prompt_until_an_idle_send_accepts_it():
    run_module("webui/components/chat/model-gate-store.js", GATE_HARNESS, """
store.start({message: 'Original prompt', attachments: [], messageId: 'pending-id', context: 'chat-a'});
const pending = store.pending;
const savedPrompt = [...saved.values()][0];
let sends = 0, accepted = false;
globalThis.sendMessage = async () => { sends++; return accepted; };
globalThis.sendMessage.inFlight = true;
await store.dispatchPendingIfConfigured();
assert.equal(store.pending, pending);
assert.equal([...saved.values()][0], savedPrompt);
assert.equal(store.connected, false);
assert.equal(sends, 0);

globalThis.sendMessage.inFlight = false;
await store.dispatchPendingIfConfigured();
assert.equal(store.pending, pending, 'failed send discarded the pending prompt');
assert.equal([...saved.values()][0], savedPrompt);
assert.equal(store.connected, false);
assert.equal(requests.at(-1).data.context_id, 'chat-a');

accepted = true;
await store.dispatchPendingIfConfigured();
assert.equal(sends, 2);
assert.equal(store.pending, null);
assert.equal(saved.size, 0);
assert.equal(store.connected, true);
""")


@pytest.mark.skipif(not shutil.which("node"), reason="Node.js is required")
def test_gate_rechecks_send_busy_state_after_readiness_await():
    run_module("webui/components/chat/model-gate-store.js", GATE_HARNESS, """
store.start({message: 'Original prompt', attachments: [], messageId: 'pending-id', context: 'chat-a'});
const pending = store.pending;
let resolve;
store.canSendToModel = () => new Promise(done => { resolve = done; });
let sends = 0;
globalThis.sendMessage = async () => { sends++; return true; };
const dispatch = store.dispatchPendingIfConfigured();
globalThis.sendMessage.inFlight = true;
resolve(true);
await dispatch;
assert.equal(sends, 0);
assert.equal(store.pending, pending);
assert.equal(store.connected, false);
assert.equal(saved.size, 1);
""")


@pytest.mark.skipif(not shutil.which("node"), reason="Node.js is required")
def test_rejected_first_send_retries_after_rendering_without_touching_new_draft():
    index = Path("webui/index.js").read_text(encoding="utf-8")
    start = index.index("export async function sendMessage(")
    end = index.index("globalThis.sendMessage = sendMessage;", start)
    run_module("webui/components/chat/model-gate-store.js", GATE_HARNESS, index[start:end] + """
const modelGateStore = store;
const context = 'chat-a';
const attachmentsStore = {getAttachmentsForSending: () => []};
const inputStore = {message: 'Original prompt', reset() { this.message = ''; }};
const chatsStore = {selectedContext: {running: false}};
const messageQueueStore = {hasQueue: false};
const callJsExtensions = async () => {};
const msgs = {scrollOnNextProcessGroup() {}};
const forceScrollChatToBottom = () => {}, adjustTextareaHeight = () => {};
const generateGUID = () => 'pending-id', setContext = () => {};
const toastFetchError = (_text, error) => { throw error; };
const messages = [];
const api = {fetchApi: async (_url, options) => {
  messages.push(JSON.parse(options.body));
  return {json: async () => messages.length === 1
    ? {model_not_configured: true, context}
    : {message: 'Message received.', context}};
}};
const setMessages = async rows => {
  if (rows.some(row => row.type === 'model_setup_gate')) {
    inputStore.message = 'New unsent draft';
    await store.dispatchPendingIfConfigured();
  }
};
globalThis.sendMessage = sendMessage;
await sendMessage();
await new Promise(setImmediate);
assert.equal(messages.length, 2, 'the pending prompt was never retried after the send settled');
assert.equal(messages[1].text, 'Original prompt');
assert.equal(messages[1].message_id, 'pending-id');
assert.equal(inputStore.message, 'New unsent draft');
assert.equal(store.pending, null);
assert.equal(saved.size, 0);
assert.equal(store.connected, true);

store.start({message: 'Prompt for another chat', attachments: [], messageId: 'other-id', context: 'chat-b'});
chatsStore.selectedContext.running = true;
messageQueueStore.addToQueue = () => { throw new Error('pending prompt entered the selected chat queue'); };
await store.dispatchPendingIfConfigured();
assert.equal(messages.at(-1).context, 'chat-b');
assert.equal(messages.at(-1).text, 'Prompt for another chat');
assert.equal(inputStore.message, 'New unsent draft');
assert.equal(store.pending, null);
""")
