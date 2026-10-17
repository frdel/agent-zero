// message actions and components
import { store as imageViewerStore } from "../components/modals/image-viewer/image-viewer-store.js";
import { marked } from "../vendor/marked/marked.esm.js";
import { store as _messageResizeStore } from "/components/messages/resize/message-resize-store.js"; // keep here, required in html
import { store as attachmentsStore } from "/components/chat/attachments/attachmentsStore.js";
import { ttsService } from "/js/tts-service.js";
import {
  createActionButton,
  copyToClipboard,
  syncActionButtons,
} from "/components/messages/action-buttons/simple-action-buttons.js";
import { store as stepDetailStore } from "/components/modals/process-step-detail/step-detail-store.js";
import { store as preferencesStore } from "/components/sidebar/bottom/preferences/preferences-store.js";
import {
  formatDateTime,
  formatDuration,
  getUserHour12,
  getUserTimezone,
} from "./time-utils.js";
import { Scroller, cancelPendingScroll } from "./scroller.js";
import {
  MessageWindow,
  PROCESS_STEP_TYPES,
  classifyMessageRenderUnits,
  getMessageCacheKey,
} from "./message-window.js";
import { callJsExtensions } from "/js/extensions.js";
import { addBlankTargetsToLinks } from "/js/html-links.js";
import { sanitizeHtml } from "/js/safe-markdown.js";
import { createThreeBubbleLoader } from "/js/loading-indicators.js";
import { measureMessageCollapseOverflow } from "./message-collapse.js";

// Delay before collapsing previous steps when a new step is added
const STEP_COLLAPSE_DELAY = {
  agent: 2000,
  other: 4000, // tools should stay longer as next gen step is placed quickly
};
// delay collapse when hovering
const STEP_COLLAPSE_HOVER_DELAY_MS = 5000;
const PROCESS_GROUP_STEP_PAGE_SIZE = 50;
const PROCESS_GROUP_RENDER_INFO = Symbol("processGroupRenderInfo");

let _messageProcessGroups = new WeakMap();
let _messageIsProcessStep = new WeakSet();
let _processStepTypes = PROCESS_STEP_TYPES;
const _processGroupStepLimits = new Map();
let _renderedProcessGroupPages = new Map();

function getMessageRenderUnitKeys(messages) {
  _messageProcessGroups = new WeakMap();
  _messageIsProcessStep = new WeakSet();
  const units = classifyMessageRenderUnits(messages, _processStepTypes);
  units.forEach((unit, index) => {
    if (!unit.group) return;
    _messageProcessGroups.set(messages[index], unit.group);
    if (unit.isStep) _messageIsProcessStep.add(messages[index]);
  });
  return units.map((unit) => unit.key);
}

// dom references
let _chatHistory = null;

// state vars
let _massRender = false;
let _windowedRender = false;
let _scrollOnNextProcessGroup = null;
const _messageWindow = new MessageWindow({
  getUnitKeys: getMessageRenderUnitKeys,
});
let _messageWindowRenderPromise = null;
let _messageRenderQueue = Promise.resolve();
let _messageRenderGeneration = 0;
let _messageWindowHistory = null;
let _messageWindowScrollFrame = null;
let _lastMessageWindowScrollTop = 0;
let _messageWindowFollowTail = true;
let _messageWindowLoadingDirection = null;
let _messageWindowSuppressScrollEvents = false;
let _messageWindowPointerActive = false;
let _messageWindowUserScrollUntil = 0;
let _messageWindowResizeObserver = null;

// Leave a small tolerance for fractional scroll positions and the passive
// boundary indicator, but do not swap pages while the user is still reading.
const MESSAGE_WINDOW_BOUNDARY_TOLERANCE_PX = 48;
const MESSAGE_WINDOW_TAIL_TOLERANCE_PX = 80;
const MESSAGE_WINDOW_USER_SCROLL_GRACE_MS = 1200;
const LAZY_MESSAGE_PREVIEW_CHARS = 6000;
const DEFERRED_REPLAY_ENTRY_THRESHOLD = 30;
const DEFERRED_REPLAY_TEXT_THRESHOLD = 50000;

/**
 * @typedef {object} MessageHandlerArgs
 * @property {number} [no]
 * @property {string | number} id
 * @property {string} type
 * @property {string | undefined} [heading]
 * @property {string | undefined} [content]
 * @property {object | undefined} [kvps]
 * @property {number | undefined} [timestamp]
 * @property {number} [agentno]
 */

/**
 * @typedef {{ element: Element } & Record<string, any>} MessageHandlerResult
 */

/**
 * @typedef {object} SetMessageResult
 * @property {IArguments} args
 * @property {MessageHandlerResult} result
 */

/**
 * @typedef {(args: MessageHandlerArgs & Record<string, any>) => (MessageHandlerResult|Promise<MessageHandlerResult>)} MessageHandler
 */

/**
 * @typedef {object} ProcessStepArgs
 * @property {string | number} id
 * @property {string} title
 * @property {string} code
 * @property {string[] | undefined} [classes]
 * @property {any} [kvps]
 * @property {string | undefined} [content]
 * @property {string[] | undefined} [contentClasses]
 * @property {Element[] | undefined} [actionButtons]
 * @property {any} log
 * @property {boolean} [allowCompletedGroup]
 */


export function scrollOnNextProcessGroup() {
  _scrollOnNextProcessGroup = "wait";
}

// handlers for log message rendering
/**
 * Returns a message renderer for a given log message type.
 *
 * The returned handler has the same input object shape as `setMessage(...)` passes through
 * and may return a rich object `{ element, actionButtons?, ...additional }`.
 *
 * @param {string} type
 * @returns {Promise<MessageHandler>}
 */
export async function getMessageHandler(type) {
  switch (type) {
    case "user":
      return drawMessageUser;
    case "agent":
      return drawMessageAgent;
    case "response":
      return drawMessageResponse;
    case "tool":
      return drawMessageTool;
    case "progress":
      return drawMessageProgress;
    case "mcp":
      return drawMessageMcp;
    case "subagent":
      return drawMessageSubagent;
    case "warning":
      return drawMessageWarning;
    case "rate_limit":
      return drawMessageWarning;
    case "error":
      return drawMessageError;
    case "info":
      return drawMessageInfo;
    case "util":
      return drawMessageUtil;
    case "hint":
      return drawMessageHint;
    case "model_setup_gate":
      return drawMessageModelSetupGate;
    default:
      return await getHandlerFromExtensions(type);
  }

  async function getHandlerFromExtensions(type){
    const extData = { type: type, handler: undefined }
    await callJsExtensions("get_message_handler", extData);
    // return handler from extensions
    if(typeof extData.handler == "function") return extData.handler;
    //not set by extensions, return default
    return drawMessageTool;
  }
}


// entrypoint called from poll/WS communication, this is how all messages are rendered and updated
// input is raw log format
//
// Render conflation: streaming pushes can arrive far faster than individual
// renders complete. Chaining one full render per snapshot makes the render
// queue grow unboundedly, so the chat body falls behind in real time during an
// active turn and only catches up long after the agent finishes (a finished
// workflow looks like it is still running). Snapshot logs are deltas, but
// merging is cumulative-safe (message-window dedups by id+type, last write
// wins), so accumulate pending deltas and drain them in as few renders as
// possible instead of rendering every intermediate state.
let _messageRenderRunning = false;
let _messageRenderPending = null;
let _messageRenderPendingGeneration = -1;

export function setMessages(messages) {
  const generation = _messageRenderGeneration;
  if (_messageRenderPendingGeneration !== generation) {
    // A render-state reset happened since the last call; drop stale deltas.
    _messageRenderPending = null;
    _messageRenderPendingGeneration = generation;
  }
  const incoming = Array.isArray(messages) ? messages : [];
  _messageRenderPending = (_messageRenderPending || []).concat(incoming);

  if (_messageRenderRunning) {
    // A drain is already in flight; its loop picks up everything accumulated
    // above before finishing, so resolve with the current drain.
    return _messageRenderQueue;
  }

  const task = _messageRenderQueue.then(drain, drain);
  _messageRenderQueue = task.catch(() => undefined);
  return task;

  async function drain() {
    _messageRenderRunning = true;
    try {
      while (
        generation === _messageRenderGeneration &&
        _messageRenderPending &&
        _messageRenderPending.length
      ) {
        const batch = _messageRenderPending;
        _messageRenderPending = null;
        await setMessagesNow(batch, generation);
      }
    } finally {
      _messageRenderRunning = false;
    }
    return null;
  }
}

async function setMessagesNow(messages, generation) {
  if (generation !== _messageRenderGeneration) return null;
  messages = normalizeMessages(messages);
  const context = { processStepTypes: new Set(PROCESS_STEP_TYPES) };
  await callJsExtensions("get_process_step_types", context);
  const types = _messageWindow.messageTypes;
  for (const message of messages) types.add(String(message.type || ""));
  for (const type of types) {
    if (!context.processStepTypes.has(type) && await getMessageHandler(type) === drawMessageTool) {
      context.processStepTypes.add(type);
    }
  }
  if (generation !== _messageRenderGeneration) return null;
  _processStepTypes = context.processStepTypes;
  const history = getChatHistoryEl();
  const followTail = shouldFollowMessageTail();

  const addedMessageKeys = _messageWindow.merge(messages, { followTail });
  bindMessageWindow(history);
  if (_messageWindowRenderPromise) await _messageWindowRenderPromise;

  const initialWindow =
    _messageWindow.size > 0 && !history?.querySelector(".message-group");
  if (initialWindow && _messageWindowFollowTail) _messageWindow.showTail();
  const compactedTail = _messageWindow.compactTailIfNeeded();
  const windowMessages = _messageWindow.visibleMessages();
  const cappedProcessGroupUpdate = hasCappedProcessGroupUpdate(
    messages,
    windowMessages,
    addedMessageKeys,
  );
  if (initialWindow || compactedTail || cappedProcessGroupUpdate) {
    return await renderMessageWindow({
      preserveScroll: !initialWindow && !followTail,
      generation,
    });
  }

  return await renderMessageBatch(messages, {
    virtualizeOffscreen: true,
    windowedRender: false,
    generation,
  });
}

export function resetMessageRenderState({ clearDom = true } = {}) {
  _messageRenderGeneration += 1;
  _messageWindow.reset([]);
  _massRender = false;
  _windowedRender = false;
  _scrollOnNextProcessGroup = null;
  _messageWindowFollowTail = true;
  _messageWindowLoadingDirection = null;
  _messageWindowSuppressScrollEvents = false;
  _messageWindowPointerActive = false;
  _messageWindowUserScrollUntil = 0;
  _messageWindowResizeObserver?.disconnect();
  _messageWindowResizeObserver = null;
  _processGroupStepLimits.clear();
  _renderedProcessGroupPages.clear();

  const history = document.getElementById("chat-history") || getChatHistoryEl();
  if (history) cancelPendingScroll(history);
  if (clearDom && history) history.replaceChildren();
  if (history) {
    delete history.dataset.messageWindowStart;
    delete history.dataset.messageWindowEnd;
    delete history.dataset.messageWindowTotal;
  }
}

function normalizeMessages(messages) {
  const normalized = Array.isArray(messages) ? [...messages].filter(Boolean) : [];
  normalized.sort(
    (a, b) =>
      (a.no ?? Number.MAX_SAFE_INTEGER) -
      (b.no ?? Number.MAX_SAFE_INTEGER),
  );
  return normalized;
}

async function renderMessageWindow({
  preserveScroll = true,
  generation = _messageRenderGeneration,
} = {}) {
  if (_messageWindowRenderPromise) return await _messageWindowRenderPromise;

  _messageWindowRenderPromise = (async () => {
    const history = getChatHistoryEl();
    if (!history) return null;
    const stagingHistory = createMessageWindowStagingHistory(history);

    _messageWindowSuppressScrollEvents = true;
    cancelPendingScroll(history);
    _messageWindowResizeObserver?.disconnect();
    try {
      const anchor = preserveScroll
        ? captureMessageWindowAnchor(history)
        : null;
      const expansionState = captureMessageExpansionState(history);
      _chatHistory = stagingHistory;

      const windowMessages = _messageWindow.visibleMessages();
      const renderMessages = getProcessGroupRenderMessages(windowMessages);
      const context = await renderMessageBatch(renderMessages, {
        forceHistoryEmpty: true,
        forceMassRender: true,
        suppressScroll: preserveScroll,
        windowedRender: shouldDeferReplayDetails(renderMessages),
        windowRebuild: true,
        generation,
      });

      if (generation !== _messageRenderGeneration) {
        return null;
      }

      updateProcessGroupPagingControls(stagingHistory);
      await restoreMessageExpansionState(stagingHistory, expansionState);
      await nextAnimationFrame();

      if (generation !== _messageRenderGeneration) return null;

      _messageWindowResizeObserver?.disconnect();
      stagingHistory
        .querySelectorAll(".message-container")
        .forEach((element) => element.classList.add("message-window-restored"));
      const stagedChildren = Array.from(stagingHistory.childNodes);
      const stagedWindowState = {
        messageWindowStart: stagingHistory.dataset.messageWindowStart,
        messageWindowEnd: stagingHistory.dataset.messageWindowEnd,
        messageWindowTotal: stagingHistory.dataset.messageWindowTotal,
        detailMode: stagingHistory.dataset.detailMode,
      };
      stagingHistory.remove();
      _chatHistory = history;

      history.replaceChildren(...stagedChildren);
      copyMessageWindowDataset(history, stagedWindowState);
      let anchorRestored = anchor
        ? restoreMessageWindowAnchor(history, anchor)
        : false;
      if (!anchorRestored && _messageWindow.isAtTail() && _messageWindowFollowTail) {
        history.scrollTop = history.scrollHeight;
      }

      await nextAnimationFrame();
      refreshCollapsibleMessageOverflow(history);
      if (anchor) {
        anchorRestored = restoreMessageWindowAnchor(history, anchor) ||
          anchorRestored;
      }
      if (!anchorRestored && _messageWindow.isAtTail() && _messageWindowFollowTail) {
        history.scrollTop = history.scrollHeight;
      }

      context.history = history;
      context.mainScroller = null;
      refreshMessageWindowResizeObserver(history);
      return context;
    } finally {
      stagingHistory.remove();
      _chatHistory = history;
      _lastMessageWindowScrollTop = history.scrollTop;
      _messageWindowSuppressScrollEvents = false;
    }
  })();

  try {
    return await _messageWindowRenderPromise;
  } finally {
    _messageWindowRenderPromise = null;
  }
}

