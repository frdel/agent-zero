import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const source = await readFile(new URL('../webui/components/durability/durability-state.js', import.meta.url), 'utf8');
const { createDurabilityState } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };
const run = (version = 1) => ({ run_id: 'run-a', context_id: 'chat-a', name: 'Synthetic chat', status: 'attention', phase: 'model_inflight', version,
  calls: [{ call_id: 'model:0', kind: 'model', name: 'Model request', status: 'intent', has_result: false, may_retry: true }],
  actions: { resume: false, stop: true, confirm_completed: true, confirm_not_completed: true, new_attempt: true } });
const status = (version = 1) => ({ available: true, enabled: true, restore: { required: false, epoch: 'epoch-1' }, runs: [run(version)] });
const inventory = (count, version = 1) => Array.from({ length: count }, (_, index) => ({ ...run(version),
  run_id: `run-${index}`, context_id: `chat-${index}`, restore_selected: false }));
const page = (rows, offset = 0) => ({ ...status(), runs: rows.slice(offset, offset + 50), total: rows.length,
  next_offset: offset + 50 < rows.length ? offset + 50 : null });
const document = (revision = 1, title = 'Saved plan') => ({ kind: 'todo', schema_version: 1, revision, value: { title, items: [{ id: 'item-1', text: 'Saved item', done: false }] } });
const rig = (handler = () => ({})) => {
  const requests = []; let serial = 0;
  const state = createDurabilityState(async (payload) => {
    requests.push(structuredClone(payload));
    if (payload.action === 'status') return status();
    if (payload.action === 'document_read') return document();
    return handler(payload);
  }, () => `request-${++serial}`);
  return { state, requests };
};

test('stale status responses cannot replace a newer snapshot', async () => {
  const old = deferred(), newer = deferred(); let count = 0;
  const state = createDurabilityState(() => (++count === 1 ? old.promise : newer.promise));
  state.mounted = true;
  const first = state.refresh(), second = state.refresh();
  newer.resolve(status(2)); await second;
  old.resolve(status(1)); await first;
  assert.equal(state.runs[0].version, 2);
  assert.equal(state.loading, false);
});

test('explicit pagination preserves selections and refreshes every loaded review version', async () => {
  let rows = inventory(75);
  const offsets = [];
  const state = createDurabilityState(async (payload) => {
    if (payload.action === 'document_read') return document();
    offsets.push(payload.offset); return page(rows, payload.offset);
  });
  await state.mount('chat-0');
  assert.equal(state.runs.length, 50); assert.equal(state.nextOffset, 50); assert.equal(state.totalRuns, 75);
  state.toggleSelection('run-0', true);
  await state.loadMore();
  assert.equal(state.runs.length, 75); assert.equal(state.nextOffset, null);
  assert.deepEqual(state.selected, ['run-0'], 'Loading a dependency never selects it');
  for (const item of state.runs) state.toggleSelection(item.run_id, true);
  rows = inventory(75, 2); offsets.length = 0;
  await state.refresh();
  assert.deepEqual(offsets, [0, 50]); assert.equal(state.selected.length, 75);
  state.reviewRestore();
  assert.equal(state.pending.run_ids.length, 75);
  assert.equal(Object.keys(state.pending.versions).length, 75);
  assert.ok(Object.values(state.pending.versions).every(version => version === 2));
});

test('load more deduplicates run identities while retaining newer row details', async () => {
  const rows = inventory(51);
  const state = createDurabilityState(async (payload) => {
    if (payload.action === 'document_read') return document();
    if (!payload.offset) return page(rows);
    return { ...page(rows, 50), runs: [{ ...rows[0], version: 2 }, rows[50]] };
  });
  await state.mount('chat-0'); await state.loadMore();
  assert.equal(state.runs.length, 51); assert.equal(state.runs[0].version, 2);
  assert.equal(new Set(state.runs.map(item => item.run_id)).size, 51);
});

