from __future__ import annotations

import base64
from pathlib import Path
import re
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "plugins" / "_agent_editor" / "webui" / "agent-editor-store.js"
MODAL = ROOT / "plugins" / "_agent_editor" / "webui" / "main.html"
TOOLTIP_STORE = ROOT / "webui" / "components" / "tooltips" / "tooltip-store.js"
SWITCHER = (
    ROOT
    / "plugins"
    / "_model_config"
    / "extensions"
    / "webui"
    / "chat-input-progress-start"
    / "model-switcher.html"
)
SWITCHER_MIXIN = ROOT / "plugins" / "_model_config" / "webui" / "switcher-mixin.js"


def test_agent_editor_surface_has_normative_entry_points_and_accessible_controls() -> None:
    modal = MODAL.read_text(encoding="utf-8")
    store = STORE.read_text(encoding="utf-8")
    switcher = SWITCHER.read_text(encoding="utf-8")
    tool_section = re.search(
        r'data-agent-editor-section="3".*?(?=<section x-show="\$store\.agentEditor\.section === \'4\'")',
        modal,
        re.DOTALL,
    ).group(0)
    mcp_section = re.search(
        r'data-agent-editor-section="4".*?(?=<section x-show="\$store\.agentEditor\.section === \'5\'")',
        modal,
        re.DOTALL,
    ).group(0)
    skill_section = re.search(
        r'data-agent-editor-section="5".*?(?=<section x-show="\$store\.agentEditor\.section === \'6\'")',
        modal,
        re.DOTALL,
    ).group(0)
    easy_surface = modal.split('<div class="agent-advanced"', 1)[0]

    assert "Create agent" not in switcher
    assert "Manage agents" in switcher
    assert '<div class="agent-profile-row"' in switcher
    assert 'class="agent-profile-row-edit"' in switcher
    assert ':aria-label="`Edit ${profile.label || profile.key}`"' in switcher
    assert "profileId: profile.key" in switcher
    assert "<span>Edit</span>" in switcher
    assert "profile.customized" not in switcher
    assert 'class="model-switcher-item agent-profile-edit"' not in switcher
    assert "min-height: 24px" in re.search(
        r"\.agent-profile-row-edit\s*\{([^}]*)\}", switcher
    ).group(1)
    assert "createAgentProfileChat" not in switcher
    assert all(
        label in modal
        for label in (
            "Identity",
            "Prompt files",
            "Tools",
            "MCPs",
            "Skills",
            "Review",
            "Save & test",
        )
    )
    assert 'aria-label="Editor mode"' in modal
    assert "Allow selected" not in modal and "Block selected" not in modal
    assert "No optional tools" not in modal
    assert 'class="agent-model-preset-picker"' in modal
    assert modal.count('x-model="$store.agentEditor.draft.modelPreset"') == 2
    assert modal.count('$el.value = $store.agentEditor.draft.modelPreset') == 2
    assert 'id="agent-editor-easy-model-preset"' in easy_surface
    easy_identity = easy_surface[easy_surface.index('<section class="agent-easy-identity">'):easy_surface.index('<section class="agent-easy-field">')]
    assert easy_identity.index('id="agent-editor-name"') < easy_identity.index('id="agent-editor-easy-model-preset"')
    assert easy_surface.index('id="agent-editor-easy-model-preset"') < easy_surface.index('id="agent-editor-instructions"')
    assert '`Use current preset (${$store.agentEditor.state.model_preset.effective})`' in modal
    assert 'x-for="preset in $store.agentEditor.state.model_presets"' in modal
    assert modal.count("Edit Presets") == 2
    assert "Manage presets" not in modal
    assert "model-preset-row" not in modal
    assert easy_surface.count('<details class="capability-accordion">') == 3
    assert re.findall(r'<summary><span>(Choose individual (?:tools|MCPs|skills))</span><x-icon name="expand_more"></x-icon></summary>', easy_surface) == ["Choose individual tools", "Choose individual MCPs", "Choose individual skills"]
    assert '<details class="capability-accordion" open' not in easy_surface
    assert 'x-for="tool in $store.agentEditor.standardToolCatalog"' in easy_surface
    assert 'x-for="skill in $store.agentEditor.skillCatalog"' in easy_surface
    assert 'x-for="tool in $store.agentEditor.mcpCatalog"' in easy_surface
    assert "Choose tools in Advanced" not in modal
    assert "Use standard tool access" not in modal
    assert "Use standard skill access" not in modal
    assert 'class="policy-lists"' not in modal
    assert "policy-transfer-actions" not in modal
    assert tool_section.count('class="policy-group"') == 1
    assert mcp_section.count('class="policy-group"') == 1
    assert skill_section.count('class="policy-group"') == 1
    assert '<label>Category ' not in tool_section
    assert "indeterminate" not in modal
    assert modal.count('class="policy-state-control" role="group"') == 6
    assert modal.count(':aria-pressed="$store.agentEditor.policyItemState') == 18
    assert '<details class="policy-description"' not in tool_section
    assert '<details class="policy-description"' not in mcp_section
    assert '<details class="policy-description"' not in skill_section
    assert tool_section.count('class="policy-item-description"') == 1
    assert mcp_section.count('class="policy-item-description"') == 1
    assert skill_section.count('class="policy-item-description"') == 1
    assert "Your changes override the built-in profile. The original files stay unchanged." in modal
    assert 'x-model="$store.agentEditor.projectName"' in modal
    assert 'x-init="$nextTick(() => $el.value = $store.agentEditor.projectName)"' in modal
    assert '@change="$store.agentEditor.onScopeChanged()"' in modal
    assert '<option value="">Global</option>' in modal
    assert 'x-for="project in $store.agentEditor.projects"' in modal
    assert 'x-show="profile.deletable"' in modal
    assert 'class="agent-customized-indicator"' not in modal
    assert 'class="button agent-manager-create"' in modal
    assert 'class="active-agent-display"' in modal
    assert 'class="button icon-button" title="Edit"' in modal
    assert 'class="text-button agent-manager-inline-action"' in modal
    inline_action_style = re.search(
        r"\.agent-editor \.agent-manager-inline-action\s*\{([^}]*)\}", modal
    ).group(1)
    assert "color:var(--color-message-text)" in inline_action_style
    assert ".agent-editor .agent-manager-inline-action:hover:not(:disabled)" in modal
    assert ':disabled="!!$store.agentEditor.duplicatingProfile"' in modal
    assert ':aria-label="`Duplicate ${profile.title || profile.id}`"' in modal
    assert "$store.agentEditor.duplicateProfile(profile)" in modal
    assert 'x-show="profile.scope_has_overrides && !profile.deletable"' in modal
    assert ':aria-label="`Reset ${profile.title || profile.id} to default`"' in modal
    assert "Restore original" not in modal
    assert modal.count("Reset to default") >= 6
    assert "$store.agentEditor.restoreProfile(profile)" in modal
    assert "$store.agentEditor.restoreProfile($store.agentEditor.state.profile)" in modal
    assert 'class="agent-editor-topbar-actions"' in modal
    topbar = modal.split('class="agent-editor-topbar-actions"', 1)[1].split("</header>", 1)[0]
    footer = modal.split('class="modal-footer agent-editor-footer"', 1)[1]
    assert "Reset to default" not in topbar
    assert "$store.agentEditor.restoreProfile($store.agentEditor.state.profile)" in footer
    assert 'class="btn btn-cancel agent-reset-profile"' in footer
    assert '<x-icon name="restore"></x-icon><span>Reset to default</span>' not in footer
    assert "x-show=\"$store.agentEditor.draft && !$store.agentEditor.draft.creating" in footer
    assert ':disabled="$store.agentEditor.saving || !$store.agentEditor.state?.profile?.scope_has_overrides"' in footer
    avatar_reset = 'x-show="$store.agentEditor.state.profile.metadata.avatar.has_override || $store.agentEditor.draft.avatar" @click="$store.agentEditor.resetAvatar()">Reset</button>'
    assert modal.count(avatar_reset) == 2
    assert '@click="$store.agentEditor.resetAvatar()">Remove</button>' not in modal
    assert 'class="btn btn-cancel" @click="window.closeModal?.()">Cancel</button>' not in modal
    assert 'class="toggle agent-profile-availability"' in modal
    assert ':disabled="$store.agentEditor.profileAvailabilitySaving"' in modal
    assert "Default is always available" not in modal
    assert "$store.agentEditor.setProfileEnabled(profile, $event.target.checked)" in modal
    assert "agent-profile-availability" not in store
    assert "activateProfile(profile.id)" not in modal
    assert 'class="button cancel icon-button" x-show="profile.deletable"' in modal
    assert "project_override_active" not in modal
    assert "profile.origin === 'Custom'" not in modal
    assert "Agent scope" not in modal
    assert "Create agents and customize inherited profiles" not in modal
    assert "Unavailable — kept in your settings" in modal
    assert "Customize this file" not in modal
    assert "Choose a file and edit its prompt." in modal
    assert "inherited version next to your version" not in modal
    assert 'role="tablist" aria-label="Prompt view"' not in modal
    assert "Your version" not in modal and ">Compare</button>" not in modal
    assert "Find in file" not in modal and "prompt-match-action" not in modal
    assert "No prompt files match your search." in modal
    assert "Saving will change exactly these files — nothing else." in modal
    assert "Review & test" not in modal
    assert "Refresh change plan" not in modal
    assert "Back to Easy" not in modal
    assert "This agent has a detailed prompt" not in modal
    assert "Replace with simple instructions" not in modal
    assert "easyInstructionsEditable" not in modal
    assert '<textarea id="agent-editor-instructions"' in modal
    assert ':required="$store.agentEditor.draft?.creating"' in easy_surface
    assert '>Instructions <span class="agent-status-badge compact"' in easy_surface
    assert ">Required</span>" in easy_surface
    assert "<h2" not in modal
    assert "Section 1" not in modal
    assert '<textarea id="agent-editor-description" rows="2"' in modal
    assert "Allow newly installed" not in modal
    assert modal.count("<strong>Allow tools by default</strong>") == 2
    assert modal.count("<strong>Allow MCPs by default</strong>") == 2
    assert modal.count("<strong>Allow skills by default</strong>") == 2
    assert "Allow tools and MCPs by default" not in modal
    assert "Applies to Tools and MCPs left on Default." not in modal
    assert "Applies to Skills left on Default." not in modal
    assert "No blocked tools" not in modal and "No blocked skills" not in modal
    assert "policy-description" not in modal and "-webkit-line-clamp:2" not in modal
    assert 'class="prompt-file-list" role="region" aria-label="Prompt file list" tabindex="0"' in modal
    assert 'class="prompt-editor" role="region" aria-label="Selected prompt file" tabindex="0"' in modal
    assert "Preview combined prompt" not in modal
    assert 'class="prompt-customization-path"' in modal
    assert '<strong x-text="$store.agentEditor.promptTitle($store.agentEditor.selectedPromptDraft)"></strong>' in modal
    assert 'x-text="$store.agentEditor.promptTitle(prompt)"' in modal
    assert "prompt-details" not in modal
    assert "Python processors" not in modal
    assert 'x-text="$store.agentEditor.promptDisplayState($store.agentEditor.selectedPromptDraft)"' in modal
    assert '<span>Saves to</span>' in modal
    assert 'title="Copy path" aria-label="Copy path"' in modal
    assert "This file is generated dynamically" not in modal
    assert '<p class="prompt-template-help"' in modal
    assert 'x-text="$store.agentEditor.promptVariableExample"' in modal
    assert modal.index('id="agent-editor-prompt-ace"') < modal.index('<p class="prompt-template-help"')
    assert "source-chain" not in modal and "promptSourceChain" not in store
    assert "$store.agentEditor.promptCustomizationPath()" in modal
    assert 'class="review-identity"' in modal
    assert 'aria-label="Agent identity"' in modal
    assert 'id="review-identity-title"' not in modal
    review_identity = modal[modal.index('class="review-identity"'):modal.index('class="change-plan"')]
    assert "draft.profileId\"></code>" not in review_identity
    assert "width:92vw" in modal
    assert ".modal-inner.agent-editor-advanced .modal-scroll { max-height:none; }" in modal
    assert '.agent-advanced-content > section[data-agent-editor-section="2"] { height:100%; min-height:0; }' in modal
    assert ".prompt-workspace { flex:1 1 auto;" in modal
    assert 'width:1.5rem; height:1.5rem' in modal
    assert 'id="agent-editor-prompt-ace"' in modal
    assert 'id="agent-editor-prompt-text"' not in modal
    assert "globalThis.ace.edit(container)" in store
    assert 'editor.session.setMode("ace/mode/markdown")' in store
    assert "editor.session.setUseWrapMode(true)" in store
    assert "showPrintMargin: false" in store and "useWorker: false" in store
    assert "findInPrompt" not in store and "promptTextSearch" not in store
    assert 'class="agent-editor-heading"' in modal
    assert ':aria-invalid=' in modal
    assert modal.count('role="alert"') >= 4
    assert "Fix ${$store.agentEditor.validationIssues().length}" in modal
    assert modal.count("$store.agentEditor.validationIssues().length > 0") == 2
    assert ':title="$store.agentEditor.validationErrors().join(\' \')"' in modal
    assert "Fix the highlighted issues before saving" not in modal
    assert "$store.agentEditor.view === 'editor' && !$store.agentEditor.pendingMutation" in modal
    assert 'x-show="$store.agentEditor.view === \'editor\' && !$store.agentEditor.draft?.creating"' in modal
    assert 'class="btn btn-ok" x-show="$store.agentEditor.view === \'editor\'"' in modal
    assert "Delete all customizations in" in modal
    assert '.agent-editor input[type="checkbox"]' not in modal
    assert 'promptDisplayState(prompt)' in modal
    assert "Will reset to default on save." in modal
    assert "metadataProvenance('description')" not in modal
    assert 'x-show="$store.agentEditor.metadataProvenance(\'title\')"' in modal
    assert 'metadataProvenance(\'context\')' not in modal
    assert ':title="prompt.filename"' not in modal
    assert "promptEditPending($store.agentEditor.selectedPromptDraft)" in modal
    assert 'aria-label="Discard current edit"' in modal
    assert 'aria-label="Accept current edit"' in modal
    assert ':readonly="!$store.agentEditor.isPromptEditing' not in modal
    assert ".prompt-ace { flex:1; min-height:0;" in modal
    store_source = STORE.read_text(encoding="utf-8")
    assert "cannot be recovered" in store_source
    assert "deletionImpactHtml" not in store_source
    assert "agent-profile-avatar" in switcher
    assert '<button type="button" class="model-switcher-item agent-profile-item"' in switcher
    assert '<div class="model-switcher-item agent-profile-item"' not in switcher
    switcher_mixin = SWITCHER_MIXIN.read_text(encoding="utf-8")
    assert "avatar_url" in switcher_mixin
    assert "BUILT_IN_AGENT_COLORS" in switcher_mixin
    assert '!["_example", "default"].includes(profile.id)' in switcher_mixin
    assert 'activeKey !== "default"' in switcher_mixin
    assert "customized: !!profile.has_user_overrides" not in switcher_mixin
    assert 'x-for="profile in $store.agentEditor.visibleProfiles"' in modal
    assert "$store.agentEditor.activeProfile().id !== 'default'" in modal
    assert 'name="palette"' in modal and 'name="add_photo_alternate"' in modal
    assert ".capability-accordion .policy-items { max-height:none; overflow:visible;" in modal
    assert ".capability-policy-group + .capability-policy-group { border-top:1px solid var(--color-border);" in modal
    assert "font-weight:500" in re.search(
        r"\.capability-accordion summary\s*\{([^}]*)\}", modal
    ).group(1)
    assert ".capability-accordion[open] summary x-icon { transform:rotate(180deg); }" in modal
    assert "toolCategory" not in store_source
    assert "selectedAllowed" not in store_source and "selectedBlocked" not in store_source
    assert "moveAllVisible" not in store_source and "confirmBulkMove" not in store_source
    assert "setPolicyItemState" in store_source and "collapsePolicy" in store_source
    assert '.agent-editor [aria-invalid="true"]' not in modal
    assert "color-scheme:dark" not in modal
    assert "#fff 82%" not in modal
    assert ".agent-manager-name strong,.agent-manager-copy p { overflow-wrap:anywhere; }" in modal
    assert ".field-error { display:block; color:var(--color-text)" in modal
    assert ".prompt-pane" not in modal
    assert 'callJsonApi("/plugins/_agent_editor/agent_editor"' in switcher_mixin
    assert "profile.enabled !== false" in switcher_mixin
    assert 'x-show="!$store.modelConfig.agentProfilesLoading"' in switcher
    assert "@keydown.ctrl.s.prevent" in modal
    assert "@media (max-width: 760px)" in modal
    assert "tri-state-item" not in modal
    assert "policy-state-legend" not in modal
    assert "policy-item-state" not in modal
    assert modal.count("Default (${$store.agentEditor.policyDefault") == 6
    assert "border-radius:var(--border-radius-sm)" in modal
    assert "cyclePolicyItem" not in store_source and "policyAriaChecked" not in store_source
    assert ".agent-manager-card { grid-template-columns:3rem minmax(0,1fr) auto; align-items:start; }" in modal
    assert ".agent-manager-actions { grid-column:auto; align-self:stretch; display:grid;" in modal
    assert ".agent-manager-actions .agent-profile-availability { grid-column:1/-1; }" in modal
    assert ".footer-actions { width:auto; max-width:100%; flex-wrap:wrap; justify-content:flex-end; }" in modal
    assert ".footer-actions .btn { flex:0 1 auto; text-align:center; }" in modal
    assert modal.count("data-modal-footer") == 1
    assert ">Close</button>" not in modal