function shouldDeferReplayDetails(messages) {
  if (
    _messageWindow.hasOlder ||
    _messageWindow.hasNewer ||
    messages.length > DEFERRED_REPLAY_ENTRY_THRESHOLD
  ) {
    return true;
  }

  let textSize = 0;
  for (const message of messages) {
    textSize += String(message?.heading ?? "").length;
    textSize += String(message?.content ?? "").length;
    for (const value of Object.values(message?.kvps || {})) {
      textSize += typeof value === "string" ? value.length : 500;
    }
    if (textSize > DEFERRED_REPLAY_TEXT_THRESHOLD) return true;
  }
  return false;
}

async function renderMessageBatch(messages, options = {}) {
  const generation = options.generation ?? _messageRenderGeneration;
  if (generation !== _messageRenderGeneration) return null;
  const history = getChatHistoryEl();
  const context = {
    messages: normalizeMessages(messages),
    history,
    historyEmpty:
      options.forceHistoryEmpty ?? !history?.querySelector(".message-group"),
    isLargeAppend: false,
    cutoff: 0,
    massRender: false,
    windowRebuild: Boolean(options.windowRebuild),
    messageWindow: getMessageWindowContext(),
    scrollerOptions: {
      smooth: true,
      toleranceRem: 4,
      reapplyDelayMs: 1000,
      applyStabilization: true,
    },
    /** @type {Scroller | null} */
    mainScroller: null,
    /** @type {SetMessageResult[]} */
    results: [],
  };

  context.isLargeAppend = !context.historyEmpty && context.messages.length > 10;
  context.cutoff = context.isLargeAppend
    ? Math.max(0, context.messages.length - 2)
    : 0;
  context.massRender =
    Boolean(options.forceMassRender) ||
    context.historyEmpty ||
    context.isLargeAppend;
  context.scrollerOptions.smooth = !context.massRender;

  await callJsExtensions("set_messages_before_loop", context);
  if (generation !== _messageRenderGeneration) {
    context.history?.replaceChildren();
    return null;
  }

  if (context.history) {
    context.mainScroller = new Scroller(
      context.history,
      context.scrollerOptions,
    );
  }

  try {
    for (let i = 0; i < context.messages.length; i++) {
      if (generation !== _messageRenderGeneration) break;
      const message = context.messages[i];
      const messageKey = getMessageCacheKey(message);
      if (
        options.virtualizeOffscreen &&
        messageKey &&
        !_messageWindow.isKeyVisible(messageKey)
      ) {
        context.results.push({
          args: message,
          result: { element: null, virtualized: true, dontScroll: true },
        });
        continue;
      }
      _massRender =
        Boolean(options.forceMassRender) ||
        context.historyEmpty ||
        (context.isLargeAppend && i < context.cutoff);
      _windowedRender = Boolean(options.windowedRender);
      const entry = await setMessage(message);
      if (generation !== _messageRenderGeneration) {
        context.history?.replaceChildren();
        break;
      }
      context.results.push(entry);
    }

    if (generation === _messageRenderGeneration) {
      updateMessageWindowIndicators(context.history);
      if (
        context.windowRebuild &&
        typeof preferencesStore.applyCurrentDetailMode === "function"
      ) {
        await preferencesStore.applyCurrentDetailMode(context.history);
      }
      refreshMessageWindowResizeObserver(context.history);
      await callJsExtensions("set_messages_after_loop", context);
    }
  } finally {
    _massRender = false;
    _windowedRender = false;
  }

  if (generation !== _messageRenderGeneration) return null;

  const lastResult = context.results[context.results.length - 1]?.result;
  const shouldScroll =
    !options.suppressScroll &&
    (context.historyEmpty || !lastResult?.dontScroll);

  if (shouldScroll) context.mainScroller?.reApplyScroll();

  if (_scrollOnNextProcessGroup === "scroll") {
    requestAnimationFrame(() => {
      if (
        generation !== _messageRenderGeneration ||
        _scrollOnNextProcessGroup !== "scroll"
      ) {
        return;
      }
      context.mainScroller?.scrollToBottom();
      _scrollOnNextProcessGroup = null;
    });
  }

  return context;
}

// entrypoint called from poll/WS communication, this is how all messages are rendered and updated
// input is raw log format
/**
 * @param {MessageHandlerArgs & Record<string, any>} param0
 * @returns {Promise<SetMessageResult>}
 */
export async function setMessage({
  no,
  id,
  type,
  heading,
  content,
  kvps,
  timestamp,
  agentno,
  ...additional
}) {
  const rawMessage = arguments[0];
  const handler = await getMessageHandler(type);
  // prefer log ID if set to match user message created on frontend with backend updates
  const handlerArgs = {
    no,
    id: id || String(no) || "",
    type,
    heading,
    content,
    kvps,
    timestamp,
    agentno,
    ...additional,
  };
  handlerArgs[PROCESS_GROUP_RENDER_INFO] = _messageProcessGroups.get(rawMessage);
  const handlerResult = await handler(handlerArgs);
  const messageKey = getMessageCacheKey(rawMessage);

  if (handlerResult?.element && messageKey) {
    handlerResult.element.dataset.messageKey = messageKey;
  }
  if (handlerResult?.element && no !== undefined && no !== null) {
    handlerResult.element.dataset.logNo = String(no);
  }

  if (handlerResult?.step) {
    handlerResult.step.__renderDetail = async () => {
      if (!handlerResult.step?.isConnected) return null;
      return await requestDeferredMessageDetail(rawMessage);
    };
    handlerResult.step.__discardDetail = () =>
      discardProcessStepDetail(handlerResult.step);
    handlerResult.step.__setExpanded = (expanded) =>
      toggleStepCollapse(handlerResult.step, expanded);
  }

  return {
    args: rawMessage,
    result: handlerResult,
  }
}

function getOrCreateMessageContainer(
  id,
  position,
  containerClasses = [],
  forceNewGroup = false,
) {
  let container = getChatHistoryElementById(`message-${id}`);
  if (!container) {
    container = document.createElement("div");
    container.id = `message-${id}`;
    container.classList.add("message-container");
  }

  if (containerClasses.length) {
    container.classList.add(...containerClasses);
  }

  if (!container.parentNode) {
    appendToMessageGroup(container, position, forceNewGroup);
  }

  return container;
}

function getChatHistoryEl() {
  if (!_chatHistory) _chatHistory = document.getElementById("chat-history");
  return _chatHistory;
}

function getChatHistoryElementById(id) {
  const history = getChatHistoryEl();
  if (!history || !id) return null;
  if (globalThis.CSS?.escape) {
    return history.querySelector(`#${globalThis.CSS.escape(id)}`);
  }
  return Array.from(history.querySelectorAll("[id]")).find(
    (element) => element.id === id,
  ) || null;
}

function getLastMessageGroup() {
  const groups = getChatHistoryEl()?.querySelectorAll(":scope > .message-group");
  return groups?.[groups.length - 1] || null;
}

function getMessageWindowContext() {
  return {
    start: _messageWindow.visibleStart,
    end: _messageWindow.visibleEnd,
    total: _messageWindow.size,
    rendered: _messageWindow.renderedCount,
    older: _messageWindow.olderCount,
    newer: _messageWindow.newerCount,
    hasOlder: _messageWindow.hasOlder,
    hasNewer: _messageWindow.hasNewer,
  };
}

function getProcessGroupPageState(messages) {
  const groups = new Map();
  for (const message of messages) {
    const group = _messageProcessGroups.get(message);
    if (!group || !_messageIsProcessStep.has(message)) continue;
    let state = groups.get(group.key);
    if (!state) {
      state = { group, steps: [] };
      groups.set(group.key, state);
    }
    state.steps.push(message);
  }
  return groups;
}

function getProcessGroupRenderMessages(messages) {
  const groups = getProcessGroupPageState(messages);
  const hiddenByGroup = new Map();
  _renderedProcessGroupPages = new Map();

  for (const [key, state] of groups) {
    const limit = _processGroupStepLimits.get(key) ||
      PROCESS_GROUP_STEP_PAGE_SIZE;
    const hidden = Math.max(0, state.steps.length - limit);
    hiddenByGroup.set(key, hidden);
    _renderedProcessGroupPages.set(key, {
      ...state,
      hidden,
      visible: state.steps.length - hidden,
    });
  }

  const seen = new Map();
  return messages.filter((message) => {
    const group = _messageProcessGroups.get(message);
    if (!group || !_messageIsProcessStep.has(message)) return true;
    const index = seen.get(group.key) || 0;
    seen.set(group.key, index + 1);
    return index >= (hiddenByGroup.get(group.key) || 0);
  });
}

function hasCappedProcessGroupUpdate(messages, windowMessages, addedMessageKeys) {
  if (!messages.length) return false;
  const groupStates = getProcessGroupPageState(windowMessages);
  return messages.some((message) => {
    const group = _messageProcessGroups.get(message);
    if (!group || !_messageIsProcessStep.has(message)) return false;
    const total = groupStates.get(group.key)?.steps.length || 0;
    const limit = _processGroupStepLimits.get(group.key) ||
      PROCESS_GROUP_STEP_PAGE_SIZE;
    return total > limit && addedMessageKeys.has(getMessageCacheKey(message));
  });
}

function updateProcessGroupPagingControls(history) {
  history
    ?.querySelectorAll(".process-group-show-more")
    .forEach((element) => element.remove());

  for (const [key, state] of _renderedProcessGroupPages) {
    const group = Array.from(
      history?.querySelectorAll(".process-group[data-render-group-key]") || [],
    ).find((candidate) => candidate.dataset.renderGroupKey === key);
    if (!group) continue;

    const allSteps = state.steps;
    const firstTimestamp = allSteps[0]?.timestamp;
    const lastTimestamp = allSteps.at(-1)?.timestamp;
    if (firstTimestamp != null) {
      group.dataset.fullStartTimestamp = String(firstTimestamp);
      group.setAttribute("data-start-timestamp", String(firstTimestamp));
    }
    if (lastTimestamp != null) {
      group.dataset.fullEndTimestamp = String(lastTimestamp);
    }
    group.dataset.fullAgentSteps = String(
      Math.max(
        0,
        allSteps.filter((message) => message?.type === "agent").length - 1,
      ),
    );
    group.dataset.fullWarningSteps = String(
      allSteps.filter((message) => message?.type === "warning").length,
    );
    group.dataset.fullInfoSteps = String(
      allSteps.filter((message) => message?.type === "info").length,
    );
    const lastAgentMessage = allSteps.findLast(
      (message) => message?.type === "agent",
    );
    const fullTitle = cleanStepTitle(lastAgentMessage?.heading, 50);
    if (fullTitle) {
      const title = group.querySelector(".process-group-header .group-title");
      if (title) title.textContent = fullTitle;
    }
    updateProcessGroupHeader(group);

    if (state.hidden <= 0) continue;
    const stepsContainer = group.querySelector(":scope .process-steps");
    if (!stepsContainer) continue;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "process-group-show-more";
    button.textContent = "Show more";
    const nextCount = Math.min(PROCESS_GROUP_STEP_PAGE_SIZE, state.hidden);
    button.setAttribute("aria-label", `Show ${nextCount} earlier steps`);
    button.addEventListener("click", () => {
      void showMoreProcessGroupSteps(key);
    });
    stepsContainer.insertBefore(button, stepsContainer.firstChild);
  }
}

function showMoreProcessGroupSteps(groupKey) {
  const generation = _messageRenderGeneration;
  const task = _messageRenderQueue.then(async () => {
    if (generation !== _messageRenderGeneration) return false;
    const current = _processGroupStepLimits.get(groupKey) ||
      PROCESS_GROUP_STEP_PAGE_SIZE;
    _processGroupStepLimits.set(
      groupKey,
      current + PROCESS_GROUP_STEP_PAGE_SIZE,
    );
    await renderMessageWindow({ preserveScroll: true, generation });
    return true;
  });
  _messageRenderQueue = task.catch(() => undefined);
  return task;
}

function shouldFollowMessageTail() {
  if (_messageWindow.size === 0) return true;
  return _messageWindowFollowTail && _messageWindow.isAtTail();
}

async function renderDeferredMessageDetail(message) {
  const entry = await setMessage(message);
  await callJsExtensions("set_messages_after_loop", {
    messages: [message],
    history: getChatHistoryEl(),
    historyEmpty: true,
    isLargeAppend: false,
    cutoff: 0,
    massRender: false,
    windowRebuild: false,
    detailMaterialization: true,
    messageWindow: getMessageWindowContext(),
    mainScroller: null,
    results: [entry],
  });
  return entry;
}