test('a late page cannot append to a newer refreshed inventory', async () => {
  const waiting = deferred(); let version = 1;
  const state = createDurabilityState(async (payload) => {
    if (payload.action === 'document_read') return document();
    return payload.offset ? waiting.promise : page(inventory(75, version));
  });
  await state.mount('chat-0'); const loading = state.loadMore();
  version = 2; await state.refresh();
  waiting.resolve(page(inventory(75, 1), 50)); await loading;
  assert.equal(state.runs.length, 50); assert.ok(state.runs.every(item => item.version === 2));
  assert.equal(state.nextOffset, 50); assert.equal(state.loading, false);
});

test('a late inventory page cannot refill a closed modal or cross a chat switch', async () => {
  for (const action of ['switch', 'close']) {
    const waiting = deferred();
    const state = createDurabilityState(async (payload) => {
      if (payload.action === 'document_read') return document();
      return payload.offset ? waiting.promise : page(inventory(75));
    });
    await state.mount('chat-0'); const loading = state.loadMore();
    if (action === 'switch') await state.changeContext('chat-other'); else state.close();
    waiting.resolve(page(inventory(75), 50)); await loading;
    assert.equal(state.runs.length, action === 'switch' ? 50 : 0);
    assert.equal(state.loading, false);
    if (action === 'close') assert.equal(state.nextOffset, null);
  }
});

test('a failed later refresh page retains loaded selections and their prior snapshot', async () => {
  let fail = false;
  const state = createDurabilityState(async (payload) => {
    if (payload.action === 'document_read') return document();
    if (fail && payload.offset) throw new Error('Later page unavailable');
    return page(inventory(75, fail ? 2 : 1), payload.offset);
  });
  await state.mount('chat-0'); await state.loadMore(); state.toggleSelection('run-74', true);
  fail = true; await state.refresh();
  assert.equal(state.runs.length, 75); assert.deepEqual(state.selected, ['run-74']);
  assert.ok(state.runs.every(item => item.version === 1)); assert.match(state.error, /unavailable/);
});

test('restore selection supports connected families through the store limit without selecting extra runs', () => {
  const state = createDurabilityState(async () => ({}));
  state.runs = inventory(1001);
  for (const item of state.runs) state.toggleSelection(item.run_id, true);
  assert.equal(state.selected.length, 1000); assert.ok(!state.selected.includes('run-1000'));
  assert.match(state.error, /1000/);
  state.reviewRestore(); assert.equal(state.pending.run_ids.length, 1000);
});

test('document context switches reject a late response and clear action scope', async () => {
  const old = deferred();
  const state = createDurabilityState((payload) => payload.context === 'chat-a' ? old.promise : Promise.resolve(document(2, 'Chat B')));
  state.mounted = true; state.context = 'chat-a';
  const first = state.loadDocument();
  state.pending = { kind: 'resolve', context: 'chat-a' };
  await state.changeContext('chat-b');
  old.resolve(document(1, 'Chat A')); await first;
  assert.equal(state.context, 'chat-b'); assert.equal(state.draft.title, 'Chat B');
  assert.equal(state.pending, null);
});

test('close removes private state and late load cannot refill it', async () => {
  const waiting = deferred();
  const state = createDurabilityState(() => waiting.promise);
  state.mounted = true; state.context = 'private-chat'; state.pending = { note: 'private note' };
  const load = state.refresh(); state.close(); waiting.resolve(status()); await load;
  assert.deepEqual(state.runs, []); assert.equal(state.pending, null);
  assert.equal(state.context, ''); assert.equal(state.draft, null);
});

test('stale run versions disable confirmation before dispatch', async () => {
  const { state, requests } = rig(); await state.mount('chat-a');
  state.chooseDecision(state.runs[0], 'stop'); state.pending.ack = true;
  state.runs = [run(2)];
  assert.equal(state.pendingStale, true); assert.equal(state.confirmationAllowed, false);
  await state.confirm(); assert.equal(requests.filter((request) => request.action === 'resolve').length, 0);
});

