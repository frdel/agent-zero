# WebUI CSS DOX

## Purpose

- Own shared stylesheet modules for the WebUI.
- Keep shared visual primitives stable across components and pages.

## Ownership

- Each CSS file owns a named surface or primitive family such as buttons, messages, modals, notifications, scheduler, settings, surfaces, tables, or toast.
- `loading-indicators.css` owns reusable loading visuals; `messages.css` owns chat-history paging placement, the context-switch splash surface, and lazy message-preview states in addition to message presentation.
- `overflow.css` owns the globally loaded `x-overflow` row, borderless ellipsis button, and popover styles constrained by both viewport and available submenu space; original plugin panel styling remains in its owner.
- Overflow entry visuals retain their owner styles inside a non-interactive `.overflow-icon` slot. Empty slots must not reserve space.
- Component-specific styles should usually stay inside the component HTML unless they are intentionally shared.
- `modals.css` owns the shared stacked modal shell, backdrop, scroll area, footer slot, modal button classes, floating/no-backdrop modal behavior, and shared modal section primitives.
- `surfaces.css` owns surface modal switchers, action rails, draggable header affordances, focus-button state, and right-canvas surface primitives. Files, Editor, and Browser opt into `surface-workspace` for the lighter panel palette, common toolbar chrome, flat `surface-control` buttons, and group separators. Surface modal headers share a 48px border-box height with centered titles and controls; component styles must not override their sizing. Surface modal header controls are borderless in normal, hover, and active states; preserve group separators and keyboard focus outlines. Tab bars and toolbars share a 48px baseline with vertically centered controls. File trees use `--color-background` to contrast with the lighter `--color-panel` workspace. Keep these styles opt-in and preserve viewer/content themes; primary empty-state actions such as Open Browser retain their existing button styling.
- `index.css` defines global theme variables such as `--color-*`, `--spacing-*`, `--font-size-*`, and `--transition-speed`; `--color-surface-translucent` is the shared glass fill for floating header and canvas surfaces and stays theme-derived through the chat background.

- `tables.css` owns the shared selection summary and borderless close control used by Files and Memory.

## Local Contracts

- Use existing CSS variables and naming patterns before introducing new global tokens.
- Avoid broad selectors that unexpectedly restyle plugin UI or unrelated components.
- Keep layout rules responsive and verify text does not overflow fixed controls.
- Settings replaces its sidebar tree with a compact native section picker at mobile widths and uses dynamic viewport height to keep its footer in view.
- Shared modal buttons use `btn btn-ok` for positive actions and `btn btn-cancel` for dismissive or negative actions.
- Shared compact text actions use `.text-button`; component-local styles may adjust layout or sizing but must not be the only definition of the primitive.
- Modal footer action order is positive action first, dismissive or negative action second.
- Modal footers use `.modal-footer` plus `data-modal-footer`; do not redefine `.btn`, `.modal-footer`, `.modal-inner`, or `.modal-scroll` inside components.
- Shared modal sizing keeps `.modal-inner` centered with `width: 90%`, `max-width: 960px`, and `max-height: 90vh`.
- Tall modal bodies must scroll inside `.modal-scroll`; pinned footer content must stay outside that scroll area.
- `.modal-floating` must keep the full-screen shell pointer-transparent while `.modal-inner` remains pointer-active.
- Use `.modal-no-backdrop` only for backdrop suppression without click-through floating behavior.
- Shared modal layers must stay above the mobile right-canvas rail while confirmation dialogs remain above normal modals.
- Generic `.loading` placeholders and their shimmer pseudo-elements remain invisible for the default 500ms loading delay.
- Shared message collapsing targets `.message-collapse-content`; user-message attachments must remain outside that target so expanding text never changes attachment visibility.
- The virtualized chat history disables native scroll anchoring and replay fade-in motion; the message-window renderer owns anchor restoration during atomic page swaps.
- The persistent right panel transitions its background symmetrically between Welcome and chat in 200ms; the Welcome container remains transparent so it cannot hide the return transition.
- Do not add decorative one-note palette changes that conflict with existing WebUI design.

## Work Guidance

- Keep shared CSS small and scoped to clear class families.
- Coordinate class renames with all component and plugin references.
- Prefer improving an existing primitive over creating a near-duplicate style family.
- Use component-local styles for unique layouts and shared CSS for repeated primitives such as modal sections, toolbars, buttons, tables, notifications, and surfaces.
- Preserve modal sizing and scrolling expectations: centered `.modal-inner`, constrained viewport height, body scroll inside `.modal-scroll`, and footer outside the scroll area.

## Verification

- Manually inspect affected WebUI screens at desktop and mobile widths for shared CSS changes.
- Run visual or frontend tests if the touched style has coverage.
- For modal CSS, test a tall modal, a footer modal, a stacked modal, and a floating modal.

## Child DOX Index

No child DOX files.