function requestDeferredMessageDetail(message) {
  if (_messageWindowRenderPromise) {
    return renderDeferredMessageDetail(message);
  }

  const generation = _messageRenderGeneration;
  const task = _messageRenderQueue.then(async () => {
    if (generation !== _messageRenderGeneration) return null;
    return await renderDeferredMessageDetail(message);
  });
  _messageRenderQueue = task.catch(() => undefined);
  return task;
}

function bindMessageWindow(history) {
  if (!history || _messageWindowHistory === history) return;
  _messageWindowHistory = history;
  _lastMessageWindowScrollTop = history.scrollTop;

  const noteUserScrollIntent = () => {
    _messageWindowUserScrollUntil =
      messageWindowNow() + MESSAGE_WINDOW_USER_SCROLL_GRACE_MS;
  };

  history.addEventListener("wheel", noteUserScrollIntent, { passive: true });
  history.addEventListener("touchstart", noteUserScrollIntent, {
    passive: true,
  });
  history.addEventListener("pointerdown", () => {
    _messageWindowPointerActive = true;
    noteUserScrollIntent();
  });
  globalThis.addEventListener("pointerup", () => {
    _messageWindowPointerActive = false;
  });
  globalThis.addEventListener("pointercancel", () => {
    _messageWindowPointerActive = false;
  });
  globalThis.addEventListener("keydown", (event) => {
    const target = event.target;
    if (
      target instanceof Element &&
      target.closest("input, textarea, select, [contenteditable='true']")
    ) {
      return;
    }
    if (
      ["ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End"].includes(
        event.key,
      )
    ) {
      noteUserScrollIntent();
    }
  });

  history.addEventListener(
    "scroll",
    () => {
      if (_messageWindowScrollFrame != null) return;
      _messageWindowScrollFrame = requestAnimationFrame(() => {
        _messageWindowScrollFrame = null;
        if (_messageWindowRenderPromise) return;

        const previous = _lastMessageWindowScrollTop;
        const current = history.scrollTop;
        const direction = current < previous ? "older" : current > previous ? "newer" : null;
        _lastMessageWindowScrollTop = current;

        const hasUserScrollIntent =
          _messageWindowPointerActive ||
          messageWindowNow() <= _messageWindowUserScrollUntil;
        const bottomDistance =
          history.scrollHeight - current - history.clientHeight;

        if (hasUserScrollIntent && direction) {
          _messageWindowFollowTail =
            _messageWindow.isAtTail() &&
            bottomDistance <= MESSAGE_WINDOW_TAIL_TOLERANCE_PX;
        }

        if (
          _messageWindowSuppressScrollEvents ||
          _messageWindowRenderPromise ||
          !hasUserScrollIntent
        ) {
          return;
        }

        if (
          direction === "older" &&
          current <= MESSAGE_WINDOW_BOUNDARY_TOLERANCE_PX &&
          _messageWindow.hasOlder
        ) {
          void shiftMessageWindow("older");
          return;
        }

        if (
          direction === "newer" &&
          bottomDistance <= MESSAGE_WINDOW_BOUNDARY_TOLERANCE_PX &&
          _messageWindow.hasNewer
        ) {
          void shiftMessageWindow("newer");
        }
      });
    },
    { passive: true },
  );
}

function messageWindowNow() {
  return globalThis.performance?.now?.() ?? Date.now();
}

function refreshMessageWindowResizeObserver(history) {
  if (!history || typeof ResizeObserver === "undefined") return;
  if (!_messageWindowResizeObserver) {
    _messageWindowResizeObserver = new ResizeObserver((entries) => {
      entries.forEach((entry) =>
        refreshCollapsibleMessageOverflow(entry.target),
      );

      const liveHistory = getChatHistoryEl();
      if (
        _messageWindowSuppressScrollEvents ||
        _messageWindowRenderPromise ||
        !_messageWindowFollowTail ||
        !_messageWindow.isAtTail()
      ) {
        return;
      }

      cancelPendingScroll(liveHistory);
      liveHistory.scrollTop = liveHistory.scrollHeight;
      _lastMessageWindowScrollTop = liveHistory.scrollTop;
    });
  }

  history
    .querySelectorAll(":scope > .message-group")
    .forEach((group) => _messageWindowResizeObserver.observe(group));
}

async function shiftMessageWindow(direction) {
  await loadAdjacentMessageWindow(direction);
}

export function loadAdjacentMessageWindow(direction) {
  if (!["older", "newer"].includes(direction)) {
    return Promise.resolve(false);
  }
  if (_messageWindowLoadingDirection) return Promise.resolve(false);

  const generation = _messageRenderGeneration;
  _messageWindowLoadingDirection = direction;
  setMessageWindowIndicatorLoading(getChatHistoryEl(), direction, true);

  const renderTask = _messageRenderQueue.then(async () => {
    if (generation !== _messageRenderGeneration) return false;
    const shifted =
      direction === "older"
        ? _messageWindow.shiftOlder()
        : _messageWindow.shiftNewer();
    if (!shifted) return false;
    await renderMessageWindow({ preserveScroll: true, generation });
    return true;
  });
  const task = renderTask.finally(() => {
    if (_messageWindowLoadingDirection === direction) {
      _messageWindowLoadingDirection = null;
      setMessageWindowIndicatorLoading(getChatHistoryEl(), direction, false);
    }
  });
  _messageRenderQueue = task.catch(() => undefined);
  return task;
}

export function scrollMessageWindowToEdge(edge) {
  const generation = _messageRenderGeneration;
  const task = _messageRenderQueue.then(async () => {
    if (generation !== _messageRenderGeneration) return false;
    const history = getChatHistoryEl();

    if (edge === "start") {
      _messageWindowFollowTail = false;
      cancelPendingScroll(history);
      if (!_messageWindow.hasOlder && _messageWindow.start === 0) {
        history?.scrollTo({ top: 0, behavior: "instant" });
        return true;
      }
      _messageWindow.showHead();
      await renderMessageWindow({ preserveScroll: false, generation });
      history?.scrollTo({ top: 0, behavior: "instant" });
      return true;
    }

    _messageWindowFollowTail = true;
    cancelPendingScroll(history);
    if (_messageWindow.isAtTail()) {
      if (history) history.scrollTop = history.scrollHeight;
      return true;
    }
    _messageWindow.showTail();
    await renderMessageWindow({ preserveScroll: false, generation });
    if (history) history.scrollTop = history.scrollHeight;
    return true;
  });
  _messageRenderQueue = task.catch(() => undefined);
  return task;
}

export function getMessageWindowState() {
  return getMessageWindowContext();
}

function updateMessageWindowIndicators(history) {
  if (!history) return;
  history
    .querySelectorAll(":scope > [data-message-window-ui]")
    .forEach((element) => element.remove());

  history.dataset.messageWindowStart = String(_messageWindow.visibleStart);
  history.dataset.messageWindowEnd = String(_messageWindow.visibleEnd);
  history.dataset.messageWindowTotal = String(_messageWindow.size);

  if (_messageWindow.hasOlder) {
    const older = createMessageWindowIndicator("older");
    history.insertBefore(older, history.firstChild);
  }

  if (_messageWindow.hasNewer) {
    history.appendChild(createMessageWindowIndicator("newer"));
  }
}

function setMessageWindowIndicatorLoading(history, direction, loading) {
  if (!history) return;
  let indicator = history.querySelector(
    `:scope > [data-message-window-ui="${direction}"]`,
  );
  if (!indicator && loading) {
    updateMessageWindowIndicators(history);
    indicator = history.querySelector(
      `:scope > [data-message-window-ui="${direction}"]`,
    );
  }
  if (!indicator) return;

  indicator.classList.toggle("is-loading", loading);
  indicator
    .querySelector(":scope > .three-bubble-loader")
    ?.classList.toggle("is-active", loading);
  if (loading) {
    const label = direction === "older" ? "earlier" : "newer";
    indicator.setAttribute("role", "status");
    indicator.setAttribute("aria-live", "polite");
    indicator.setAttribute("aria-label", `Loading ${label} messages`);
    indicator.removeAttribute("aria-hidden");
  } else {
    indicator.removeAttribute("role");
    indicator.removeAttribute("aria-live");
    indicator.removeAttribute("aria-label");
    indicator.setAttribute("aria-hidden", "true");
  }
}

function createMessageWindowIndicator(direction) {
  const indicator = document.createElement("div");
  const label = direction === "older" ? "earlier" : "newer";
  const isLoading = _messageWindowLoadingDirection === direction;
  indicator.className = `message-window-loader message-window-${direction}`;
  indicator.classList.toggle("is-loading", isLoading);
  indicator.dataset.messageWindowUi = direction;
  if (isLoading) {
    indicator.setAttribute("role", "status");
    indicator.setAttribute("aria-live", "polite");
    indicator.setAttribute("aria-label", `Loading ${label} messages`);
  } else {
    indicator.setAttribute("aria-hidden", "true");
  }
  indicator.appendChild(createThreeBubbleLoader({ active: isLoading }));
  const statusLabel = document.createElement("span");
  statusLabel.className = "loading-indicator-label";
  statusLabel.textContent = `Loading ${label} messages`;
  indicator.appendChild(statusLabel);
  return indicator;
}

function createMessageWindowStagingHistory(history) {
  const staging = history.cloneNode(false);
  const historyRect = history.getBoundingClientRect();
  staging.classList.add("message-window-staging");
  staging.setAttribute("aria-hidden", "true");
  staging.style.position = "fixed";
  staging.style.top = "0";
  staging.style.left = "-100000px";
  staging.style.width = `${historyRect.width}px`;
  staging.style.height = `${historyRect.height}px`;
  staging.style.visibility = "hidden";
  staging.style.pointerEvents = "none";
  staging.style.contain = "layout style paint";
  delete staging.dataset.scrollerTimeout;
  delete staging.dataset.scrollerReapplySnapshot;
  delete staging.dataset.scrollingTo;
  history.after(staging);
  return staging;
}

function copyMessageWindowDataset(history, state) {
  for (const [key, value] of Object.entries(state)) {
    if (value === undefined) delete history.dataset[key];
    else history.dataset[key] = value;
  }
}

function getMessageWindowAnchorCandidates(history) {
  return Array.from(
    history.querySelectorAll(
      ".process-group[data-render-group-key], [data-message-key]",
    ),
  ).filter((element) =>
    element.dataset.renderGroupKey || !element.closest(".process-group")
  );
}

function getMessageWindowAnchorIdentity(element) {
  if (element?.dataset?.renderGroupKey) {
    return `group:${element.dataset.renderGroupKey}`;
  }
  if (element?.dataset?.messageKey) {
    return `message:${element.dataset.messageKey}`;
  }
  return null;
}

function captureMessageWindowAnchor(history) {
  const historyRect = history.getBoundingClientRect();
  const candidates = getMessageWindowAnchorCandidates(history);
  let fallback = null;

  for (const element of candidates) {
    const rect = element.getBoundingClientRect();
    if (rect.height <= 0 || rect.bottom <= historyRect.top) continue;
    const anchor = {
      identity: getMessageWindowAnchorIdentity(element),
      offset: rect.top - historyRect.top,
    };
    if (rect.top < historyRect.bottom) return anchor;
    fallback ||= anchor;
  }

  return fallback;
}

function restoreMessageWindowAnchor(history, anchor) {
  if (!anchor?.identity) return false;
  const historyRect = history.getBoundingClientRect();
  const element = getMessageWindowAnchorCandidates(history).find(
    (candidate) =>
      getMessageWindowAnchorIdentity(candidate) === anchor.identity,
  );
  if (!element) return false;
  const nextOffset = element.getBoundingClientRect().top - historyRect.top;
  history.scrollTop += nextOffset - anchor.offset;
  return true;
}

function captureMessageExpansionState(history) {
  const state = new Map();
  history
    .querySelectorAll(".process-group[id], .process-step[id]")
    .forEach((element) => {
      const kind = element.classList.contains("process-group")
        ? "group"
        : "step";
      state.set(
        `${kind}:${element.id}`,
        element.classList.contains("expanded"),
      );
    });
  history
    .querySelectorAll("[data-message-key] > .message")
    .forEach((element) => {
      state.set(
        `message:${element.parentElement.dataset.messageKey}`,
        element.classList.contains("expanded"),
      );
    });
  return state;
}

async function restoreMessageExpansionState(history, state) {
  const pending = [];
  for (const [key, expanded] of state) {
    let element = null;
    if (key.startsWith("group:") || key.startsWith("step:")) {
      const separator = key.indexOf(":");
      const kind = key.slice(0, separator);
      const id = key.slice(separator + 1);
      const selector = kind === "group" ? ".process-group[id]" : ".process-step[id]";
      element = Array.from(history.querySelectorAll(selector)).find(
        (candidate) => candidate.id === id,
      );
    } else if (key.startsWith("message:")) {
      const messageKey = key.slice(8);
      const container = Array.from(
        history.querySelectorAll("[data-message-key]"),
      ).find((candidate) => candidate.dataset.messageKey === messageKey);
      element = container?.querySelector(":scope > .message") || null;
    }
    if (!element || !history.contains(element)) continue;
    if (typeof element.__setExpanded === "function") {
      pending.push(Promise.resolve(element.__setExpanded(expanded)));
    } else {
      element.classList.toggle("expanded", expanded);
    }
  }
  await Promise.allSettled(pending);
}

