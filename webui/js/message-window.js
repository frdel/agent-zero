const DEFAULT_INITIAL_LIMIT = 60;
const DEFAULT_PAGE_SIZE = 60;
const DEFAULT_MAX_WINDOW = DEFAULT_PAGE_SIZE * 2;

function compareRecords(a, b) {
  const aNo = getRecordOrder(a.message);
  const bNo = getRecordOrder(b.message);
  return aNo - bNo || a.sequence - b.sequence;
}

function getRecordOrder(message) {
  const rawNo = message?.no;
  return rawNo !== undefined && rawNo !== null && Number.isFinite(Number(rawNo))
    ? Number(rawNo)
    : Number.MAX_SAFE_INTEGER;
}

export function getMessageCacheKey(message) {
  const id = message?.id;
  if (id !== undefined && id !== null && String(id) !== "") {
    // A root agent's final GEN record and its response intentionally share an
    // id, but they are separate log entries and both must survive replay.
    // Including the type still lets optimistic user messages merge with their
    // backend update while keeping that GEN/response pair distinct.
    const type = String(message?.type || "unknown");
    return `id:${String(id)}:type:${type}`;
  }

  const no = message?.no;
  if (no !== undefined && no !== null && String(no) !== "") {
    return `no:${String(no)}`;
  }

  return null;
}

export const PROCESS_STEP_TYPES = new Set([
  "agent",
  "tool",
  "mcp",
  "subagent",
  "info",
]);

function hasUpcomingProcessStep(messages, startIndex, processStepTypes) {
  for (let index = startIndex + 1; index < messages.length; index++) {
    const message = messages[index];
    const type = String(message?.type || "");
    if (type === "util") continue;
    if (processStepTypes.has(type)) return true;
    if (type === "warning" || type === "rate_limit") return true;
    if (type === "response" && Number(message?.agentno || 0) > 0) {
      return true;
    }
    return false;
  }
  return false;
}

/**
 * Classifies raw log entries into the same logical units that the message DOM
 * renderer creates. Window boundaries use these units so plugin-backed steps
 * such as code execution cannot split an otherwise contiguous process group.
 */
export function classifyMessageRenderUnits(messages = [], processStepTypes = PROCESS_STEP_TYPES) {
  let activeGroup = null;
  let lastGroup = null;
  let lastUnitType = null;

  const startGroup = (message, index) => {
    const rawIdentity = message?.id !== undefined && message?.id !== null &&
        String(message.id) !== ""
      ? message.id
      : message?.no !== undefined && message?.no !== null
      ? message.no
      : `anonymous-${index}`;
    const identity = String(rawIdentity);
    return { id: identity, key: `process:${identity}`, complete: false };
  };
  const assignGroup = (group, isStep) => {
    lastGroup = group;
    lastUnitType = "process";
    return { key: group.key, group, isStep };
  };

  return messages.map((message, index) => {
    const type = String(message?.type || "");
    const standalone = {
      key: `entry:${getMessageCacheKey(message) || index}`,
      group: null,
      isStep: false,
    };

    if (processStepTypes.has(type)) {
      activeGroup ||= startGroup(message, index);
      const unit = assignGroup(activeGroup, true);
      if (type === "info" && message?.kvps?.finished) {
        activeGroup.complete = true;
        activeGroup = null;
      }
      return unit;
    }

    if (type === "util") {
      if (activeGroup || hasUpcomingProcessStep(messages, index, processStepTypes)) {
        activeGroup ||= startGroup(message, index);
        return assignGroup(activeGroup, true);
      }

      // Utilities on their own must not manufacture a visible process group
      // around a root response. They remain standalone until a real process
      // step appears, and post-response utilities cannot reopen the group.
      activeGroup = null;
      lastUnitType = "standalone";
      return standalone;
    }

    if (type === "response" && Number(message?.agentno || 0) > 0) {
      activeGroup ||= startGroup(message, index);
      return assignGroup(activeGroup, true);
    }

    if (
      type === "response" &&
      (activeGroup || (lastUnitType === "process" && lastGroup))
    ) {
      const group = activeGroup || lastGroup;
      const unit = assignGroup(group, false);
      group.complete = true;
      activeGroup = null;
      return unit;
    }

    if ((type === "warning" || type === "rate_limit") && activeGroup) {
      return assignGroup(activeGroup, true);
    }

    activeGroup = null;
    lastUnitType = "standalone";
    return standalone;
  });
}