def test_agent_editor_store_has_no_conversational_or_model_builder_path() -> None:
    source = STORE.read_text(encoding="utf-8")
    modal = MODAL.read_text(encoding="utf-8")
    switcher_source = (
        ROOT / "plugins" / "_model_config" / "webui" / "switcher-mixin.js"
    ).read_text(encoding="utf-8")

    assert 'createStore("agentEditor", model)' in source
    assert "CREATE_AGENT_PROFILE_PROMPT" not in switcher_source
    assert "a0-create-agent" not in switcher_source
    assert "save_agent_data" not in source
    assert not re.search(r"utility.?model|call.?model|generate", source, re.IGNORECASE)
    assert "Advanced <span" not in modal
    assert 'class="toast-action-row"' in source
    assert 'class="button confirm"' in source
    assert "toast-link" not in source and ".toast-link" not in modal


@pytest.mark.skipif(not shutil.which("node"), reason="node is required")
def test_empty_dynamic_title_disposes_its_tooltip() -> None:
    source = re.sub(
        r"^import .*?;\n",
        "",
        TOOLTIP_STORE.read_text(encoding="utf-8"),
        flags=re.MULTILINE,
    )
    source += "\nexport { ensureBootstrapTooltip };\n"
    module_url = "data:text/javascript;base64," + base64.b64encode(
        ("const createStore = (_name, value) => value;\n" + source).encode("utf-8")
    ).decode("ascii")
    script = f"""
class FakeElement {{
  constructor() {{ this.attributes = new Map([["title", "Instructions are required."]]); }}
  getAttribute(name) {{ return this.attributes.has(name) ? this.attributes.get(name) : null; }}
  hasAttribute(name) {{ return this.attributes.has(name); }}
  setAttribute(name, value) {{ this.attributes.set(name, String(value)); }}
  removeAttribute(name) {{ this.attributes.delete(name); }}
}}
globalThis.Element = FakeElement;
let instance = null;
class Tooltip {{
  static getInstance(element) {{ return instance?.element === element ? instance : null; }}
  constructor(element) {{ this.element = element; instance = this; }}
  dispose() {{ instance = null; }}
  setContent() {{}}
}}
globalThis.bootstrap = {{ Tooltip }};
const {{ ensureBootstrapTooltip }} = await import({module_url!r});
const element = new FakeElement();
ensureBootstrapTooltip(element);
if (!instance || element.getAttribute("data-bs-original-title") !== "Instructions are required.") throw new Error("tooltip was not initialized");
element.setAttribute("title", "");
ensureBootstrapTooltip(element);
if (instance || element.hasAttribute("data-bs-original-title") || element.hasAttribute("data-bs-tooltip-initialized")) throw new Error("cleared title left a stale tooltip");
"""
    subprocess.run(["node", "--input-type=module", "-e", script], check=True)