test('failed mutation retry keeps the same request ID and evidence', async () => {
  let attempts = 0;
  const { state, requests } = rig(() => { if (++attempts === 1) throw new Error('Synthetic lost response'); return { ok: true }; });
  await state.mount('chat-a');
  state.chooseDecision(state.runs[0], 'confirmed_completed', state.runs[0].calls[0]);
  state.pending.note = 'Verified target-side receipt'; state.pending.ack = true;
  await state.confirm(); assert.equal(state.pending.note, 'Verified target-side receipt');
  await state.confirm();
  const writes = requests.filter((request) => request.action === 'resolve');
  assert.equal(writes.length, 2); assert.equal(writes[0].request_id, writes[1].request_id);
  assert.equal(writes[0].version, 1); assert.equal(writes[0].call_id, 'model:0');
  assert.equal(state.pending, null);
});

test('accepted decision with a lost dispatch reply can reconcile its exact request after refresh', async () => {
  let committed = false, serial = 0;
  const writes = [];
  const state = createDurabilityState(async (payload) => {
    if (payload.action === 'status') {
      const snapshot = status(committed ? 2 : 1);
      if (committed) snapshot.runs[0].actions.new_attempt = false;
      return snapshot;
    }
    if (payload.action === 'document_read') return document();
    writes.push(structuredClone(payload));
    if (!committed) { committed = true; throw new Error('Dispatch failed after the decision was committed'); }
    return { ok: true };
  }, () => `request-${++serial}`);
  await state.mount('chat-a');
  state.chooseDecision(state.runs[0], 'new_attempt', state.runs[0].calls[0]);
  state.pending.note = 'Original approved evidence'; state.pending.ack = true;
  await state.confirm();
  assert.equal(state.pendingStale, true); assert.equal(state.confirmationAllowed, false);
  assert.equal(state.runs[0].actions.new_attempt, false);
  state.pending.note = 'Later draft must not change the accepted request';
  state.pending.call_id = 'model:other';
  await state.refresh();
  await state.retryDecision();
  assert.deepEqual(writes[1], writes[0]);
  assert.equal(writes.length, 2); assert.equal(serial, 1);
  assert.equal(state.decisionRetry, null); assert.equal(state.pending, null);
});

test('retrying an unaccepted stale decision preserves its version and cannot grant a new attempt', async () => {
  let changed = false, effects = 0, serial = 0;
  const writes = [];
  const state = createDurabilityState(async (payload) => {
    if (payload.action === 'status') return status(changed ? 2 : 1);
    if (payload.action === 'document_read') return document();
    writes.push(structuredClone(payload));
    changed = true;
    if (payload.version !== 2) throw new Error(JSON.stringify({ error: 'Recovery review is stale' }));
    effects++; return { ok: true };
  }, () => `request-${++serial}`);
  await state.mount('chat-a');
  state.chooseDecision(state.runs[0], 'new_attempt', state.runs[0].calls[0]); state.pending.ack = true;
  await state.confirm(); await state.retryDecision();
  assert.deepEqual(writes[1], writes[0]); assert.equal(effects, 0); assert.equal(serial, 1);
  assert.match(state.error, /stale/); assert.equal(state.pendingStale, true);
});

test('decision acknowledgment retry is single flight and cleared by context changes or close', async () => {
  const waiting = deferred(); let writes = 0;
  const { state } = rig(() => { if (++writes === 1) throw new Error('Lost response'); return waiting.promise; });
  await state.mount('chat-a'); state.chooseDecision(state.runs[0], 'stop'); state.pending.ack = true;
  await state.confirm(); assert.ok(state.decisionRetry);
  const retry = state.retryDecision(); await state.retryDecision();
  assert.equal(writes, 2);
  await state.changeContext('chat-b'); assert.equal(state.decisionRetry, null);
  waiting.reject(new Error('Late failure')); await retry;
  assert.equal(state.decisionRetry, null);
  await state.retryDecision(); assert.equal(writes, 2);
  state.decisionRetry = { payload: { note: 'Private evidence' }, scope: state._scope };
  state.close(); assert.equal(state.decisionRetry, null);
});

test('completion evidence requires both an explicit acknowledgment and note', async () => {
  const { state } = rig(); await state.mount('chat-a');
  state.chooseDecision(state.runs[0], 'confirmed_not_completed', state.runs[0].calls[0]);
  assert.equal(state.confirmationAllowed, false);
  state.pending.ack = true; assert.equal(state.confirmationAllowed, false);
  state.pending.note = 'Verified no target-side receipt'; assert.equal(state.confirmationAllowed, true);
});

