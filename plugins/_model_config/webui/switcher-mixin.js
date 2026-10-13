import { callJsonApi, fetchApi } from "/js/api.js";

const API_BASE = "/plugins/_model_config";
const BUILT_IN_AGENT_COLORS = {
  agent0: "#8E44AD",
  default: "#D35400",
  developer: "#202124",
  hacker: "#C0392B",
  researcher: "#6C5CE7",
  "tiny-local": "#E67E22",
};
function normalizeModelIdentity(value) {
  if (!value || typeof value !== "object") return null;
  const provider = String(value.provider || "").trim();
  const name = String(value.name || "").trim();
  if (!provider && !name) return null;
  return { provider, name };
}

export function getModelLeafName(value) {
  const name = String(typeof value === "string" ? value : value?.name || "").trim();
  if (!name) return "";
  const leaf = name.slice(name.lastIndexOf("/") + 1).trim();
  return leaf || name;
}

export const switcherState = {
  switcherAllowed: false,
  switcherOverride: null,
  switcherConfiguredPreset: "Default",
  switcherEffectivePreset: "Default",
  switcherPresets: [],
  switcherLoading: true,
  switcherLoadSeq: 0,
  agentProfiles: [],
  agentProfilesLoading: true,
  agentProfilesLoaded: false,
  agentProfilesLoadSeq: 0,
  agentProfileSaving: false,
};

let agentProfilesRequest = null;
let agentProfilesRequestContext = "";

