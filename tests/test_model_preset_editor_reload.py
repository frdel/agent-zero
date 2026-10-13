import base64
from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).parents[1]


def module_url(path: str, prelude: str) -> str:
    source = re.sub(r"^import .*?;\n", "", (ROOT / path).read_text(), flags=re.MULTILINE)
    return "data:text/javascript;base64," + base64.b64encode((prelude + source).encode()).decode()


@pytest.mark.skipif(not shutil.which("node"), reason="node is required")
def test_preset_editor_opens_on_presets_changed_outside_it():
    store_url = module_url(
        "plugins/_model_config/webui/model-config-store.js",
        "const createStore = (_name, value) => value;\n"
        "const fetchApi = (...args) => globalThis.fetchApi(...args);\n"
        "const apiKeysState = {}, apiKeysMethods = {}, switcherState = {}, switcherMethods = {};\n",
    )
    hook_url = module_url(
        "plugins/_model_config/extensions/webui/open_modal_before/refresh-preset-editor.js",
        "const modelConfigStore = globalThis.modelConfigStore, chatsStore = globalThis.chatsStore;\n",
    )
    script = r'''
import assert from 'node:assert/strict';
const preset = name => ({name, chat: {provider: 'p', name: 'm'}, utility: {provider: 'p', name: 'u'},
                         embedding: {provider: 'p', name: 'e'}});
let presets = [preset('Default')], selected = 'Default';
globalThis.fetchApi = async (url, options) => {
  const body = JSON.parse(options.body);
  const data = url.endsWith('/model_presets') && body.action === 'get' ? {presets: structuredClone(presets)}
    : url.endsWith('/model_config_get') ? {selected_preset: selected} : assert.fail(url);
  return {ok: true, json: async () => data};
};
const { store } = await import(STORE_URL);
Object.assign(globalThis, {window: globalThis, modelConfigStore: store, chatsStore: {selected: 'chat'}});
const { default: refreshPresetEditor } = await import(HOOK_URL);
let editor;
// modals.js runs open_modal_before first. main.html then builds the draft at once
// when presets were loaded before, otherwise after its own x-init load.
globalThis.openModal = async modalPath => {
  await refreshPresetEditor({modalPath, modal: null, cancel: false});
  if (!store._presetsLoaded) await store.loadGlobalPresets();
  editor = store.createPresetEditor(store.presetEditorInitialName);
};
const shown = () => [editor.presets.map(p => p.name).join(), editor.selectedPreset?.name];

await store.openPresetEditor('Default');
assert.deepEqual(shown(), ['Default', 'Default']);

// Another client adds a preset: the editor lists it and opens on it.
presets = [...presets, preset('probe')];
await store.openPresetEditor('probe');
assert.deepEqual(shown(), ['Default,probe', 'probe']);

// /presets opens the modal directly: the editor opens on the chat's active preset.
presets = [...presets, preset('probe2')];
selected = 'probe2';
await globalThis.openModal('/plugins/_model_config/webui/main.html');
assert.deepEqual(shown(), ['Default,probe,probe2', 'probe2']);
'''.replace("STORE_URL", repr(store_url)).replace("HOOK_URL", repr(hook_url))
    subprocess.run(["node", "--input-type=module", "-e", script], check=True)