@pytest.mark.skipif(not shutil.which("node"), reason="node is required")
def test_local_slugging_and_fresh_chat_profile_selection_are_deterministic() -> None:
    source = STORE.read_text(encoding="utf-8")
    source = re.sub(r"^import .*?;\n", "", source, flags=re.MULTILINE)
    harness = r"""
const calls = [];
const confirmations = [];
const toasts = [];
let setEnabledHandler = null;
let loadHandler = null;
let profilesHandler = null;
let confirmResult = false;
const createStore = (_name, value) => value;
const callJsonApi = async (endpoint, payload) => {
  calls.push({ endpoint, payload });
  if (payload?.action === "load" && loadHandler) return loadHandler(payload);
  if (payload?.action === "list") return profilesHandler
    ? profilesHandler(payload)
    : { ok: true, profiles: [] };
  if (payload?.action === "set_enabled") return setEnabledHandler
    ? setEnabledHandler(payload)
    : { ok: true, active_profile: "default", active_profile_label: "Default" };
  if (payload?.action === "plan") return {
    ok: true,
    written: [payload.project_name
      ? `usr/projects/${payload.project_name}/.a0proj/agents/${payload.patch.profile_id}/agent.yaml`
      : `usr/agents/${payload.patch.profile_id}/agent.yaml`],
    deleted: [],
    warnings: [],
  };
  if (payload?.action === "duplicate") return {
    ok: true,
    profile_id: "researcher-1",
    title: "Researcher 1",
    profiles: [{ id: "researcher" }, { id: "researcher-1" }],
  };
  if (endpoint === "/agent_profile_set") return {
    ok: true,
    agent_profile: payload.agent_profile,
    agent_profile_label: "Researcher",
  };
  return endpoint === "/chat_create" ? { ok: true, ctxid: "fresh-chat" } : { ok: true };
};
const fetchApi = async () => ({ ok: true, json: async () => ({}) });
const closeModal = async () => {};
const openModal = async () => {};
const showConfirmDialog = async options => { confirmations.push(options); return confirmResult; };
const chatsStore = {
  selected: "old-chat",
  selectedContext: { project: { name: "demo" }, agent_profile: "researcher" },
  selectChat: async (id) => {
    calls.push({ endpoint: "selectChat", payload: id });
    chatsStore.selected = id;
    chatsStore.selectedContext = { agent_profile: "default", agent_profile_label: "Default" };
  },
};
const modelConfigStore = {
  loadAgentProfiles: async force => calls.push({ endpoint: "loadAgentProfiles", payload: force }),
  openPresetEditor: async preset => calls.push({ endpoint: "openPresetEditor", payload: preset }),
  selectAgentProfile: async (contextId, profileId) => {
    calls.push({ endpoint: "selectAgentProfile", payload: { contextId, profileId } });
    return true;
  },
  getAgentProfileVisual: (_id, label) => ({ color: "#123456", url: "", initials: label?.[0] || "A" }),
};
const aceState = { change: null, find: null, destroyed: false, value: "" };
const aceContainer = { textContent: "" };
const aceSession = {
  setMode: value => { aceState.mode = value; },
  setUseWrapMode: value => { aceState.wrap = value; },
  on: (name, callback) => { if (name === "change") aceState.change = callback; },
  off: (name, callback) => { if (name === "change" && aceState.change === callback) aceState.change = null; },
};
const aceEditor = {
  container: aceContainer,
  session: aceSession,
  textInput: { getElement: () => ({ setAttribute: (key, value) => { aceState[key] = value; } }) },
  setTheme: value => { aceState.theme = value; },
  setOptions: value => { aceState.options = value; },
  setValue: value => { aceState.value = value; aceState.change?.(); },
  getValue: () => aceState.value,
  find: (query, options) => { aceState.find = { query, options }; },
  focus: () => { aceState.focused = true; },
  resize: () => { aceState.resized = true; },
  destroy: () => { aceState.destroyed = true; },
};
globalThis.ace = { edit: container => { aceState.container = container; return aceEditor; } };
globalThis.window = globalThis;
globalThis.document = {
  dispatchEvent: (event) => calls.push({ endpoint: "event", payload: event.type }),
  createElement: () => ({ textContent: "", get innerHTML() { return this.textContent; } }),
  addEventListener: () => {},
  removeEventListener: () => {},
};
globalThis.CustomEvent = class { constructor(type) { this.type = type; } };
globalThis.sessionStorage = { setItem: () => {}, getItem: () => "", removeItem: () => {} };
globalThis.localStorage = { setItem: () => {}, getItem: () => "" };
globalThis.requestAnimationFrame = callback => callback();
globalThis.confirm = () => true;
globalThis.justToast = (...args) => toasts.push(args);
"""
    checks = r"""
if (slugifyProfileName("  Crème Brûlée__Lab  ") !== "creme-brulee-lab") throw new Error("slug mismatch");
if (slugifyProfileName("東京") !== "") throw new Error("unsupported slug mismatch");
store.draft = { title: "stale" };
store.initialDraft = { title: "clean" };
store.intent = { view: "manage", contextId: "" };
const modalTitle = { textContent: "" };
const modalElement = { querySelector: selector => selector === ".modal-title" ? modalTitle : null };
const modalInner = { classList: { toggle: () => {} } };
await store.mount({
  closest: selector => selector === ".modal" ? modalElement : selector === ".modal-inner" ? modalInner : null,
  querySelector: () => null,
});
if (store.draft !== null || store.initialDraft !== null || store.dirty || store.loading) throw new Error("manage mount kept stale draft state");
if (modalTitle.textContent !== "Manage agents") throw new Error("manage mount title mismatch");
store.state = {
  profile: { id: "new-agent", avatar_url: "", metadata: { title: {}, description: {}, context: {}, avatar: {} } },
  prompts: [
    { filename: "agent.system.main.specifics.md", group: "2.1", group_label: "Agent instructions", effective: "", inherited: "", source_chain: [] },
    { filename: "agent.system.main.communication.md", group: "2.4", group_label: "Communication", effective: "Inherited comm", inherited: "Inherited comm", source_chain: ["Framework", "Researcher"], state: "Inherited", has_override: false },
  ],
  model_preset: { has_override: false },
  tools: { policy: { mode: "inherit" }, effective_policy: { mode: "inherit", default: "allow", mcp_default: "allow", allowed: [], blocked: [] }, has_override: false, catalog: [] },
  skills: { policy: { mode: "inherit" }, effective_policy: { mode: "inherit", default: "allow", allowed: [], blocked: [] }, has_override: false, catalog: [] },
};
store.makeDraft(true);
if (await store.previewPlan()) throw new Error("invalid plan unexpectedly succeeded");
if (store.planStatus !== "blocked" || store.error || store.validationIssues().length !== 2) throw new Error("blocked plan state mismatch");
if (store.fieldIssue("name")?.message !== "Agent name is required.") throw new Error("inline name issue missing");
if (store.fieldIssue("instructions")?.field !== "agent-editor-instructions") throw new Error("Easy validation targeted the wrong input");
await store.save();
if (store.error) throw new Error("validation leaked into dismissible error banner");
store.state.profile.id = "new-agent";
store.state.profile.origin = "Built-in";
store.state.profile.metadata.title = { inherited_source: "agents/new-agent/agent.yaml" };
if (store.metadataProvenance("title") !== "") throw new Error("new profile showed misleading provenance");
store.draft.creating = false;
if (store.metadataProvenance("title") !== "Using the default") throw new Error("default provenance mismatch");
store.profiles = [{ id: "researcher", title: "Researcher" }, { id: "default", title: "Default" }];
if (store.visibleProfiles.length !== 1 || store.visibleProfiles[0].id !== "researcher") throw new Error("Default profile remained selectable in Agent Editor");
store.state.profile.metadata.title = { inherited_source: "agents/researcher/agent.yaml" };
if (store.metadataProvenance("title") !== "Inherited from Researcher") throw new Error("inherited provenance mismatch");
store.state.profile.metadata.title.has_override = true;
if (store.metadataProvenance("title") !== "Customized by you") throw new Error("custom provenance mismatch");
store.draft.creating = true;
store.draft.profileId = "researcher";
store.selectedPrompt = "agent.system.main.specifics.md";
store.projectName = "";
if (store.promptCustomizationPath() !== "usr/agents/researcher/prompts/agent.system.main.specifics.md") throw new Error("Global prompt customization path mismatch");
store.projectName = "demo";
if (store.promptCustomizationPath() !== "usr/projects/demo/.a0proj/agents/researcher/prompts/agent.system.main.specifics.md") throw new Error("project prompt customization path mismatch");
const copiedPaths = [];
Object.defineProperty(globalThis, "navigator", { configurable: true, value: { clipboard: { writeText: async value => copiedPaths.push(value) } } });
await store.copyPromptPath();
if (copiedPaths[0] !== store.promptCustomizationPath() || toasts.at(-1)?.[1] !== "success") throw new Error("copy path failed");
navigator.clipboard.writeText = async () => { throw new Error("Clipboard denied"); };
await store.copyPromptPath();
if (toasts.at(-1)?.[1] !== "error") throw new Error("clipboard failure reported success");
navigator.clipboard = undefined;
await store.copyPromptPath();
if (toasts.at(-1)?.[1] !== "error") throw new Error("missing clipboard reported success");
store.projectName = "";
const originalInstructions = store.instructions.value;
store.instructions.value = '{{ include "base.md" }}\n{{if available}}\n{{endif}}\nSave in {{workdir_path}}.';
if (store.promptVariableExample !== "{{workdir_path}}") throw new Error("variable hint showed a template directive");
store.instructions.value = "Profiles: {{agent_profiles}}";
if (store.promptVariableExample !== "{{agent_profiles}}") throw new Error("variable hint did not follow the selected template");
store.instructions.value = "Plain instructions";
if (store.promptVariableExample !== "{{name}}") throw new Error("variable hint fallback missing");
store.instructions.value = originalInstructions;
store.state.model_preset.effective = "Current";
store.state.model_presets = [{ name: "Codex" }];
store.draft.modelPreset = "Codex";
if (store.buildPatch().model_preset?.name !== "Codex") throw new Error("Easy model preset was not saved");
loadHandler = () => ({ ok: true, state: { model_presets: [{ name: "Codex" }] } });
await store.openPresetManager();
loadHandler = null;
if (!calls.some(call => call.endpoint === "openPresetEditor" && call.payload === "Codex")) throw new Error("Easy preset editor action did not reuse Model Configuration");
store.draft.modelPreset = "";
store.state.tools.catalog = [
  { id: "local:shell", name: "shell", label: "Shell", origin: "Agent Zero", available: true },
  { id: "local:gone", name: "gone", label: "Gone", origin: "Unavailable", available: false },
  { id: "mcp:docs:read", name: "read", label: "Docs read", origin: "MCP", available: true },
];
store.draft.toolPolicy = { mode: "inherit", default: "allow", mcp_default: "allow", allowed: [], blocked: [] };
store.initialDraft.toolPolicy = clone(store.draft.toolPolicy);
if (store.standardToolCatalog.length !== 1 || store.mcpCatalog.length !== 1 || store.toolCatalog.length !== 2) throw new Error("Easy tool/MCP grouping mismatch");
if (store.filteredTools("tool").length !== 2 || store.filteredTools("mcp").length !== 1) throw new Error("Advanced retained catalog grouping mismatch");
if (store.policyItemState("tool", "local:shell") !== "default") throw new Error("initial segmented state mismatch");
store.setPolicyItem("tool", "local:shell", "allow");
if (store.policyItemState("tool", "local:shell") !== "allow" || !store.draft.toolPolicy.allowed.includes("local:shell")) throw new Error("On selection failed");
store.setPolicyItem("tool", "local:shell", "block");
if (store.policyItemState("tool", "local:shell") !== "block" || !store.draft.toolPolicy.blocked.includes("local:shell")) throw new Error("Off selection failed");
if (JSON.stringify(store.skillWarnings({ allowed_tools: ["shell"] })) !== JSON.stringify(["shell"])) throw new Error("live skill warning missing");
store.setPolicyItem("tool", "local:shell", "default");
if (store.draft.toolPolicy.mode !== "inherit" || store.policyItemState("tool", "local:shell") !== "default") throw new Error("segmented undo did not collapse to inherit");
store.setPolicyDefault("tool", "block");
store.setPolicyItem("tool", "local:shell", "allow");
store.setPolicyDefault("tool", "allow");
if (!store.draft.toolPolicy.allowed.includes("local:shell")) throw new Error("explicit On was lost when the default changed");
store.setPolicyItem("tool", "local:shell", "block");
store.setPolicyDefault("tool", "block");
if (!store.draft.toolPolicy.blocked.includes("local:shell")) throw new Error("explicit Off was lost when the default changed");
store.setPolicyItem("tool", "local:shell", "default");
store.setPolicyDefault("tool", "allow");
if (store.draft.toolPolicy.mode !== "inherit") throw new Error("default undo did not collapse to inherit");
store.setPolicyDefault("mcp", "block");
if (store.policyDefault("tool") !== "allow" || store.policyDefault("mcp") !== "block") throw new Error("tool and MCP defaults were not independent");
if (!store.isToolAllowed(store.state.tools.catalog[0]) || store.isToolAllowed(store.state.tools.catalog[2])) throw new Error("MCP default affected the wrong catalog group");
store.setPolicyItem("mcp", "mcp:docs:read", "allow");
store.setPolicyDefault("mcp", "allow");
if (!store.draft.toolPolicy.allowed.includes("mcp:docs:read")) throw new Error("explicit MCP On was lost when its default changed");
store.setPolicyItem("mcp", "mcp:docs:read", "default");
if (store.draft.toolPolicy.mode !== "inherit") throw new Error("MCP default undo did not collapse to inherit");
store.projectName = "demo";
store.intent = { ...store.intent, projectName: "demo" };
if (!store.currentChatUsesScope() || !store.isProfileActive("researcher")) throw new Error("active project profile state mismatch");
store.profiles = [{ id: "researcher", title: "Researcher", enabled: true }, { id: "default", title: "Default", enabled: true }];
if (store.activeProfile()?.id !== "researcher") throw new Error("active profile summary mismatch");
await store.setProfileEnabled(store.profiles[0], false);
if (!calls.some(item => item.payload?.action === "set_enabled" && item.payload.profile_id === "researcher") || chatsStore.selectedContext.agent_profile !== "default") throw new Error("profile availability did not reconcile the active chat");
if (!calls.some(item => item.endpoint === "loadAgentProfiles" && item.payload === true)) throw new Error("profile switcher did not refresh eagerly");
let releaseFirstToggle;
const firstToggleResponse = new Promise(resolve => { releaseFirstToggle = resolve; });
let toggleRequest = 0;
setEnabledHandler = () => {
  toggleRequest += 1;
  return toggleRequest === 1
    ? firstToggleResponse
    : Promise.resolve({ ok: true });
};
const rapidProfiles = [
  { id: "agent0", title: "Agent 0", enabled: true },
  { id: "developer", title: "Developer", enabled: true },
];
store.profiles = rapidProfiles;
const firstToggle = store.setProfileEnabled(rapidProfiles[0], false);
while (!toggleRequest) await Promise.resolve();
const secondToggle = store.setProfileEnabled(rapidProfiles[1], false);
await secondToggle;
if (toggleRequest !== 1 || rapidProfiles[1].enabled !== true || !store.profileAvailabilitySaving) throw new Error("availability saves were not serialized");
releaseFirstToggle({ ok: true });
await firstToggle;
if (store.profiles !== rapidProfiles || rapidProfiles[0].enabled || rapidProfiles[1].enabled !== true || store.profileAvailabilitySaving) throw new Error("first availability save did not settle cleanly");
await store.setProfileEnabled(rapidProfiles[1], false);
if (toggleRequest !== 2 || rapidProfiles[1].enabled || store.profileAvailabilitySaving) throw new Error("availability gate did not reopen after save");
setEnabledHandler = null;
await store.duplicateProfile({ id: "researcher", title: "Researcher" });
if (!calls.some(item => item.payload?.action === "duplicate" && item.payload.profile_id === "researcher") || !store.profiles.some(profile => profile.id === "researcher-1")) throw new Error("profile duplication failed");
calls.length = 0;
confirmResult = false;
await store.restoreProfile({ id: "researcher", title: "Researcher", scope_has_overrides: true, deletable: false });
if (calls.length || confirmations.at(-1)?.title !== "Reset Researcher to default?") throw new Error("restore cancellation failed");
confirmResult = true;
profilesHandler = () => ({
  ok: true,
  profiles: [{ id: "researcher", title: "Researcher", scope_has_overrides: false }],
});
await store.restoreProfile({ id: "researcher", title: "Researcher", scope_has_overrides: true, deletable: false });
if (!calls.some(item => item.payload?.action === "remove_changes" && item.payload.profile_id === "researcher" && item.payload.destructive === false)) throw new Error("reset to default did not use sparse removal");
if (!calls.some(item => item.endpoint === "loadAgentProfiles" && item.payload === true) || store.saving) throw new Error("reset to default did not refresh profile state");
if (store.profiles[0]?.scope_has_overrides || toasts.at(-1)?.[0] !== "Researcher reset to default.") throw new Error("reset to default kept its action or omitted feedback");
profilesHandler = null;
let editorReload = null;
const loadEditor = store.loadEditor;
const setMode = store.setMode;
store.view = "editor";
store.mode = "advanced";
store.section = "3";
store.loadEditor = async (...args) => { editorReload = { args }; };
store.setMode = (...args) => { editorReload.mode = args; };
await store.restoreProfile({ id: "researcher", title: "Researcher", scope_has_overrides: true, deletable: false });
if (editorReload?.args.join(":") !== "researcher:false" || editorReload.mode.join(":") !== "advanced:3:false") throw new Error("editor reset did not restore its surface");
store.loadEditor = loadEditor;
store.setMode = setMode;
store.view = "manage";
confirmations.length = 0;
confirmResult = false;
store.projectName = "other";
if (store.currentChatUsesScope() || store.isProfileActive("default")) throw new Error("foreign project profile appeared active");
store.projectName = "demo";
store.state.tools.effective_policy = { mode: "custom", default: "allow", mcp_default: "allow", allowed: [], blocked: ["local:shell"] };
if (store.isToolAllowed(store.state.tools.catalog[0])) throw new Error("project scope ignored inherited tool restriction");
store.setPolicyItem("tool", "local:shell", "default");
if (store.draft.toolPolicy.mode !== "custom" || !store.isToolAllowed(store.state.tools.catalog[0])) throw new Error("project scope did not customize inherited policy");
store.setPolicyItem("tool", "local:shell", "allow");
if (!store.draft.toolPolicy.allowed.includes("local:shell")) throw new Error("project scope did not pin explicit On");
store.setPolicyItem("tool", "local:shell", "block");
if (store.draft.toolPolicy.mode !== "inherit" || store.isToolAllowed(store.state.tools.catalog[0])) throw new Error("project scope did not restore inherited policy");
store.projectName = "";
store.state.tools.effective_policy = { mode: "inherit", default: "allow", mcp_default: "allow", allowed: [], blocked: [] };
store.state.skills.catalog = [
  { name: "Research", path: "skills/research/SKILL.md", origin: "Agent Zero", description: "Research sources", available: true, tags: [], allowed_tools: [] },
  { name: "Gone", path: "skills/gone/SKILL.md", origin: "Unavailable", description: "Missing skill", available: false, tags: [], allowed_tools: [] },
];
store.draft.skillPolicy = { mode: "inherit", default: "allow", allowed: [], blocked: [] };
store.initialDraft.skillPolicy = clone(store.draft.skillPolicy);
if (store.skillCatalog.length !== 1 || store.filteredSkills().length !== 2) throw new Error("Easy/Advanced skill catalog mismatch");
store.setPolicyItem("skill", "Research", "allow");
if (!store.draft.skillPolicy.allowed.includes("Research")) throw new Error("skill On selection failed");
store.setPolicyItem("skill", "Research", "block");
if (!store.draft.skillPolicy.blocked.includes("Research")) throw new Error("skill Off selection failed");
store.setPolicyItem("skill", "Research", "default");
if (store.draft.skillPolicy.mode !== "inherit") throw new Error("skill sparse undo did not collapse");
store.draft.title = "Preserved Agent";
store.onNameInput();
store.instructions.value = "Preserved instructions";
store.draft.description = "Created description";
store.draft.context = "Delegate created work";
const createdMetadata = store.buildPatch().metadata.set;
if (createdMetadata.description !== "Created description" || createdMetadata.context !== "Delegate created work") throw new Error("Advanced create metadata was omitted");
store.mode = "advanced";
store.instructions.value = "";
const callsBeforeInvalidAdvancedCreate = calls.length;
if (!store.fieldIssue("instructions")) throw new Error("Advanced create accepted empty instructions");
if (store.fieldIssue("instructions")?.field !== "agent-editor-prompt-ace") throw new Error("Advanced validation targeted the wrong editor");
await store.save();
if (calls.length !== callsBeforeInvalidAdvancedCreate) throw new Error("Advanced create submitted empty instructions");
store.instructions.value = "Preserved instructions";
store.draft.creating = false;
store.mode = "easy";
store.instructions.initialValue = "Preserved instructions";
store.instructions.value = "";
if (!store.fieldIssue("instructions")) throw new Error("existing empty Easy instructions were accepted");
store.instructions.value = "Preserved instructions";
if (store.fieldIssue("instructions")) throw new Error("corrected Easy instructions kept a validation error");
store.mode = "advanced";
store.instructions.value = "";
if (store.fieldIssue("instructions")) throw new Error("Advanced empty instructions were rejected");
store.instructions.value = "Preserved instructions";
store.markPromptSet("agent.system.main.specifics.md");
if (store.instructions.reset || store.promptEditPending(store.instructions)) throw new Error("Easy instructions did not update its edit checkpoint");
store.restoreInstructions();
if (!store.instructions.reset || store.instructions.value !== "" || store.promptEditPending(store.instructions)) throw new Error("default instructions were not restored");
store.state = {
  profile: { id: "new-agent", avatar_url: "", metadata: { title: {}, description: {}, context: {}, avatar: { effective: { kind: "color", value: "#111111" } } } },
  prompts: [
    { filename: "agent.system.main.specifics.md", group: "2.1", group_label: "Agent instructions", effective: "", inherited: "Old instructions", source: "old-source", source_chain: ["Old"] },
    { filename: "agent.system.main.communication.md", group: "2.4", group_label: "Communication", effective: "Old comm", inherited: "Old comm", source: "old-source", source_chain: ["Old"], state: "Inherited", has_override: false },
  ],
  model_preset: { has_override: false, effective: "Default" },
  model_presets: [],
  tools: { policy: { mode: "inherit" }, effective_policy: { mode: "inherit", default: "allow", mcp_default: "allow", allowed: [], blocked: [] }, has_override: false, catalog: [
    { id: "local:shell", name: "shell", label: "Shell", origin: "Agent Zero", available: true },
    { id: "local:old", name: "old", label: "Old", origin: "Old scope", available: true },
  ] },
  skills: { policy: { mode: "inherit" }, effective_policy: { mode: "inherit", default: "allow", allowed: [], blocked: [] }, has_override: false, catalog: [
    { name: "Research", path: "skills/research/SKILL.md", origin: "Agent Zero", description: "Research", available: true, tags: [], allowed_tools: [] },
    { name: "Old skill", path: "skills/old/SKILL.md", origin: "Old scope", description: "Old", available: true, tags: [], allowed_tools: [] },
  ] },
};
store.view = "editor";
store.intent = { ...store.intent, view: "create", projectName: "" };
store.makeDraft(true);
store.root = {
  querySelector: selector => selector === "#agent-editor-prompt-ace" ? aceContainer : null,
  contains: node => node === aceContainer,
  closest: () => null,
};
store.mode = "advanced";
store.section = "2";
const draftBeforeAce = JSON.stringify(store.draft);
store.initPromptEditor();
if (aceState.mode !== "ace/mode/markdown" || aceState.wrap !== true || aceState.options?.showPrintMargin !== false || aceState.options?.useWorker !== false) throw new Error("ACE configuration mismatch");
if (aceState["aria-label"] !== "Prompt Markdown" || JSON.stringify(store.draft) !== draftBeforeAce) throw new Error("ACE initialization created a false edit");
aceState.value = "Edited in ACE";
aceState.change();
if (store.instructions.value !== "Edited in ACE" || !store.promptEditPending(store.instructions)) throw new Error("ACE change did not update the prompt draft");
store.selectPrompt("agent.system.main.communication.md");
if (aceState.value !== "Old comm" || store.instructions.value !== "Edited in ACE") throw new Error("ACE file switch lost a draft");
store.selectPrompt("agent.system.main.specifics.md");
store.destroyPromptEditor();
if (!aceState.destroyed || aceState.change) throw new Error("ACE instance was not destroyed cleanly");
store.draft.title = "Scoped Agent";
store.onNameInput();
store.draft.description = "Scoped description";
store.draft.context = "Use for scoped work";
store.instructions.value = "Authored instructions";
store.markPromptSet("agent.system.main.specifics.md");
store.draft.prompts["agent.system.main.communication.md"].value = "Authored communication";
store.acceptPromptEdit("agent.system.main.communication.md");
store.chooseAvatarColor("#ABCDEF");
store.setPolicyItem("tool", "local:shell", "block");
store.setPolicyDefault("tool", "block");
store.setPolicyItem("skill", "Research", "block");
const projectState = {
  profile: { id: "new-agent", avatar_url: "", metadata: { title: {}, description: {}, context: {}, avatar: { effective: { kind: "color", value: "#222222" } } } },
  prompts: [
    { filename: "agent.system.main.specifics.md", group: "2.1", group_label: "Agent instructions", effective: "", inherited: "Project instructions", source: "project-source", source_chain: ["Project"] },
    { filename: "agent.system.main.communication.md", group: "2.4", group_label: "Communication", effective: "Inherited comm", inherited: "Inherited comm", source: "project-source", source_chain: ["Project"], state: "Inherited", has_override: false },
  ],
  model_preset: { has_override: false, effective: "Default" },
  model_presets: [],
  tools: { policy: { mode: "inherit" }, effective_policy: { mode: "inherit", default: "allow", mcp_default: "allow", allowed: [], blocked: [] }, has_override: false, catalog: [
    { id: "local:shell", name: "shell", label: "Shell", origin: "Agent Zero", available: true },
    { id: "local:new", name: "new", label: "New", origin: "Project", available: true },
  ] },
  skills: { policy: { mode: "inherit" }, effective_policy: { mode: "inherit", default: "allow", allowed: [], blocked: [] }, has_override: false, catalog: [
    { name: "Research", path: "skills/research/SKILL.md", origin: "Agent Zero", description: "Research", available: true, tags: [], allowed_tools: [] },
    { name: "New skill", path: "skills/new/SKILL.md", origin: "Project", description: "New", available: true, tags: [], allowed_tools: [] },
  ] },
};
loadHandler = () => ({ ok: true, state: projectState });
store.mode = "advanced";
store.section = "6";
store.projectName = "demo";
store.intent = { ...store.intent, projectName: "" };
calls.length = 0;
await store.onScopeChanged();
if (store.state !== projectState || store.draft.title !== "Scoped Agent" || store.draft.profileId !== "scoped-agent") throw new Error("create scope rebase lost identity");
if (store.draft.description !== "Scoped description" || store.draft.context !== "Use for scoped work") throw new Error("create scope rebase lost authored metadata");
if (store.instructions.value !== "Authored instructions" || store.instructions.source !== "project-source") throw new Error("create scope rebase kept stale prompt provenance");
if (store.draft.avatar?.value !== "#ABCDEF" || store.isToolAllowed(projectState.tools.catalog[0]) || store.isToolAllowed(projectState.tools.catalog[1]) || store.draft.toolPolicy.default !== "block") throw new Error("create scope rebase lost avatar or tool policy");
if (store.isSkillAllowed(projectState.skills.catalog[0]) || !store.isSkillAllowed(projectState.skills.catalog[1])) throw new Error("create scope rebase lost explicit skill decision");
if (store.draft.prompts["agent.system.main.communication.md"].value !== "Authored communication" || store.draft.prompts["agent.system.main.communication.md"].source !== "project-source" || store.promptEditPending(store.draft.prompts["agent.system.main.communication.md"])) throw new Error("create scope rebase lost an accepted prompt edit or kept stale provenance");
if (calls.at(-1)?.payload?.action !== "plan" || calls.at(-1)?.payload?.project_name !== "demo" || store.planStatus !== "ready" || !store.plan.written[0].startsWith("usr/projects/demo/.a0proj/agents/scoped-agent/")) throw new Error("Review plan was not recomputed after scope change");
loadHandler = null;
store.projectName = "";
store.intent = { ...store.intent, projectName: "" };
const communication = store.draft.prompts["agent.system.main.communication.md"];
if (store.promptTitle(communication) !== "Communication") throw new Error("friendly prompt title missing");
if (store.promptTitle({ filename: "agent.system.main.tips.md", group_label: "Tips" }) !== "Tips") throw new Error("Tips title missing");
if (store.promptTitle({ filename: "agent.system.main.communication.native.md", group_label: "Communication" }) !== "agent.system.main.communication.native.md") throw new Error("distinct prompt variants lost their filenames");
if (store.promptTitle(null) !== "") throw new Error("empty prompt title mismatch");
store.promptFileSearch = "Agent instructions";
if (store.filteredPromptFiles()[0]?.filename !== "agent.system.main.specifics.md") throw new Error("friendly prompt title search failed");
store.promptFileSearch = "agent.system.main.communication.md";
if (store.filteredPromptFiles()[0] !== communication) throw new Error("filename search failed");
store.promptFileSearch = "";
communication.value = communication.initialValue;
communication.reset = false;
store.acceptPromptEdit(communication.filename);
if (store.filteredPromptFiles("2.4")[0] !== communication) throw new Error("grouped prompt filter mismatch");
if (store.promptEditPending(communication) || store.promptDisplayState(communication) !== "Default") throw new Error("default prompt checkpoint mismatch");
communication.value += "\nNew rule";
store.onPromptInput(communication.filename);
if (!store.promptEditPending(communication)) throw new Error("prompt edit actions did not appear");
if (!store.buildPatch().prompts.set[communication.filename].endsWith("New rule")) throw new Error("pending prompt edit missing from sparse patch");
store.discardPromptEdit(communication.filename);
if (store.promptEditPending(communication) || communication.value !== "Inherited comm") throw new Error("prompt edit was not discarded");
if (store.buildPatch().prompts.set[communication.filename]) throw new Error("discarded prompt edit remained in sparse patch");
communication.value += "\nNew rule";
store.onPromptInput(communication.filename);
store.acceptPromptEdit(communication.filename);
if (store.promptEditPending(communication)) throw new Error("prompt edit was not accepted");
if (store.promptDisplayState(communication) !== "Customized by you") throw new Error("customized state missing");
store.resetPrompt(communication.filename);
if (store.promptEditPending(communication) || store.promptDisplayState(communication) !== "Will use the default") throw new Error("reset state mismatch");
const draftBeforeModes = JSON.stringify(store.draft);
store.setMode("advanced", "2");
store.setMode("easy");
if (store.section !== "2" || JSON.stringify(store.draft) !== draftBeforeModes) throw new Error("mode switch lost draft");
store.setMode("advanced", "6");
await Promise.resolve();
await Promise.resolve();
if (store.planStatus !== "ready" || calls.at(-1).payload.action !== "plan") throw new Error("review plan was not computed on entry");
calls.length = 0;
store.intent = { contextId: "source-chat" };
await store.openFreshChat("researcher", true);
const endpoints = calls.map((item) => item.endpoint);
const expected = ["/chat_create", "/projects", "/agent_profile_set", "/plugins/_model_config/model_override", "selectChat", "event"];
if (JSON.stringify(endpoints) !== JSON.stringify(expected)) throw new Error(JSON.stringify(calls));
if (calls[1].payload.action !== "deactivate") throw new Error("global test chat kept a project");
if (calls[2].payload.agent_profile !== "researcher") throw new Error("profile not selected");
if (calls[3].payload.action !== "clear") throw new Error("chat preset override not cleared");
if (store.readyNoteContext !== "fresh-chat") throw new Error("ready note missing");
if (chatsStore.selectedContext.agent_profile !== "researcher" || chatsStore.selectedContext.agent_profile_label !== "Researcher") throw new Error("fresh chat showed a stale profile");
calls.length = 0;
store.projectName = "demo";
await store.openFreshChat("researcher", false);
if (calls[1].endpoint !== "/projects" || calls[1].payload.action !== "activate" || calls[1].payload.name !== "demo") throw new Error("project test chat did not activate selected scope");
store.draft.title = `${store.draft.title} dirty`;
calls.length = 0;
if (await store.planRemoval(true)) throw new Error("removal plan accepted unsaved edits");
if (calls.length || !store.error.includes("Save or discard")) throw new Error("dirty removal plan was not blocked locally");
store.initialDraft = clone(store.draft);
store.error = "";
await store.planRemoval(true);
if (!store.pendingMutation?.destructive || store.section !== "6" || store.planStatus !== "ready") throw new Error("removal plan was replaced");
if (calls.at(-1).payload.action !== "plan_remove_changes") throw new Error("removal plan request missing");
if (calls.at(-1).payload.project_name !== "demo") throw new Error("removal request lost selected scope");
const callsBeforePendingSave = calls.length;
if (await store.save() || calls.length !== callsBeforePendingSave) throw new Error("ordinary save ran over a pending removal plan");
store.draft.title += " changed after planning";
if (await store.applyPendingMutation() !== false || confirmations.length || calls.length !== callsBeforePendingSave || !store.error.includes("before applying")) throw new Error("removal plan discarded edits made after planning");
store.draft.title = store.initialDraft.title;
store.error = "";
store.plan = { written: ["usr/agents/researcher/agent.yaml"], deleted: ["usr/agents/researcher/prompts/old.md"], warnings: [] };
confirmResult = true;
loadHandler = () => ({ ok: true, state: store.state });
await store.applyPendingMutation();
if (confirmations.length !== 1 || confirmations[0].type !== "danger") throw new Error("danger confirmation missing");
if (!confirmations[0].message.includes("agent.yaml") || !confirmations[0].message.includes("old.md")) throw new Error("planned paths missing from confirmation");
if (confirmations[0].title !== "Delete all customizations for this profile?") throw new Error("cleanup confirmation title mismatch");
const removalCall = calls.find(item => item.payload?.action === "remove_changes");
if (!removalCall || removalCall.payload.confirm !== true || removalCall.payload.destructive !== true) throw new Error("destructive removal omitted explicit confirmation");
loadHandler = null;
confirmResult = false;
confirmations.length = 0;
calls.length = 0;
store.projectName = "";
await store.deleteProfile("custom-agent");
if (calls.length) throw new Error("cancelled deletion made an API request");
if (confirmations.length !== 1 || confirmations[0].title !== "Delete custom-agent?") throw new Error("delete confirmation mismatch");
if (confirmations[0].message !== "<p>This agent profile will be permanently deleted from Global and cannot be recovered.</p>") throw new Error("delete confirmation is not concise");
confirmResult = true;
store.view = "editor";
store.mode = "advanced";
store.draft = { title: "dirty", avatar: null, avatarToken: "", metadataResets: [] };
store.initialDraft = { title: "clean", avatar: null, avatarToken: "", metadataResets: [] };
store.promptEditBaselines = { stale: { value: "stale", reset: false } };
await store.deleteProfile("custom-agent");
if (store.view !== "manage" || store.mode !== "easy" || store.draft !== null || store.initialDraft !== null || Object.keys(store.promptEditBaselines).length) throw new Error("delete did not enter a clean Manage state");
store.view = "editor";
store.mode = "advanced";
store.draft = { title: "dirty" };
store.initialDraft = { title: "clean" };
store.promptEditBaselines = { stale: { value: "stale", reset: false } };
store.error = "stale";
store.showManager();
if (store.view !== "manage" || store.mode !== "easy" || store.draft !== null || store.initialDraft !== null || store.error || Object.keys(store.promptEditBaselines).length) throw new Error("Back did not discard editor state before Manage");
"""
    module_source = harness + "\n" + source + "\n" + checks
    module_url = "data:text/javascript;base64," + base64.b64encode(
        module_source.encode("utf-8")
    ).decode("ascii")
    subprocess.run(
        ["node", "--input-type=module", "-e", f"await import('{module_url}')"],
        check=True,
        text=True,
    )


