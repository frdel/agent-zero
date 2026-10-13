import { createStore } from "/js/AlpineStore.js";
import { store as navStore } from "/components/chat/navigation/chat-navigation-store.js";
import * as api from "/js/api.js";
import {
  toastFrontendInfo,
  NotificationPriority,
} from "/components/notifications/notification-store.js";
import { sleep } from "/js/sleep.js";
import { store as chatsStore } from "/components/sidebar/chats/chats-store.js";
import { store as attachmentsStore } from "/components/chat/attachments/attachmentsStore.js";

const model = {
  // items: [],
  get items() {
    return chatsStore.selectedContext?.message_queue || [];
  },

  pendingItems: [], // Local pending items (uploading to queue)

  _pendingAddOps: {},

  _lastAddToQueuePromise: Promise.resolve(),

  _getQueueScrollerEl() {
    return document.querySelector(".queue-preview .queue-items");
  },

  scrollQueueToBottom() {
    const el = this._getQueueScrollerEl();
    if (!el) return;

    const scroll = () => {
      el.scrollTop = el.scrollHeight;
    };

    requestAnimationFrame(() => {
      scroll();
      requestAnimationFrame(scroll);
    });
  },

  get hasQueue() {
    return this.items.length > 0 || this.pendingItems.length > 0;
  },

  get count() {
    return this.items.length + this.pendingItems.length;
  },

  // Combined items for display: confirmed first, then pending at the end
  get allItems() {
    return [...this.items, ...this.pendingItems];
  },

  async addToQueue(text, attachments = []) {
    const context = globalThis.getContext?.();
    if (!context) return false;

    // Generate a temporary ID for pending item
    const tempId = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const pendingItem = {
      id: tempId,
      text: text.substring(0, 200) || "(attachment only)",
      attachments: attachments.map((a) => a.name || a.file?.name || "file"),
      attachmentUrls: this._pendingAttachmentUrls(attachments),
      pending: true,
    };

    const controller =
      typeof AbortController !== "undefined" ? new AbortController() : null;
    this._pendingAddOps = {
      ...this._pendingAddOps,
      [tempId]: {
        canceled: false,
        controller,
      },
    };

    // Add to pending immediately for UI feedback
    this.pendingItems = [...this.pendingItems, pendingItem];
    this.scrollQueueToBottom();

    const run = async () => {
      const op = this._pendingAddOps?.[tempId];
      if (!op || op.canceled) {
        this._pendingAddOps = { ...this._pendingAddOps };
        delete this._pendingAddOps[tempId];
        return false;
      }

      try {
        let filenames = [];
        if (attachments.length > 0) {
          const formData = new FormData();
          for (const att of attachments) {
            formData.append("file", att.file || att);
          }
          const resp = await api.fetchApi("/upload", {
            method: "POST",
            body: formData,
            signal: op.controller ? op.controller.signal : undefined,
          });
          if (resp.ok) {
            const result = await resp.json();
            filenames = result.filenames || [];
          }
        }

        const resp = await api.fetchApi("/message_queue_add", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          credentials: "same-origin",
          body: JSON.stringify({
            context,
            text,
            attachments: filenames,
            item_id: tempId,
          }),
          signal: op.controller ? op.controller.signal : undefined,
        });

        if (!resp || !resp.ok) {
          this._dropPendingItem(tempId);
          return false;
        }

        const response = await resp.json();

        if (!response?.ok) {
          this._dropPendingItem(tempId);
        }

        return response?.ok || false;
      } catch (e) {
        if (e?.name !== "AbortError") {
          console.error("Failed to queue message:", e);
          this._dropPendingItem(tempId);
        }
        return false;
      } finally {
        this._pendingAddOps = { ...this._pendingAddOps };
        delete this._pendingAddOps[tempId];
      }
    };

    // Chain promises to ensure sequential execution
    const previous = this._lastAddToQueuePromise || Promise.resolve();
    const chained = previous.catch(() => false).then(run);
    this._lastAddToQueuePromise = chained.catch(() => false);
    return await chained;
  },

  _pendingAttachmentUrls(attachments) {
    const urls = {};
    for (const att of attachments) {
      const name = att.name || att.file?.name || "file";
      if (attachmentsStore.isImageFile(name)) {
        urls[name] = att.url || (att.file ? URL.createObjectURL(att.file) : null);
      }
    }
    return urls;
  },

  _dropPendingItem(tempId) {
    this.pendingItems = this.pendingItems.filter((p) => p.id !== tempId);
  },

  async removeItem(itemId) {
    const context = globalThis.getContext?.();
    if (!context) return;

    const isPending = this.pendingItems.some((p) => p.id === itemId);
    if (isPending) {
      const op = this._pendingAddOps?.[itemId];
      if (op) {
        op.canceled = true;
        if (op.controller) {
          op.controller.abort();
        }
      }
      this.pendingItems = this.pendingItems.filter((p) => p.id !== itemId);
      return;
    }

    try {
      await api.callJsonApi("/message_queue_remove", {
        context,
        item_id: itemId,
      });
    } catch (e) {
      console.error("Failed to remove from queue:", e);
    }
  },

  async clearQueue() {
    const context = globalThis.getContext?.();
    if (!context) return;
    try {
      await api.callJsonApi("/message_queue_remove", { context });
    } catch (e) {
      console.error("Failed to clear queue:", e);
    }
  },

  async sendItem(itemId) {
    const context = globalThis.getContext?.();
    if (!context) return;
    try {
      await api.callJsonApi("/message_queue_send", {
        context,
        item_id: itemId,
      });
    } catch (e) {
      console.error("Failed to send queued message:", e);
    }
  },

  async sendAll() {
    const context = globalThis.getContext?.();
    if (!context || !this.hasQueue) return;

    // check for pending uploads and notify user
    if (this.pendingItems.length > 0) {
      await sleep(1000);
      if (this.pendingItems.length > 0) {
        toastFrontendInfo(
          "There are pending uploads in the queue. You can wait for them to finish or remove them.",
          "Pending uploads",
          3,
          "pending-uploads",
          NotificationPriority.NORMAL,
          true,
        );
        return;
      }
    }

    if (!this.hasQueue) return;
    try {
      navStore.scrollToBottom();
      await api.callJsonApi("/message_queue_send", { context, send_all: true });
    } catch (e) {
      console.error("Failed to send all queued:", e);
    }
  },

  updateFromPoll() {
    // this.items = queue || [];

    if (this.pendingItems.length > 0) {
      const serverIds = new Set(this.items.map((i) => i.id).filter(Boolean));
      this.pendingItems = this.pendingItems.filter((p) => {
        if (!p.id) return true;
        return !serverIds.has(p.id);
      });
    }
    // this.scrollQueueToBottom();
  },

  getAttachmentUrl(item, filename) {
    const local = item?.pending ? item.attachmentUrls?.[filename] : null;
    return local || `/api/image_get?path=/a0/usr/uploads/${encodeURIComponent(filename)}`;
  },
};

const store = createStore("messageQueue", model);
export { store };
