# Agent Editor Plugin DOX

## Purpose

- Own the deterministic Easy and Advanced Agent Editor API and WebUI workflow.

## Ownership

- `helpers/editor.py` composes existing profile, prompt, model, tool, and skill
  owners into editor state and sparse change plans.
- `api/` owns authenticated/CSRF-protected state, save, and avatar routes.
- `webui/` owns the Alpine store, modal surface, styling, and client-side draft.
- `extensions/webui/` owns lifecycle registration on the shared modal stack and
  the global entry points used by existing WebUI surfaces.

## Local Contracts

- Plugin profile metadata layers merge bundled roots before user roots using
  stable root-priority sorting, matching runtime profile loading and catalogs.
- The editor performs zero model calls.
- Profile list requests stay lightweight: summary rows inspect only sparse
  editor-owned keys and files and never construct full save or removal plans.
- Writes are limited to the selected profile layer — global
  `usr/agents/<profile-id>` or project
  `usr/projects/<project>/.a0proj/agents/<profile-id>` — and only to paths or
  config keys listed in the validated change plan. The availability toggle
  reuses the existing project `.a0proj/agents.json` load/save owner; the WebUI
  permits one availability save at a time. Global availability remains a sparse
  `enabled` profile override.
- Every profile, including `Default`, can be made unavailable. The backend
  rejects only the change that would leave the selected scope with no available
  profile, then reconciles loaded chats through the shared project owner.
- Destructive cleanup and custom-profile deletion require an explicit confirmed
  apply request. Profile creation and availability invariants are rechecked at
  the existing editor mutation boundary; project availability refuses malformed
  `agents.json` and changes only the requested profile entry through the existing
  project storage owner.
- Never call `helpers.subagents.save_agent_data`.
- Fast creation from slash commands and connector clients calls
  `helpers/editor.py:save_easy_profile`, so profile IDs, validation, sparse
  writes, and the mutation boundary stay identical to Easy mode.
- Authored profile definitions remain YAML; editor-written plugin configs remain
  JSON.
- Profile config paths use `helpers.plugins.determine_plugin_asset_path` for the
  selected Global or project scope and remain rooted in that exact validated
  profile boundary.
- Project profiles inherit the existing global, plugin, and bundled layers.
  Removing or deleting in project scope never mutates those inherited layers;
  only agents created in the selected scope are deletable.
- Bundled `agents/` files are read-only.
- Advanced prompt text is edited directly with a full-height bundled ACE editor
  in Markdown mode. Main instruction sections use readable titles and the
  current customization status. A compact Saves to row shows the destination
  once with a copy action; variable hints sit below the editor and omit Python
  implementation details. Preserve authored placeholders on save and never run
  processors in the editor.
  Per-file close/check actions discard or accept the current edit checkpoint,
  while the editor's global save remains the only persistence boundary.
- New profiles require a display name and non-empty agent instructions in both
  Easy and Advanced; existing Advanced prompt edits retain per-file semantics.
- Easy and Advanced share the same segmented capability controls: Default
  removes the item from `allowed` and `blocked`, On stores it in `allowed`, and
  Off stores it in `blocked`. Tools, canonical MCP entries, and Skills expose
  independent default switches; explicit choices remain pinned when a default
  changes, and opening then undoing an inherited policy produces no write. Easy
  places each initially closed native accordion directly below its default
  switch. Advanced gives Tools, MCPs, and Skills separate sections while keeping
  unavailable retained IDs reviewable. Framework-required tools remain absent.
- Model selection in both modes reuses `_model_config`'s compact preset dropdown
  and preset editor; Agent Editor persists only the scoped preset reference.
- The exact `default` profile is an internal baseline and is omitted only from
  selectable and editable UI rows. Runtime discovery remains unchanged, and an
  existing chat using it may still report it as current status.
- Manage agents reuses the plugin-settings project vocabulary: Global or one
  existing project. The active chat profile appears once above the list; each
  row exposes scoped availability, duplication, restore for inherited profiles,
  icon-only Edit, and Delete for profiles owned by that scope. Duplicate
  materializes the effective source profile into the selected writable layer
  with a collision-free ID and title. Restore visibility follows the sparse
  removal plan, ignores unrelated profile files, and reports successful reset.
  Availability changes quietly refresh the adjacent profile switcher catalog
  without a success toast.
- The same project selector is available inside Create and Edit. Create keeps
  the in-progress draft when its destination changes; Edit reloads the selected
  profile from the new scope after guarding unsaved changes.
- Save & test activates the saved profile in a fresh chat using that same scope.
- The WebUI uses the shared modal stack, labeled prompt scroll regions, and
  24px-or-larger policy and text-action targets.

## Verification

- Run Agent Editor, profile merge, tool policy, skill policy, API security, and
  WebUI tests, then verify the explicitly named bind-mounted runtime.

## Child DOX Index

No child DOX files.
