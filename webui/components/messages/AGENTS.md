# Message Components DOX

## Purpose

- Own message rendering helpers, action buttons, process groups, and resize behavior.

## Ownership

- `action-buttons/` owns simple message action controls.
- `process-group/` owns grouped process-step DOM and styling helpers.
- `resize/` owns message resize state.

## Local Contracts

- Keep message DOM helpers compatible with extension points that modify rendered messages.
- Sanitize or safely render model/user-provided content through shared rendering paths.
- Avoid layout shifts that break long-running message streaming.
- Terminal output keeps text-size adjustment at 100% so mobile browsers do not inflate its wide, unwrapped content when streamed or expanded; preserve horizontal scrolling and normal browser zoom.
- Keep message action chrome out of text selection so copy/paste captures message content without button labels or icons.
- Reconcile standard action buttons in place during streamed updates so hover, focus, tooltips, and click feedback survive while handlers receive the latest message data; position buttons by index and never re-insert an already-mounted button, since re-inserting detaches and remounts it mid-stream. Preserve extension-owned buttons in the same action bar.
- Order standard message actions as Detail, Copy, then Speak; omit unavailable actions without changing the relative order of the remaining controls. Insert new or replaced actions before the next retained action or the stable extension anchor, never using a newly inserted action as that anchor. Plugin-rendered message actions must follow the same order.
- Collapsible action rows keep the hover-revealed `Show less` control laid out with reserved space on pointer devices; hover reveals it through opacity only so the row height never shifts, and its opacity fade matches the row fade so it never disappears ahead of sibling buttons.
- Keep collapsed process-step detail text out of the DOM; opening a step may materialize its current cached log data and collapsing it must discard that heavy detail again without removing extension action hooks.
- Preference-driven process detail modes must await the same materialization path as manual expansion and accept an explicit chat-history target for off-screen window staging. `STEP` opens only the current non-utility step at the live tail; historical windows must not invent a current step at their boundary.
- Keep oversized standalone replay bodies and key/value tables in a bounded preview state until the user expands them; collapsing must remove the full body again.
- Message-window boundaries must not split process groups. Groups with more than 50 steps initially render their newest 50 steps and prepend earlier steps in 50-step increments through the group-local `Show more` control while retaining stable full-group header metrics.
- The process-group `Show more` paging control uses the same understated, non-underlined typography and hover-opacity treatment as message-body expansion controls.
- A root response may attach only to a substantive process render unit. Utility-prefixed units remain visible even while utility steps are hidden; standalone utility-only groups remain separate and hidden while utility messages are disabled, and completed groups must not absorb later utility records. Determine this from full-log render metadata, not partially mounted DOM children.
- Do not add an `EXE` accent class for `code_execution_tool` process steps to `process-group.css`; `code_execution_tool` items use the default process-step accent. Plugin-local accent overrides (such as `TXT` for `text_editor`) live next to their owning plugin.

## Work Guidance

- Coordinate changes with `webui/js/messages.js` and frontend extension hooks.

## Verification

- Smoke-test message rendering, action buttons, process groups, and resizing after changes.

## Child DOX Index

No child DOX files.
