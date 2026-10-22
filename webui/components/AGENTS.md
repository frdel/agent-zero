# WebUI Components DOX

## Purpose

- Own self-contained Alpine.js components, component stores, and component-local styles.
- Keep component lifecycle, store registration, and nested component loading consistent.

## Ownership

- Each subdirectory owns a UI feature area such as sidebar, settings, projects, notifications, plugins, canvas, or welcome screens.
- `*-store.js` files own component state and actions.
- Component HTML files own their markup, local module imports, and local scoped styles.
- `_examples/` contains reference implementations for component and store shape.
- Modal components normally live under `modals/<name>/<name>.html`; settings components live under `settings/`.

## Local Contracts

- Module imports belong in the component `<head>`.
- Module scripts must use `type="module"` and import stores before Alpine evaluates bindings.
- Rendered content belongs in the component `<body>`.
- Wrap store-dependent content with `x-data` and a `template x-if="$store.name"` gate.
- A gated `<template>` must contain one root element.
- Keep component-specific styles in the component `<style>` block; use shared CSS only for primitives that are genuinely reused.
- Use CSS variables from `index.css` for color, spacing, typography, borders, and transitions.
- Use `x-create` for per-mount setup and `x-destroy` for cleanup; do not call long-lived store `init()` from `x-init`.
- Store `init()` must be idempotent and guarded when it registers global listeners, intervals, or one-time data.
- Store state can be read as `$store.name` in templates and through direct module imports in JavaScript; avoid `window.Alpine.store()` lookups in component code.
- Use `globalThis.xAttrs(element)` only for explicit parent `<x-component>` attribute inheritance.
- Use shared API, modal, notification, confirmation, and store helpers instead of ad hoc globals.
- Author Material Symbols as empty `<x-icon name="lowercase_snake_case"></x-icon>` elements. Bind changing icons through `:name`, keep accessible text on the owning control, and do not add new ligature-text spans or `x-text` icon bindings.
- Components that use polling directives may use `x-every-second`, `x-every-minute`, or `x-every-hour` only while mounted.
- Use `$confirmClick` for destructive two-click confirmations where the existing UI pattern fits.
- Name component files `feature-name.html` and stores `feature-store.js` or `feature-name-store.js`.

## Work Guidance

- Keep component stores cohesive and avoid cross-component state mutation unless a shared store owns that state.
- Prefer nested `<x-component path="...">` for reusable UI pieces.
- Use absolute imports such as `/components/...` and `/js/...` so loader-generated module URLs resolve reliably.
- Preserve flex layouts through loader wrappers with `display: contents` on the specific wrapper chain when needed.
- Use `callJsonApi()` for JSON-in/JSON-out calls and `fetchApi()` for raw fetches that still need CSRF handling.
- Use `openModal(path)` for modal entry points; modal titles come from component `<title>`.
- Add modal footers with `data-modal-footer` so `modals.js` can move them to the pinned footer slot.
- Keep modal footer elements stable after load; conditional footers should not be repeatedly created and destroyed.
- Use `.modal-floating` only for non-blocking utility panels where page clicks must pass through; do not use it for destructive confirmations, settings, auth, import/export, or required workflows.
- Do not add `document.addEventListener("alpine:init", ...)` blocks inside component HTML.
- Do not use legacy `x-teleport` plus `.modal-overlay` modal patterns for new work.
- Do not introduce a second modal overlay system or manually reshape `.modal-inner`, `.modal-scroll`, or `.modal-footer-slot`.
- Do not hide fetch, import, or lifecycle errors with broad `.catch(() => null)` handlers; surface failures through notifications or console errors as appropriate.
- Do not store sensitive modal values in long-lived stores without explicit cleanup on close.

## Verification

- Manually exercise the affected component in the WebUI for visible or lifecycle changes.
- Run targeted tests for settings, plugins, notifications, projects, state sync, or other touched flows when available.
- For modal changes, verify open, close button, Escape, click-outside, stacked modal, scroll, and pinned footer behavior.

## Child DOX Index

Direct child DOX files:

| Child | Scope |
| --- | --- |
| [_examples/AGENTS.md](_examples/AGENTS.md) | Reference component and store examples. |
| [canvas/AGENTS.md](canvas/AGENTS.md) | Right-canvas component surface and store. |
| [chat/AGENTS.md](chat/AGENTS.md) | Chat composer, attachments, queue, navigation, and top-section components. |
| [dropdown/AGENTS.md](dropdown/AGENTS.md) | Shared dropdown component. |
| [durability/AGENTS.md](durability/AGENTS.md) | Recovery decisions, explicit restore selection and typed chat plans. |
| [messages/AGENTS.md](messages/AGENTS.md) | Message rendering helpers, action buttons, process groups, and resize behavior. |
| [modals/AGENTS.md](modals/AGENTS.md) | Modal component workflows loaded through the shared modal stack. |
| [notifications/AGENTS.md](notifications/AGENTS.md) | Toasts, notification modal, icons, and notification store. |
| [plugins/AGENTS.md](plugins/AGENTS.md) | Plugin settings, info, list, execution, and toggle components. |
| [projects/AGENTS.md](projects/AGENTS.md) | Project creation, selection, edit, secrets, model, skill, and file-structure components. |
| [settings/AGENTS.md](settings/AGENTS.md) | Settings shell and built-in settings subsections. |
| [sidebar/AGENTS.md](sidebar/AGENTS.md) | Left sidebar layout, chat/task lists, top actions, and preferences. |
| [sync/AGENTS.md](sync/AGENTS.md) | WebUI sync status component and store. |
| [tooltips/AGENTS.md](tooltips/AGENTS.md) | Shared tooltip store and behavior. |
| [welcome/AGENTS.md](welcome/AGENTS.md) | Welcome screen, discovery cards, banners, and welcome state. |