function nextAnimationFrame() {
  return new Promise((resolve) => {
    // Browsers may stop painting hidden or occluded windows. A visual layout
    // yield must not hold state synchronization until the window is repainted.
    const finish = () => {
      cancelAnimationFrame(frame);
      clearTimeout(timer);
      resolve();
    };
    const frame = requestAnimationFrame(finish);
    const timer = setTimeout(finish, 100);
  });
}

function appendToMessageGroup(
  messageContainer,
  position,
  forceNewGroup = false,
) {
  const chatHistoryEl = getChatHistoryEl();
  if (!chatHistoryEl) return;

  const lastGroup = getLastMessageGroup();
  const lastGroupType = lastGroup?.getAttribute("data-group-type");

  if (!forceNewGroup && lastGroup && lastGroupType === position) {
    lastGroup.appendChild(messageContainer);
  } else {
    const group = document.createElement("div");
    group.classList.add("message-group", `message-group-${position}`);
    group.setAttribute("data-group-type", position);
    group.appendChild(messageContainer);
    const bottomControl = chatHistoryEl.querySelector(
      ':scope > [data-message-window-ui="newer"]',
    );
    chatHistoryEl.insertBefore(group, bottomControl || null);
  }
}

function getLastProcessGroup(allowCompleted = true) {
  const lastContainer = getLastMessageGroup();
  if (!lastContainer) return null;
  const group = lastContainer.lastElementChild?.querySelector(":scope > .process-group");
  if (!group) return null;
  if (!allowCompleted && isProcessGroupComplete(group)) return null;

  return group;
}

function getOrCreateProcessGroup(id, allowCompleted = true, renderInfo = null) {
  const groupIdentity = renderInfo?.id || id;
  // first try direct match by ID
  const byId = getChatHistoryElementById(`process-group-${groupIdentity}`);
  if (byId) return byId;

  // if not found, try to find the last process group
  const existing = getLastProcessGroup(allowCompleted);
  if (existing) return existing;

  // lastly create new
  const messageContainer = document.createElement("div");
  messageContainer.classList.add(
    "message-container",
    "ai-container",
    "has-process-group",
  );

  const group = createProcessGroup(groupIdentity);
  if (renderInfo?.key) group.dataset.renderGroupKey = renderInfo.key;
  group.classList.add("embedded");
  messageContainer.appendChild(group);

  if (_scrollOnNextProcessGroup === "wait") {
    _scrollOnNextProcessGroup = "scroll";
  }

  appendToMessageGroup(messageContainer, "left");
  return group;
}

export function buildDetailPayload(stepData, extras = {}) {
  if (!stepData) return null;
  return {
    ...stepData,
    ...extras,
  };
}

/**
 * @param {ProcessStepArgs & Record<string, any>} param0
 * @returns {MessageHandlerResult}
 */
export function drawProcessStep({
  id,
  title,
  code,
  classes,
  kvps,
  content,
  contentClasses,
  actionButtons = [],
  log,
  allowCompletedGroup = false,
  ...additional
}) {
  // group and steps DOM elements
  const stepId = `process-step-${id}`;
  let step = getChatHistoryElementById(stepId);

  const renderInfo = log[PROCESS_GROUP_RENDER_INFO];
  const group =
    getStepProcessGroup(step) ||
    getOrCreateProcessGroup(
      id,
      allowCompletedGroup,
      renderInfo,
    );
  if (renderInfo) {
    // A later process step can promote a previously standalone live utility
    // into a substantive unit when the full cache is reclassified.
    group.classList.remove("utility-only");
  } else if (log.type === "util") {
    // Standalone utilities are not part of a substantive render unit. Mark
    // them directly from the full-log classifier instead of inferring group
    // visibility from whichever child steps happen to be mounted so far.
    group.classList.add("utility-only");
  }
  const stepsContainer = group.querySelector(".process-steps");

  const isNewStep = !step;
  const isGroupComplete = isProcessGroupComplete(group);

  // Set start timestamp on group when first step is created
  if (
    isNewStep &&
    !group.hasAttribute("data-start-timestamp") &&
    log.timestamp
  ) {
    group.setAttribute("data-start-timestamp", String(log.timestamp));
  }

  if (!step) {
    // create the base DOM element for the step
    step = document.createElement("div");
    step.id = stepId;
    step.classList.add("process-step");

    // set data attributes of the step
    step.setAttribute("data-log-type", log.type);
    step.setAttribute("data-step-id", String(id));
    step.setAttribute("data-agent-number", log.agentno);

    // set timestamp attribute (convert to milliseconds for duration calculation)
    if (log.timestamp) {
      step.setAttribute(
        "data-timestamp",
        String(Math.round(log.timestamp * 1000)),
      );
    }

    // apply step classes
    if (classes) step.classList.add(...classes);

    let appendTarget = stepsContainer;
    
    // grouping subordinate chain under the delegation call
    // for now disabled, let's keep the UI simple and unified for now
    // const parentStep = findParentDelegationStep(group, log.agentno);
    // if (parentStep) {
    //   appendTarget = getNestedContainer(parentStep);
    //   step.classList.add("nested-step");
    // }

    // remove any existing shiny-text from group
    group
      .querySelectorAll(".process-step .step-title.shiny-text")
      .forEach((el) => {
        el.classList.remove("shiny-text");
      });

    // insert step
    appendTarget.appendChild(step);

    // expand all or current step based on settings
    const detailMode = preferencesStore.detailMode;
    // const isActiveGroup = group.classList.contains("active");

    //expand all
    if (detailMode === "expanded") {
      toggleStepCollapse(step, true);
      // expand current step and schedule collapse of previous
    } else if (
      detailMode === "current" &&
      !isMassRender() &&
      !isGroupComplete
    ) {
      stepsContainer
        .querySelectorAll(".process-step.expanded")
        .forEach((expandedStep) => {
          const delay =
            STEP_COLLAPSE_DELAY[expandedStep.getAttribute("data-log-type")] ||
            STEP_COLLAPSE_DELAY.other;
          console.log(
            "collapsing",
            expandedStep.getAttribute("data-log-type"),
            delay,
          );
          scheduleStepCollapse(expandedStep, delay);
        });
      toggleStepCollapse(step, true);
    }

    // create step header
    const stepHeader = ensureChild(
      step,
      ".process-step-header",
      "div",
      "process-step-header",
    );
  }

  // is step expanded?
  const isExpanded = step.classList.contains("expanded");
  const shouldRenderDetail =
    isExpanded && group.classList.contains("expanded");

  // create step header
  const stepHeader = ensureChild(
    step,
    ".process-step-header",
    "div",
    "process-step-header",
  );

  // Keep the lightweight detail shell and action hooks mounted for extensions,
  // but materialize text-heavy detail content only while the step is expanded.
  const stepDetail = ensureChild(
    step,
    ".process-step-detail",
    "div",
    "process-step-detail",
  );
  // set click handlers
  setupProcessStepHandlers(step, stepHeader);

  // header row - expand icon
  ensureChild(stepHeader, ".step-expand-icon", "span", "step-expand-icon");

  // header row - status badge
  const badge = ensureChild(stepHeader, ".step-badge", "span", "step-badge");

  // set code class if changed
  const prevCode = step.getAttribute("data-step-code");
  if (prevCode !== code) {
    if (prevCode) step.classList.remove(prevCode);
    step.setAttribute("data-step-code", code);
    step.classList.add(code);
    badge.innerText = code;
  }

  // header row - title
  const titleEl = ensureChild(stepHeader, ".step-title", "span", "step-title");
  titleEl.textContent = title;

  // Render action buttons: get/create container, clear, append
  const stepActionBtns = ensureChild(
    stepDetail,
    ".step-detail-actions",
    "div",
    "step-detail-actions",
    "step-action-buttons",
  );
  syncActionButtons(stepActionBtns, actionButtons);

  let detailResult = {
    content: undefined,
    contentScroller: null,
    kvpsTable: null,
  };
  if (shouldRenderDetail) {
    detailResult = renderProcessStepDetail({
      stepDetail,
      kvps,
      content,
      contentClasses,
      code,
    });
  } else {
    discardProcessStepDetail(step);
  }

  // update the process grop header by this step
  updateProcessGroupHeader(group);

  // remove shine from previous steps and add to this one if new and not completed
  if (isNewStep && !isGroupComplete) {
    group
      .querySelectorAll(".step-title.shiny-text")
      .forEach((el) => {
        el.classList.remove("shiny-text");
      });
    titleEl.classList.add("shiny-text");
  }

  // return anything useful
  return {
    element: step,
    actionButtons,
    step,
    detail: stepDetail,
    content: detailResult.content,
    contentScroller: detailResult.contentScroller,
    kvpsTable: detailResult.kvpsTable,
    isExpanded,
    detailPending: !shouldRenderDetail,
  };
}

function renderProcessStepDetail({
  stepDetail,
  kvps,
  content,
  contentClasses,
  code,
}) {
  let stepDetailScroll = stepDetail.querySelector(
    ":scope > .process-step-detail-scroll",
  );
  if (!stepDetailScroll) {
    stepDetailScroll = document.createElement("div");
    stepDetailScroll.classList.add("process-step-detail-scroll");
    stepDetail.insertBefore(
      stepDetailScroll,
      stepDetail.querySelector(":scope > .step-detail-actions"),
    );
  }

  const detailScroller = new Scroller(stepDetailScroll, {
    smooth: code !== "GEN" && !isMassRender(),
    toleranceRem: 4,
  });
  const kvpsTable = drawKvpsIncremental(stepDetailScroll, kvps);

  let stepDetailContent;
  if (content) {
    stepDetailContent = ensureChild(
      stepDetailScroll,
      ".process-step-detail-content",
      "p",
      "process-step-detail-content",
      ...(contentClasses || []),
    );
    stepDetailContent.innerHTML = adjustStepContent(content);
  } else {
    stepDetailScroll
      .querySelector(":scope > .process-step-detail-content")
      ?.remove();
  }

  detailScroller.reApplyScroll();
  return {
    content: stepDetailContent,
    contentScroller: detailScroller,
    kvpsTable,
  };
}

function discardProcessStepDetail(step, { force = false } = {}) {
  if (!step) return;
  const remove = () => {
    if (!force && step.classList.contains("expanded")) return;
    if (
      force &&
      step.classList.contains("expanded") &&
      step.closest(".process-group")?.classList.contains("expanded")
    ) {
      return;
    }
    step
      .querySelector(":scope > .process-step-detail > .process-step-detail-scroll")
      ?.remove();
  };

  if (isMassRender()) remove();
  else setTimeout(remove, 250);
}

function adjustStepContent(content) {
  content = escapeHTML(content);
  content = convertPathsToLinks(content);
  return content;
}

function toggleStepCollapse(step, expanded) {
  if (!step) return;

  let nextExpanded = expanded;
  if (nextExpanded === undefined || nextExpanded === null) {
    nextExpanded = !step.classList.contains("expanded");
  }
  nextExpanded = Boolean(nextExpanded);

  step.classList.toggle("expanded", nextExpanded);

  if (nextExpanded) {
    if (step.querySelector(".process-step-detail-scroll")) return null;
    return materializeProcessStepDetail(step);
  }

  const scroller = step.querySelector(".process-step-detail-scroll");
  if (scroller) scroller.scrollTop = 0;
  discardProcessStepDetail(step);
}

function materializeProcessStepDetail(step) {
  if (!step || typeof step.__renderDetail !== "function") return null;
  if (step.__detailRenderPromise) return step.__detailRenderPromise;

  step.__detailRenderPromise = Promise.resolve(step.__renderDetail()).finally(
    () => {
      delete step.__detailRenderPromise;
    },
  );
  return step.__detailRenderPromise;
}

function drawStandaloneMessage({
  id,
  heading,
  content,
  position = "mid",
  forceNewGroup = false,
  containerClasses = [],
  mainClass = "",
  messageClasses = [],
  contentClasses = [],
  markdown = false,
  latex = false,
  kvps = null,
  actionButtons = [],
}) {
  // end last process group on any standalone messge
  completeLastProcessGroup();

  const container = getOrCreateMessageContainer(
    id,
    position,
    containerClasses,
    forceNewGroup,
  );
  const messageDiv = _drawMessage({
    messageContainer: container,
    heading,
    content,
    kvps,
    messageClasses,
    contentClasses,
    markdown,
    latex,
    mainClass,
  });

  // Collapsible with action buttons
  setupCollapsible(messageDiv, ".step-action-buttons", false, actionButtons);

  return container;
}

