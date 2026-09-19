import * as msgs from "/js/messages.js";
import * as api from "/js/api.js";
import { callJsExtensions } from "/js/extensions.js";
import * as css from "/js/css.js";
import { sleep } from "/js/sleep.js";
import { ttsService } from "/js/tts-service.js";
import { store as attachmentsStore } from "/components/chat/attachments/attachmentsStore.js";
import { store as notificationStore } from "/components/notifications/notification-store.js";
import { store as preferencesStore } from "/components/sidebar/bottom/preferences/preferences-store.js";
import { store as inputStore } from "/components/chat/input/input-store.js";
import { store as chatsStore } from "/components/sidebar/chats/chats-store.js";
import { getStore } from "/js/AlpineStore.js";
import { store as chatTopStore } from "/components/chat/top-section/chat-top-store.js";
import { store as _tooltipsStore } from "/components/tooltips/tooltip-store.js";
import { store as messageQueueStore } from "/components/chat/message-queue/message-queue-store.js";
import { store as syncStore } from "/components/sync/sync-store.js"
import { store as welcomeStore } from "/components/welcome/welcome-store.js";
import { store as modelGateStore } from "/components/chat/model-gate-store.js";
import { getUserHour12, getUserTimezone } from "/js/time-utils.js";
import { createThreeBubbleLoader } from "/js/loading-indicators.js";

globalThis.fetchApi = api.fetchApi; // TODO - backward compatibility for non-modular scripts, remove once refactored to alpine

// Declare variables for DOM elements, they will be assigned on DOMContentLoaded
let leftPanel,
  rightPanel,
  container,
  chatInput,
  sendButton,
  inputSection,
  statusSection,
  progressBar,
  autoScrollSwitch,
  timeDate;

let autoScroll = true;
let context = null;
let loadingContext = null;
let chatLoadingSplashVisible = false;
let chatLoadingSplashTimer = null;
globalThis.resetCounter = 0; // Used by stores and getChatBasedId
let skipOneSpeech = false;
const CHAT_LOADING_SPLASH_DELAY_MS = 300;

function syncChatLoadingSplash() {
  const splash = document.getElementById("chat-loading-splash");
  if (!splash) return;
  if (!splash.querySelector(":scope > .three-bubble-loader")) {
    splash.prepend(createThreeBubbleLoader({ active: true }));
  }
  splash.hidden = !chatLoadingSplashVisible;
}

function beginChatLoading(id) {
  if (chatLoadingSplashTimer) {
    clearTimeout(chatLoadingSplashTimer);
    chatLoadingSplashTimer = null;
  }
  loadingContext = id || null;
  chatLoadingSplashVisible = false;
  syncChatLoadingSplash();

  if (loadingContext !== null) {
    const expectedContext = loadingContext;
    chatLoadingSplashTimer = setTimeout(() => {
      chatLoadingSplashTimer = null;
      if (loadingContext !== expectedContext) return;
      chatLoadingSplashVisible = true;
      syncChatLoadingSplash();
    }, CHAT_LOADING_SPLASH_DELAY_MS);
  }
}

function finishChatLoading(id) {
  if (loadingContext === null || id !== loadingContext) return;
  if (chatLoadingSplashTimer) {
    clearTimeout(chatLoadingSplashTimer);
    chatLoadingSplashTimer = null;
  }
  loadingContext = null;
  chatLoadingSplashVisible = false;
  syncChatLoadingSplash();
}

// Sidebar toggle logic is now handled by sidebar-store.js

