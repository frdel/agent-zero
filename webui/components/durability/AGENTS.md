# Recovery and Documents UI DOX

## Purpose

- Own the native modal for operator recovery decisions, explicit backup selection, and the revisioned chat plan.

## Ownership

- `durability.html` owns safe Alpine markup, responsive styles, keyboard labels and explicit confirmation.
- `durability-store.js` registers the store and calls the authenticated, CSRF-protected `/durability` API through `callJsonApi`.
- `durability-state.js` owns request generations, context isolation, revision checks, drafts and idempotent mutation retries.

## Local Contracts

- Display only the backend's bounded public projection. Render server/user values through `x-text` or form models; never HTML.
- Inventory pages load only on explicit request; Refresh revalidates all loaded pages before replacing rows/selections.
- An acknowledgment retry resends only the frozen approved payload/ID/version, survives a status refresh, and clears on context switch or unmount.
- Every mutation includes its original revision/version and a stable request ID across identical retries. Backend authorization remains authoritative.
- Selection of restored runs is explicit; dependency errors never select related or unseen runs automatically.
- Completion evidence stops a run without inventing a tool result. A new attempt requires a separate explicit duplicate-effect/cost acknowledgment.
- Preserve the user's draft on document conflicts; require current-version comparison before rebasing and a separate save.
- Ignore stale responses after context switches, newer loads or unmount. Clear modal-private state and drafts on close.

## Work Guidance

- Use the shared modal shell, native icons, theme variables and shared API helper. Keep runtime and storage policy in backend owners.

## Verification

- Run `node --test tests/test_durability_ui.mjs` for state, race, revision, request-ID and safe-rendering contracts.
- Verify the real modal on desktop/mobile, keyboard interaction and authenticated API failures in the isolated browser acceptance fixture.

## Child DOX Index

No child DOX files.
