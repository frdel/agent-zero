import { createStore } from "/js/AlpineStore.js";
import { scrollModal } from "/js/modals.js";
import sleep from "/js/sleep.js";

const model = {
  editor: null,
  settingsJsonField: settingsModalProxy.settings.sections
    .filter((x) => x.id == "mcp_client")[0]
    .fields.filter((x) => x.id == "mcp_servers")[0],
  servers: [
    { connected: true, name: "Server 1", tools: 10 },
    { connected: false, name: "Server 2", tools: 0, error: "Server is disabled in configuration" },
  ],
  loading: false,

  async initialize() {
    // Initialize the JSON Viewer after the modal is rendered
    const container = document.getElementById("mcp-servers-config-json");
    if (container) {
      const editor = ace.edit("mcp-servers-config-json");

      const dark = localStorage.getItem("darkMode");
      if (dark != "false") {
        editor.setTheme("ace/theme/github_dark");
      } else {
        editor.setTheme("ace/theme/tomorrow");
      }

      editor.session.setMode("ace/mode/json");
      const json = this.settingsJsonField.value;
      editor.setValue(json);
      editor.clearSelection();
      this.editor = editor;
    }
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

  onClose() {
    const val = this.editor.getValue();
    this.settingsJsonField.value = val;
  },

  async applyNow() {
    if (this.loading) return;
    this.loading = true;
      scrollModal("mcp-servers-status");
    await sleep(1000);
      scrollModal("mcp-servers-status");
      this.loading = false;
  },
};

const store = createStore("mcpServersStore", model);

export { store };