export async function sendMessage(options = {}) {
  try {
    const hasProvidedMessage = Object.prototype.hasOwnProperty.call(options, "message");
    let message = String(hasProvidedMessage ? options.message : inputStore.message).trim();
    let attachmentsWithUrls = options.attachments || attachmentsStore.getAttachmentsForSending();
    let hasAttachments = attachmentsWithUrls.length > 0;

    const sendCtx = { message, attachments: attachmentsWithUrls, context: options.context || context, cancel: false };
    if (!options.skipExtensions) await callJsExtensions("send_message_before", sendCtx);
    if (sendCtx.cancel) return;
    message = sendCtx.message;
    attachmentsWithUrls = sendCtx.attachments;
    hasAttachments = attachmentsWithUrls.length > 0;
    const sendContext = options.context || context;
    const messageId = options.messageId || generateGUID();
    const shouldResetInput = !hasProvidedMessage && !options.preserveInput;

    // If empty input but has queued messages, send all queued
    if (!message && !hasAttachments && messageQueueStore.hasQueue) {
      await messageQueueStore.sendAll();
      return;
    }

    if (message || hasAttachments) {
      if (!options.bypassModelGate && !(await modelGateStore.canSendToModel())) {
        modelGateStore.start({
          message,
          attachments: attachmentsWithUrls,
          messageId,
          context: sendContext,
        });

        if (shouldResetInput) {
          inputStore.reset();
          adjustTextareaHeight();
        }

        await setMessages(modelGateStore.syntheticMessages(sendContext));
        forceScrollChatToBottom();
        return;
      }

      // Check if agent is busy - queue instead of sending
      if (chatsStore.selectedContext?.running || messageQueueStore.hasQueue) {
        const success = messageQueueStore.addToQueue(message, attachmentsWithUrls);
        // no await for the queue
        // if (success) {
          if (shouldResetInput) inputStore.reset();
          adjustTextareaHeight();
        // }
        return;
      }

      // Sending a message is an explicit user intent to go to the bottom
      msgs.scrollOnNextProcessGroup();
      forceScrollChatToBottom();

      let response;

      // Clear input and attachments
      if (shouldResetInput) {
        inputStore.reset();
        adjustTextareaHeight();
      }

      // Render immediately; the backend log reuses messageId and merges into this row.
      const heading = hasAttachments ? "Uploading attachments..." : "";
      await setMessages([{ id: messageId, type: "user", heading, content: message, kvps: {} }]);

      // Include attachments in the user message
      if (hasAttachments) {
        // sleep one frame to render the message before upload starts - better UX
        sleep(0);

        const formData = new FormData();
        formData.append("text", message);
        formData.append("context", sendContext);
        formData.append("message_id", messageId);

        for (let i = 0; i < attachmentsWithUrls.length; i++) {
          formData.append("attachments", attachmentsWithUrls[i].file);
        }

        response = await api.fetchApi("/message_async", {
          method: "POST",
          body: formData,
        });
      } else {
        // For text-only messages
        const data = {
          text: message,
          context: sendContext,
          message_id: messageId,
        };
        response = await api.fetchApi("/message_async", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(data),
        });
      }

      // Handle response
      const jsonResponse = await response.json();
      if (!jsonResponse) {
        toast("No response returned.", "error");
      } else {
        setContext(jsonResponse.context);
      }
    }
  } catch (e) {
    toastFetchError("Error sending message", e); // Will use new notification system
  }
}
globalThis.sendMessage = sendMessage;

function forceScrollChatToBottom() {
  return msgs.scrollMessageWindowToEdge("end");
}
globalThis.forceScrollChatToBottom = forceScrollChatToBottom;

export function toastFetchError(text, error) {
  console.error(text, error);
  // Use new frontend error notification system (async, but we don't need to wait)
  const errorMessage = error?.message || error?.toString() || "Unknown error";

  if (getConnectionStatus()) {
    // Backend is connected, just show the error
    toastFrontendError(`${text}: ${errorMessage}`).catch((e) =>
      console.error("Failed to show error toast:", e)
    );
  } else {
    // Backend is disconnected, show connection error
    toastFrontendError(
      `${text} (backend appears to be disconnected): ${errorMessage}`,
      "Connection Error"
    ).catch((e) => console.error("Failed to show connection error toast:", e));
  }
}
globalThis.toastFetchError = toastFetchError;

// Event listeners will be set up in DOMContentLoaded

export function updateChatInput(text) {
  if (!inputStore) {
    console.warn("`chatInput` store not found, cannot update.");
    return;
  }
  console.log("updateChatInput called with:", text);

  // Append text with proper spacing in Alpine store first.
  const currentValue = inputStore.message || "";
  const needsSpace = currentValue.length > 0 && !currentValue.endsWith(" ");
  inputStore.message = currentValue + (needsSpace ? " " : "") + text + " ";

  // Adjust height after Alpine applies store value.
  setTimeout(() => {
    adjustTextareaHeight();
  }, 0);

  console.log("Updated chat input value:", inputStore.message);
}

async function updateUserTime() {
  let userTimeElement = document.getElementById("time-date");

  while (!userTimeElement) {
    await sleep(100);
    userTimeElement = document.getElementById("time-date");
  }

  const now = new Date();
  const timezone = getUserTimezone();
  const hour12 = getUserHour12();
  const timeString = new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
    hour12,
    timeZone: timezone,
  }).format(now).toLowerCase();
  const dateString = new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: timezone,
  }).format(now);

  // Update the HTML
  userTimeElement.innerHTML = `${timeString}<br><span id="user-date">${dateString}</span>`;
}

