"""Display-only snapshot refreshes must not hold up chat rendering."""

from pathlib import Path
import re
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="Node.js is required")


def run_module(path: str, harness: str, checks: str) -> None:
    source = (ROOT / path).read_text()
    source = re.sub(r"^import[\s\S]*?;\n", "", source, flags=re.MULTILINE)
    result = subprocess.run(
        ["node", "--input-type=module"],
        input='import assert from "node:assert/strict";\n' + harness + source + checks,
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("plugin", "filename", "function"),
    [
        ("_model_config", "refresh-switcher", "refreshSwitcherOnOverrideRevision"),
        ("_context_window", "refresh-context-window", "refreshContextWindow"),
        ("_goal", "refresh-goal", "refreshGoalOnRevision"),
    ],
)
def test_display_hooks_finish_while_requests_are_pending(plugin, filename, function):
    run_module(
        f"plugins/{plugin}/extensions/webui/apply_snapshot_before/{filename}.js",
        """
const calls = [];
let contextId;
const pending = () => { calls.push(contextId); return new Promise(() => {}); };
const modelConfigStore = { loadAgentProfiles: pending, refreshSwitcher: pending };
const contextWindowStore = { refresh: pending };
const goalStore = { refresh: pending };
""",
        f"""
const refresh = {function};
const snapshots = ["a", "b", "a"];
for (contextId of snapshots) {{
  const ctx = {{ snapshot: {{ context: contextId, contexts: [{{ id: contextId }}], logs: [] }} }};
  let finished = false;
  Promise.resolve(refresh(ctx)).then(() => {{ finished = true; }});
  await Promise.resolve();
  assert.ok(finished, "chat rendering waited for a display API");
  const count = calls.length;
  await refresh(ctx);
  assert.equal(calls.length, count, "unchanged snapshot started another refresh");
}}
assert.deepEqual([...new Set(calls)], ["a", "b"]);
assert.equal(calls.filter(id => id === "a").length, 2 * calls.filter(id => id === "b").length);
""",
    )


DEFERRED = """
const requests = [];
const pending = () => new Promise((resolve, reject) => requests.push({ resolve, reject }));
const errors = [];
console.error = (...args) => errors.push(args);
let selected = "a";
const chatsStore = { getSelectedChatId: () => selected };
const createStore = (_name, model) => model;
"""


def test_model_switcher_keeps_only_latest_selected_chat_and_loading_state():
    run_module(
        "plugins/_model_config/webui/switcher-mixin.js",
        DEFERRED + """
globalThis.window = { Alpine: { store: () => ({ selected }) } };
const callJsonApi = pending;
""",
        """
const store = { ...switcherState, ...switcherMethods, loadSwitcherState: pending };
const state = name => ({ allowed: true, presets: [], override: null,
  configuredPreset: name, effectivePreset: name });
const first = store.refreshSwitcher("a");
selected = "b";
const second = store.refreshSwitcher("b");
selected = "a";
const latest = store.refreshSwitcher("a");
requests[0].resolve(state("old-a"));
await first;
assert.ok(store.switcherLoading, "old refresh cleared the current loading flag");
requests[2].resolve(state("new-a"));
await latest;
requests[1].resolve(state("old-b"));
await second;
assert.equal(store.switcherEffectivePreset, "new-a");
assert.equal(store.switcherLoading, false);

const deselected = store.refreshSwitcher("a");
selected = "";
requests[3].resolve(state("late-a"));
await deselected;
assert.equal(store.switcherEffectivePreset, "new-a", "deselected chat replaced selector state");
const failed = store.refreshSwitcher("");
requests[4].reject(new Error("offline"));
await failed;
assert.equal(store.switcherLoading, false);
assert.equal(errors.length, 1);

selected = "a";
const profiles = store.loadAgentProfiles(true);
selected = "b";
requests[5].resolve({ profiles: [{ id: "private-to-a", title: "A" }] });
await profiles;
assert.equal(store.agentProfiles.length, 0, "old profile catalog escaped into the next chat");
""",
    )


def test_profile_save_in_old_chat_does_not_cancel_current_selector_refresh():
    run_module(
        "plugins/_model_config/webui/switcher-mixin.js",
        DEFERRED + """
const contexts = { a: { agent_profile: "agent0" }, b: { agent_profile: "researcher" } };
globalThis.window = { Alpine: { store: () => ({ selected, selectedContext: contexts[selected] }) } };
const fetchApi = pending;
""",
        """
const store = { ...switcherState, ...switcherMethods,
  loadAgentProfiles: async () => [], loadSwitcherState: pending };
const saved = store.selectAgentProfile("a", "developer");
await Promise.resolve();
selected = "b";
const current = store.refreshSwitcher("b");
requests[0].resolve({ ok: true, json: async () => ({
  ok: true, agent_profile: "developer", agent_profile_label: "Developer",
}) });
for (let tick = 0; tick < 4; tick++) await Promise.resolve();
assert.equal(requests.length, 2, "old profile save started a refresh for the wrong chat");
assert.ok(store.switcherLoading, "old profile save finished the current load");
requests[1].resolve({ allowed: true, presets: [], override: null,
  configuredPreset: "b", effectivePreset: "b" });
assert.equal(await saved, true);
await current;
assert.equal(store.switcherEffectivePreset, "b");
assert.equal(store.switcherLoading, false);
assert.equal(store.agentProfileSaving, false);
assert.equal(contexts.a.agent_profile, "developer");
assert.equal(contexts.b.agent_profile, "researcher");
""",
    )