/**
 * Keeps the complete raw log in JavaScript while exposing a bounded contiguous
 * slice for DOM rendering. The class deliberately has no DOM dependencies so
 * window selection can be tested independently from message handlers.
 */
export class MessageWindow {
  constructor({
    initialLimit = DEFAULT_INITIAL_LIMIT,
    pageSize = DEFAULT_PAGE_SIZE,
    maxWindow = DEFAULT_MAX_WINDOW,
    getUnitKeys = null,
  } = {}) {
    this.initialLimit = Math.max(1, initialLimit);
    this.pageSize = Math.max(1, pageSize);
    this.maxWindow = Math.max(this.initialLimit, maxWindow);
    this.getUnitKeys = typeof getUnitKeys === "function" ? getUnitKeys : null;
    this.reset([]);
  }

  reset(messages = []) {
    this._recordsByKey = new Map();
    this._indexByKey = new Map();
    this._records = [];
    this._nextSequence = 0;
    this._nextAnonymous = 0;
    this.start = 0;
    this.end = 0;
    this.merge(messages);
    this.showTail();
  }

  merge(messages = [], { followTail = true } = {}) {
    const previousStartKey = this._records[this.start]?.key || null;
    const previousEndKey = this._records[this.end - 1]?.key || null;
    const wasAtTail = followTail && this.end >= this._records.length;
    const addedKeys = new Set();
    let requiresSort = false;

    for (const message of Array.isArray(messages) ? messages : []) {
      if (!message) continue;
      const key = getMessageCacheKey(message) ||
        `anonymous:${this._nextAnonymous++}`;
      const existing = this._recordsByKey.get(key);
      if (existing) {
        requiresSort ||=
          getRecordOrder(existing.message) !== getRecordOrder(message);
        existing.message = message;
      } else {
        const record = {
          key,
          message,
          sequence: this._nextSequence++,
        };
        const previous = this._records[this._records.length - 1];
        if (previous && compareRecords(previous, record) > 0) {
          requiresSort = true;
        }
        this._recordsByKey.set(key, record);
        this._indexByKey.set(key, this._records.length);
        this._records.push(record);
        addedKeys.add(key);
      }
    }

    if (requiresSort) {
      this._records.sort(compareRecords);
      this._rebuildIndexes();
    }
    this._rebuildRenderUnits();

    if (!previousStartKey || !this._records.length) {
      this.showTail();
    } else if (wasAtTail) {
      const previousStart = this._indexOf(previousStartKey);
      this.start = previousStart >= 0
        ? previousStart
        : Math.max(0, this._records.length - this.initialLimit);
      this.end = this._records.length;
    } else {
      const previousStart = this._indexOf(previousStartKey);
      const previousEnd = this._indexOf(previousEndKey);
      this.start = previousStart >= 0 ? previousStart : this.start;
      this.end = previousEnd >= 0 ? previousEnd + 1 : this.end;
      this._clampBounds();
    }
    return addedKeys;
  }

  showTail() {
    this.end = this._records.length;
    this.start = Math.max(0, this.end - this.initialLimit);
  }

  showHead() {
    this.start = 0;
    this.end = Math.min(this._records.length, this.initialLimit);
  }

  compactTailIfNeeded() {
    if (!this.isAtTail() || this.baseRenderedCount <= this.maxWindow) {
      return false;
    }
    this.end = this._records.length;
    this.start = Math.max(0, this.end - this.maxWindow);
    return true;
  }

