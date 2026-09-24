# Sidebar Folders DOX

## Purpose

- Own project folders, sorting, filters, and manual ordering for sidebar chats and scheduler tasks.

## Ownership

- `webui/sidebar-folders-store.js` owns presentation, preferences, drag and drop, and folder actions.
- `webui/folder-list.html` reuses the core `chat-tree.html` and the `_scheduler` plugin's shared `task-row.html` components.
- `webui/thumbnail.webp` supplies the plugin gallery thumbnail at 256×256 pixels and under 20 KB.
- `api/layout.py` persists independent project/chat/task order lists through `helpers.kvp`.
- `api/move_chat.py` changes project context for an entire chat family.

## Local Contracts

- Folder view is enabled by default; config is instance-wide with a flat-view fallback. Register the optional view through the sidebar row-list extension contract, without replacing stores or moving row DOM.
- Default sorting is creation time, newest first, in both views; message activity must not reorder chats unless recent-activity sorting is explicitly selected.
- Reordering folders, chats, or tasks by drag and drop automatically selects and saves manual sorting.
- Neighboring folder/thread/task drops select the insertion edge that swaps their order; longer moves use the hovered row's midpoint for before/after placement.
- Drag hover reuses the rendered sections and rows; do not regroup chat families on each pointer event or republish an unchanged drop target.
- A grouping pass shares one root list and parent/child index across pins and folders. Filter passes share a child index across families; direct family lookups build a fresh index, preserving current nesting without a persistent cache.
- The folder list passes its existing sections to `sections()`. Retain them when group metadata, row identities and ordering are unchanged; reactive chat metadata continues updating in place without refreshing every row scope.
- Focus refreshes preserve config and order identities when their values are unchanged; the project store preserves unchanged project lists. Refreshes must not rebuild the sidebar solely because a response contains new object instances.
- Both sides of a gap share one insertion target at the following row's top edge, with a bottom edge only after the last row. Drop indicators and released drops use that same target; dragged rows do not target themselves.
- Folder containers receive drops across their padding and expanded contents. Thread-list gaps resolve to the nearest thread, including the last thread's bottom edge; folder headers remain project-move targets for chats. Folder insertion markers surround the whole folder, including its workers, and clear when the drag leaves the list.
- Pin state and row indicators belong to `_pin_to_top`. Each list groups pins above all project folders, including pinned **No project**, with a separator and no subtitle. Pins retain their project/color, appear only once, and return to their own folder when unpinned; project filters also apply to pins.
- Pinned parents retain their nested workers; pinning a worker promotes its whole family without detaching or duplicating it. Only explicitly pinned rows display the Pin to Top indicator.
- Manual ordering stays within the pinned section or the unpinned folders. Reordering pins across projects never changes project assignments, including scheduler tasks. Dropping a pinned chat onto a folder header changes its project while retaining its pin.
- **No project** uses the empty project key and starts pinned first within the default pinned order; its pin action stays available, and explicit manual ordering still applies within the pinned group. Its **Projects** menu action opens the existing global projects list through `$store.projects.openProjectsModal()`.
- Pinned folders reorder among themselves; unpinned folders stay below them. Validate the insertion position, allowing the shared gap after the last pin from either side. Invalid positions show no insertion marker, accept no drop, and do not save order or sorting changes.
- Keep parallel children nested and selectable. Move visible descendants and background workers with their root; retain parent IDs, history, and selection. Reject running families and scheduler-owned contexts before any mutation.
- Use existing project activation/deactivation helpers, persistence, and state invalidation. Restore project/profile state if a family move fails.
- Scheduler tasks retain their configured project; dragging may reorder them within their folder or within the shared pinned section.
- Closed project folders mount their rows only when expanded. Expansion is browser-local, while view, sort, filters, and order survive server/browser reloads. The empty project-filter key means **No project** and must not be replaced with the all-projects default.
- Folder rows use compact spacing tokens; thread lists have no vertical guide border and reuse the smaller core thread dots. Dim empty-folder labels and give their rows the same height as a chat row, preserving space before the next folder.
- Extend list rows `--spacing-xs` beyond the header controls, with the same inset after their last action button. Keep header positions fixed so folder, chat, and worker action columns align in both views.
- Folder actions reuse the standard chat action buttons with a subtle border at rest. Show them on pointer hover, keyboard focus, or while the folder menu is open; touch devices also show them for expanded folders.
- Folder-row new-chat and overflow buttons use accessible labels without tooltips; Chats header controls retain their tooltips.
- Sidebar menus share their pointer scope with the opening row or header. Dismiss after leaving both, allowing a short gap-crossing delay; also dismiss when focus leaves, the surrounding list scrolls, the window resizes, or the header extension unmounts. Mouse cleanup must not interrupt touch interaction or scrolling inside a menu.
- Resolve the core row menu through its `rowActionsMenu` reference, not shared menu styling classes that community plugins may also use. Header integrations must preserve the core header and its `chats-header-controls` extension point.
- The two list-view extension points are display-only alternatives. Disabling the plugin restores the core lists and existing chat/task controls.
- Register view and sorting callbacks when each list-view extension mounts, and unregister them when it unmounts. Importing the store from another plugin must not hide or filter the core lists while this plugin is disabled.

## Work Guidance

- Reuse project creation/edit/file dialogs, notifications, native drag events, and Material `x-icon` elements.
- View, sort, and Project/Status/Last activity filters share the plugin configuration API and save automatically from the sidebar menu. Missing or invalid filters fall back to all projects/statuses/times. This plugin has no separate configuration page.
- Project moves and ordering use drag and drop, without move actions in thread menus. Folder-row creation uses the same `chat_add_on` icon as the New chat menu action.
- Header, folder, chat, worker, and task action buttons share hover/focus treatment. The two Chats header icons use `1.125rem` inside the existing button frames, preserving action-column alignment with the smaller row icons. Header borders appear only on hover; row buttons retain their resting borders. Use `--spacing-xs` between buttons and at row ends. Keep these sidebar-scoped overrides in the plugin's header extension and retain row visibility behavior and confirmation states.
- The options menu contains only View (Folders / Flat mode), Sort by, Project, Status, and Last activity. Keep native dropdowns consistent with Settings: muted borders, the small radius token, and an opaque menu-colored surface so native option lists remain readable. Use `--spacing-xs` gaps between fields and `--spacing-sm` outer padding. Show focus outlines for keyboard navigation, without a lingering pointer-click ring. Folder expansion belongs to individual folder rows.
- Sort copy uses **Last active**. Chats and tasks share **All**, **Working**, and **Idle**. A family is Working if any member runs without being paused or disabled; otherwise it is Idle, including completed/waiting chats, paused chats, and disabled tasks.

## Verification

- `python -m pytest plugins/_sidebar_folders/tests/test_folders.py tests/test_chat_create.py tests/test_sidebar_row_actions.py tests/test_chat_working_animation.py tests/test_webui_chat_deletion.py -q`
- `node plugins/_sidebar_folders/tests/test_frontend.mjs`
- Check unchanged window-focus refreshes avoid sidebar DOM updates; activity metadata must still update clocks, status and names, with regrouping when ordering, filters or family membership change.
- Verify live creation in an explicit project, folder/flat switching, nesting, pins, drag ordering, cross-project chat moves, no-project moves, task actions, reload persistence, and desktop/mobile/light-mode layouts.

## Child DOX Index

No child DOX files.