// draw a message with a specific type
export function _drawMessage({
  messageContainer,
  heading,
  content,
  kvps = null,
  messageClasses = [],
  contentClasses = [],
  markdown = false,
  latex = false,
  mainClass = "",
  smoothStream = false,
}) {
  // Find existing message div or create new one
  let messageDiv = messageContainer.querySelector(".message");
  if (!messageDiv) {
    messageDiv = document.createElement("div");
    messageDiv.classList.add("message");
    messageContainer.appendChild(messageDiv);
  }

  // Update message classes (preserve collapsible state)
  const preserve = ["message-collapsible", "expanded", "has-overflow"]
    .filter((c) => messageDiv.classList.contains(c))
    .join(" ");
  messageDiv.className = `message ${mainClass} ${messageClasses.join(" ")} ${preserve}`;

  // Handle heading (important for error/rate_limit messages that show context)
  if (heading) {
    let headingElement = messageDiv.querySelector(".msg-heading");
    if (!headingElement) {
      headingElement = document.createElement("div");
      headingElement.classList.add("msg-heading");
      messageDiv.insertBefore(headingElement, messageDiv.firstChild);
    }

    let headingH4 = headingElement.querySelector("h4");
    if (!headingH4) {
      headingH4 = document.createElement("h4");
      headingElement.appendChild(headingH4);
    }
    headingH4.innerHTML = convertIcons(escapeHTML(heading));
  } else {
    // Remove heading if it exists but heading is null
    const existingHeading = messageDiv.querySelector(".msg-heading");
    if (existingHeading) {
      existingHeading.remove();
    }
  }

  // Find existing body div or create new one
  let bodyDiv = messageDiv.querySelector(".message-body");
  if (!bodyDiv) {
    bodyDiv = document.createElement("div");
    bodyDiv.classList.add("message-body");
    messageDiv.appendChild(bodyDiv);
  }

  // reapply scroll position or autoscroll
  bodyDiv.dataset.scrollStabilization = "1";
  const scroller = new Scroller(bodyDiv, { smooth: !isMassRender() });

  const contentText = String(content ?? "");
  const lazyContent =
    _windowedRender &&
    contentText.length + estimateKvpTextSize(kvps) > LAZY_MESSAGE_PREVIEW_CHARS;
  const contentOptions = {
    bodyDiv,
    content: contentText,
    kvps,
    contentClasses,
    markdown,
    latex,
    smoothStream,
  };

  if (lazyContent) {
    messageDiv.classList.add("lazy-content");
    delete messageDiv.__lazyRenderedExpanded;
    messageDiv.__renderLazyContent = (expanded) => {
      if (messageDiv.__lazyRenderedExpanded === Boolean(expanded)) return;
      messageDiv.__lazyRenderedExpanded = Boolean(expanded);
      renderStandaloneMessageContent({
        ...contentOptions,
        content: expanded
          ? contentText
          : `${contentText.slice(0, LAZY_MESSAGE_PREVIEW_CHARS)}\n\n…`,
        kvps: expanded ? kvps : null,
        smoothStream: false,
      });
    };
    messageDiv.__renderLazyContent(
      messageDiv.classList.contains("expanded"),
    );
  } else {
    messageDiv.classList.remove("lazy-content");
    delete messageDiv.__renderLazyContent;
    delete messageDiv.__lazyRenderedExpanded;
    renderStandaloneMessageContent(contentOptions);
  }

  // reapply scroll position or reset for collapsed
  messageDiv.classList.contains("expanded")
    ? scroller.reApplyScroll()
    : (bodyDiv.scrollTop = 0);

  return messageDiv;
}

function renderStandaloneMessageContent({
  bodyDiv,
  content,
  kvps,
  contentClasses,
  markdown,
  latex,
  smoothStream,
}) {
  drawKvpsIncremental(bodyDiv, kvps);
  if (!content || !content.trim()) {
    bodyDiv.querySelector(".msg-content")?.remove();
    return;
  }

  if (markdown) {
    let contentDiv = bodyDiv.querySelector(".msg-content");
    if (!contentDiv || contentDiv.tagName === "PRE") {
      contentDiv?.remove();
      contentDiv = document.createElement("div");
      bodyDiv.appendChild(contentDiv);
    }
    contentDiv.className = `msg-content ${contentClasses.join(" ")}`;

    let processedContent = content;
    if (latex) processedContent = convertLatexDelimiters(processedContent);
    processedContent = convertImageTags(processedContent);
    processedContent = convertImgFilePaths(processedContent);
    processedContent = convertFilePaths(processedContent);
    processedContent = marked.parse(processedContent, { breaks: true });
    processedContent = sanitizeHtml(processedContent, {
      allowDataImages: true,
      allowLatex: latex,
    });
    processedContent = convertPathsToLinks(processedContent);
    processedContent = addBlankTargetsToLinks(processedContent);

    if (smoothStream) smoothRender(contentDiv, processedContent);
    else contentDiv.innerHTML = processedContent;

    if (latex) renderLatexElements(contentDiv);
    adjustMarkdownRender(contentDiv);
    return;
  }

  let preElement = bodyDiv.querySelector(".msg-content");
  if (!preElement || preElement.tagName !== "PRE") {
    preElement?.remove();
    preElement = document.createElement("pre");
    preElement.style.whiteSpace = "pre-wrap";
    preElement.style.wordBreak = "break-word";
    bodyDiv.appendChild(preElement);
  }
  preElement.className = `msg-content ${contentClasses.join(" ")}`;

  if (smoothStream) smoothRender(preElement, convertHTML(content));
  else preElement.innerHTML = convertHTML(content);
}

function estimateKvpTextSize(kvps) {
  if (!kvps) return 0;
  try {
    return JSON.stringify(kvps)?.length || 0;
  } catch {
    return LAZY_MESSAGE_PREVIEW_CHARS + 1;
  }
}

export { addBlankTargetsToLinks };

/**
 * @param {MessageHandlerArgs & Record<string, any>} param0
 * @returns {MessageHandlerResult}
 */
export function drawMessageDefault({
  id,
  heading,
  content,
  kvps = null,
  ...additional
}) {
  const contentText = String(content ?? "");
  const actionButtons = contentText.trim()
    ? [
        createActionButton("copy", "", () => copyToClipboard(contentText)),
        createActionButton("speak", "", () => ttsService.speak(contentText)),
      ].filter(Boolean)
    : [];

  const element = drawStandaloneMessage({
    id,
    heading,
    content,
    position: "left",
    containerClasses: ["ai-container"],
    mainClass: "message-default",
    messageClasses: ["message-ai"],
    contentClasses: ["msg-json"],
    kvps,
    actionButtons,
  });

  return { element };
}

/**
 * @param {MessageHandlerArgs & Record<string, any>} param0
 * @returns {MessageHandlerResult}
 */
export function drawMessageAgent({
  id,
  type,
  heading,
  content,
  kvps = undefined,
  timestamp = undefined,
  agentno = 0,
  ...additional
}) {
  const title = cleanStepTitle(heading);
  const reservedKeys = new Set(["thoughts", "step", "reasoning", "tool_name", "tool_args", "args", "headline"]);
  let displayKvps = {};
  if (kvps?.thoughts) displayKvps["icon://lightbulb[Thoughts]"] = kvps.thoughts;
  const isResponse = kvps?.tool_name === "response";
  if (preferencesStore.showToolArgs && !isResponse) {
    if (kvps?.tool_name) displayKvps["icon://build[Tool]"] = kvps.tool_name;
    const toolArgs = kvps?.tool_args ?? kvps?.args;
    if (toolArgs) {
      Object.entries(toolArgs).forEach(([key, value]) => {
        if (!reservedKeys.has(key)) displayKvps[key] = value;
      });
    }
  }
  if (kvps?.step) displayKvps["icon://step[Step]"] = kvps.step;
  const thoughtsText = String(kvps?.thoughts ?? "");
  const headerLabels = [
    kvps?.tool_name && { label: kvps.tool_name, class: "tool-name-badge" },
  ].filter(Boolean);
  const actionButtons = [
    createActionButton("detail", "", () =>
      stepDetailStore.showStepDetail(
        buildDetailPayload(arguments[0], { headerLabels }),
      ),
    ),
  ];

  if (thoughtsText.trim()) {
    actionButtons.push(
      createActionButton("copy", "", () => copyToClipboard(thoughtsText)),
    );
    actionButtons.push(
      createActionButton("speak", "", () => ttsService.speak(thoughtsText)),
    );
  }

  const result = drawProcessStep({
    id,
    title,
    code: "GEN",
    classes: undefined,
    kvps: displayKvps,
    actionButtons,
    log: arguments[0],
  });
  if (result.kvpsTable) renderLatexText(result.kvpsTable);
  return result;
}

/**
 * @param {MessageHandlerArgs & Record<string, any>} param0
 * @returns {MessageHandlerResult}
 */
export function drawMessageResponse({
  id,
  type,
  heading,
  content,
  kvps = undefined,
  timestamp = undefined,
  agentno = 0,
  ...additional
}) {
  // response of subordinate agent - render as process step
  if (agentno && agentno > 0) {
    const title = getStepTitle(heading, content, type);
    const contentText = String(content ?? "");
    const actionButtons = contentText.trim()
      ? [
          createActionButton("copy", "", () => copyToClipboard(contentText)),
          createActionButton("speak", "", () => ttsService.speak(contentText)),
        ].filter(Boolean)
      : [];
    return drawProcessStep({
      id,
      title,
      code: "RES",
      kvps: {},
      type,
      heading,
      content,
      timestamp,
      agentno,
      actionButtons,
      log: arguments[0],
    });
  }

  // response of agent 0, render as response to user
  // get last process group or create new container (if first message)

  let group = getLastProcessGroup();
  if (group?.classList.contains("utility-only")) {
    group.setAttribute("data-group-complete", "true");
    updateProcessGroupHeader(group);
    group = null;
  }
  let container = getChatHistoryElementById(`message-${id}`); // first check for already existing message


  // if no container found, add to previous process group if exists
  if (!container) {
    if (group) {
      // new response, collapse all previous steps once
      if (!group.querySelector(".process-group-response")) {
        if (preferencesStore.detailMode == "current")
          group.querySelectorAll(".process-step").forEach((step) => {
            scheduleStepCollapse(step);
          });
      }

      container = ensureChild(
        group,
        `#message-${id}.process-group-response`,
        "div",
        "process-group-response",
      );
      container.id = `message-${id}`;
    }
  }

  // no container or valid process group, create new container
  if (!container) container = getOrCreateMessageContainer(id, "left");

  const messageDiv = _drawMessage({
    messageContainer: container,
    heading: undefined,
    content,
    kvps: undefined,
    messageClasses: [],
    contentClasses: [],
    markdown: true,
    latex: true,
    mainClass: "message-agent-response",
    smoothStream: false, // smooth render disabled, not reliable yet !isMassRender(), // stream smoothly if not in mass render mode
  });

  // Collapsible with action buttons
  const responseText = String(content ?? "");
  const responseActionButtons = responseText.trim()
    ? [
        createActionButton("copy", "", () => copyToClipboard(responseText)),
        createActionButton("speak", "", () => ttsService.speak(responseText)),
      ].filter(Boolean)
    : [];
  setupCollapsible(
    messageDiv,
    ":scope > .step-action-buttons",
    !isMassRender(),
    responseActionButtons,
  );

  if (group) updateProcessGroupHeader(group);

  return { element: container };
}

export function drawMessageModelSetupGate({ id }) {
  const container = getOrCreateMessageContainer(id, "left");
  container.classList.add("model-setup-gate-container");
  container.innerHTML = "";

  const messageDiv = document.createElement("div");
  messageDiv.className = "message message-agent-response model-setup-gate-message";

  const component = document.createElement("x-component");
  component.setAttribute("path", "chat/model-setup-gate.html");
  messageDiv.appendChild(component);
  container.appendChild(messageDiv);

  return { element: container };
}

/**
 * @param {MessageHandlerArgs & Record<string, any>} param0
 * @returns {MessageHandlerResult}
 */
export function drawMessageUser({
  id,
  heading,
  content,
  kvps = null,
  ...additional
}) {
  // end last process group on any user message
  completeLastProcessGroup();

  const messageContainer = getOrCreateMessageContainer(
    id,
    "right",
    ["user-container"],
    true,
  );

  // Find existing message div or create new one
  let messageDiv = messageContainer.querySelector(".message");
  if (!messageDiv) {
    messageDiv = document.createElement("div");
    messageDiv.classList.add("message", "message-user");
    messageContainer.appendChild(messageDiv);
  } else {
    // Ensure it has the correct classes if it already exists
    messageDiv.className = "message message-user";
  }

  // Handle content
  let textDiv = messageDiv.querySelector(".message-text");
  if (content && content.trim().length > 0) {
    if (!textDiv) {
      textDiv = document.createElement("div");
      textDiv.classList.add("message-text");
      messageDiv.appendChild(textDiv);
    }
    let spanElement = textDiv.querySelector("pre");
    if (!spanElement) {
      spanElement = document.createElement("pre");
      textDiv.appendChild(spanElement);
    }
    spanElement.innerHTML = escapeHTML(content);
  } else {
    if (textDiv) textDiv.remove();
  }

  // Handle attachments
  let attachmentsContainer = messageDiv.querySelector(".attachments-container");
  if (kvps && kvps.attachments && kvps.attachments.length > 0) {
    if (!attachmentsContainer) {
      attachmentsContainer = document.createElement("div");
      attachmentsContainer.classList.add("attachments-container");
      messageDiv.appendChild(attachmentsContainer);
    }
    // Important: Clear existing attachments to re-render, preventing duplicates on update
    attachmentsContainer.innerHTML = "";

    kvps.attachments.forEach((attachment) => {
      const attachmentDiv = document.createElement("div");
      attachmentDiv.classList.add("attachment-item");

      const displayInfo = attachmentsStore.getAttachmentDisplayInfo(attachment);

      if (displayInfo.isImage) {
        attachmentDiv.classList.add("image-type");

        const img = document.createElement("img");
        img.src = displayInfo.previewUrl;
        img.alt = displayInfo.filename;
        img.classList.add("attachment-preview");
        img.style.cursor = "pointer";

        attachmentDiv.appendChild(img);
      } else {
        // Render as file tile with title and icon
        attachmentDiv.classList.add("file-type");

        // File icon
        if (
          displayInfo.previewUrl &&
          displayInfo.previewUrl !== displayInfo.filename
        ) {
          const iconImg = document.createElement("img");
          iconImg.src = displayInfo.previewUrl;
          iconImg.alt = `${displayInfo.extension} file`;
          iconImg.classList.add("file-icon");
          attachmentDiv.appendChild(iconImg);
        }

        // File title
        const fileTitle = document.createElement("div");
        fileTitle.classList.add("file-title");
        fileTitle.textContent = displayInfo.filename;

        attachmentDiv.appendChild(fileTitle);
      }

      attachmentDiv.addEventListener("click", displayInfo.clickHandler);

      // @ts-ignore
      attachmentsContainer.appendChild(attachmentDiv);
    });
  } else {
    if (attachmentsContainer) attachmentsContainer.remove();
  }

  // Render heading below message, if provided
  let headingElement = messageDiv.querySelector(".message-user-heading");
  if (heading && heading.trim() && heading.trim() !== "User message") {
    if (!headingElement) {
      headingElement = document.createElement("div");
      headingElement.className = "message-user-heading shiny-text";
    }
    headingElement.textContent = heading;
    messageDiv.appendChild(headingElement);
  } else if (headingElement) {
    headingElement.remove();
  }

  // Render action buttons: get/create container, clear, append
  const userText = String(content ?? "");
  const userActionButtons = userText.trim()
    ? [
        createActionButton("copy", "", () => copyToClipboard(userText)),
        createActionButton("speak", "", () => ttsService.speak(userText)),
      ].filter(Boolean)
    : [];
  setupCollapsible(
    messageDiv,
    ":scope > .step-action-buttons",
    false,
    userActionButtons,
    ":scope > .message-text",
  );

  return { element: messageContainer };
}

