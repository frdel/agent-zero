import base64
from pathlib import Path
import re
import shutil
import subprocess

import pytest

from test_chat_loading_refresh import run_module


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_STORE = PROJECT_ROOT / "webui/components/chat/input/input-store.js"
INDEX_JS = PROJECT_ROOT / "webui/index.js"


@pytest.mark.skipif(not shutil.which("node"), reason="Node.js is required")
def test_chat_input_keeps_separate_session_drafts() -> None:
    index_source = INDEX_JS.read_text(encoding="utf-8")
    set_context = index_source[index_source.index("export const setContext"):]
    assert set_context.index("inputStore.setDraftContext(id);") < set_context.index("context = id;")

    source = INPUT_STORE.read_text(encoding="utf-8")
    source = re.sub(r"^import .*?;\n", "", source, flags=re.MULTILINE)
    source = source[: source.index('const store = createStore("chatInput", model);')]
    module_source = r"""
const shortcuts = {
  getCurrentContextId: () => globalThis.__context,
  callJsonApi: async () => ({}),
  frontendNotification: () => {},
  NotificationType: {},
  NotificationPriority: {},
};
const fileBrowserStore = {};
const messageQueueStore = { hasQueue: false };
const attachmentsStore = {
  attachments: [],
  clearAttachments() { this.attachments = []; },
};
const chatsStore = { selected: "", selectedContext: null };
""" + source + "\nexport { model, chatsStore };\n"
    module_url = "data:text/javascript;base64," + base64.b64encode(
        module_source.encode("utf-8")
    ).decode("ascii")

    script = f"""
const makeStorage = () => ({{
  values: new Map(),
  getItem(key) {{ return this.values.get(key) ?? null; }},
  setItem(key, value) {{ this.values.set(key, String(value)); }},
  removeItem(key) {{ this.values.delete(key); }},
}});
globalThis.sessionStorage = makeStorage();
globalThis.localStorage = makeStorage();
globalThis.document = {{ activeElement: null, getElementById: () => null, querySelectorAll: () => [] }};
globalThis.__context = null;

const {{ model, chatsStore }} = await import({module_url!r});
const assert = (condition, message) => {{ if (!condition) throw new Error(message); }};

globalThis.__context = "chat-a";
model.setDraftContext("chat-a");
model.message = "alpha draft";
assert(sessionStorage.getItem("a0:chat-draft:chat-a") === "alpha draft", "chat A was not saved");

globalThis.__context = "chat-b";
model.setDraftContext("chat-b");
assert(model.message === "", "a new chat inherited another chat's draft");
model.message = "beta draft";

globalThis.__context = "chat-a";
model.setDraftContext("chat-a");
assert(model.message === "alpha draft", "chat A was not restored");
model.message = "";
assert(sessionStorage.getItem("a0:chat-draft:chat-a") === null, "cleared draft remained stored");

globalThis.__context = null;
model.setDraftContext("");
model.message = "welcome prompt";
chatsStore.newChat = async () => {{
  globalThis.__context = "chat-new";
  chatsStore.selected = "chat-new";
  model.setDraftContext("chat-new");
  return "chat-new";
}};
let sent = "";
globalThis.sendMessage = async () => {{ sent = model.message; }};
await model.sendMessage();
assert(sent === "welcome prompt", "creating a chat erased the Welcome prompt");
assert(sessionStorage.getItem("a0:chat-draft:chat-new") === "welcome prompt", "first prompt did not follow its new chat");

const editor = {{
  style: {{ height: "240px" }},
  get scrollHeight() {{ throw new Error("composer sizing must not freeze a transient layout"); }},
}};
model._editorEl = editor;
model.adjustTextareaHeight();
assert(editor.style.height === "auto", "composer retained its measured height");
model.adjustTextareaHeight();
assert(editor.style.height === "auto", "repeated sizing froze the composer height");
model.unmountEditor(editor);
"""

    subprocess.run(["node", "--input-type=module", "-e", script], check=True, text=True)


@pytest.mark.skipif(not shutil.which("node"), reason="Node.js is required")
def test_welcome_send_serializes_chat_creation_and_dispatch() -> None:
    run_module("webui/components/chat/input/input-store.js", """
const createStore = (_name, model) => model;
const shortcuts = {}, fileBrowserStore = {}, messageQueueStore = {hasQueue: false};
const attachmentsStore = {attachments: []};
const chatsStore = {selected: '', selectedContext: null};
const document = {activeElement: null, getElementById: () => null};
""", """
store._saveDraft = () => {};
const history = [];
store._pushHistory = text => history.push(text);
store.message = 'First Welcome prompt';
let finishCreate, finishSend, creates = 0, sends = 0, stops = 0;
chatsStore.newChat = () => {
  creates++;
  return new Promise(resolve => { finishCreate = resolve; });
};
globalThis.sendMessage = () => {
  sends++;
  assert.equal(store.message, 'First Welcome prompt');
  store.message = '';
  chatsStore.selectedContext = {running: true};
  return new Promise(resolve => { finishSend = resolve; });
};
store.stopAgent = async () => { stops++; };
const first = store.sendMessage();
await Promise.all([store.sendMessage(), store.activateSendButton(), store.sendMessage()]);
assert.equal(creates, 1, 'repeated sends created multiple Welcome chats');
assert.equal(sends, 0);
chatsStore.selected = 'new-chat';
store.message = '';
finishCreate('new-chat');
await Promise.resolve();
assert.equal(sends, 1);
await Promise.all([store.activateSendButton(), store.sendMessage()]);
assert.equal(stops, 0, 'a repeated send click stopped the new run before dispatch settled');
assert.equal(sends, 1);
assert.deepEqual(history, ['First Welcome prompt']);
finishSend();
await first;
await store.activateSendButton();
assert.equal(stops, 1, 'Stop was not available after sending settled');

chatsStore.selected = '';
chatsStore.selectedContext = null;
store.message = 'Retry prompt';
chatsStore.newChat = async () => { throw new Error('creation failed'); };
await assert.rejects(store.sendMessage(), /creation failed/);
assert.equal(store.message, 'Retry prompt');
chatsStore.newChat = async () => null;
await store.sendMessage();
assert.equal(sends, 1, 'a failed chat creation dispatched the prompt');
chatsStore.selected = 'retry-chat';
globalThis.sendMessage = async () => { sends++; throw new Error('dispatch failed'); };
await assert.rejects(store.sendMessage(), /dispatch failed/);
globalThis.sendMessage = async () => { sends++; };
await store.sendMessage();
assert.equal(sends, 3, 'a failed create or dispatch left sending locked');
""")
