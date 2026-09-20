import { createStore, getStore } from "/js/AlpineStore.js";
import { callJsonApi } from "/js/api.js";
import {
  sendJsonData,
  getContext,
  setContext,
  toastFetchError,
  toast,
  justToast,
  getConnectionStatus,
} from "/index.js";
import { store as notificationStore } from "/components/notifications/notification-store.js";
import { store as sidebarStore } from "/components/sidebar/sidebar-store.js";
import { store as syncStore } from "/components/sync/sync-store.js";
import { store as chatInputStore } from "/components/chat/input/input-store.js";

const model = {
  contexts: [],
  contextsJson: "",
  selected: "",
  selectedContext: null,
  loggedIn: false,
  expandedParents: {},
  deletedContextIds: {},

  // for convenience
  getSelectedChatId() {
    return this.selected;
  },

  getSelectedContext(){
    return this.selectedContext;
  },

  init() {
    this.loggedIn = Boolean(window.runtimeInfo && window.runtimeInfo.loggedIn);

    // URL parameter takes priority (e.g. ?ctxid=abc from "open in new window")
    const urlParams = new URL(window.location.href).searchParams;
    const urlCtxId = urlParams.get("ctxid");
    if (urlCtxId) {
      const cleanUrl = new URL(window.location.href);
      cleanUrl.searchParams.delete("ctxid");
      window.history.replaceState({}, "", cleanUrl);
      this.selectChat(urlCtxId);
      return;
    }

    // Initialize from sessionStorage
    const lastSelectedChat = sessionStorage.getItem("lastSelectedChat");
    if (lastSelectedChat) {
      this.selectChat(lastSelectedChat);
    }
  },

  // Update contexts from sync snapshots
  applyContexts(contextsList) {
    const incomingContexts = Array.isArray(contextsList) ? contextsList : [];

    // Sort by created_at time (newer first)
    const nextContexts = incomingContexts
      .filter((context) => !this.deletedContextIds[context?.id])
      .sort((a, b) => (b.created_at || 0) - (a.created_at || 0));
    const contextsJson = JSON.stringify(nextContexts);
    if (contextsJson !== this.contextsJson) {
      this.contextsJson = contextsJson;
      const sameRows =
        nextContexts.length === this.contexts.length &&
        nextContexts.every((context, index) => context?.id === this.contexts[index]?.id);

      if (sameRows) {
        nextContexts.forEach((context, index) => {
          const current = this.contexts[index];
          if (JSON.stringify(current) === JSON.stringify(context)) return;
          Object.keys(current).forEach((key) => {
            if (!(key in context)) delete current[key];
          });
          Object.assign(current, context);
        });
      } else {
        this.contexts = nextContexts;
      }
    }

    // Keep selectedContext in sync when the currently selected context's
    // metadata changes (e.g. project activation/deactivation).
    if (this.selected) {
      const selectedId = this.selected;
      const updated = this.contexts.find((ctx) => ctx.id === selectedId);
      if (updated) {
        if (this.selectedContext !== updated) this.selectedContext = updated;
        if (updated.parent_context_id) {
          this.expandAncestors(updated);
        } else if (
          this.hasChildren(selectedId) &&
          this.expandedParents[selectedId] === undefined
        ) {
          this.expandedParents = {
            ...this.expandedParents,
            [selectedId]: true,
          };
        }
      }
    }
  },

  topLevelContexts() {
    return sidebarStore.sortRows(
      "chat",
      this.contexts.filter((ctx) => !ctx?.parent_context_id),
    );
  },

  childContexts(parentId) {
    return sidebarStore.sortRows(
      "chat",
      this.contexts.filter((ctx) => ctx?.parent_context_id === parentId),
    );
  },

  hasChildren(parentId) {
    return this.contexts.some((context) => context.parent_context_id === parentId);
  },

  expandAncestors(context) {
    const seen = new Set();
    while (context?.parent_context_id && !seen.has(context.parent_context_id)) {
      const parentId = context.parent_context_id;
      seen.add(parentId);
      if (!this.expandedParents[parentId]) this.expandedParents[parentId] = true;
      context = this.contexts.find((row) => row.id === parentId);
    }
  },

  isExpanded(parentId) {
    return Boolean(this.expandedParents?.[parentId]);
  },

  toggleChildren(parentId) {
    if (!parentId || !this.hasChildren(parentId)) return;
    this.expandedParents = {
      ...this.expandedParents,
      [parentId]: !this.expandedParents?.[parentId],
    };
  },

  displayName(context) {
    if (!context) return "";
    return context.parent_context_label || context.name || `Chat #${context.no}`;
  },

  // Select a chat
  async selectChat(id) {
    // The row may still have a queued click while Alpine removes it.
    if (!id || this.deletedContextIds[id]) return;

    const currentContext = getContext();
    if (id === currentContext) {
      this.setSelected(id);
      return;
    }

    // Proceed with context selection
    setContext(id);

    // Update selection state (will also persist to localStorage)
    this.setSelected(id);

    // In push mode, context switching triggers a new `state_request` via setContext().
    // Keep polling only as a degraded-mode fallback.
    try {
      const mode = typeof syncStore.mode === "string" ? syncStore.mode : null;
      const shouldFallbackPoll = mode === "DEGRADED";
      if (shouldFallbackPoll && typeof globalThis.poll === "function") {
        globalThis.poll();
      }
    } catch (_e) {
      // no-op
    }
  },

  // Delete a chat
  async killChat(id) {
    if (!id) {
      console.error("No chat ID provided for deletion");
      return;
    }
    if (this.deletedContextIds[id]) return;

    const removedContext = this.contexts.find((context) => context.id === id);
    const deletingSelectedContext = this.selected === id || getContext() === id;

    // Remove first, before selecting the fallback chat. Alpine batches both
    // state changes into one render so the old row cannot remain above the new
    // selection while the HTTP request is in flight.
    this.deletedContextIds = { ...this.deletedContextIds, [id]: true };
    this.contexts = this.contexts.filter((context) => context.id !== id);

    try {
      // Switch to another context if deleting current
      if (deletingSelectedContext) {
        await this.switchFromContext(id);
      }

      // Delete the chat on the server
      await sendJsonData("/chat_remove", { context: id });

      // Show success notification
      justToast("Chat deleted successfully", "success", 1000, "chat-removal");
    } catch (e) {
      const deletedContextIds = { ...this.deletedContextIds };
      delete deletedContextIds[id];
      this.deletedContextIds = deletedContextIds;

      // Roll back the optimistic row removal without disturbing any chat the
      // user selected while the request was pending.
      if (removedContext && !this.contexts.some((context) => context.id === id)) {
        this.contexts = [...this.contexts, removedContext].sort(
          (a, b) => (b.created_at || 0) - (a.created_at || 0),
        );
      }

      console.error("Error deleting chat:", e);
      toastFetchError("Error deleting chat", e);
    }
  },

  // Switch from a context that's being deleted
  async switchFromContext(id) {
    // Find an alternate chat to switch to
    let alternateChat = null;
    for (let i = 0; i < this.contexts.length; i++) {
      if (this.contexts[i].id !== id) {
        alternateChat = this.contexts[i];
        break;
      }
    }

    if (alternateChat) {
      await this.selectChat(alternateChat.id);
    } else {
      // If no other chats, create a new empty context
      this.deselectChat();
      //await this.newChat();
    }
  },

  // Reset current chat
  async resetChat(ctxid = null) {
    try {
      const context = ctxid || this.selected || getContext();
      await sendJsonData("/chat_reset", {
        context
      });

      // Increment reset counter
      if (typeof globalThis.resetCounter === 'number') {
        globalThis.resetCounter = globalThis.resetCounter + 1;
      }      
    } catch (e) {
      toastFetchError("Error resetting chat", e);
    }
  },

  // Create new chat
  async newChat(projectName = undefined) {
    try {

      // first create a new chat on the backend
      const response = await sendJsonData("/chat_create", {
        current_context: this.selected,
        ...(projectName !== undefined ? { project_name: projectName } : {}),
      });

      if (response.ok) {
        await this.selectChat(response.ctxid);
        document.dispatchEvent(new CustomEvent("chat-created", { detail: { ctxid: response.ctxid } }));
        return response.ctxid;
      }

    } catch (e) {
      toastFetchError("Error creating new chat", e);
    }
    return null;
  },

  deselectChat(){
    globalThis.deselectChat(); //TODO move here
  },

  // Smoothly scroll the chats list to top if present
  _scrollChatsToTop() {
    const listEl = document.querySelector('#chats-section .chats-config-list');
    if (!listEl) return; // no-op if not in DOM
    listEl.scrollTo({ top: 0, behavior: 'smooth' });
  },

  // Load chats from files
  async loadChats() {
    try {
      const fileContents = await this.readJsonFiles();
      if (!fileContents.length) return;
      const response = await sendJsonData("/chat_load", { chats: fileContents });

      if (!response) {
        toast("No response returned.", "error");
      } else {
        // Set context to first loaded chat
        if (response.ctxids?.[0]) {
          setContext(response.ctxids[0]);
        }
        toast("Chats loaded.", "success");
      }
    } catch (e) {
      toastFetchError("Error loading chats", e);
    }
  },

  // Save the supplied chat, or the current chat when omitted
  async saveChat(ctxid = null) {
    try {
      const context = ctxid || this.selected || getContext();
      const response = await sendJsonData("/chat_export", { ctxid: context });

      if (!response) {
        toast("No response returned.", "error");
      } else {
        this.downloadFile(response.ctxid + ".json", response.content);
        toast("Chat file downloaded.", "success");
      }
    } catch (e) {
      toastFetchError("Error saving chat", e);
    }
  },

  // Helper: read JSON files
  readJsonFiles() {
    return new Promise((resolve, reject) => {
      const input = document.createElement("input");
      input.type = "file";
      input.accept = ".json";
      input.multiple = true;
      input.oncancel = () => resolve([]);

      input.click();

      input.onchange = async () => {
        const files = input.files;
        if (!files.length) {
          resolve([]);
          return;
        }

        const filePromises = Array.from(files).map((file) => {
          return new Promise((fileResolve, fileReject) => {
            const reader = new FileReader();
            reader.onload = () => fileResolve(reader.result);
            reader.onerror = fileReject;
            reader.readAsText(file);
          });
        });

        try {
          const fileContents = await Promise.all(filePromises);
          resolve(fileContents);
        } catch (error) {
          reject(error);
        }
      };
    });
  },

  // Helper: download file
  downloadFile(filename, content) {
    const blob = new Blob([content], { type: "application/json" });
    const link = document.createElement("a");
    const url = URL.createObjectURL(blob);
    link.href = url;
    link.download = filename;
    link.click();

    setTimeout(() => {
      URL.revokeObjectURL(url);
    }, 0);
  },

  // Check if context exists
  contains(contextId) {
    return this.contexts.some((ctx) => ctx.id === contextId);
  },

  // Get first context ID
  firstId() {
    return this.contexts.length > 0 ? this.contexts[0].id : null;
  },

  // Set selected context
  setSelected(contextId) {
    this.selected = contextId || "";
    this.selectedContext = this.contexts.find((ctx) => ctx.id === this.selected);
    // if not found in contexts, try to find in tasks < not nice, will need refactor later
    if(!this.selectedContext) this.selectedContext = (getStore("tasks")?.tasks ?? []).find((ctx) => ctx.id === this.selected);
    this.expandAncestors(this.selectedContext);
    if (this.selected) {
      sessionStorage.setItem("lastSelectedChat", this.selected);
    } else {
      sessionStorage.removeItem("lastSelectedChat");
    }
  },

  // Restart the backend
  async restart() {
    // Check connection status (avoid spamming requests when already disconnected)
    const connectionStatus = getConnectionStatus();
    if (connectionStatus === false) {
      await notificationStore.frontendError(
        "Backend disconnected, cannot restart.",
        "Restart Error",
      );
      return;
    }

    // Create a backend notification first so other tabs have a chance to show it
    // before the process is replaced.
    const notificationId = await notificationStore.info(
      "Restarting...",
      "System Restart",
      "",
      9999,
      "restart",
    );

    // Best-effort: wait briefly for the notification to arrive via state sync so
    // the initiating tab (and typically other tabs) renders the toast before restart.
    if (notificationId) {
      const deadline = Date.now() + 800;
      while (Date.now() < deadline) {
        try {
          
          const stack = Array.isArray(notificationStore.toastStack) ? notificationStore.toastStack : null;
          if (stack && stack.some((toast) => toast && toast.id === notificationId)) {
            break;
          }
        } catch (_err) {
          break;
        }
        await new Promise((resolve) => setTimeout(resolve, 25));
      }
    }

    // The restart endpoint usually drops the connection as the process is replaced.
    // Do not wait on /health - recovery is driven by WebSocket CSRF preflight + reconnect.
    try {
      await sendJsonData("/restart", {});
    } catch (_e) {
      // ignore
    }
  },

  async logout() {
    try {
      await callJsonApi("/logout", {});
    } catch (_e) {
      // ignore
    }

    try {
      sessionStorage.removeItem("lastSelectedChat");
      sessionStorage.removeItem("lastSelectedTask");
    } catch (_e) {
      // ignore
    }

    try {
      window.location.reload();
    } catch (_e) {
      // ignore
    }
  }
};

const store = createStore("chats", model);

export { store };