export const switcherMethods = {
  async loadAgentProfiles(force = false) {
    const contextId = window.Alpine?.store("chats")?.selected || "";
    if (agentProfilesRequest && agentProfilesRequestContext === contextId) {
      return agentProfilesRequest;
    }
    if (!force && this.agentProfilesLoaded) return this.agentProfiles;
    const requestSeq = ++this.agentProfilesLoadSeq;
    this.agentProfilesLoading = true;
    const request = (async () => {
      try {
        const data = await callJsonApi("/plugins/_agent_editor/agent_editor", {
          action: "list",
          context_id: contextId,
        });
        if (requestSeq !== this.agentProfilesLoadSeq || contextId !== (window.Alpine?.store("chats")?.selected || "")) return this.agentProfiles;
        this.agentProfiles = (data.profiles || [])
          .filter(profile => profile.id && !["_example", "default"].includes(profile.id) && profile.enabled !== false)
          .map(profile => ({
            key: profile.id,
            label: profile.title || profile.id,
            avatar: profile.avatar || null,
            avatarUrl: profile.avatar_url || "",
          }));
        this.agentProfilesLoaded = true;
      } catch (e) {
        if (requestSeq !== this.agentProfilesLoadSeq) return this.agentProfiles;
        console.error("Agent profile list load failed:", e);
        this.agentProfiles = [];
        this.agentProfilesLoaded = false;
      } finally {
        if (requestSeq === this.agentProfilesLoadSeq) {
          this.agentProfilesLoading = false;
        }
      }
      return this.agentProfiles;
    })();
    agentProfilesRequest = request;
    agentProfilesRequestContext = contextId;
    try {
      return await request;
    } finally {
      if (agentProfilesRequest === request) agentProfilesRequest = null;
    }
  },

  async loadSwitcherState(contextId) {
    const result = { allowed: false, presets: [], override: null, configuredPreset: "Default", effectivePreset: "Default" };
    try {
      await this.loadGlobalPresets();
      result.presets = this.globalPresets.filter(p => p.name);
      if (contextId) {
        const overRes = await fetchApi(`${API_BASE}/model_override`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action: "get", context_id: contextId }),
        });
        const overData = await overRes.json();
        result.allowed = !!overData.allowed;
        result.override = overData.override || null;
        result.configuredPreset = overData.configured_preset || "Default";
        result.effectivePreset = overData.effective_preset || result.configuredPreset;
      }
    } catch (e) {
      console.error("Model switcher load failed:", e);
    }
    return result;
  },

  async setPresetOverride(contextId, presetName) {
    try {
      const res = await fetchApi(`${API_BASE}/model_override`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "set_preset", context_id: contextId, preset_name: presetName }),
      });
      const data = await res.json();
      return data?.ok ? data : null;
    } catch (e) {
      console.error("Failed to set preset override:", e);
      return false;
    }
  },

  async clearOverride(contextId) {
    try {
      const res = await fetchApi(`${API_BASE}/model_override`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "clear", context_id: contextId }),
      });
      const data = await res.json();
      return data?.ok ? data : null;
    } catch (e) {
      console.error("Failed to clear override:", e);
      return false;
    }
  },

  getAgentProfileList(activeKey = "", activeLabel = "") {
    const profiles = [...(this.agentProfiles || [])];
    if (activeKey && activeKey !== "default" && !profiles.some(profile => profile.key === activeKey)) {
      profiles.unshift({ key: activeKey, label: activeLabel || activeKey });
    }
    return profiles;
  },

  getAgentProfileVisual(profileKey, profileLabel = "") {
    const profile = this.agentProfiles.find(item => item.key === profileKey) || {};
    const label = profile.label || profileLabel || profileKey || "Agent";
    const palette = ["#6C5CE7", "#0984E3", "#00A884", "#D35400", "#C0392B", "#8E44AD"];
    let hash = 0;
    for (const char of profileKey || label) hash = ((hash * 31) + char.charCodeAt(0)) >>> 0;
    return {
      url: profile.avatarUrl || "",
      color: profile.avatar?.kind === "color"
        ? profile.avatar.value
        : BUILT_IN_AGENT_COLORS[profileKey] || palette[hash % palette.length],
      initials: label.trim().split(/\s+/).slice(0, 2).map(word => word[0]).join("").toUpperCase() || "A",
    };
  },

  async selectAgentProfile(contextId, agentProfile) {
    if (!contextId || !agentProfile) return false;
    if (this.agentProfileSaving) return false;
    const chatsStore = window.Alpine?.store("chats");
    const selectedContext = chatsStore?.selectedContext;
    const activeProfile = selectedContext?.agent_profile || "";
    if (activeProfile === agentProfile) return true;

    this.agentProfileSaving = true;
    try {
      await this.loadAgentProfiles();
      const res = await fetchApi("/agent_profile_set", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ context_id: contextId, agent_profile: agentProfile }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      if (!data.ok) return false;

      const label = data.agent_profile_label || this.agentProfiles.find(profile => profile.key === agentProfile)?.label || agentProfile;
      if (selectedContext) {
        selectedContext.agent_profile = data.agent_profile || agentProfile;
        selectedContext.agent_profile_label = label;
      }
      await this.refreshSwitcher(contextId);
      window.justToast?.(`Agent profile: ${label}`, "success", 1600, "agent-profile-switch");
      return true;
    } catch (e) {
      console.error("Failed to set active agent profile:", e);
      window.toastFetchError?.("Failed to set agent profile", e);
      return false;
    } finally {
      this.agentProfileSaving = false;
    }
  },

  getPresetLabel(preset) {
    return preset?.name || "Unnamed";
  },

  getPresetSummary(preset) {
    if (!preset) return "";
    const parts = [];
    if (preset.chat?.name) parts.push(preset.chat.name);
    if (preset.utility?.name) parts.push(preset.utility.name);
    return parts.join(" / ");
  },

  async refreshSwitcher(contextId) {
    if (contextId !== (window.Alpine?.store("chats")?.selected || "")) return;
    const requestSeq = ++this.switcherLoadSeq;
    if (!this.switcherPresets.length) this.switcherLoading = true;
    try {
      const state = await this.loadSwitcherState(contextId);
      if (requestSeq !== this.switcherLoadSeq || contextId !== (window.Alpine?.store("chats")?.selected || "")) return;
      this.switcherAllowed = state.allowed;
      this.switcherPresets = state.presets;
      this.switcherOverride = state.override;
      this.switcherConfiguredPreset = state.configuredPreset;
      this.switcherEffectivePreset = state.effectivePreset;
    } catch (e) {
      console.error('Model switcher refresh failed:', e);
    } finally {
      if (requestSeq === this.switcherLoadSeq) this.switcherLoading = false;
    }
  },

  async selectPresetSwitch(contextId, presetName) {
    const data = await this.setPresetOverride(contextId, presetName);
    if (data && contextId === (window.Alpine?.store("chats")?.selected || "")) {
      const selected = data.preset_name || presetName;
      this.switcherOverride = { preset_name: selected };
      this.switcherEffectivePreset = selected;
    }
    return !!data;
  },

  async clearOverrideSwitch(contextId) {
    const data = await this.clearOverride(contextId);
    if (data && contextId === (window.Alpine?.store("chats")?.selected || "")) {
      this.switcherOverride = null;
      this.switcherEffectivePreset = data.effective_preset || this.switcherConfiguredPreset || 'Default';
    }
    return !!data;
  },

  getSwitcherLabel() {
    const o = this.switcherOverride;
    const presetName = this.switcherEffectivePreset || o?.preset_name || 'Default';
    const preset = this.getActivePreset();
    if (preset) {
      const mainModelName = getModelLeafName(preset.chat);
      return mainModelName ? `${presetName} ${mainModelName}` : presetName;
    }
    if (!o || o.preset_name) return presetName;

    const models = this.getCustomOverrideModels();
    const mainModelName = getModelLeafName(models.main);
    return mainModelName ? `Custom ${mainModelName}` : 'Custom';
  },

  getActivePreset() {
    return this.switcherPresets.find(p => p.name === this.switcherEffectivePreset) || null;
  },

  getActiveModels() {
    const preset = this.getActivePreset();
    if (preset) {
      return {
        main: normalizeModelIdentity(preset.chat),
        utility: normalizeModelIdentity(preset.utility),
        embedding: normalizeModelIdentity(preset.embedding),
      };
    }
    return this.getCustomOverrideModels();
  },

  getCustomOverrideModels() {
    const o = this.switcherOverride;
    if (!o || o.preset_name) return { main: null, utility: null, embedding: null };
    return {
      main: normalizeModelIdentity(o.chat || o),
      utility: normalizeModelIdentity(o.utility),
      embedding: normalizeModelIdentity(o.embedding),
    };
  },
};