updateUserTime();
setInterval(updateUserTime, 1000);

async function setMessages(...params) {
  return await msgs.setMessages(...params);
}

globalThis.loadKnowledge = async function () {
  await inputStore.loadKnowledge();
};

function adjustTextareaHeight() {
  inputStore.adjustTextareaHeight();
}

export const sendJsonData = async function (url, data) {
  return await api.callJsonApi(url, data);
  // const response = await api.fetchApi(url, {
  //     method: 'POST',
  //     headers: {
  //         'Content-Type': 'application/json'
  //     },
  //     body: JSON.stringify(data)
  // });

  // if (!response.ok) {
  //     const error = await response.text();
  //     throw new Error(error);
  // }
  // const jsonResponse = await response.json();
  // return jsonResponse;
};
globalThis.sendJsonData = sendJsonData;

function generateGUID() {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
    var r = (Math.random() * 16) | 0;
    var v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export function getConnectionStatus() {
  return chatTopStore.connected;
}
globalThis.getConnectionStatus = getConnectionStatus;

function setConnectionStatus(connected) {
  chatTopStore.connected = connected;
  // connectionStatus = connected;
  // // Broadcast connection status without touching Alpine directly
  // try {
  //   window.dispatchEvent(
  //     new CustomEvent("connection-status", { detail: { connected } })
  //   );
  // } catch (_e) {
  //   // no-op
  // }
}

let lastLogVersion = 0;
let lastLogGuid = "";
let lastSpokenNo = 0;

export function buildStateRequestPayload(options = {}) {
  const { forceFull = false } = options || {};
  const timezone = getUserTimezone();
  return {
    context: context || null,
    log_from: forceFull ? 0 : lastLogVersion,
    notifications_from: forceFull ? 0 : notificationStore.lastNotificationVersion || 0,
    timezone,
    collections_delta: true,
  };
}

export async function applySnapshot(snapshot, options = {}) {
  const { touchConnectionStatus = false, onLogGuidReset = null } = options || {};

  let updated = false;

  // Check if the snapshot is valid
  if (!snapshot || typeof snapshot !== "object") {
    console.error("Invalid snapshot payload");
    return { updated: false };
  }

  // deselect chat if it is requested by the backend
  if (snapshot.deselect_chat) {
    chatsStore.deselectChat();
    return { updated: false };
  }

  if (
    snapshot.context != context &&
    context !== null
  ) {
    return { updated: false };
  }

  const hasCollections =
    Array.isArray(snapshot.contexts) && Array.isArray(snapshot.tasks);
  const extensionSnapshot = hasCollections
    ? snapshot
    : {
        ...snapshot,
        contexts: chatsStore.contexts,
        tasks: getStore("tasks")?.tasks ?? [],
      };
  const snapCtx = {
    snapshot: extensionSnapshot,
    willUpdateMessages: lastLogVersion != snapshot.log_version,
    skip: false,
  };
  const applyingContext = context;
  await callJsExtensions("apply_snapshot_before", snapCtx);
  if (snapCtx.skip || context !== applyingContext) return { updated: false };

  // If the chat has been reset, reset cursors and request a resync from the caller.
  // Note: on first snapshot after a context switch, lastLogGuid is intentionally empty,
  // so the mismatch is expected and should not trigger a second state_request/poll.
  if (lastLogGuid != snapshot.log_guid) {
    if (lastLogGuid) {
      msgs.resetMessageRenderState();
      lastLogVersion = 0;
      lastLogGuid = snapshot.log_guid;
      if (typeof onLogGuidReset === "function") {
        await onLogGuidReset();
      }
      return { updated: false, resynced: true };
    }
    // First guid observed for this context: accept it and continue applying snapshot.
    lastLogVersion = 0;
    lastLogGuid = snapshot.log_guid;
  }

  if (lastLogVersion != snapshot.log_version) {
    updated = true;
    if (snapshot.logs?.[0]?.no === 0) {
      msgs.resetMessageRenderState();
    }
    await setMessages(modelGateStore.mergeSyntheticMessages(snapshot.logs, context));
    if (context !== applyingContext) return { updated: false };
    afterMessagesUpdate(snapshot.logs);
  }

  lastLogVersion = snapshot.log_version;
  lastLogGuid = snapshot.log_guid;

  updateProgress(snapshot.log_progress, snapshot.log_progress_active);

  // Update notifications from snapshot
  notificationStore.updateFromPoll(snapshot);

  // set ui model vars from backend
  inputStore.paused = snapshot.paused;

  // Optional: treat snapshot application as proof of connectivity (poll path)
  if (touchConnectionStatus) {
    setConnectionStatus(true);
  }

  if (hasCollections) {
    // Update chats list using store
    chatsStore.applyContexts(snapshot.contexts);

    // Update tasks list using store
    getStore("tasks")?.applyTasks?.(snapshot.tasks);

    // Make sure the active context is properly selected in both lists
    // Leave an empty selection unchanged so the welcome screen stays visible.
    if (context) {
      // Update selection in both stores
      chatsStore.setSelected(context);

      const contextInChats = chatsStore.contains(context);
      const contextInTasks = getStore("tasks")?.contains?.(context);

      if (contextInTasks) {
        getStore("tasks")?.setSelected?.(context);
      }

      if (!contextInChats && !contextInTasks) {
        if (chatsStore.contexts.length > 0) {
          // If it doesn't exist in the list but other contexts do, fall back to the first
          const firstChatId = chatsStore.firstId();
          if (firstChatId) {
            setContext(firstChatId);
            chatsStore.setSelected(firstChatId);
          }
        } else if (typeof deselectChat === "function") {
          // No contexts remain – clear state so the welcome screen can surface
          deselectChat();
        }
      }
    }
  }

  // update message queue
  messageQueueStore.updateFromPoll();

  // A context switch is visually complete only after its matching snapshot
  // has rendered and the surrounding chat state has been synchronized.
  finishChatLoading(snapshot.context);

  return { updated };
}

export async function poll() {
  try {
    const timezone = getUserTimezone();

    const log_from = lastLogVersion;
    const response = await sendJsonData("/poll", {
      log_from: log_from,
      notifications_from: notificationStore.lastNotificationVersion || 0,
      context: context || null,
      timezone: timezone,
    });

    const result = await applySnapshot(response, {
      touchConnectionStatus: true,
      onLogGuidReset: poll,
    });
    return { ok: true, updated: Boolean(result && result.updated) };
  } catch (error) {
    console.error("Error:", error);
    setConnectionStatus(false);
    return { ok: false, updated: false };
  }
}
globalThis.poll = poll;

function afterMessagesUpdate(logs) {
  if (preferencesStore.speech) speakMessages(logs);
}

function speakMessages(logs) {
  if (skipOneSpeech) {
    skipOneSpeech = false;
    return;
  }
  // log.no, log.type, log.heading, log.content
  for (let i = logs.length - 1; i >= 0; i--) {
    const log = logs[i];

    // if already spoken, end
    // if(log.no < lastSpokenNo) break;

    // finished response
    if (log.type == "response") {
      // lastSpokenNo = log.no;
      ttsService.speakStream(
        getChatBasedId(log.no),
        log.content,
        log.kvps?.finished
      );
      return;

      // finished LLM headline, not response
    } else if (
      log.type == "agent" &&
      log.kvps &&
      log.kvps.headline &&
      log.kvps.tool_args &&
      log.kvps.tool_name != "response"
    ) {
      // lastSpokenNo = log.no;
      ttsService.speakStream(getChatBasedId(log.no), log.kvps.headline, true);
      return;
    }
  }
}

function updateProgress(progress, active) {
  if (!progress) progress = "";

  // Strip HTML tags for plain-text placeholder use
  const plainText = progress.replace(/<[^>]*>/g, "").trim();

  // Update the input store so the placeholder reflects progress
  inputStore.progressText = plainText;
  inputStore.progressActive = !!active;

  // Apply shimmer class to the textarea when active
  const chatInputEl = document.getElementById("chat-input");
  if (chatInputEl) {
    if (active && plainText) {
      addClassToElement(chatInputEl, "progress-active");
    } else {
      removeClassFromElement(chatInputEl, "progress-active");
    }
  }

  // Also update legacy progress bar element if it still exists
  const progressBarEl = document.getElementById("progress-bar");
  if (progressBarEl) {
    setProgressBarShine(progressBarEl, active);
    const html = msgs.convertIcons(progress);
    if (progressBarEl.innerHTML != html) {
      progressBarEl.innerHTML = html;
    }
  }
}

function setProgressBarShine(progressBarEl, active) {
  if (!progressBarEl) return;
  if (!active) {
    removeClassFromElement(progressBarEl, "shiny-text");
  } else {
    addClassToElement(progressBarEl, "shiny-text");
  }
}

globalThis.pauseAgent = async function (paused) {
  await inputStore.pauseAgent(paused);
};

function generateShortId() {
  const chars =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  let result = "";
  for (let i = 0; i < 8; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return result;
}

export const newContext = function () {
  context = generateShortId();
  setContext(context);
};
globalThis.newContext = newContext;

export const setContext = function (id) {
  if (id == context) return;
  inputStore.setDraftContext(id);
  context = id;
  if (id) beginChatLoading(id);
  else beginChatLoading(null);
  // Always reset the log tracking variables when switching contexts
  // This ensures we get fresh data from the backend
  lastLogGuid = "";
  lastLogVersion = 0;
  lastSpokenNo = 0;

  // Stop speech when switching chats
  ttsService.stop();

  // Clear the chat history immediately to avoid showing stale content
  msgs.resetMessageRenderState();

  // Update both selected states using stores
  chatsStore.setSelected(id);
  getStore("tasks")?.setSelected?.(id);

  // Trigger a new WS handshake for the newly selected context (push-based sync).
  // This keeps the UI current without needing /poll during healthy operation.
  try {
    if (typeof syncStore.sendStateRequest === "function") {
      syncStore.sendStateRequest({ forceFull: true }).catch((error) => {
        console.error("[index] syncStore.sendStateRequest failed:", error);
      });
    }
  } catch (_error) {
    // no-op: sync store may not be initialized yet
  }

  //skip one speech if enabled when switching context
  if (preferencesStore.speech) skipOneSpeech = true;

  // Focus the chat input
  if (id) {
    setTimeout(() => {
      inputStore.focus();
    }, 50);
  }
};

export const deselectChat = function () {
  // Clear current context to show welcome screen
  setContext(null);

  // Clear selections so we don't auto-restore
  sessionStorage.removeItem("lastSelectedChat");
  sessionStorage.removeItem("lastSelectedTask");

  // Clear the chat history
  msgs.resetMessageRenderState();
};
globalThis.deselectChat = deselectChat;

export const getContext = function () {
  return context;
};
globalThis.getContext = getContext;
globalThis.setContext = setContext;

export const getChatBasedId = function (id) {
  return context + "-" + globalThis.resetCounter + "-" + id;
};

function addClassToElement(element, className) {
  element.classList.add(className);
}

function removeClassFromElement(element, className) {
  element.classList.remove(className);
}

export function justToast(text, type = "info", timeout = 5000, group = "") {
  notificationStore.addFrontendToastOnly(type, text, "", timeout / 1000, group);
}
globalThis.justToast = justToast;

export function toast(text, type = "info", timeout = 5000) {
  // Convert timeout from milliseconds to seconds for new notification system
  const display_time = Math.max(timeout / 1000, 1); // Minimum 1 second

  // Use new frontend notification system based on type
  switch (type.toLowerCase()) {
    case "error":
      return notificationStore.frontendError(text, "Error", display_time);
    case "success":
      return notificationStore.frontendInfo(text, "Success", display_time);
    case "warning":
      return notificationStore.frontendWarning(text, "Warning", display_time);
    case "info":
    default:
      return notificationStore.frontendInfo(text, "Info", display_time);
  }
}
globalThis.toast = toast;


import { store as _chatNavigationStore } from "/components/chat/navigation/chat-navigation-store.js";


// Navigation logic in chat-navigation-store.js
// forceScrollChatToBottom is kept here as it is used by system events


// setInterval(poll, 250);

async function startPolling() {
  // Fallback polling cadence:
  // - DISCONNECTED: do not poll (transport down, avoid request spam)
  // - HANDSHAKE_PENDING/DEGRADED: steady fallback cadence to keep UI responsive
  const degradedIntervalMs = 250;
  let missingSyncSinceMs = null;
  let consecutivePollFailures = 0;
  let lastHandshakeKickMs = 0;
  const startedAtMs = Date.now();
  const initialNoPollGraceMs = 2000;
  let pollInFlight = false;

  async function _doPoll() {
    const tickStartedAt = Date.now();
    let nextInterval = degradedIntervalMs;

    try {
      const syncMode = typeof syncStore.mode === "string" ? syncStore.mode : null;
      // Polling is a fallback. In V1:
      // - DEGRADED: poll at fallback cadence to keep the UI usable while WS sync is unavailable.
      // - DISCONNECTED: do not poll; rely on Socket.IO reconnect and avoid console/network spam.
      // Safety net: if the sync store never loads, start polling after a short grace period.
      if (!syncStore || !syncMode) {
        if (missingSyncSinceMs == null) {
          missingSyncSinceMs = Date.now();
        }
      } else {
        missingSyncSinceMs = null;
      }

      const shouldPoll =
        syncMode === "DEGRADED" ||
        (missingSyncSinceMs != null && Date.now() - missingSyncSinceMs > 2000);
      if (!shouldPoll) {
        setTimeout(_doPoll.bind(this), nextInterval);
        return;
      }

      if (pollInFlight) {
        setTimeout(_doPoll.bind(this), nextInterval);
        return;
      }

      // Avoid a “single poll on boot” while the websocket handshake is racing to take over.
      if (Date.now() - startedAtMs < initialNoPollGraceMs && (!syncStore || !syncMode)) {
        setTimeout(_doPoll.bind(this), nextInterval);
        return;
      }

      // Call through `globalThis.poll` so test harnesses (and future instrumentation)
      // can wrap/spy on polling behaviour. Fall back to the module-local function
      // if the global is unavailable.
      const pollFn = typeof globalThis.poll === "function" ? globalThis.poll : poll;
      pollInFlight = true;
      let result;
      try {
        result = await pollFn();
      } finally {
        pollInFlight = false;
      }
      const pollOk = Boolean(result && result.ok);

      if (!pollOk) {
        consecutivePollFailures += 1;
      } else {
        consecutivePollFailures = 0;
      }

      // If we are degraded but polling repeatedly fails, upgrade to DISCONNECTED.
      if (
        syncStore &&
        syncMode === "DEGRADED" &&
        !pollOk &&
        consecutivePollFailures >= 3
      ) {
        syncStore.mode = "DISCONNECTED";
      }

      // If we're polling and the backend responds, try to re-establish push sync immediately.
      if (syncStore && pollOk) {
        const now = Date.now();
        const modeNow = typeof syncStore.mode === "string" ? syncStore.mode : null;
        const kickCooldownMs = modeNow === "DISCONNECTED" ? 0 : 3000;
        const eligible =
          (modeNow === "DISCONNECTED" || modeNow === "DEGRADED") &&
          typeof syncStore.sendStateRequest === "function" &&
          now - lastHandshakeKickMs >= kickCooldownMs;
        if (eligible) {
          lastHandshakeKickMs = now;
          syncStore.sendStateRequest({ forceFull: true }).catch(() => {});
        }
      }

      const effectiveMode =
        syncStore && typeof syncStore.mode === "string" ? syncStore.mode : syncMode;
      nextInterval =
        effectiveMode === "DEGRADED" || effectiveMode === "HANDSHAKE_PENDING"
          ? degradedIntervalMs
          : degradedIntervalMs;
    } catch (error) {
      console.error("Error:", error);
    }

    // Call the function again after the selected interval
    const elapsedMs = Date.now() - tickStartedAt;
    const delayMs = Math.max(0, nextInterval - elapsedMs);
    setTimeout(_doPoll.bind(this), delayMs);
  }

  _doPoll();
}

// All initializations and event listeners are now consolidated here
document.addEventListener("DOMContentLoaded", function () {
  // Assign DOM elements to variables now that the DOM is ready
  leftPanel = document.getElementById("left-panel");
  rightPanel = document.getElementById("right-panel");
  container = document.querySelector(".container");
  chatInput = document.getElementById("chat-input");
  sendButton = document.getElementById("send-button");
  inputSection = document.getElementById("input-section");
  statusSection = document.getElementById("status-section");
  progressBar = document.getElementById("progress-bar");
  autoScrollSwitch = document.getElementById("auto-scroll-switch");
  timeDate = document.getElementById("time-date-container");
  syncChatLoadingSplash();


  // Start polling for updates
  startPolling();
});

/*
 * A0 Chat UI
 *
 * Unified sidebar layout:
 * - Both Chats and Tasks lists are always visible in a vertical layout
 * - Both lists are sorted by creation time (newest first)
 * - Tasks use the same context system as chats for communication with the backend
 */