test('restore dependency errors never auto-select related or invisible runs', async () => {
  const { state } = rig(() => { throw new Error(JSON.stringify({ error: 'Related runs required', required_ids: ['not-visible'] })); });
  await state.mount('chat-a'); state.restore = { required: true, epoch: 'epoch-1' };
  state.selected = ['run-a']; state.reviewRestore(); state.pending.ack = true;
  await state.confirm();
  assert.deepEqual(state.selected, ['run-a']); assert.deepEqual(state.requiredIds, ['not-visible']);
  assert.deepEqual(state.pending.run_ids, ['run-a']);
});

test('stale document save retains the complete draft and requires explicit merge review', async () => {
  let revision = 1, writes = [];
  const state = createDurabilityState(async (payload) => {
    if (payload.action === 'status') return status();
    if (payload.action === 'document_read') return document(revision, revision === 1 ? 'Saved plan' : 'Changed by agent');
    writes.push(structuredClone(payload));
    if (writes.length === 1) { revision = 2; throw new Error(JSON.stringify({ error: 'Revision conflict', current_revision: 2 })); }
    revision = 3; return { ok: true };
  }, () => 'synthetic-id');
  await state.mount('chat-a'); state.draft.title = 'My unsaved plan'; state.draft.items[0].text = 'My item'; state.markDirty();
  await state.saveDocument();
  assert.equal(state.draft.title, 'My unsaved plan'); assert.equal(state.draft.items[0].text, 'My item');
  assert.equal(state.document.value.title, 'Changed by agent'); assert.equal(state.draftRevision, 1);
  assert.equal(state.draftStale, true);
  await state.saveDocument(); assert.equal(writes.length, 1);
  state.acceptComparedDraft(); assert.equal(state.draftStale, true);
  state.compared = true; state.acceptComparedDraft(); assert.equal(state.draftRevision, 2);
  await state.saveDocument(); assert.equal(writes[1].expected_revision, 2);
});

test('new attempt stays explicitly confirmed and duplicate clicks send one mutation', async () => {
  const writing = deferred();
  const { state, requests } = rig(() => writing.promise); await state.mount('chat-a');
  state.chooseDecision(state.runs[0], 'new_attempt', state.runs[0].calls[0]);
  await state.confirm(); assert.equal(requests.filter((request) => request.action === 'resolve').length, 0);
  state.pending.ack = true;
  const first = state.confirm(); await state.confirm();
  assert.equal(state.busy, true); writing.resolve({ ok: true }); await first;
  assert.equal(requests.filter((request) => request.action === 'resolve').length, 1);
});

test('a mutation from a closed modal cannot clear a new modal mutation latch', async () => {
  const old = deferred(), current = deferred(); let writes = 0;
  const { state } = rig(() => (++writes === 1 ? old.promise : current.promise));
  await state.mount('chat-a'); state.chooseDecision(state.runs[0], 'stop'); state.pending.ack = true;
  const first = state.confirm(); state.close();
  await state.mount('chat-a'); state.chooseDecision(state.runs[0], 'stop'); state.pending.ack = true;
  const second = state.confirm(); old.resolve({ ok: true }); await first;
  assert.equal(state.busy, true); current.resolve({ ok: true }); await second; assert.equal(state.busy, false);
});

test('document conflict decisions include exact run and document revisions', async () => {
  const { state, requests } = rig(); await state.mount('chat-a');
  state.chooseConflict(state.runs[0], { id: 'conflict-a', current_revision: 5 }, 'keep_current');
  state.pending.ack = true; await state.confirm();
  const payload = requests.find((request) => request.action === 'document_conflict');
  assert.equal(payload.expected_revision, 5); assert.equal(payload.version, 1);
  assert.equal(payload.conflict_id, 'conflict-a'); assert.equal(payload.decision, 'keep_current');
});

test('retrying a failed initial document read opens the editor without a phantom conflict', async () => {
  let reads = 0;
  const state = createDurabilityState(async (payload) => {
    if (payload.action === 'status') return status();
    if (++reads === 1) throw new Error('Synthetic read failure');
    return document(3);
  });
  await state.mount('chat-a'); assert.equal(state.draft, null);
  await state.loadDocument(true);
  assert.equal(state.draft.title, 'Saved plan'); assert.equal(state.draftRevision, 3);
  assert.equal(state.draftStale, false); assert.equal(state.documentError, '');
});