/**
 * @param {MessageHandlerArgs & Record<string, any>} param0
 * @returns {Promise<MessageHandlerResult>}
 */
export async function drawMessageTool({
  id,
  type,
  heading,
  content,
  kvps,
  timestamp,
  agentno = 0,
  ...additional
}) {
  const tool_name = kvps?._tool_name || "";

  if (!tool_name) {
    return drawMessageToolSimple({ ...arguments[0] });
  } else if (kvps._tool_name === "skills_tool") {
    const displayKvps = { ...(kvps || {}) };
    delete displayKvps._tool_name;
    return drawMessageToolSimple({ ...arguments[0], code: "SKL", displayKvps });
  } else if (kvps._tool_name === "vision_load") {
    return drawMessageToolSimple({ ...arguments[0], code: "EYE" });
  } else if (kvps._tool_name === "search_engine") {
    return drawMessageToolSimple({ ...arguments[0], code: "WEB" });
  } else if (kvps._tool_name.startsWith("memory_")) {
    return drawMessageToolSimple({ ...arguments[0], code: "MEM" });
  }

  /** @type {{ tool_name: string, kvps: any, handler: Function | undefined }} */
  const extData = {
    tool_name,
    kvps,
    handler: undefined,
  };
  await callJsExtensions("get_tool_message_handler", extData);
  if (typeof extData.handler === "function") {
    return extData.handler(arguments[0]);
  }
  return drawMessageToolSimple({ ...arguments[0] });
}

/**
 * @param {MessageHandlerArgs & Record<string, any>} param0
 * @returns {MessageHandlerResult}
 */
export function drawMessageToolSimple({
  id,
  type,
  heading,
  content,
  kvps,
  timestamp,
  agentno = 0,
  code,
  displayKvps,
  ...additional
}) {
  const title = cleanStepTitle(heading);
  displayKvps = displayKvps || { ...kvps };
  const headerLabels = [
    kvps?._tool_name && { label: kvps._tool_name, class: "tool-name-badge" },
  ].filter(Boolean);
  const contentText = String(content ?? "");
  const actionButtons = contentText.trim()
    ? [
        createActionButton("detail", "", () =>
          stepDetailStore.showStepDetail(
            buildDetailPayload(arguments[0], { headerLabels }),
          ),
        ),
        createActionButton("copy", "", () => copyToClipboard(contentText)),
        createActionButton("speak", "", () => ttsService.speak(contentText)),
      ].filter(Boolean)
    : [];

  return drawProcessStep({
    id,
    title,
    code: code || "USE",
    classes: undefined,
    kvps: displayKvps,
    content,
    // contentClasses: [],
    actionButtons,
    log: arguments[0],
  });
}

/**
 * @param {MessageHandlerArgs & Record<string, any>} param0
 * @returns {MessageHandlerResult}
 */
export function drawMessageMcp({
  id,
  type,
  heading,
  content,
  kvps,
  timestamp,
  agentno = 0,
  ...additional
}) {
  const title = cleanStepTitle(heading);
  let displayKvps = { ...kvps };
  const headerLabels = [
    kvps?.tool_name && { label: kvps.tool_name, class: "tool-name-badge" },
  ].filter(Boolean);
  const contentText = String(content ?? "");
  const actionButtons = contentText.trim()
    ? [
        createActionButton("detail", "", () =>
          stepDetailStore.showStepDetail(
            buildDetailPayload(arguments[0], { headerLabels }),
          ),
        ),
        createActionButton("copy", "", () => copyToClipboard(contentText)),
        createActionButton("speak", "", () => ttsService.speak(contentText)),
      ].filter(Boolean)
    : [];

  return drawProcessStep({
    id,
    title,
    code: "MCP",
    classes: undefined,
    kvps: displayKvps,
    content,
    // contentClasses: [],
    actionButtons,
    log: arguments[0],
  });
}

/**
 * @param {MessageHandlerArgs & Record<string, any>} param0
 * @returns {MessageHandlerResult}
 */
export function drawMessageSubagent({
  id,
  type,
  heading,
  content,
  kvps,
  timestamp,
  agentno = 0,
  ...additional
}) {
  const title = cleanStepTitle(heading);
  let displayKvps = { ...kvps };
  const headerLabels = [
    kvps?.tool_name && { label: kvps.tool_name, class: "tool-name-badge" },
  ].filter(Boolean);
  const contentText = String(content ?? "");
  const actionButtons = contentText.trim()
    ? [
        createActionButton("detail", "", () =>
          stepDetailStore.showStepDetail(
            buildDetailPayload(arguments[0], { headerLabels }),
          ),
        ),
        createActionButton("copy", "", () => copyToClipboard(contentText)),
        createActionButton("speak", "", () => ttsService.speak(contentText)),
      ].filter(Boolean)
    : [];

  return drawProcessStep({
    id,
    title,
    code: "SUB",
    classes: undefined,
    kvps: displayKvps,
    content,
    // contentClasses: [],
    actionButtons,
    log: arguments[0],
  });
}

/**
 * @param {MessageHandlerArgs & Record<string, any>} param0
 * @returns {MessageHandlerResult}
 */
export function drawMessageInfo({
  id,
  heading,
  content,
  kvps,
  ...additional
}) {
  const title = cleanStepTitle(heading || content);
  let displayKvps = { ...kvps };
  delete displayKvps.finished;
  const contentText = String(content ?? "");
  const actionButtons = contentText.trim()
    ? [
        createActionButton("copy", "", () => copyToClipboard(contentText)),
        createActionButton("speak", "", () => ttsService.speak(contentText)),
      ].filter(Boolean)
    : [];

  const result = drawProcessStep({
    id,
    title,
    code: "INF",
    classes: undefined,
    kvps: displayKvps,
    content,
    // contentClasses: [],
    actionButtons,
    log: arguments[0],
  });

  if (kvps?.finished) completeLastProcessGroup();
  return result;
}

/**
 * @param {MessageHandlerArgs & Record<string, any>} param0
 * @returns {MessageHandlerResult}
 */
export function drawMessageUtil({
  id,
  type,
  heading,
  content,
  kvps,
  timestamp,
  agentno = 0,
  ...additional
}) {
  const title = cleanStepTitle(heading || content);
  const contentText = String(content ?? "");
  const actionButtons = contentText.trim()
    ? [
        createActionButton("copy", "", () => copyToClipboard(contentText)),
        createActionButton("speak", "", () => ttsService.speak(contentText)),
      ].filter(Boolean)
    : [];

  const result = drawProcessStep({
    id,
    title,
    code: "UTL",
    classes: ["message-util"],
    kvps,
    content,
    actionButtons,
    log: arguments[0],
    allowCompletedGroup: false,
  });

  result.dontScroll = !preferencesStore.showUtils;
  return result;
}

/**
 * @param {MessageHandlerArgs & Record<string, any>} param0
 * @returns {MessageHandlerResult}
 */
export function drawMessageHint({
  id,
  type,
  heading,
  content,
  kvps,
  timestamp,
  agentno = 0,
  ...additional
}) {
  const title = getStepTitle(heading, content, type);
  const contentText = String(content ?? "");
  const actionButtons = contentText.trim()
    ? [
        createActionButton("copy", "", () => copyToClipboard(contentText)),
        createActionButton("speak", "", () => ttsService.speak(contentText)),
      ].filter(Boolean)
    : [];

  const element = drawStandaloneMessage({
    id,
    heading: title,
    // statusClass,
    // statusCode: "HNT",
    kvps,
    // type,
    content,
    // timestamp,
    // agentno,
    actionButtons,
  });

  return { element };
}

/**
 * @param {MessageHandlerArgs & Record<string, any>} param0
 * @returns {MessageHandlerResult}
 */
export function drawMessageProgress({
  id,
  type,
  heading,
  content,
  kvps,
  timestamp,
  agentno = 0,
  ...additional
}) {
  const title = cleanStepTitle(heading || content);
  let displayKvps = { ...kvps };

  return drawProcessStep({
    id,
    title,
    code: "HDL",
    classes: undefined,
    kvps: displayKvps,
    content,
    // contentClasses: [],
    actionButtons: [],
    log: arguments[0],
  });
}

/**
 * @param {MessageHandlerArgs & Record<string, any>} param0
 * @returns {MessageHandlerResult}
 */
export function drawMessageWarning({
  id,
  type,
  heading,
  content,
  kvps = null,
  ...additional
}) {
  const title = getStepTitle(heading, content, type);
  let displayKvps = { ...kvps };
  const contentText = String(content ?? "");
  const actionButtons = contentText.trim()
    ? [
        createActionButton("copy", "", () => copyToClipboard(contentText)),
        createActionButton("speak", "", () => ttsService.speak(contentText)),
      ].filter(Boolean)
    : [];

  // Keep replayed warnings in their classified process group.
  if (
    arguments[0][PROCESS_GROUP_RENDER_INFO] ||
    getLastProcessGroup(false)
  ) {
    return drawProcessStep({
      id,
      title,
      code: "WRN",
      // classes: null,
      kvps: displayKvps,
      content,
      // contentClasses: [],
      actionButtons,
      log: arguments[0],
    });
  }

  // if no process group is running, draw as standalone
  const element = drawStandaloneMessage({
    id,
    heading: title,
    content,
    position: "mid",
    containerClasses: ["ai-container", "center-container"],
    mainClass: "message-warning",
    kvps: displayKvps,
    actionButtons,
  });

  return { element };
}

/**
 * @param {MessageHandlerArgs & Record<string, any>} param0
 * @returns {MessageHandlerResult}
 */
export function drawMessageError({
  id,
  type,
  heading,
  content,
  kvps = null,
  ...additional
}) {
  const contentText = String(content ?? "");
  let title = getStepTitle(heading, content, type);
  let displayKvps = { ...kvps };

  const actionButtons = [];
  actionButtons.push(
    createActionButton("detail", "", () =>
      stepDetailStore.showStepDetail(
        buildDetailPayload(arguments[0], { headerLabels: [] }),
      ),
    ),
  );
  if (contentText.trim()) {
    actionButtons.push(
      createActionButton("copy", "", () => copyToClipboard(contentText)),
    );
  }

  const element = drawStandaloneMessage({
    id,
    heading: title,
    content: contentText,
    position: "mid",
    containerClasses: ["ai-container", "center-container"],
    mainClass: "message-error",
    kvps: displayKvps,
    actionButtons,
  });

  return { element };
}

function drawKvpsIncremental(container, kvps) {
  // existing KVPS table
  let table = container.querySelector(".msg-kvps");
  if (kvps) {
    // create table if not found
    if (!table) {
      table = document.createElement("table");
      table.classList.add("msg-kvps");
      container.insertBefore(table, container.firstChild);
    }

    // Get all current rows for comparison
    let existingRows = table.querySelectorAll(".kvps-row");
    // Filter out reasoning
    const kvpEntries = Object.entries(kvps).filter(
      ([key]) => key !== "reasoning",
    );

    // Update or create rows as needed
    kvpEntries.forEach(([key, value], index) => {
      let row = existingRows[index];

      if (!row) {
        // Create new row if it doesn't exist
        row = table.insertRow();
        row.classList.add("kvps-row");
      }

      // Update row classes
      row.className = "kvps-row";

      // Handle key cell
      let th = row.querySelector(".kvps-key");
      if (!th) {
        th = row.insertCell(0);
        th.classList.add("kvps-key");
      }
      const convertedKey = convertIcons(String(key), "");
      if (convertedKey !== String(key)) {
        th.innerHTML = convertedKey;
      } else {
        th.textContent = convertToTitleCase(key);
      }

      // Handle value cell
      let td = row.cells[1];
      if (!td) {
        td = row.insertCell(1);
        td.classList.add("kvps-val");
      }

      // reapply scroll position or autoscroll
      // no inner scrolling for kvps anymore
      // const scroller = new Scroller(td);

      // Clear and rebuild content (for now - could be optimized further)
      td.innerHTML = "";

      if (Array.isArray(value)) {
        for (const item of value) {
          addValue(item, td);
        }
      } else {
        addValue(value, td);
      }

      // reapply scroll position or autoscroll
      // scroller.reApplyScroll();
    });

    // Remove extra rows if we have fewer kvps now
    while (existingRows.length > kvpEntries.length) {
      const lastRow = existingRows[existingRows.length - 1];
      lastRow.remove();
      existingRows = table.querySelectorAll(".kvps-row");
    }

    function addValue(value, tdiv) {
      if (typeof value === "object") value = JSON.stringify(value, null, 2);

      if (typeof value === "string" && value.startsWith("img://")) {
        const imgElement = document.createElement("img");
        imgElement.classList.add("kvps-img");
        imgElement.src = value.replace("img://", "/api/image_get?path=");
        imgElement.alt = "Image Attachment";
        tdiv.appendChild(imgElement);

        // Add click handler and cursor change
        imgElement.style.cursor = "pointer";
        imgElement.addEventListener("click", () => {
          imageViewerStore.open(imgElement.src, { refreshInterval: 1000 });
        });
      } else {
        const span = document.createElement("p");
        span.innerHTML = convertHTML(value);
        tdiv.appendChild(span);
      }
    }
  } else {
    // Remove table if kvps is null/empty
    if (table) table.remove();
    return null;
  }
  return table;
}

