import { createStore } from "/js/AlpineStore.js";
import * as shortcuts from "/js/shortcuts.js";
import { store as fileBrowserStore } from "/components/modals/file-browser/file-browser-store.js";
import { openLatest as openLatestSurface } from "/js/surfaces.js";
import { store as messageQueueStore } from "/components/chat/message-queue/message-queue-store.js";
import { store as attachmentsStore } from "/components/chat/attachments/attachmentsStore.js";
import { store as chatsStore } from "/components/sidebar/chats/chats-store.js";

const ICON_MARKER_RE = /icon:\/\/([a-zA-Z0-9_]+)(\[(?:\\.|[^\]])*\])?/g;
const FENCE_LINE_RE = /^```([A-Za-z0-9_-]*)?$/;
const BLOCK_TAGS = new Set(["DIV", "P", "LI"]);
const DRAFT_STORAGE_PREFIX = "a0:chat-draft:";

function escapeHTML(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function unescapeIconTooltip(block) {
  if (!block) return "";
  return block
    .slice(1, -1)
    .replace(/\\\[/g, "[")
    .replace(/\\\]/g, "]")
    .replace(/\\\\/g, "\\");
}

function convertIconMarkersToHtml(value) {
  const text = String(value ?? "");
  let html = "";
  let lastIndex = 0;

  text.replace(ICON_MARKER_RE, (match, iconName, tooltipBlock, offset) => {
    html += escapeHTML(text.slice(lastIndex, offset));
    const tooltip = unescapeIconTooltip(tooltipBlock) || iconName;
    html += (
      `<x-icon class="icon chat-input-progress-icon" ` +
      `title="${escapeHTML(tooltip)}" name="${escapeHTML(iconName)}"></x-icon>`
    );
    lastIndex = offset + match.length;
    return match;
  });

  html += escapeHTML(text.slice(lastIndex));
  return html;
}

const model = {
  paused: false,
  _pendingPause: 0,
  _message: "",
  _editorEl: null,
  _history: [],
  _historyIndex: null,
  _draft: "",
  _historyCtxid: null,
  _draftCtxid: null,
  /** Composer + menu (bottom actions moved into dropdown) */
  chatMoreMenuOpen: false,
  progressText: "",
  progressActive: false,

  get message() {
    return this._message;
  },

  set message(value) {
    this._message = String(value ?? "");
    this._renderEditorFromText(this._message);
    this._saveDraft();
  },

  toggleChatMoreMenu() {
    this.chatMoreMenuOpen = !this.chatMoreMenuOpen;
  },

  closeChatMoreMenu() {
    this.chatMoreMenuOpen = false;
  },

  _getSendState() {
    const hasInput = this.message.trim() || attachmentsStore?.attachments?.length > 0;
    const hasQueue = !!messageQueueStore?.hasQueue;
    const running = !!chatsStore.selectedContext?.running;

    if (running && !hasInput) return "stop";
    if (hasQueue && !hasInput) return "all";
    if ((running || hasQueue) && hasInput) return "queue";
    return "normal";
  },

  get inputPlaceholder() {
    if (!chatsStore.selected) return "Ask anything to start a new chat";
    const state = this._getSendState();
    if ((state === "all" || state === "stop") && messageQueueStore?.hasQueue) {
      return "Press Enter to send queued messages";
    }
    if (this.showProgressPlaceholder) return "";
    return "Type your message here...";
  },

  get showProgressPlaceholder() {
    const state = this._getSendState();
    return (
      !!chatsStore.selected &&
      state !== "all" &&
      !(state === "stop" && messageQueueStore?.hasQueue) &&
      !!this.progressText &&
      !this.message
    );
  },

  get progressPlaceholderHtml() {
    return convertIconMarkersToHtml(this.progressText);
  },

  // Computed: send button icon type
  get sendButtonIcon() {
    const state = this._getSendState();
    if (state === "stop") return "stop";
    if (state === "all") return "send_and_archive";
    if (state === "queue") return "schedule_send";
    return "arrow_forward";
  },

  // Computed: send button CSS class
  get sendButtonClass() {
    const state = this._getSendState();
    if (state === "stop") return "stop";
    if (state === "all") return "send-queue send-all";
    if (state === "queue") return "send-queue queue";
    return "";
  },

  // Computed: send button title
  get sendButtonTitle() {
    const state = this._getSendState();
    if (state === "stop") return "Stop agent";
    if (state === "all") return "Send all queued messages";
    if (state === "queue") return "Add to queue";
    return "Send message";
  },

  init() {
    console.log("Input store initialized");
    // Event listeners are now handled via Alpine directives in the component
  },

  async sendMessage() {
    this._syncMessageFromEditor();
    const pendingMessage = this.message;

    if (!chatsStore.selected && (this.message.trim() || attachmentsStore?.attachments?.length > 0)) {
      const ctxid = await chatsStore.newChat();
      if (!ctxid && !chatsStore.selected) return;
      this.message = pendingMessage;
    }

    // Capture sent prompt to per-chat history (bash-style)
    try { this._pushHistory(this.message); } catch (_e) { /* ignore */ }

    // Delegate to the global function
    if (globalThis.sendMessage) {
      await globalThis.sendMessage();
    }
  },

  async activateSendButton() {
    this._syncMessageFromEditor();
    if (this._getSendState() === "stop") {
      await this.stopAgent();
      return;
    }
    await this.sendMessage();
  },

  mountEditor(editor) {
    this._editorEl = editor;
    this.setDraftContext(shortcuts.getCurrentContextId());
    this._renderEditorFromText(this._message);
    this.adjustTextareaHeight({ target: editor });
  },

  unmountEditor(editor) {
    if (this._editorEl === editor) this._editorEl = null;
  },

  _composerTextareas(target = null) {
    const editor = target?.closest?.("#chat-input") || this._editorEl || document.getElementById("chat-input");
    return editor ? [editor] : [];
  },

  _activeTextarea() {
    const active = document.activeElement;
    const activeEditor = active?.closest?.("#chat-input");
    if (activeEditor) {
      return activeEditor;
    }
    return this._editorEl || document.getElementById("chat-input");
  },

  _renderEditorFromText(text) {
    const editor = this._editorEl;
    if (!editor) return;
    if (editor.textContent !== text || editor.querySelector("[data-code-block]")) {
      editor.textContent = text;
    }
    this._setEditorEmptyState();
  },

  _setEditorEmptyState() {
    const editor = this._editorEl;
    if (editor) editor.classList.toggle("is-empty", !this._message);
  },

  _createCodeBlock(lang = "") {
    const block = document.createElement("div");
    block.className = "composer-code-block";
    block.dataset.codeBlock = "true";
    block.dataset.lang = lang;
    block.contentEditable = "false";

    const code = document.createElement("pre");
    code.className = "composer-code-content";
    code.dataset.codeContent = "true";
    code.contentEditable = "true";
    code.spellcheck = false;
    code.setAttribute("aria-label", "Code block");
    block.append(code);

    return block;
  },

  _plainText(node) {
    if (!node) return "";
    if (node.nodeType === Node.TEXT_NODE) return node.nodeValue || "";
    if (node.nodeType !== Node.ELEMENT_NODE) return "";
    if (node.matches?.("[data-code-block]")) {
      const lang = node.dataset.lang || "";
      const code = this._plainText(node.querySelector("[data-code-content]")).replace(/\n$/, "");
      return "```" + lang + "\n" + code + "\n```";
    }
    if (node.tagName === "BR") return "\n";

    let text = "";
    for (const child of node.childNodes) text += this._plainText(child);
    if (node !== this._editorEl && BLOCK_TAGS.has(node.tagName) && text && !text.endsWith("\n")) {
      text += "\n";
    }
    return text;
  },

  _editorToMarkdown() {
    return this._plainText(this._editorEl).replace(/\n$/, "");
  },

  _syncMessageFromEditor() {
    if (!this._editorEl) return;
    this._message = this._editorToMarkdown();
    this._setEditorEmptyState();
    this._saveDraft();
  },

  _isInCodeBlock(target) {
    return Boolean(target?.closest?.("[data-code-content]"));
  },

  _selectionOffsets(editor) {
    const selection = document.getSelection?.();
    if (!selection || selection.rangeCount === 0 || !editor) {
      return { start: this._message.length, end: this._message.length };
    }
    const range = selection.getRangeAt(0);
    if (!editor.contains(range.startContainer) || !editor.contains(range.endContainer)) {
      return { start: this._message.length, end: this._message.length };
    }

    const before = range.cloneRange();
    before.selectNodeContents(editor);
    before.setEnd(range.startContainer, range.startOffset);

    const selected = range.cloneRange();
    return {
      start: before.toString().length,
      end: before.toString().length + selected.toString().length,
    };
  },

  _setEditorCaret(offset) {
    const editor = this._activeTextarea();
    const selection = document.getSelection?.();
    if (!editor || !selection) return;

    editor.focus();
    const range = document.createRange();
    let remaining = Math.max(0, Number(offset) || 0);
    const walker = document.createTreeWalker(editor, NodeFilter.SHOW_TEXT);
    let node = walker.nextNode();

    while (node) {
      const length = node.nodeValue.length;
      if (remaining <= length) {
        range.setStart(node, remaining);
        range.collapse(true);
        selection.removeAllRanges();
        selection.addRange(range);
        return;
      }
      remaining -= length;
      node = walker.nextNode();
    }

    range.selectNodeContents(editor);
    range.collapse(false);
    selection.removeAllRanges();
    selection.addRange(range);
  },

  _focusCodeBlock(block) {
    queueMicrotask(() => {
      const code = block.querySelector("[data-code-content]");
      const selection = document.getSelection?.();
      if (!code || !selection) return;
      code.focus();
      const range = document.createRange();
      range.selectNodeContents(code);
      range.collapse(false);
      selection.removeAllRanges();
      selection.addRange(range);
    });
  },

  _insertPlainText(text) {
    const selection = document.getSelection?.();
    if (!selection || selection.rangeCount === 0) return false;
    const range = selection.getRangeAt(0);
    range.deleteContents();
    const node = document.createTextNode(text);
    range.insertNode(node);
    range.setStart(node, node.nodeValue.length);
    range.collapse(true);
    selection.removeAllRanges();
    selection.addRange(range);
    return true;
  },

  _tryCreateCodeBlock($event) {
    const editor = this._activeTextarea();
    const selection = document.getSelection?.();
    if (!editor || !selection || selection.rangeCount === 0) return false;

    const range = selection.getRangeAt(0);
    if (!range.collapsed || !editor.contains(range.startContainer)) return false;
    if (this._isInCodeBlock(range.startContainer.parentElement)) return false;

    const before = range.cloneRange();
    before.selectNodeContents(editor);
    before.setEnd(range.startContainer, range.startOffset);

    const after = range.cloneRange();
    after.selectNodeContents(editor);
    after.setStart(range.startContainer, range.startOffset);

    const lineBefore = before.toString().split("\n").pop() || "";
    const lineAfter = (after.toString().split("\n")[0] || "");
    const match = (lineBefore + lineAfter).match(FENCE_LINE_RE);
    if (!match || lineAfter) return false;
    if (range.startContainer.nodeType !== Node.TEXT_NODE || range.startOffset < lineBefore.length) return false;

    $event.preventDefault();
    const editRange = range.cloneRange();
    editRange.setStart(range.startContainer, range.startOffset - lineBefore.length);
    editRange.deleteContents();

    const block = this._createCodeBlock(match[1] || "");
    editRange.insertNode(block);
    block.after(document.createTextNode("\n"));
    this._focusCodeBlock(block);
    this._syncMessageFromEditor();
    this.adjustTextareaHeight({ target: editor });
    return true;
  },

  handleInput($event) {
    this._syncMessageFromEditor();
    this.adjustTextareaHeight($event);
  },

  handlePaste($event) {
    const text = $event.clipboardData?.getData("text/plain");
    if (text === undefined) return;
    $event.preventDefault();
    this._insertPlainText(text);
    this.handleInput($event);
  },

  handleKeydown($event) {
    if ($event.isComposing || $event.keyCode === 229) return;

    if ($event.key === "Enter") {
      if (this._isInCodeBlock($event.target)) return;
      if (!$event.shiftKey) {
        if (this._tryCreateCodeBlock($event)) return;
        $event.preventDefault();
        this.sendMessage();
      }
      return;
    }

    if ($event.key === "ArrowUp") this.historyPrev($event);
    if ($event.key === "ArrowDown") this.historyNext($event);
  },

  adjustTextareaHeight($event = null) {
    const target = $event?.target || null;
    for (const chatInput of this._composerTextareas(target)) {
      // Contenteditable grows naturally; freezing scrollHeight can retain a transient layout.
      chatInput.style.height = "auto";
    }
  },

  applyPausedSnapshot(paused) {
    // A click in flight owns the pause state until its request settles
    if ((this._pendingPause || 0) > 0) return;
    this.paused = paused;
  },

  async pauseAgent(paused) {
    const prev = this.paused;
    this.paused = paused;
    this._pendingPause = (this._pendingPause || 0) + 1;
    try {
      const context = globalThis.getContext?.();
      if (!globalThis.sendJsonData)
        throw new Error("sendJsonData not available");
      await globalThis.sendJsonData("/pause", { paused, context });
    } catch (e) {
      if ((this._pendingPause || 0) <= 1) this.paused = prev;
      if (globalThis.toastFetchError) {
        globalThis.toastFetchError("Error pausing agent", e);
      }
    } finally {
      this._pendingPause = Math.max(0, (this._pendingPause || 0) - 1);
    }
  },

  async stopAgent() {
    try {
      const context = globalThis.getContext?.();
      if (!context || !globalThis.sendJsonData) return;
      await globalThis.sendJsonData("/stop", { context });
    } catch (e) {
      if (globalThis.toastFetchError) {
        globalThis.toastFetchError("Error stopping agent", e);
      }
    }
  },

  async nudge() {
    try {
      const context = globalThis.getContext();
      await globalThis.sendJsonData("/nudge", { ctxid: context });
    } catch (e) {
      if (globalThis.toastFetchError) {
        globalThis.toastFetchError("Error nudging agent", e);
      }
    }
  },

  async loadKnowledge() {
    try {
      const resp = await shortcuts.callJsonApi(
        "/plugins/_memory/knowledge_path_get",
        { ctxid: shortcuts.getCurrentContextId() }
      );
      if (!resp.ok) throw new Error("Error getting knowledge path");
      const path = resp.path;

      // open file browser and wait for it to close
      await fileBrowserStore.open(path);

      // progress notification
      shortcuts.frontendNotification({
        type: shortcuts.NotificationType.PROGRESS,
        message: "Loading knowledge...",
        priority: shortcuts.NotificationPriority.NORMAL,
        displayTime: 999,
        group: "knowledge_load",
        frontendOnly: true,
      });

      // then reindex knowledge
      await globalThis.sendJsonData("/plugins/_memory/knowledge_reindex", {
        ctxid: shortcuts.getCurrentContextId(),
      });

      // finished notification
      shortcuts.frontendNotification({
        type: shortcuts.NotificationType.SUCCESS,
        message: "Knowledge loaded successfully",
        priority: shortcuts.NotificationPriority.NORMAL,
        displayTime: 2,
        group: "knowledge_load",
        frontendOnly: true,
      });
    } catch (e) {
      // error notification
      shortcuts.frontendNotification({
        type: shortcuts.NotificationType.ERROR,
        message: "Error loading knowledge",
        priority: shortcuts.NotificationPriority.NORMAL,
        displayTime: 5,
        group: "knowledge_load",
        frontendOnly: true,
      });
    }
  },

  // previous implementation without projects
  async _loadKnowledge() {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".txt,.pdf,.csv,.html,.json,.md";
    input.multiple = true;

    input.onchange = async () => {
      try {
        const formData = new FormData();
        for (let file of input.files) {
          formData.append("files[]", file);
        }

        formData.append("ctxid", globalThis.getContext());

        const response = await globalThis.fetchApi("/import_knowledge", {
          method: "POST",
          body: formData,
        });

        if (!response.ok) {
          if (globalThis.toast)
            globalThis.toast(await response.text(), "error");
        } else {
          const data = await response.json();
          if (globalThis.toast) {
            globalThis.toast(
              "Knowledge files imported: " + data.filenames.join(", "),
              "success"
            );
          }
        }
      } catch (e) {
        if (globalThis.toastFetchError) {
          globalThis.toastFetchError("Error loading knowledge", e);
        }
      }
    };

    input.click();
  },

  async browseFiles(path) {
    if (!path) {
      const ctxid = shortcuts.getCurrentContextId();

      if (ctxid) {
        try {
          const resp = await shortcuts.callJsonApi("/chat_files_path_get", {
            ctxid,
          });
          if (resp.ok) path = resp.path;
        } catch (_e) {
          console.error("Error getting chat files path", _e);
        }
      }
    }
    let opened = false;
    try {
      opened = await openLatestSurface("files", { path, source: "sidebar" });
    } catch (error) {
      console.error("Error opening Files surface", error);
    }
    if (!opened) await fileBrowserStore.open(path);
  },

  focus() {
    const chatInput = this._activeTextarea();
    if (chatInput) {
      chatInput.focus();
    }
  },

  setDraftContext(ctxid) {
    const nextCtxid = String(ctxid || "");
    if (nextCtxid === this._draftCtxid) return;
    if (this._draftCtxid !== null) this._syncMessageFromEditor();

    this._draftCtxid = nextCtxid;
    this._historyIndex = null;
    this._draft = "";

    let draft = "";
    if (nextCtxid) {
      try { draft = sessionStorage.getItem(DRAFT_STORAGE_PREFIX + nextCtxid) || ""; } catch (_e) { /* ignore */ }
    }
    this._message = draft;
    this._renderEditorFromText(draft);
    queueMicrotask(() => this.adjustTextareaHeight());
  },

  _saveDraft() {
    if (!this._draftCtxid) return;
    try {
      const key = DRAFT_STORAGE_PREFIX + this._draftCtxid;
      if (this._message) sessionStorage.setItem(key, this._message);
      else sessionStorage.removeItem(key);
    } catch (_e) { /* ignore unavailable storage */ }
  },

  _loadHistory() {
    let ctxid = null;
    try { ctxid = shortcuts.getCurrentContextId(); } catch (_e) { ctxid = null; }
    this._historyCtxid = ctxid;
    this._history = [];
    this._historyIndex = null;
    this._draft = "";
    if (!ctxid) return;
    let raw = null;
    try { raw = localStorage.getItem("a0:chat-history:" + ctxid); } catch (_e) { raw = null; }
    if (raw !== null) {
      try {
        const arr = JSON.parse(raw);
        if (Array.isArray(arr)) {
          this._history = arr.filter((s) => typeof s === "string");
        }
      } catch (_e) { /* ignore */ }
      return;
    }
    // No entry yet for this chat: seed from rendered chat DOM (one-time bootstrap)
    try {
      const seeded = this._seedFromChatDom();
      if (seeded.length > 0) {
        this._history = seeded;
        this._saveHistory();
      } else {
        // Persist an empty array so we don't re-seed on every nav; respects user clearing
        this._saveHistory();
      }
    } catch (_e) { /* ignore */ }
  },

  _seedFromChatDom() {
    const out = [];
    let nodes;
    try {
      nodes = document.querySelectorAll(".user-container .message-user .message-text pre");
    } catch (_e) {
      return out;
    }
    for (const pre of nodes) {
      const text = (pre.textContent || "").trim();
      if (!text) continue;
      if (out.length > 0 && out[out.length - 1] === text) continue; // ignoredups
      out.push(text);
    }
    if (out.length > 50) return out.slice(-50);
    return out;
  },

  _saveHistory() {
    if (!this._historyCtxid) return;
    try {
      localStorage.setItem(
        "a0:chat-history:" + this._historyCtxid,
        JSON.stringify(this._history)
      );
    } catch (_e) { /* ignore quota / disabled */ }
  },

  _ensureHistoryLoaded() {
    let ctxid = null;
    try { ctxid = shortcuts.getCurrentContextId(); } catch (_e) { ctxid = null; }
    if (ctxid !== this._historyCtxid) {
      this._loadHistory();
    }
  },

  _pushHistory(text) {
    if (typeof text !== "string") return;
    const trimmed = text.trim();
    if (!trimmed) return;
    this._ensureHistoryLoaded();
    if (this._history.length > 0 && this._history[this._history.length - 1] === trimmed) {
      this._historyIndex = null;
      this._draft = "";
      return;
    }
    this._history.push(trimmed);
    if (this._history.length > 50) {
      this._history = this._history.slice(-50);
    }
    this._saveHistory();
    this._historyIndex = null;
    this._draft = "";
  },

  _setCaretStart() {
    queueMicrotask(() => {
      const editor = this._activeTextarea();
      if (editor) {
        this._setEditorCaret(0);
        try { editor.scrollTop = 0; } catch (_e) { /* ignore */ }
      }
      this.adjustTextareaHeight();
    });
  },

  _setCaretEnd() {
    queueMicrotask(() => {
      const editor = this._activeTextarea();
      if (editor) {
        this._setEditorCaret(editor.innerText.length);
        try { editor.scrollTop = editor.scrollHeight; } catch (_e) { /* ignore */ }
      }
      this.adjustTextareaHeight();
    });
  },

  historyPrev($event) {
    if ($event && ($event.isComposing || $event.keyCode === 229)) return;
    if (this._isInCodeBlock($event?.target)) return;
    const editor = this._activeTextarea();
    if (!editor) return;
    const { start, end } = this._selectionOffsets(editor);
    if (start !== 0 || end !== 0) return;
    $event.preventDefault();
    this._ensureHistoryLoaded();
    if (this._history.length === 0) return;
    if (this._historyIndex === null) {
      this._draft = this.message || "";
      this._historyIndex = this._history.length - 1;
    } else if (this._historyIndex > 0) {
      this._historyIndex -= 1;
    } else {
      return;
    }
    this.message = this._history[this._historyIndex];
    this._setCaretStart();
  },

  historyNext($event) {
    if ($event && ($event.isComposing || $event.keyCode === 229)) return;
    if (this._isInCodeBlock($event?.target)) return;
    const editor = this._activeTextarea();
    if (!editor) return;
    const { start, end } = this._selectionOffsets(editor);
    const valueLength = editor.innerText.length;
    if (start !== valueLength || end !== valueLength) return;
    $event.preventDefault();
    if (this._historyIndex === null) return;
    if (this._historyIndex < this._history.length - 1) {
      this._historyIndex += 1;
      this.message = this._history[this._historyIndex];
    } else {
      this._historyIndex = null;
      this.message = this._draft || "";
      this._draft = "";
    }
    this._setCaretEnd();
  },

  reset() {
    this.message = "";
    attachmentsStore.clearAttachments();
    this.chatMoreMenuOpen = false;
    this._historyIndex = null;
    this._draft = "";
    this.adjustTextareaHeight();
  }
};

const store = createStore("chatInput", model);

export { store };