@pytest.mark.skipif(not shutil.which("node"), reason="node is required")
def test_agent_profile_loads_dedupe_same_context_and_ignore_stale_context() -> None:
    source = SWITCHER_MIXIN.read_text(encoding="utf-8")
    source = re.sub(r"^import .*?;\n", "", source, flags=re.MULTILINE)
    harness = r"""
const pending = [];
const callJsonApi = async () => await new Promise(resolve => pending.push(resolve));
const fetchApi = async () => ({ ok: true, json: async () => ({}) });
let selectedContextId = "ctx";
globalThis.window = { Alpine: { store: () => ({ selected: selectedContextId }) } };
"""
    checks = r"""
const store = { ...switcherState, ...switcherMethods };
const older = store.loadAgentProfiles(true);
const newer = store.loadAgentProfiles(true);
if (pending.length !== 1 || !store.agentProfilesLoading) throw new Error("same-context profile loads were not deduplicated");
pending[0]({ profiles: [
  { id: "default", title: "Default", enabled: true },
  { id: "new", title: "New", enabled: true },
] });
await Promise.all([older, newer]);
if (store.agentProfiles[0]?.key !== "new" || store.agentProfilesLoading || !store.agentProfilesLoaded) throw new Error("newest profile load did not settle");
if (store.agentProfiles.length !== 1 || store.getAgentProfileList("default", "Default").some(profile => profile.key === "default")) throw new Error("Default profile remained selectable in the chat popover");
selectedContextId = "older-context";
const stale = store.loadAgentProfiles(true);
selectedContextId = "newer-context";
const fresh = store.loadAgentProfiles(true);
if (pending.length !== 3) throw new Error("different-context profile loads were incorrectly deduplicated");
pending[2]({ profiles: [{ id: "fresh", title: "Fresh", enabled: true }] });
await fresh;
pending[1]({ profiles: [{ id: "stale", title: "Stale", enabled: true }] });
await stale;
if (store.agentProfiles[0]?.key !== "fresh" || store.agentProfilesLoading) throw new Error("stale profile load replaced newer state");
const requestCount = pending.length;
await store.loadAgentProfiles();
if (pending.length !== requestCount) throw new Error("cached profile catalog unexpectedly reloaded");
"""
    module_source = harness + "\n" + source + "\n" + checks
    module_url = "data:text/javascript;base64," + base64.b64encode(
        module_source.encode("utf-8")
    ).decode("ascii")
    subprocess.run(
        ["node", "--input-type=module", "-e", f"await import('{module_url}')"],
        check=True,
        text=True,
    )


def test_profile_slash_effects_reuse_the_agent_editor_entry_points() -> None:
    slash_store = (
        ROOT / "plugins" / "_commands" / "webui" / "commands-slash-store.js"
    ).read_text(encoding="utf-8")

    assert 'type === "open_agent_editor"' in slash_store
    assert "globalThis.openAgentEditor?." in slash_store
    assert 'type === "test_agent_profile"' in slash_store
    assert "globalThis.testAgentProfile?." in slash_store
    assert "String(effect.project_name || \"\")" in slash_store