function convertToTitleCase(str) {
  return str
    .replace(/_/g, " ") // Replace underscores with spaces
    .toLowerCase() // Convert the entire string to lowercase
    .replace(/\b\w/g, function (match) {
      return match.toUpperCase(); // Capitalize the first letter of each word
    });
}

function convertImageTags(content) {
  // Regular expression to match <image> tags and extract base64 content
  const imageTagRegex = /<image>(.*?)<\/image>/g;

  // Replace <image> tags with <img> tags with base64 source
  const updatedContent = content.replace(
    imageTagRegex,
    (match, base64Content) => {
      return `<img src="data:image/jpeg;base64,${base64Content}" alt="Image Attachment" style="max-width: 250px !important;"/>`;
    },
  );

  return updatedContent;
}

function convertHTML(str) {
  if (typeof str !== "string") str = JSON.stringify(str, null, 2);

  let result = escapeHTML(str);
  result = convertImageTags(result);
  result = convertPathsToLinks(result);
  return result;
}

function convertLatexDelimiters(content) {
  return content.replace(
    /(```[\s\S]*?```|~~~[\s\S]*?~~~|`[^`\n]*`)|\\\[([\s\S]*?)\\\]|\\\(([\s\S]*?)\\\)|\$\$([\s\S]*?)\$\$/g,
    (match, code, display, inline, dollars) => {
      if (code) return code;
      const tex = display ?? inline ?? dollars;
      const displayAttribute =
        display !== undefined || dollars !== undefined
          ? ' data-display="true"'
          : "";
      const encodedTex = Array.from(
        tex.trim(),
        (char) => `&#${char.codePointAt(0)};`,
      ).join("");
      return `<latex${displayAttribute}>${encodedTex}</latex>`;
    },
  );
}

function renderLatexElements(container) {
  container.querySelectorAll("latex").forEach((element) => {
    globalThis.katex.render(element.textContent, element, {
      displayMode: element.dataset.display === "true",
      throwOnError: false,
    });
  });
}

function renderLatexText(container) {
  globalThis.renderMathInElement(container, {
    throwOnError: false,
    errorCallback: () => {},
  });
}

