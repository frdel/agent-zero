import { store as modelConfigStore } from "/plugins/_model_config/webui/model-config-store.js";
import { store as chatsStore } from "/components/sidebar/chats/chats-store.js";

const PRESET_EDITOR = "/plugins/_model_config/webui/main.html";

// The editor builds its draft as soon as it renders, and presets may have changed
// outside it (another tab, the API, a plugin). Reload them before every open,
// including /presets, which opens the modal without openPresetEditor().
export default async function refreshPresetEditor(ctx) {
  if (ctx?.modalPath !== PRESET_EDITOR) return;
  await Promise.all([
    modelConfigStore.loadGlobalPresets(),
    modelConfigStore.preparePresetEditor(chatsStore?.selected || ""),
  ]);
}
