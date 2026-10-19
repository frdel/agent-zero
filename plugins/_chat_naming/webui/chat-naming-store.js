import { createStore } from "/js/AlpineStore.js";
import { callJsonApi } from "/js/api.js";
import { openModal, closeModal } from "/js/modals.js";
import {
  toastFrontendError,
  toastFrontendSuccess,
} from "/components/notifications/notification-store.js";
import { store as chatsStore } from "/components/sidebar/chats/chats-store.js";
import { store as sidebarStore } from "/components/sidebar/sidebar-store.js";
import { store as tasksStore } from "/plugins/_scheduler/webui/sidebar/tasks-store.js";

const PLUGIN_ID = "_chat_naming";
const MODAL_PATH = `/plugins/${PLUGIN_ID}/webui/rename.html`;

const model = {
  itemId: "",
  kind: "chat",
  name: "",
  loading: false,
  generating: false,
  saving: false,

  async openFromMenu(menuId, kind) {
    const prefix = `${kind}:`;
    if (typeof menuId !== "string" || !menuId.startsWith(prefix)) return;
    this.itemId = menuId.slice(prefix.length);
    this.kind = kind;
    this.name = this.localName();
    sidebarStore.rowMenuClose();
    await openModal(MODAL_PATH);
  },

  async onOpen() {
    if (!this.itemId) return;
    this.loading = true;
    try {
      const response = await this.call("get");
      this.name = response?.name || "";
    } catch (error) {
      void toastFrontendError(error?.message || "Failed to load the name.", "Chat Naming");
    } finally {
      this.loading = false;
    }
  },

  async generate() {
    if (!this.itemId || this.generating) return;
    this.generating = true;
    try {
      const response = await this.call("generate");
      this.name = response?.name || this.name;
    } catch (error) {
      void toastFrontendError(error?.message || "Failed to generate a name.", "Chat Naming");
    } finally {
      this.generating = false;
    }
  },

  async openSettings() {
    try {
      const { store } = await import("/components/plugins/plugin-settings-store.js");
      const item = this.localItem();
      await store.openConfig(
        PLUGIN_ID,
        item?.project?.name || "",
        item?.agent_profile || "",
      );
    } catch (error) {
      void toastFrontendError(
        error?.message || "Failed to open settings.",
        "Chat Naming",
      );
    }
  },

  async save() {
    const name = this.name.trim();
    if (!this.itemId || !name || this.saving) return;
    this.saving = true;
    try {
      const response = await this.call("save", { name });
      this.name = response?.name || name;
      this.updateLocalName(this.name);
      await closeModal(MODAL_PATH);
      void toastFrontendSuccess(
        this.kind === "task" ? "Task renamed." : "Chat renamed.",
        "Chat Naming",
      );
    } catch (error) {
      void toastFrontendError(error?.message || "Failed to save the name.", "Chat Naming");
    } finally {
      this.saving = false;
    }
  },

  close() {
    return closeModal(MODAL_PATH);
  },

  call(action, extra = {}) {
    return callJsonApi(`/plugins/${PLUGIN_ID}/chat_name`, {
      action,
      kind: this.kind,
      item_id: this.itemId,
      ...extra,
    });
  },

  localName() {
    const item = this.localItem();
    return this.kind === "task" ? item?.task_name || "" : item?.name || "";
  },

  localItem() {
    return this.kind === "task"
      ? tasksStore.tasks.find((task) => task.id === this.itemId)
      : chatsStore.contexts.find((context) => context.id === this.itemId);
  },

  updateLocalName(name) {
    if (this.kind === "task") {
      tasksStore.tasks = tasksStore.tasks.map((task) =>
        task.id === this.itemId ? { ...task, name, task_name: name } : task,
      );
      return;
    }
    chatsStore.contexts = chatsStore.contexts.map((context) =>
      context.id === this.itemId
        ? {
            ...context,
            name,
            ...(context.parent_context_id ? { parent_context_label: name } : {}),
          }
        : context,
    );
    if (chatsStore.selectedContext?.id === this.itemId) {
      chatsStore.selectedContext = {
        ...chatsStore.selectedContext,
        name,
        ...(chatsStore.selectedContext.parent_context_id
          ? { parent_context_label: name }
          : {}),
      };
    }
  },
};

export const store = createStore("chatNaming", model);
