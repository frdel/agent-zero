/** Private modal state. The API is injected so race and retry rules are testable. */
export function createDurabilityState(api, uuid = () => crypto.randomUUID()) {
  const copy = (value) => JSON.parse(JSON.stringify(value));
  const message = (error) => {
    let data = error;
    if (error instanceof Error) {
      try { data = JSON.parse(error.message); } catch { data = { error: error.message }; }
    }
    return typeof data === "object" && data ? data : { error: String(data) };
  };
  return {
    mounted: false, loading: false, documentLoading: false, busy: false,
    available: false, enabled: false, restore: { required: false, epoch: null },
    runs: [], nextOffset: null, totalRuns: 0, context: "", error: "", notice: "", requiredIds: [], selected: [],
    pending: null, decisionRetry: null, queuedDecisions: [], document: null, draft: null, draftRevision: 0, dirty: false,
    draftStale: false, compared: false, documentError: "", filter: "all",
    _generation: 0, _documentGeneration: 0, _mutationGeneration: 0, _scope: 0, _chatSelection: "", _requests: {},

    async mount(context = "") {
      this.mounted = true; this._scope++;
      this.decisionRetry = null; this.queuedDecisions = [];
      this.context = String(context || ""); this._chatSelection = this.context;
      await Promise.all([this.refresh(), this.loadDocument()]);
    },
    close() {
      this.mounted = false; this._scope++; this._mutationGeneration++;
      this._chatSelection = "";
      this._generation++;
      this._documentGeneration++;
      this.runs = []; this.document = null; this.draft = null; this.pending = null; this.decisionRetry = null;
      this.nextOffset = null; this.totalRuns = 0;
      this.available = false; this.enabled = false; this.restore = { required: false, epoch: null };
      this.context = ""; this.selected = []; this.requiredIds = [];
      this.error = ""; this.notice = ""; this.documentError = "";
      this.dirty = false; this.draftStale = false; this.compared = false;
      this.loading = false; this.documentLoading = false; this.busy = false;
      this._requests = {}; this.queuedDecisions = [];
    },
    async refresh() {
      const generation = ++this._generation, scope = this._scope;
      const target = Math.max(50, this.runs.length);
      this.loading = true;
      try {
        let data, offset = 0, next = null;
        const rows = new Map();
        do {
          data = await api({ action: "status", offset });
          if (!this.mounted || generation !== this._generation || scope !== this._scope) return;
          for (const run of Array.isArray(data.runs) ? data.runs : []) rows.set(run.run_id, run);
          next = Number.isInteger(data.next_offset) && data.next_offset > offset ? data.next_offset : null;
          offset = next;
        } while (next !== null && rows.size < target);
        this.available = !!data.available; this.enabled = !!data.enabled;
        this.restore = data.restore || { required: false, epoch: null };
        this.runs = [...rows.values()]; this.nextOffset = next;
        this.totalRuns = Number.isInteger(data.total) ? data.total : this.runs.length;
        const visible = new Set(this.runs.filter((run) => !run.restore_selected && ["running", "blocked", "attention"].includes(run.status)).map((run) => run.run_id));
        this.selected = this.selected.filter((id) => visible.has(id));
        await this.refreshQueued(scope, generation);
      } catch (error) {
        if (this.mounted && generation === this._generation && scope === this._scope) this.error = this.errorText(error);
      } finally {
        if (generation === this._generation) this.loading = false;
      }
    },
    async loadMore() {
      if (!this.mounted || this.loading || this.busy || this.nextOffset === null) return;
      const generation = ++this._generation, scope = this._scope, offset = this.nextOffset;
      this.loading = true;
      try {
        const data = await api({ action: "status", offset });
        if (!this.mounted || generation !== this._generation || scope !== this._scope) return;
        if (data.restore?.epoch !== this.restore.epoch) { await this.refresh(); return; }
        const rows = new Map(this.runs.map((run) => [run.run_id, run]));
        for (const run of Array.isArray(data.runs) ? data.runs : []) rows.set(run.run_id, run);
        this.runs = [...rows.values()];
        this.nextOffset = Number.isInteger(data.next_offset) && data.next_offset > offset ? data.next_offset : null;
        this.totalRuns = Number.isInteger(data.total) ? data.total : this.runs.length;
      } catch (error) {
        if (this.mounted && generation === this._generation && scope === this._scope) this.error = this.errorText(error);
      } finally {
        if (generation === this._generation) this.loading = false;
      }
    },
    errorText(error) {
      const data = message(error);
      return String(data.error?.message || data.error || data.message || "The request failed.").slice(0, 1200);
    },
    get contexts() {
      const contexts = new Map();
      if (this.context) contexts.set(this.context, this.context);
      for (const run of this.runs) contexts.set(run.context_id, run.name || run.context_id);
      return [...contexts].map(([id, name]) => ({ id, name }));
    },
    get visibleRuns() {
      if (this.filter === "context") return this.runs.filter((run) => run.context_id === this.context);
      if (this.filter === "attention") return this.runs.filter((run) => ["attention", "blocked"].includes(run.status));
      return this.runs;
    },
    followSelectedContext(context) {
      const next = String(context || "");
      if (!this.mounted || this._chatSelection === next) return;
      this._chatSelection = next;
      return this.changeContext(next);
    },
    get documentSelection() { return this.context; },
    set documentSelection(context) {
      // Alpine owns select hydration; route user writes through the same scope
      // invalidation as an external chat switch before changing the context.
      void this.changeContext(context);
    },
    async changeContext(context) {
      const next = String(context || "");
      if (this.context === next) return;
      this._documentGeneration++; this._scope++;
      this.pending = null; this.decisionRetry = null; this.queuedDecisions = []; this.requiredIds = []; this._requests = {};
      this.context = next; this.document = null; this.draft = null;
      this.dirty = false; this.draftStale = false; this.compared = false;
      this.documentError = "";
      await this.loadDocument();
    },
    async loadDocument(preserveDraft = false) {
      const context = this.context;
      const generation = ++this._documentGeneration;
      if (!context || !this.mounted) { this.documentLoading = false; return; }
      this.documentLoading = true;
      try {
        const response = await api({ action: "document_read", context, kind: "todo" });
        if (!this.mounted || context !== this.context || generation !== this._documentGeneration) return;
        const document = response.document || response;
        if (document.kind !== "todo" || document.schema_version !== 1 || !Array.isArray(document.value?.items)) {
          throw new Error("This document version is not supported by this editor.");
        }
        this.document = copy(document); this.documentError = "";
        if (!this.draft || (!preserveDraft && !this.dirty)) this.useSavedDocument();
        else if (this.draftRevision !== document.revision) this.draftStale = true;
      } catch (error) {
        if (this.mounted && context === this.context && generation === this._documentGeneration) {
          this.documentError = this.errorText(error);
        }
      } finally {
        if (generation === this._documentGeneration) this.documentLoading = false;
      }
    },
    useSavedDocument() {
      if (!this.document) return;
      this.draft = copy(this.document.value); this.draftRevision = this.document.revision;
      this.dirty = false; this.draftStale = false; this.compared = false; this.documentError = "";
    },
    markDirty() { this.dirty = true; },
    addItem() {
      if (!this.draft || this.busy || this.draft.items.length >= 100) return;
      this.draft.items.push({ id: uuid(), text: "", done: false }); this.markDirty();
    },
    removeItem(id) {
      if (!this.draft || this.busy) return;
      this.draft.items = this.draft.items.filter((item) => item.id !== id); this.markDirty();
    },
    acceptComparedDraft() {
      if (!this.compared || !this.document || !this.draftStale) return;
      this.draftRevision = this.document.revision; this.draftStale = false; this.compared = false;
    },
    async mutate(payload) {
      const signature = JSON.stringify(payload);
      const request_id = this._requests[signature] || (this._requests[signature] = uuid());
      const response = await api({ ...payload, request_id });
      if (this._requests[signature] === request_id) delete this._requests[signature];
      return response;
    },
    get draftProblem() {
      if (!this.draft) return "";
      if (this.draft.title.length > 160) return "Keep the plan title within 160 characters.";
      if (this.draft.items.length > 100) return "A plan supports up to 100 items.";
      if (this.draft.items.some((item) => !item.text.trim() || item.text.length > 2000)) return "Each item needs 1 to 2000 characters of text.";
      if (new TextEncoder().encode(JSON.stringify(this.draft)).byteLength > 64 * 1024) return "This plan exceeds the 64 KiB document limit.";
      return "";
    },
    async saveDocument() {
      if (this.busy || !this.context || !this.draft || !this.dirty || this.draftStale || this.draftProblem) return;
      const context = this.context, generation = this._documentGeneration;
      const operation = ++this._mutationGeneration;
      const value = copy(this.draft), revision = this.draftRevision;
      this.busy = true; this.documentError = "";
      try {
        await this.mutate({ action: "document_update", context, kind: "todo", expected_revision: revision, value });
        if (!this.mounted || context !== this.context || generation !== this._documentGeneration) return;
        this.dirty = false; this.notice = "Plan saved.";
        await this.loadDocument();
      } catch (error) {
        if (!this.mounted || context !== this.context || generation !== this._documentGeneration) return;
        this.documentError = this.errorText(error);
        // Fetch the current revision, retaining the complete user's draft.
        await this.loadDocument(true);
      } finally { if (this.mounted && operation === this._mutationGeneration) this.busy = false; }
    },
    toggleSelection(id, checked) {
      if (this.busy) return;
      if (checked && !this.selected.includes(id) && this.selected.length >= 1000) {
        this.error = "Select at most 1000 restored runs at a time."; return;
      }
      this.selected = checked ? [...new Set([...this.selected, id])] : this.selected.filter((value) => value !== id);
    },
    reviewRestore() {
      if (this.busy || !this.selected.length) return;
      const runs = this.runs.filter((run) => this.selected.includes(run.run_id));
      this.pending = { kind: "restore", run_ids: runs.map((run) => run.run_id),
        versions: Object.fromEntries(runs.map((run) => [run.run_id, run.version])), epoch: this.restore.epoch, ack: false };
      this.error = "";
    },
    chooseDecision(run, decision, call = null) {
      if (this.busy) return;
      this.pending = { kind: "resolve", context: run.context_id, run_id: run.run_id, version: run.version,
        decision, call_id: call?.call_id, note: "", ack: false };
      this.error = "";
    },
    chooseConflict(run, conflict, decision) {
      if (this.busy) return;
      this.pending = { kind: "conflict", context: run.context_id, run_id: run.run_id, version: run.version,
        conflict_id: conflict.id, expected_revision: conflict.current_revision, decision, ack: false };
      this.error = "";
    },
    get pendingStale() {
      if (!this.pending) return false;
      if (this.pending.kind === "restore") return this.pending.epoch !== this.restore.epoch ||
        this.pending.run_ids.some((id) => this.runs.find((run) => run.run_id === id)?.version !== this.pending.versions[id]);
      return this.runs.find((run) => run.run_id === this.pending.run_id)?.version !== this.pending.version;
    },
    get confirmationAllowed() {
      if (!this.pending || this.busy || this.pendingStale) return false;
      if (!this.pending.ack) return false;
      if (["confirmed_completed", "confirmed_not_completed"].includes(this.pending.decision)) return !!this.pending.note.trim();
      return true;
    },
    get confirmationTitle() {
      if (!this.pending) return "";
      if (this.pending.kind === "restore") return "Select restored runs";
      return ({ resume: "Resume recorded work", stop: "Stop this run", confirmed_completed: "Record completion evidence",
        confirmed_not_completed: "Record non-completion evidence", new_attempt: "Authorize a new attempt",
        keep_current: "Keep the saved document", apply_proposed: "Apply the proposed document" })[this.pending.decision] || "Review action";
    },
    async confirm() {
      if (!this.confirmationAllowed) return;
      const pending = copy(this.pending);
      let payload;
      if (pending.kind === "restore") payload = { action: "restore_select", run_ids: pending.run_ids,
        versions: pending.versions, epoch: pending.epoch };
      else if (pending.kind === "conflict") payload = { action: "document_conflict", context: pending.context,
        run_id: pending.run_id, version: pending.version, conflict_id: pending.conflict_id,
        expected_revision: pending.expected_revision, decision: pending.decision };
      else payload = { action: "resolve", context: pending.context, run_id: pending.run_id,
        version: pending.version, decision: pending.decision, note: pending.note,
        ...(pending.call_id ? { call_id: pending.call_id } : {}) };
      const signature = JSON.stringify(payload);
      const request_id = this._requests[signature] || (this._requests[signature] = uuid());
      await this._sendDecision({ payload, request_id, signature, scope: this._scope, kind: pending.kind });
    },
    async retryDecision() {
      if (!this.mounted || this.busy || !this.decisionRetry || this.decisionRetry.scope !== this._scope) return;
      // Reconcile only the exact request already approved. Its old version is
      // intentional: the server may have committed it before losing the reply.
      await this._sendDecision(copy(this.decisionRetry));
    },
    async refreshQueued(scope = this._scope, generation = this._generation) {
      if (!this.queuedDecisions.length) return;
      const receipts = await Promise.all(this.queuedDecisions.map(async (item) => {
        if (item.state !== "pending") return item;
        const response = await api({ action: "command_status", context: item.context,
          run_id: item.run_id, request_id: item.request_id });
        const command = response.command || {};
        if (!["pending", "applied", "rejected"].includes(command.state)) throw new Error("Worker receipt is unavailable. Refresh to check again.");
        return { ...item, state: command.state };
      }));
      if (!this.mounted || scope !== this._scope || generation !== this._generation) return;
      this.queuedDecisions = receipts;
      const pending = receipts.filter((item) => item.state === "pending").length;
      const rejected = receipts.filter((item) => item.state === "rejected").length;
      this.notice = pending ? `${pending} decision(s) waiting for a worker. Refresh checks delivery.` :
        (rejected ? "A worker rejected a queued decision. Refresh and review the current run before submitting a new decision." :
          "The worker applied the queued decisions. Review the current run for its recovery state.");
    },
    async _sendDecision(envelope) {
      const { payload, request_id, signature, scope, kind } = copy(envelope);
      const operation = ++this._mutationGeneration;
      this.busy = true; this.error = ""; this.requiredIds = [];
      let accepted = false;
      try {
        const response = await api({ ...payload, request_id }); accepted = true;
        if (this._requests[signature] === request_id) delete this._requests[signature];
        if (!this.mounted || scope !== this._scope) return;
        this.decisionRetry = null;
        this.pending = null;
        if (response?.command?.state === "rejected") {
          this.notice = "The worker rejected this decision. Review the current run before submitting a new decision.";
        } else if (response?.queued) {
          this.queuedDecisions = [...this.queuedDecisions.filter((item) => item.request_id !== request_id),
            { request_id, context: payload.context, run_id: payload.run_id, state: "pending" }].slice(-20);
          this.notice = "Decision queued for a worker. It has not been applied yet; Refresh checks its receipt.";
        } else this.notice = "Decision recorded. The server will recheck recovery requirements.";
      } catch (error) {
        if (!this.mounted || scope !== this._scope) return;
        this.decisionRetry = copy(envelope);
        const data = message(error);
        this.error = this.errorText(error);
        this.requiredIds = Array.isArray(data.required_ids) ? data.required_ids :
          (Array.isArray(data.error?.required_ids) ? data.error.required_ids : []);
      } finally { if (this.mounted && operation === this._mutationGeneration) this.busy = false; }
      if (this.mounted && scope === this._scope) {
        await this.refresh();
        if (accepted && kind === "conflict") await this.loadDocument(this.dirty);
      }
    },
  };
}
