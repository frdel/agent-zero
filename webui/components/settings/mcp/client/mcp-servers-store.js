import { createStore } from "/js/AlpineStore.js";
import { scrollModal } from "/js/modals.js";
import sleep from "/js/sleep.js";
import * as API from "/js/api.js";

const model = {
  editor: null,
  servers: [],
  loading: true,
  statusCheck: false,
  serverLog: "",
  // profile management
  profiles: ["default"],
  selectedProfile: "default",

  async initialize() {
    // Initialize the JSON Viewer after the modal is rendered
    const container = document.getElementById("mcp-servers-config-json");
    // Ensure profiles are loaded first so UI can render options safely
    // Wait briefly if settingsModalProxy is not ready yet
    let retries = 10;
    while ((!window.settingsModalProxy || !settingsModalProxy.settings) && retries-- > 0) {
      await sleep(50);
    }
    await this._loadProfiles();
    this._renderProfilesSelect();
    if (container) {
      const editor = ace.edit("mcp-servers-config-json");

      const dark = localStorage.getItem("darkMode");
      if (dark != "false") {
        editor.setTheme("ace/theme/github_dark");
      } else {
        editor.setTheme("ace/theme/tomorrow");
      }

      editor.session.setMode("ace/mode/json");
      const json = await this._getConfigForSelectedProfile();
      editor.setValue(json);
      editor.clearSelection();
      this.editor = editor;
    }

    this.startStatusCheck();
  },

  formatJson() {
    try {
      // get current content
      const currentContent = this.editor.getValue();

      // parse and format with 2 spaces indentation
      const parsed = JSON.parse(currentContent);
      const formatted = JSON.stringify(parsed, null, 2);

      // update editor content
      this.editor.setValue(formatted);
      this.editor.clearSelection();

      // move cursor to start
      this.editor.navigateFileStart();
    } catch (error) {
      console.error("Failed to format JSON:", error);
      alert("Invalid JSON: " + error.message);
    }
  },

  getEditorValue() {
    return this.editor.getValue();
  },

  getSettingsFieldConfigJson() {
    return settingsModalProxy.settings.sections
      .filter((x) => x.id == "mcp_client")[0]
      .fields.filter((x) => x.id == "mcp_servers")[0];
  },

  onClose() {
    const val = this.getEditorValue();
    if (this.selectedProfile === "default") {
      this.getSettingsFieldConfigJson().value = val;
    }
    this.stopStatusCheck();
  },

  async startStatusCheck() {
    this.statusCheck = true;
    let firstLoad = true;

    while (this.statusCheck) {
      try {
        await this._statusCheck();
      } catch (e) {
        console.error("MCP status check failed:", e);
      } finally {
        if (firstLoad) {
          this.loading = false;
          firstLoad = false;
        }
      }
      await sleep(3000);
    }
  },

  async _statusCheck() {
    const resp = await API.callJsonApi("mcp_servers_status", { profile: this.selectedProfile });
    if (resp && resp.success) {
      this.servers = resp.status || [];
      this.servers.sort((a, b) => a.name.localeCompare(b.name));
    } else {
      // In case of failure, show empty list rather than hang in loading
      this.servers = this.servers || [];
    }
    // Always ensure loading indicator can be cleared by status checks
    this.loading = false;
  },

  async stopStatusCheck() {
    this.statusCheck = false;
  },

  async applyNow() {
    if (this.loading) return;
    this.loading = true;
    try {
      scrollModal("mcp-servers-status");
      const resp = await API.callJsonApi("mcp_servers_apply", {
        mcp_servers: this.getEditorValue(),
        profile: this.selectedProfile,
      });
      if (resp.success) {
        this.servers = resp.status;
        this.servers.sort((a, b) => a.name.localeCompare(b.name));
        // Immediately refresh once to reflect current state
        try { await this._statusCheck(); } catch (e) { /* ignore */ }
      }
      this.loading = false;
      await sleep(100); // wait for ui and scroll
      scrollModal("mcp-servers-status");
    } catch (error) {
      console.error("Failed to apply MCP servers:", error);
    }
    this.loading = false;
  },

  async getServerLog(serverName) {
    this.serverLog = "";
    const resp = await API.callJsonApi("mcp_server_get_log", {
      server_name: serverName,
      profile: this.selectedProfile,
    });
    if (resp.success) {
      this.serverLog = resp.log;
      openModal("settings/mcp/client/mcp-servers-log.html");
    }
  },

  async onToolCountClick(serverName) {
    const resp = await API.callJsonApi("mcp_server_get_detail", {
      server_name: serverName,
      profile: this.selectedProfile,
    });
    if (resp.success) {
      this.serverDetail = resp.detail;
      openModal("settings/mcp/client/mcp-server-tools.html");
    }
  },

  async _loadProfiles() {
    // Try API first so we see a network call and get accurate list from backend
    try {
      const resp = await API.callJsonApi("list_agent_profiles", null);
      if (resp && resp.success && Array.isArray(resp.profiles)) {
        const list = ["default", ...resp.profiles.filter((p) => p && p !== "_example")];
        this.profiles = list.length ? list : ["default"];
      } else {
        throw new Error("profiles api failed");
      }
    } catch (_e) {
      // Fallback to reading from settings schema if API is not available yet
      const agentSection = (window.settingsModalProxy && settingsModalProxy.settings && settingsModalProxy.settings.sections)
        ? settingsModalProxy.settings.sections.find((s) => s.id === "agent")
        : null;
      const agentProfileField = agentSection && Array.isArray(agentSection.fields)
        ? agentSection.fields.find((f) => f.id === "agent_profile")
        : null;
      const opts = agentProfileField && Array.isArray(agentProfileField.options) ? agentProfileField.options : [];
      const values = opts.map((o) => o.value).filter((p) => p && p !== "_example");
      const list = ["default", ...values];
      this.profiles = list.length ? list : ["default"];
    }
    // Keep current selection if still valid, otherwise reset to default
    if (!this.profiles.includes(this.selectedProfile)) {
      this.selectedProfile = "default";
    }
    this._renderProfilesSelect();
  },

  _renderProfilesSelect() {
    const select = document.getElementById("mcp-profiles-select");
    if (!select) return;
    // Clear existing options
    select.innerHTML = "";
    // Render new options
    for (const p of this.profiles) {
      const opt = document.createElement("option");
      opt.value = p;
      opt.textContent = p;
      select.appendChild(opt);
    }
    // Keep selection in sync
    select.value = this.selectedProfile;
  },

  async _getConfigForSelectedProfile() {
    if (this.selectedProfile === "default") {
      return this.getSettingsFieldConfigJson().value;
    }
    // try to read file content via API
    const resp = await API.callJsonApi("mcp_profile_get_config", { profile: this.selectedProfile });
    if (resp.success) {
      return resp.mcp_servers;
    }
    return '{\n  "mcpServers": {}\n}';
  },

  async onProfileChange(profile) {
    this.selectedProfile = profile;
    if (this.editor) {
      const json = await this._getConfigForSelectedProfile();
      this.editor.setValue(json);
      this.editor.clearSelection();
    }
    // force refresh status list for new profile
    await this._statusCheck();
    this._renderProfilesSelect();
  },
};

const store = createStore("mcpServersStore", model);

export { store };
