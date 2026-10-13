# Sidebar Components DOX

## Purpose

- Own left sidebar layout, chat/task lists, top actions, and bottom preferences components.

## Ownership

- `left-sidebar.html` and `sidebar-store.js` own sidebar shell and shared state.
- `top-section/` owns header and quick actions.
- `chats/` owns chat list UI and state; `chat-tree.html` is the shared parent/subagent row for direct and parallel delegation.
- `tasks/` owns task list UI and state; `task-row.html` is the shared scheduler row.
- `bottom/` owns lower sidebar controls and preferences panel.

## Local Contracts

- Preserve responsive sidebar behavior and collapsed/expanded state.
- Keep chat and task list updates compatible with WebSocket state sync.
- Contexts with `parent_context_id` render as indented children beneath their parent chat; they must remain selectable while hidden from the top-level chat list.
- The shared chat tree recurses through every subordinate level, mounting children only while expanded. Selecting or restoring a descendant expands all ancestors in both list views.
- Child indentation uses `--spacing-md` + `--spacing-xs` for the first two child levels, tapers at the third, and stops increasing after it, preserving room for titles and actions in narrow sidebars.
- Chat tree expand/collapse controls use a parent-only leading slot, with right/down chevrons for collapsed/expanded state. Use spacing tokens for compact rows and the additional child indentation without consuming normal chat row text margin.
- A selected chat with children auto-expands once during context hydration at every depth, including a selected subagent that delegates again, unless the user has already toggled it.
- The Tasks list is reserved for scheduler-backed task contexts and must not be used for chat-bound parallel children.
- Running parent and child chats share the chat-list working-bubble animation; keep it scoped away from task and connection-status indicators.
- Chat and task lists reclaim the same part of the sidebar's left content inset so their project bubbles align, while their section headers retain the standard sidebar inset.
- Chat-row action buttons consume layout width only while a pointer row is hovered or while that row is selected on a touch device.
- Row overflow menus choose the roomier side of their trigger and cap their height to the available viewport so plugin actions remain reachable.
- Built-in chat and task overflow menus follow the standard row actions; plugin controls remain direct row actions.
- Row overflow buttons retain accessible labels without tooltips; Chats header controls retain their tooltips.
- `chats.saveChat(ctxid)` exports an explicit context without changing selection; omitted IDs retain current-chat behavior.
- Cancelling the Load Chat file chooser resolves without calling `chat_load` or showing a success/error notification.
- `sidebar-row-actions-menu` owns plugin-contributed row-menu actions; list-order plugins register stable sort and divider callbacks through the sidebar store instead of patching chat/task stores or injecting row DOM.
- `sidebar-chats-list-view` and `sidebar-tasks-list-view` host plugin list presentations. A row-list extension may expose `hasView()` to hide the default list; both presentations reuse the core row components and their inherited `context`/`task` scopes.
- List-view callbacks belong to their mounted extensions, not store initialization. Use `unregisterRowListExtension(kind, name)` on unmount to restore the default list and remove only the departing extension's sorting and dividers.
- `chats.newChat(projectName)` passes an explicit project choice to `chat_create`; omitted project names retain inheritance behavior, and an empty name explicitly creates a chat without a project.
- Bottom version information shows its commit timestamp in UTC without a timezone suffix and remains on one line.
- Avoid text or controls overflowing fixed sidebar widths.
- Instance-level interface visibility preferences own independent mobile and desktop states for the chat-top controls and right canvas rail; mobile uses the shared 768px breakpoint.
- Process-detail preference changes must use the message renderer's async expansion hooks and honor an explicit chat-history render target so staged pages are ready before an atomic swap.
- The utility-message preference controls both individual utility steps and utility-only process-group chrome so hidden utility runs cannot leave empty headers in the transcript.
- Chat deletion removes the sidebar row optimistically in the same render batch as fallback selection. Keep successful local deletion tombstones for the page session so out-of-order poll or push snapshots cannot reinsert rows; restore the row and clear its tombstone if the delete request fails.
- Chat selection must synchronize the sidebar store even when the low-level context has already switched to the requested ID.
- Context snapshots preserve the Alpine contexts-array and row identities while their order is stable, updating changed row metadata in place so streaming log counters do not reconcile the whole chat list. Additions, removals, reordering, and deletion tombstones must still replace the visible list; selection and parent-expansion synchronization must not publish unchanged state.

- Preserve `canvas:<surface-id>` visibility entries even when a plugin is absent, so later registration restores its saved choice.

## Work Guidance

- Coordinate navigation and state changes with WebSocket sync and chat/project stores.

## Verification

- Smoke-test sidebar collapse, chat list, task list, quick actions, and preferences after changes.

## Child DOX Index

No child DOX files.