function convertImgFilePaths(str) {
  return str.replace(/img:\/\//g, "/api/image_get?path=");
}

function convertFilePaths(str) {
  return str.replace(/file:\/\//g, "/api/download_work_dir_file?path=");
}

function escapeHTML(str) {
  const escapeChars = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "'": "&#39;",
    '"': "&quot;",
  };
  return str.replace(/[&<>'"]/g, (char) => escapeChars[char]);
}

function convertPathsToLinks(str) {
  function generateLinks(match, path) {
    const parts = path.split("/");
    if (!parts[0]) parts.shift(); // drop empty element left of first "
    let conc = "";
    let html = "";
    for (const part of parts) {
      conc += "/" + part;
      html += `/<a href="#" class="path-link" data-path="${conc}" onclick="event.preventDefault(); openFileLink(this.dataset.path);">${part}</a>`;
    }
    return html;
  }

  const prefix = `(?:^|[> \`'"\\n]|&#39;|&quot;)`;
  const pathPart = `[a-zA-Z0-9_.~@%+=,()\\-]+(?: [a-zA-Z0-9_.~@%+=,()\\-]+)*`;
  const spacedFilePath = `\\/(?:${pathPart}\\/)*${pathPart}\\.[a-zA-Z0-9]{1,12}`;
  const folder = `[a-zA-Z0-9_\\/.\\-]`;
  const file = `[a-zA-Z0-9_\\-\\/]`;
  const simplePath = `\\/${folder}*${file}(?<!\\.)`;
  const suffix = `(?=$|[\\s.,;:!?\\)\\]\\}]|&#39;|&quot;)`;
  const pathRegex = new RegExp(
    `(?<=${prefix})(?:file:\\/\\/|\\/api\\/download_work_dir_file\\?path=)?(${spacedFilePath}|${simplePath})${suffix}`,
    "g",
  );

  // Preserve existing links and code blocks as well as HTML attributes.
  const tagRegex = /(<a\b[^>]*>[\s\S]*?<\/a>|<pre\b[^>]*>[\s\S]*?<\/pre>|<(?:[^<>"']+|"[^"]*"|'[^']*')*>)/gi;

  return str
    .split(tagRegex) // keep tags & text separate
    .map((chunk) => {
      // if it *starts* with '<', it's a tag -> leave untouched
      if (chunk.startsWith("<")) return chunk;
      // otherwise run your link-generation
      return chunk.replace(pathRegex, generateLinks);
    })
    .join("");
}

// markdown render helpers //

// wraps an element with a container div
const wrapElement = (el, className) => {
  const wrapper = document.createElement("div");
  wrapper.className = className;
  el.parentNode.insertBefore(wrapper, el);
  wrapper.appendChild(el);
  return wrapper;
};

// data extractors
const extractTableTSV = (table) =>
  [...table.rows]
    .map((row) =>
      [...row.cells]
        .map((cell) =>
          cell.textContent.replace(/\t/g, "  ").replace(/\n/g, " "),
        )
        .join("\t"),
    )
    .join("\n");

function adjustMarkdownRender(element) {
  // find all tables in the element
  const tables = element.querySelectorAll("table");
  tables.forEach((el) => {
    const wrapper = wrapElement(el, "message-markdown-table-wrap");
    const outerWrapper = wrapElement(wrapper, "markdown-block-wrap");
    const actionsDiv = document.createElement("div");
    actionsDiv.className = "step-action-buttons";
    actionsDiv.appendChild(
      createActionButton("copy", "", () =>
        copyToClipboard(extractTableTSV(el)),
      ),
    );
    outerWrapper.appendChild(actionsDiv);
  });

  // find all code blocks
  const codeElements = element.querySelectorAll("pre > code");
  codeElements.forEach((code) => {
    const pre = code.parentNode;
    const wrapper = wrapElement(pre, "code-block-wrapper");
    const outerWrapper = wrapElement(wrapper, "markdown-block-wrap");
    const actionsDiv = document.createElement("div");
    actionsDiv.className = "step-action-buttons";
    actionsDiv.appendChild(
      createActionButton("copy", "", () => copyToClipboard(code.textContent)),
    );
    outerWrapper.appendChild(actionsDiv);
  });

  // find all images
  const images = element.querySelectorAll("img");

  // wrap each image in <a>
  images.forEach((img) => {
    if (img.parentNode?.tagName === "A") return;
    const link = document.createElement("a");
    link.className = "message-markdown-image-wrap";
    link.href = img.src;
    img.parentNode.insertBefore(link, img);
    link.appendChild(img);
    link.onclick = (e) => (
      e.preventDefault(),
      imageViewerStore.open(img.src, { name: img.alt || "Image" })
    );
  });
}

/**
 * Create a new collapsible process group
 */
function createProcessGroup(id) {
  const groupId = `process-group-${id}`;
  const group = document.createElement("div");
  group.id = groupId;
  group.classList.add("process-group");
  group.setAttribute("data-group-id", groupId);

  // Determine initial expansion state from current detail mode
  const initiallyExpanded = preferencesStore.detailMode !== "collapsed";
  if (initiallyExpanded) {
    group.classList.add("expanded");
  }

  // Create header
  const header = document.createElement("div");
  header.classList.add("process-group-header");
  header.innerHTML = `
    <span class="expand-icon"></span>
    <span class="group-title">Processing...</span>
    <span class="step-badge GEN">GEN</span>
    <span class="group-metrics">
      <span class="metric-time" title="Start time"><x-icon name="schedule"></x-icon><span class="metric-value">--:--</span></span>
      <span class="metric-steps display-none" title="Steps"><x-icon name="footprint"></x-icon><span class="metric-value">0</span></span>
      <span class="metric-notifications" title="Warnings/Info/Hint" hidden><x-icon name="priority_high"></x-icon><span class="metric-value">0</span></span>
      <span class="metric-duration display-none" title="Duration"><x-icon name="timer"></x-icon><span class="metric-value">--</span></span>

    </span>
  `;

  group.__setExpanded = (expanded) => {
    const nextExpanded = Boolean(expanded);
    group.classList.toggle("expanded", nextExpanded);
    const steps = group.querySelectorAll(".process-step");
    if (nextExpanded) {
      steps.forEach((step) => {
        if (
          step.classList.contains("expanded") &&
          !step.querySelector(".process-step-detail-scroll")
        ) {
          void materializeProcessStepDetail(step);
        }
      });
    } else {
      steps.forEach((step) =>
        discardProcessStepDetail(step, { force: true }),
      );
    }
  };

  // Add click handler for expansion
  header.addEventListener("click", () => {
    group.__setExpanded(!group.classList.contains("expanded"));
  });

  group.appendChild(header);

  // Create content container
  const content = document.createElement("div");
  content.classList.add("process-group-content");

  // Create steps container
  const steps = document.createElement("div");
  steps.classList.add("process-steps");
  content.appendChild(steps);

  group.appendChild(content);

  return group;
}

/**
 * Create or get nested container within a parent step
 */
function getNestedContainer(parentStep) {
  let nestedContainer = parentStep.querySelector(".process-nested-container");

  if (!nestedContainer) {
    // Create new container
    nestedContainer = document.createElement("div");
    nestedContainer.classList.add("process-nested-container");

    // Create inner wrapper for animation support
    const innerWrapper = document.createElement("div");
    innerWrapper.classList.add("process-nested-inner");
    nestedContainer.appendChild(innerWrapper);

    parentStep.appendChild(nestedContainer);
    parentStep.classList.add("has-nested-steps");
  }

  // Return the inner wrapper for appending steps
  const innerWrapper = nestedContainer.querySelector(".process-nested-inner");
  return innerWrapper || nestedContainer; // Fallback to container if wrapper missing
}

/**
 * Schedule a step to collapse after a delay
 * Automatically handles cancellation on click and reset on hover
 */
function scheduleStepCollapse(
  stepElement,
  delayMs = STEP_COLLAPSE_DELAY.other,
) {
  // skip if any existing timeout for this step
  if (stepElement.hasAttribute("data-collapse-timeout-id")) return;
  // skip already collapsed steps
  if (!stepElement.classList.contains("expanded")) return;

  // Schedule the collapse
  const timeoutId = setTimeout(() => {
    stepElement.removeAttribute("data-collapse-timeout-id");

    if (stepElement.dataset.clicked === "true") {
      console.log(`Skip clicked collapse: ${stepElement.id}`);
      return;
    }

    if (stepElement.matches(":hover")) {
      console.log(`Delay hover collapse: ${stepElement.id}`);
      scheduleStepCollapse(stepElement, STEP_COLLAPSE_HOVER_DELAY_MS);
      return;
    }

    console.log(`Collapse step: ${stepElement.id}`);
    toggleStepCollapse(stepElement, false);
  }, delayMs);

  // Store the timeout ID
  stepElement.setAttribute("data-collapse-timeout-id", String(timeoutId));
}

function setupProcessStepHandlers(stepElement, stepHeader) {
  if (!stepElement.hasAttribute("data-step-handlers")) {
    stepElement.setAttribute("data-step-handlers", "true");

    stepElement.addEventListener(
      "click",
      function handler() {
        stepElement.dataset.clicked = "true";
        console.log(`Step clicked: ${stepElement.id}`);
      },
      { once: true },
    );
  }

  if (stepHeader && !stepHeader.hasAttribute("data-expand-handler")) {
    stepHeader.setAttribute("data-expand-handler", "true");
    stepHeader.addEventListener("click", (e) => {
      e.stopPropagation();
      cancelStepCollapse(stepElement);
      stepElement.dataset.clicked = "true";
      toggleStepCollapse(stepElement);
    });
  }
}

/**
 * Cancel a scheduled collapse for a step
 */
function cancelStepCollapse(stepElement) {
  const timeoutIdStr = stepElement.getAttribute("data-collapse-timeout-id");
  if (!timeoutIdStr) return;
  const timeoutId = Number(timeoutIdStr);
  if (!Number.isNaN(timeoutId)) clearTimeout(timeoutId);
  stepElement.removeAttribute("data-collapse-timeout-id");
}

/**
 * Find parent delegation step for nested agents (DOM-first, reverse scan).
 */
function findParentDelegationStep(group, agentno) {
  if (!group || !agentno || agentno <= 0) return null;
  const steps = group.querySelectorAll(".process-step");
  for (let i = steps.length - 1; i >= 0; i -= 1) {
    const step = steps[i];
    const stepAgent = Number(step.getAttribute("data-agent-number"));
    if (
      stepAgent === agentno - 1 &&
      step.getAttribute("data-log-type") === "subagent" // map to the last tool call of superior agent
    ) {
      return step;
    }
  }
  return null;
}

/**
 * Get a concise title for a process step
 */
function getStepTitle(heading, content, type) {
  // Try to get a meaningful title from heading or kvps
  if (heading && heading.trim()) {
    return cleanStepTitle(heading, 60);
  }

  if (content && content.trim()) {
    return cleanStepTitle(content, 60);
  }

  // Fallback: capitalize type (backend is source of truth)
  return type
    ? type.charAt(0).toUpperCase() + type.slice(1).replace(/_/g, " ")
    : "Process";
}

/**
 * Convert icon://name[Optional Tooltip] into a material icon span.
 * Tooltip supports escaped brackets inside, e.g. [Tooltip of \[brackets\]].
 */
export function convertIcons(html, classes = "") {
  if (html == null) return "";

  return String(html).replace(
    /icon:\/\/([a-zA-Z0-9_]+)(\[(?:\\.|[^\]])*\])?/g,
    (match, iconName, tooltipBlock) => {
      if (!tooltipBlock) {
        return `<x-icon class="icon ${classes}" name="${iconName}"></x-icon>`;
      }

      const tooltipRaw = tooltipBlock
        .slice(1, -1)
        .replace(/\\\[/g, "[")
        .replace(/\\\]/g, "]")
        .replace(/\\\\/g, "\\");

      const tooltip = escapeHTML(tooltipRaw);

      return `<x-icon class="icon ${classes}" title="${tooltip}" data-bs-placement="top" data-bs-trigger="hover" name="${iconName}"></x-icon>`;
    },
  );
}

/**
 * Clean step title by removing icon:// prefixes and status phrases
 * Preserves agent markers (A1:, A2:, etc.) so users can see which subordinate agent is executing
 */
export function cleanStepTitle(text, maxLength = 100) {
  if (!text) return "";
  let cleaned = String(text)
    .replace(/icon:\/\/[a-zA-Z0-9_]+(\[(?:\\.|[^\]])*\])?\s*/g, "")
    .replace(/\s+/g, " ")
    .trim();
  return truncateText(cleaned, maxLength);
}

/**
 * Update process group header with step count, status, and metrics
 */
function updateProcessGroupHeader(group) {
  const header = group.querySelector(".process-group-header");
  const steps = group.querySelectorAll(".process-step");
  const titleEl = header.querySelector(".group-title");
  const badgeEl = header.querySelector(".step-badge");
  const metricsEl = header.querySelector(".group-metrics");
  const isCompleted = isProcessGroupComplete(group);
  const notificationsEl = metricsEl?.querySelector(".metric-notifications");

  // Update group title with the latest agent step heading
  if (titleEl) {
    // Find the last "agent" type step
    const agentSteps = Array.from(steps).filter(
      (step) => step.getAttribute("data-log-type") === "agent",
    );
    if (agentSteps.length > 0) {
      const lastAgentStep = agentSteps[agentSteps.length - 1];
      const lastHeading =
        lastAgentStep.querySelector(".step-title")?.textContent;
      if (lastHeading) {
        const cleanTitle = cleanStepTitle(lastHeading, 50);
        if (cleanTitle) {
          titleEl.textContent = cleanTitle;
        }
      }
    }
  }

  // If completed, set badge to END
  if (isCompleted) {
    // set end badge
    badgeEl.outerHTML = `<span class="step-badge END">END</span>`;
    // remove shine from any steps
    group.querySelectorAll(".step-title.shiny-text").forEach((el) => {
      el.classList.remove("shiny-text");
    });
  } else {
    // if not complete, clone the last step badge
    if (badgeEl && steps.length > 0) {
      const lastStep = steps[steps.length - 1];
      const code = lastStep.getAttribute("data-step-code");
      badgeEl.outerHTML = `<span class="step-badge ${code}">${code}</span>`;
    }
  }

  // Update step count in metrics - All GEN steps from all agents per process group
  const stepMetricContainerEl = metricsEl?.querySelector(".metric-steps");
  const stepsMetricValEl =
    stepMetricContainerEl?.querySelector(".metric-value");
  if (stepsMetricValEl) {
    let genSteps = Number(group.dataset.fullAgentSteps);
    if (!Number.isFinite(genSteps)) {
      genSteps = group.querySelectorAll(
        '.process-step[data-log-type="agent"]',
      ).length;
      genSteps -= 1; // don't count response as step
    }
    stepsMetricValEl.textContent = genSteps.toString();
    if (genSteps <= 0)
      stepMetricContainerEl.classList.add("display-none"); // hide when no steps
    else stepMetricContainerEl.classList.remove("display-none");
  }

  // Update time metric
  const timeMetricContainerEl = metricsEl?.querySelector(".metric-time");
  const timeMetricEl = metricsEl?.querySelector(".metric-time .metric-value");
  const startTimestamp = group.getAttribute("data-start-timestamp");
  if (timeMetricEl && startTimestamp) {
    const date = new Date(parseFloat(startTimestamp) * 1000);
    const hour12 = getUserHour12();
    timeMetricEl.textContent = new Intl.DateTimeFormat(undefined, {
      hour: hour12 ? "numeric" : "2-digit",
      minute: "2-digit",
      hour12,
      timeZone: getUserTimezone(),
    }).format(date);
    if (timeMetricContainerEl) {
      const fullDateTime = formatDateTime(date.toISOString(), "short");
      timeMetricContainerEl.title =
        timeMetricContainerEl.dataset.bsOriginalTitle = fullDateTime;
    }
  }

  const firstTimestampMs = group.dataset.fullStartTimestamp
    ? Math.round(Number(group.dataset.fullStartTimestamp) * 1000)
    : parseInt(steps[0]?.getAttribute("data-timestamp") || "0", 10);
  const lastTimestampMs = group.dataset.fullEndTimestamp
    ? Math.round(Number(group.dataset.fullEndTimestamp) * 1000)
    : parseInt(
      steps[steps.length - 1]?.getAttribute("data-timestamp") || "0",
      10,
    );
  const durationText =
    isCompleted &&
    metricsEl &&
    steps.length > 0 &&
    firstTimestampMs > 0 &&
    lastTimestampMs > 0 &&
    formatDuration(Math.max(0, lastTimestampMs - firstTimestampMs));

  const durationMetricContainerEl =
    metricsEl?.querySelector(".metric-duration");
  const durationMetricValEl =
    durationMetricContainerEl?.querySelector(".metric-value");
  if (durationMetricContainerEl && durationMetricValEl && durationText) {
    durationMetricValEl.textContent = durationText;
    durationMetricContainerEl.classList.remove("display-none");
  } else if (durationMetricContainerEl) {
    durationMetricContainerEl.classList.add("display-none");
  }

  if (notificationsEl) {
    const fullWarningSteps = Number(group.dataset.fullWarningSteps);
    const fullInfoSteps = Number(group.dataset.fullInfoSteps);
    const counts = Number.isFinite(fullWarningSteps) &&
        Number.isFinite(fullInfoSteps)
      ? { warning: fullWarningSteps, info: fullInfoSteps }
      : { warning: 0, info: 0 };
    if (!Number.isFinite(fullWarningSteps) || !Number.isFinite(fullInfoSteps)) {
      steps.forEach((step) => {
        const stepType = step.getAttribute("data-log-type");
        if (Object.prototype.hasOwnProperty.call(counts, stepType)) {
          counts[stepType] += 1;
        }
      });
    }

    const totalNotifications = counts.warning + counts.info;
    const countEl = notificationsEl.querySelector(".metric-value");
    notificationsEl.classList.remove("status-wrn", "status-inf");

    if (totalNotifications > 0) {
      if (countEl) {
        countEl.textContent = totalNotifications.toString();
      }
      if (counts.warning > 0) {
        notificationsEl.classList.add("status-wrn");
      } else if (counts.info > 0) {
        notificationsEl.classList.add("status-inf");
      }
      notificationsEl.hidden = false;
      notificationsEl.title = `Warnings: ${counts.warning}, Info: ${counts.info}`;
    } else {
      notificationsEl.hidden = true;
    }
  }
}

function isProcessGroupComplete(group) {
  // manually closed group
  if (group?.hasAttribute?.("data-group-complete")) return true;
  // naturally completed group
  const response = group.querySelector(".process-group-response");
  return !!response;
}

// manually complete last process group
export function completeLastProcessGroup() {
  const group = getLastProcessGroup();
  if (!group || isProcessGroupComplete(group)) return;
  group.setAttribute("data-group-complete", "true");
  updateProcessGroupHeader(group);
}

function getStepProcessGroup(step) {
  return step?.closest(".process-group");
}

/**
 * Truncate text to a maximum length
 */
function truncateText(text, maxLength) {
  if (!text) return "";
  text = String(text).trim();
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength - 3) + "...";
}

// gets or creates a child DOM element
/**
 * @param {Element} parent
 * @param {string} selector
 * @param {string} tagName
 * @param {...string} classNames
 * @returns {HTMLElement}
 */
function ensureChild(parent, selector, tagName, ...classNames) {
  /** @type {HTMLElement | null} */
  let el = /** @type {any} */ (parent.querySelector(selector));
  if (!el) {
    el = document.createElement(tagName);
    if (classNames.length) el.classList.add(...classNames);
    parent.appendChild(el);
  }
  return el;
}

// Setup collapsible message with expand button and action buttons
function setupCollapsible(
  messageDiv,
  containerSelector,
  initialExpanded,
  actionButtons = [],
  contentSelector = ":scope > .message-body",
) {
  messageDiv.classList.add("message-collapsible");
  messageDiv
    .querySelectorAll(":scope > .message-collapse-content")
    .forEach((element) => element.classList.remove("message-collapse-content"));
  const collapseContent = messageDiv.querySelector(contentSelector);
  collapseContent?.classList.add("message-collapse-content");
  const initialState =
    Boolean(initialExpanded) && !messageDiv.classList.contains("lazy-content");
  messageDiv.classList.toggle("expanded", initialState);

  const container = ensureChild(
    messageDiv,
    containerSelector,
    "div",
    "step-action-buttons",
  );
  const btn = ensureChild(container, ".expand-btn", "button", "expand-btn");
  const syncBtn = () => {
    const exp = messageDiv.classList.contains("expanded");
    btn.textContent = exp ? "Show less" : "Show more";
    btn.classList.toggle("show-less-btn", exp);
    btn.classList.toggle("show-more-btn", !exp);
  };
  const setExpanded = (expanded) => {
    const nextExpanded = Boolean(expanded);
    messageDiv.classList.toggle("expanded", nextExpanded);
    messageDiv.__renderLazyContent?.(nextExpanded);
    syncBtn();
    if (!nextExpanded) {
      if (collapseContent) collapseContent.scrollTop = 0;
    }
  };
  messageDiv.__setExpanded = setExpanded;
  setExpanded(initialState);
  btn.onclick = () =>
    setExpanded(!messageDiv.classList.contains("expanded"));

  syncActionButtons(container, actionButtons);

  const refreshOverflow = () => {
    const hasOverflow = measureMessageCollapseOverflow(collapseContent, {
      expanded: messageDiv.classList.contains("expanded"),
      lazy: messageDiv.classList.contains("lazy-content"),
    });
    if (hasOverflow === null) return false;
    messageDiv.classList.toggle("has-overflow", hasOverflow);
    return true;
  };
  messageDiv.__refreshCollapseOverflow = refreshOverflow;

  // Detect overflow after render. Window replays are measured again after the
  // staged DOM has moved into the live, correctly sized chat history.
  requestAnimationFrame(() => {
    if (messageDiv.__refreshCollapseOverflow === refreshOverflow) {
      refreshOverflow();
    }
  });
}

function refreshCollapsibleMessageOverflow(root) {
  if (!root) return;
  const messages = root.matches?.(".message-collapsible")
    ? [root]
    : root.querySelectorAll?.(".message-collapsible") || [];
  messages.forEach((message) => {
    if (typeof message.__refreshCollapseOverflow === "function") {
      message.__refreshCollapseOverflow();
    }
  });
}

// returns true if this is the initial render of a chat eg. when reloading window, switching chat or catching up after a break
// returns false when already in a rendered chat and adding messages regurarly
function isMassRender() {
  return _massRender;
}

// smooth fade in animation for new chunks when streaming
function smoothRender(element, newContent, delay = 350) {
  // skip on mass render
  if (isMassRender()) {
    element.innerHTML = newContent;
    return;
  }

  element.dataset.smoothPendingHtml = newContent;

  if (element.dataset.smoothTimeoutId) return;

  const timeoutId = window.setTimeout(() => {
    const pending = element.dataset.smoothPendingHtml || "";
    delete element.dataset.smoothPendingHtml;
    delete element.dataset.smoothTimeoutId;

    const existing = element.querySelector(
      ":scope > div.smooth-render-visible",
    );
    if (existing) {
      existing.classList.remove("smooth-render-visible");
      existing.classList.add("smooth-render-invisible");

      existing.addEventListener("animationend", () => existing.remove(), {
        once: true,
      });
    }

    const nextLayer = document.createElement("div");
    nextLayer.className = "smooth-render-visible";
    nextLayer.innerHTML = pending;
    element.appendChild(nextLayer);

    // Keep container height stable while layers are absolute
    element.style.height = `${nextLayer.scrollHeight}px`;
  }, delay);

  element.dataset.smoothTimeoutId = String(timeoutId);
}
