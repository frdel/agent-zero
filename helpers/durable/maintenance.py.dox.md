# Claimed shared maintenance

## Purpose and ownership

`maintenance.py` owns encrypted owner-routed app document requests and failover-safe known-provider cleanup/chat deletion. It coordinates short PostgreSQL mutations with explicit provider DELETE calls outside SQL transactions; it never starts an agent loop.

## APIs and contracts

- `metadata(owner,context_id,run_id=None)` returns the current run/generation/epoch/review binding. `enqueue(owner,context_id,run_id,kind,value,request_id,generation=...,epoch=...,version=...)` encrypts canonical bounded request data with `ResourceManager`. The inbox retains only its authenticated resource reference and binding. Stable request IDs/content deduplicate transport retries even after deletion has scrubbed resource bytes; changed requests conflict.
- Supported kinds are `KINDS`: `maintenance_document`, `maintenance_conflict`, `maintenance_delete`. Document schemas/revisions are validated again and masked by the claimed worker's policy context. CAS or conflict resolution and command acknowledgment commit in one SQL transaction.
- `process(owner,run_id,restore_context)` acquires `claim_maintenance` if needed, then invokes the coordinator's audited restore callback. A live foreign context claim prevents even constructor/policy reconstruction. Idle terminal chats use the same context advisory lock/fence as execution and never become running turns. Restoring a pruned terminal run uses its verified current context head. The caller must run this only at a live worker's safe boundary or as a dedicated reserved idle task.
- Deletion atomically freezes verified current descendant run/generation bindings and cancels them. Pending reservations block unrelated new admissions in every selected context. It waits for live descendant claims to release, then claims every selected context; it never follows a newer unrelated owner on retry. Reset invalidates a pending selection.
- A same-worker driver must unwind after cancellation before provider collection begins: cancelled calls may still publish known body outcomes. Each retry extends the encrypted cleanup plan with newly committed normalized targets, preserving stable per-target receipts. A final store snapshot comparison covers all frozen graph model outcomes/checkpoints/heads inside the scrub transaction; changed evidence returns pending and is collected on the next pass, never silently discarded.
- Known provider identities come only from retained normalized model outcomes and committed per-response target maps. Raw provider metadata and arbitrary tool results are not searched. Any saved/live opt-out suppresses provider cleanup for that context. Missing/corrupt target proof or changed configured credentials/endpoint holds cleanup and keeps shared payloads; no guessed provider is contacted.
- Retained per-response target-map keys remain cleanup targets after call/history retention. Every retry rechecks opt-outs and removes that context's previously planned targets before dispatch; an earlier plan never overrides a new opt-out.
- `provider_descriptor(agent,model=...)` supports exact configured LiteLLM OpenAI/Azure wrappers. It records source/model/provider and endpoint/account digests, with account HMAC keyed by the shared resource key. Credentials and endpoint text are never stored. Actual model intents must pin their prepared model descriptor and carry it into known result target maps; credential rotation does not authorize deletion against another account. Unsupported/global fallback credentials return no descriptor.
- A cleanup plan containing response IDs is encrypted and committed before effects. Each source-pinned target/ID has a stable intent/completed receipt. DELETE against precisely that pinned target is idempotent: HTTP 404 means already absent, so a lost acknowledgment can retry after failover without fabricating success. SDK calls pass the explicit configured provider and model, with current matching credentials. Provider errors produce only a fixed rejected receipt; private payloads remain available.
- SQL scrub and a sanitized applied command receipt commit together after all known deletions succeed. The receipt records `unresolved_provider_calls`, a count of unknown model intents whose provider IDs never returned. Explicit deletion authorizes discarding their journal payloads; this count does not promise provider-side erasure of unknown objects, independent backups, WAL or replicas.
- Successful internal processing returns `{processed,pending,deleted:true,context_ids}` so the coordinator can evict local contexts and scheduler projections. Public APIs return HTTP 202 while queued and expose only safe command state; queue acknowledgment does not claim deletion.

## PostgreSQL seams

`claim_maintenance`, `list_command_runs`, `enqueue_maintenance`, `apply_document_command`, `begin_deletion`, `deletion_contexts`, `maintenance_effect`, `finish_maintenance_effect`, and `complete_deletion` are native store operations. Provider calls never occur inside their transactions. Maintenance effects and context selections retain only identity/digest/sanitized receipts after private custody is scrubbed.

Native protocol 3 requires a quiescent upgrade from protocols 1/2: stop all workers/coordinators and settle submitted/running resource jobs. Upgrade checks actual advisory locks and job states under the global writer transaction and refuses active deployments; mixed old writers are unsupported. Ordinary new protocol-3 workers can join a running deployment.

## Verification

`tests/test_durable_maintenance.py` requires an explicitly disposable PostgreSQL test DSN and synthetic resource key. It covers encrypted requests, foreign-owner constructor prevention, terminal document CAS/ack rollback, conflict reconciliation without body replay, reset/GC, frozen descendant ownership, real installed-SDK loopback DELETE with lost acknowledgment and 404 failover, opt-outs, changed provider account/failure custody, and quiescent protocol upgrades. It establishes no real-provider or physical multi-host acceptance.

`metadata` may promote a verified unsent shared draft to one inert terminal
maintenance anchor. No agent, constructor hook or inference runs during this
transaction. Its stable run identity lets the normal inbox handle document edits
and removal before the first message.

Shared memory patches use a separate encrypted projection transaction:
`PostgresStore.commit_memory_patch` checks the current claim/job/control role,
revision and immutable operation identity before replacing the index and writing
its receipt together. Persistent memory is not part of chat deletion custody.