  shiftOlder() {
    if (!this.hasOlder) return false;
    const previous = this._getVisibleBounds(this.start, this.end);
    let nextStart = Math.max(0, this.start - this.pageSize);
    let nextEnd = Math.min(this._records.length, nextStart + this.maxWindow);
    const next = this._getVisibleBounds(nextStart, nextEnd);
    if (
      next.start === previous.start &&
      next.end === previous.end &&
      previous.start > 0
    ) {
      nextStart = Math.max(0, previous.start - this.pageSize);
      nextEnd = Math.min(this._records.length, nextStart + this.maxWindow);
    }
    this.start = nextStart;
    this.end = nextEnd;
    this._clampBounds();
    return true;
  }

  shiftNewer() {
    if (!this.hasNewer) return false;
    const previous = this._getVisibleBounds(this.start, this.end);
    let nextEnd = Math.min(this._records.length, this.end + this.pageSize);
    let nextStart = Math.max(0, nextEnd - this.maxWindow);
    const next = this._getVisibleBounds(nextStart, nextEnd);
    if (
      next.start === previous.start &&
      next.end === previous.end &&
      previous.end < this._records.length
    ) {
      nextEnd = Math.min(
        this._records.length,
        previous.end + this.pageSize,
      );
      nextStart = Math.max(0, nextEnd - this.maxWindow);
    }
    this.start = nextStart;
    this.end = nextEnd;
    this._clampBounds();
    return true;
  }

  visibleMessages() {
    const bounds = this._getVisibleBounds(this.start, this.end);
    return this._records.slice(bounds.start, bounds.end).map((record) =>
      record.message
    );
  }

  isKeyVisible(key) {
    if (!key) return false;
    const index = this._indexOf(key);
    const bounds = this._getVisibleBounds(this.start, this.end);
    return index >= bounds.start && index < bounds.end;
  }

  isAtTail() {
    return this.visibleEnd >= this._records.length;
  }

  get size() {
    return this._records.length;
  }

  get messageTypes() {
    return new Set(this._records.map(({ message }) => String(message.type || "")));
  }

  get renderedCount() {
    return Math.max(0, this.visibleEnd - this.visibleStart);
  }

  get baseRenderedCount() {
    return Math.max(0, this.end - this.start);
  }

  get visibleStart() {
    return this._getVisibleBounds(this.start, this.end).start;
  }

  get visibleEnd() {
    return this._getVisibleBounds(this.start, this.end).end;
  }

  get hasOlder() {
    return this.visibleStart > 0;
  }

  get hasNewer() {
    return this.visibleEnd < this._records.length;
  }

  get olderCount() {
    return this.visibleStart;
  }

  get newerCount() {
    return Math.max(0, this._records.length - this.visibleEnd);
  }

  _indexOf(key) {
    if (!key) return -1;
    return this._indexByKey.get(key) ?? -1;
  }

  _rebuildIndexes() {
    this._indexByKey.clear();
    this._records.forEach((record, index) => {
      this._indexByKey.set(record.key, index);
    });
  }

  _rebuildRenderUnits() {
    const messages = this._records.map((record) => record.message);
    const suppliedKeys = this.getUnitKeys?.(messages);
    const unitKeys = Array.isArray(suppliedKeys) &&
        suppliedKeys.length === messages.length
      ? suppliedKeys
      : messages.map((_, index) => index);

    this._unitStartByIndex = new Array(messages.length);
    this._unitEndByIndex = new Array(messages.length);
    let start = 0;
    while (start < unitKeys.length) {
      let end = start + 1;
      while (end < unitKeys.length && unitKeys[end] === unitKeys[start]) end++;
      for (let index = start; index < end; index++) {
        this._unitStartByIndex[index] = start;
        this._unitEndByIndex[index] = end;
      }
      start = end;
    }
  }

  _getVisibleBounds(start, end) {
    if (!this._records.length || end <= start) return { start, end };
    return {
      start: this._unitStartByIndex?.[start] ?? start,
      end: this._unitEndByIndex?.[end - 1] ?? end,
    };
  }

  _clampBounds() {
    this.start = Math.max(0, Math.min(this.start, this._records.length));
    this.end = Math.max(this.start, Math.min(this.end, this._records.length));
  }
}