@pytest.mark.parametrize("operation", ["selectPresetSwitch", "clearOverrideSwitch"])
@pytest.mark.parametrize("switch_chat", [False, True])
def test_model_save_updates_selector_only_for_selected_chat(operation, switch_chat):
    run_module(
        "plugins/_model_config/webui/switcher-mixin.js",
        DEFERRED + f"const operation = {operation!r};\nconst switchChat = {str(switch_chat).lower()};\n" + """
globalThis.window = { Alpine: { store: () => ({ selected }) } };
""",
        """
const store = { ...switcherState, ...switcherMethods,
  setPresetOverride: pending, clearOverride: pending, loadSwitcherState: pending };
const saved = store[operation]("a", "new-a");
if (switchChat) selected = "b";
const current = store.refreshSwitcher(selected);
requests[1].resolve({ allowed: true, presets: [], override: { preset_name: selected },
  configuredPreset: selected, effectivePreset: selected });
await current;
requests[0].resolve({ ok: true, preset_name: "new-a", effective_preset: "scoped-a" });
assert.equal(await saved, true, "successful save in the original chat was lost");
const expectedPreset = switchChat ? "b" : operation === "selectPresetSwitch" ? "new-a" : "scoped-a";
const expectedOverride = switchChat ? { preset_name: "b" } : operation === "selectPresetSwitch" ? { preset_name: "new-a" } : null;
assert.equal(store.switcherEffectivePreset, expectedPreset);
assert.deepEqual(store.switcherOverride, expectedOverride);
assert.equal(store.switcherLoading, false);
""",
    )


def test_goal_refresh_drops_stale_success_and_failure_and_clears_on_deselect():
    run_module(
        "plugins/_goal/webui/goal-store.js",
        DEFERRED + "const callJsonApi = pending;\n",
        """
const first = store.refresh(true);
store.goal = { objective: "old goal" };
store.editing = true;
selected = "b";
const second = store.refresh(true);
assert.equal(store.goal, null);
assert.equal(store.editing, false);
selected = "a";
const latest = store.refresh(true);
requests[0].resolve({ goal: { objective: "stale" } });
await first;
requests[1].reject(new Error("stale failure"));
await second;
assert.equal(store.goal, null);
assert.ok(store.loading, "stale failure cleared the current loading flag");
assert.equal(errors.length, 0);
requests[2].resolve({ goal: { objective: "latest" } });
await latest;
assert.equal(store.goal.objective, "latest");
assert.equal(store.loading, false);

const deselected = store.refresh(true);
selected = "";
await store.refresh(true);
requests[3].resolve({ goal: { objective: "late" } });
await deselected;
assert.equal(store.goal, null);
assert.equal(store.loading, false);
selected = "b";
const failed = store.refresh(true);
requests[4].reject(new Error("offline"));
await failed;
assert.equal(store.goal, null);
assert.equal(store.loading, false);
assert.equal(errors.length, 1);
""",
    )


def test_context_usage_ignores_stale_requests_and_deselected_chat():
    run_module(
        "plugins/_context_window/webui/context-window-store.js",
        DEFERRED + """
const callJsonApi = pending;
const preferencesStore = { registerUiControlVisibility() {} };
""",
        """
const first = store.refresh();
selected = "b";
const second = store.refresh();
selected = "a";
const latest = store.refresh();
requests[2].resolve({ tokens: 30, context_window: 100 });
await latest;
requests[0].resolve({ tokens: 10, context_window: 100 });
requests[1].resolve({ tokens: 20, context_window: 100 });
await Promise.all([first, second]);
assert.equal(store.usage.ringLabel, "30%");
const deselected = store.refresh();
selected = "b";
requests[3].resolve({ tokens: 90, context_window: 100 });
await deselected;
assert.equal(store.usage.ringLabel, "30%", "request landed after selection changed");
selected = "";
await store.refresh();
assert.equal(store.usage.ringLabel, "–");
selected = "a";
const failed = store.refresh();
requests[4].reject(new Error("offline"));
await failed;
assert.equal(errors.length, 1);
""",
    )


def test_model_switcher_keeps_the_label_mounted_during_background_refresh():
    run_module(
        "plugins/_model_config/webui/switcher-mixin.js",
        DEFERRED + """
globalThis.window = { Alpine: { store: () => ({ selected }) } };
const callJsonApi = pending;
""",
        """
const store = { ...switcherState, ...switcherMethods, loadSwitcherState: pending,
  switcherPresets: [{ name: "Default" }], switcherEffectivePreset: "Default",
  switcherLoading: false };
const refresh = store.refreshSwitcher("a");
assert.equal(store.switcherLoading, false, "background refresh unmounted the switcher label");
requests[0].resolve({ allowed: true, presets: [{ name: "Fast" }], override: null,
  configuredPreset: "Fast", effectivePreset: "Fast" });
await refresh;
assert.equal(store.switcherEffectivePreset, "Fast", "background refresh did not apply the fresh state");
assert.equal(store.switcherLoading, false);

const fresh = { ...switcherState, ...switcherMethods, loadSwitcherState: pending };
const initial = fresh.refreshSwitcher("a");
assert.ok(fresh.switcherLoading, "first load did not gate the label");
requests[1].resolve({ allowed: true, presets: [], override: null,
  configuredPreset: "Default", effectivePreset: "Default" });
await initial;
""",
    )