test('bound document selection invalidates and loads the new context before adopting its draft', async () => {
  const next = deferred();
  const state = createDurabilityState((payload) => payload.context === 'chat-b' ? next.promise : Promise.resolve(document()));
  state.mounted = true; state.context = 'chat-a'; state.draft = document().value;
  state.dirty = true; state.pending = { kind: 'resolve', context: 'chat-a' };
  state.documentSelection = 'chat-b';
  assert.equal(state.documentSelection, 'chat-b'); assert.equal(state.draft, null);
  assert.equal(state.pending, null); assert.equal(state.dirty, false);
  next.resolve(document(2, 'Chat B plan')); await Promise.resolve(); await Promise.resolve();
  assert.equal(state.draft.title, 'Chat B plan');
});

test('queued remote decision distinguishes durable acceptance from worker application', async () => {
  let delivery = 'pending';
  const { state, requests } = rig((payload) => {
    if (payload.action === 'resolve') return { queued: true, command: { request_id: payload.request_id, state: 'pending' } };
    if (payload.action === 'command_status') return { command: { request_id: payload.request_id, state: delivery } };
    throw new Error('Unexpected mutation');
  });
  await state.mount('chat-a');
  state.chooseDecision(state.runs[0], 'stop'); state.pending.ack = true;
  await state.confirm();
  assert.match(state.notice, /waiting for a worker/);
  assert.equal(state.queuedDecisions[0].state, 'pending');
  assert.equal(requests.filter(item => item.action === 'resolve').length, 1);
  delivery = 'applied'; await state.refresh();
  assert.match(state.notice, /worker applied/);
  assert.equal(state.queuedDecisions[0].state, 'applied');
  assert.equal(requests.filter(item => item.action === 'resolve').length, 1, 'Receipt checks never repeat dispatch');
});

test('rejected remote decision remains distinguishable and modal close clears receipts', async () => {
  const { state } = rig((payload) => payload.action === 'resolve' ? { queued: true } : { command: { state: 'rejected' } });
  await state.mount('chat-a');
  state.chooseDecision(state.runs[0], 'stop'); state.pending.ack = true;
  await state.confirm();
  assert.match(state.notice, /worker rejected/);
  assert.equal(state.queuedDecisions[0].state, 'rejected');
  state.close(); assert.deepEqual(state.queuedDecisions, []);
});

test('late queued-command receipt cannot overwrite a new context scope', async () => {
  const waiting = deferred();
  const { state } = rig((payload) => payload.action === 'command_status' ? waiting.promise : {});
  await state.mount('chat-a');
  state.queuedDecisions = [{ request_id: 'request-1', context: 'chat-a', run_id: 'run-a', state: 'pending' }];
  const checking = state.refresh();
  await new Promise(resolve => setImmediate(resolve));
  await state.changeContext('chat-b');
  waiting.resolve({ command: { state: 'applied' } }); await checking;
  assert.deepEqual(state.queuedDecisions, []);
  assert.equal(state.context, 'chat-b');
});

test('chat reset retries preserve request identity until acknowledgment then allow a new reset', async () => {
  const module = await readFile(new URL('../webui/components/sidebar/chats/chats-store.js', import.meta.url), 'utf8');
  const executable = module.replace(/^import[\s\S]*?;\n/gm, '').replace('export { store };', 'return store;');
  const requests = []; let fail = true;
  const store = new Function('createStore', 'sendJsonData', 'toastFetchError', executable)(
    (_name, model) => model,
    async (_endpoint, payload) => { requests.push(payload); if (fail) throw new Error('Acknowledgment lost'); return { message: 'Reset' }; },
    () => {},
  );
  await store.resetChat('chat-a');
  fail = false; await store.resetChat('chat-a');
  assert.equal(requests[0].request_id, requests[1].request_id);
  await store.resetChat('chat-a');
  assert.notEqual(requests[1].request_id, requests[2].request_id);
});
