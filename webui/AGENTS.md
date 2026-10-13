# WebUI DOX

## Purpose

- Own the Flask-served Alpine.js WebUI shell, frontend modules, components, CSS, static assets, and vendored browser libraries.
- Keep the UI coherent with backend APIs, WebSocket state, plugin extension points, and documented frontend patterns.

## Ownership

- `splash.html` owns the self-contained cache/bootstrap document served at `/`; `safe.html` owns the self-contained service-worker escape hatch served at `/safe`; `index.html`, `index.js`, and `index.css` define the rendered main UI shell served directly at `/index.html` and `/safe`, and fetched from `/ui/index` for in-place installation at `/`.
- `components/` owns self-contained Alpine components and component stores.
- `js/` owns shared frontend modules, API clients, WebSocket clients, stores, extension loaders, and utility code.
- `css/` owns shared stylesheet modules.
- `public/` owns first-party static image/icon assets.
- `vendor/` owns vendored third-party browser libraries.

## Local Contracts

- Store-dependent UI must be gated with `x-data` and `x-if="$store.storeName"` before using the store.
- Use `createStore` from `/js/AlpineStore.js` for frontend stores.
- Use `openModal(path)` and `closeModal()` from `/js/modals.js` for modal flows.
- Use `/js/api.js` helpers so CSRF and auth behavior stays consistent.
- Component tags use `<x-component path="...">`; paths are resolved under `webui/components/` when not already prefixed.
- Frontend extension breakpoints use `<x-extension id="...">` and are loaded through `/js/extensions.js`.
- `sw.js` owns same-origin HTML/CSS/JavaScript caching. The self-contained splash fetches `/ui/index` and the gzip-compressed `/ui/asset-bundle` in parallel, installs the versioned worker, waits until the bundle is usable in memory, and then installs the rendered index into the current `/` document without navigation. The worker persists the whole prepared bundle as one Cache Storage response in the background and removes obsolete version caches. Eligible text bodies up to 512 KiB each may be embedded; unknown or runtime-computed text URLs use one ordinary backend request and are cached as the native response when their transferred body is at most 256 KiB. The worker does not parse imports, call a secondary graph endpoint, or perform compression. Worker, cache, bundle, and timeout failures fall through to the already-started backend document or ordinary backend asset request. Media, images, fonts, and manifests use normal browser HTTP caching.
- `splash.html` keeps its logo, styling, and bootstrap logic self-contained. Before replacing the document, it carries its current overlay markup into the rendered index. `index.html` owns the matching inline critical overlay style and fades that same visual overlay after initial component/extension readiness, with a bounded failure timeout; it must not contain duplicate static overlay markup. The critical style carries html-level theme backgrounds and the icon guard inline, so no stylesheet blocks first paint: the carried overlay and its logo render immediately, and the reveal additionally waits (bounded) for the main stylesheet to be applied since application stylesheets are non-render-blocking. Icon-font preloading begins when the index is placed behind the overlay, continues independently behind square transparent placeholders, and must neither compete with the startup bundle nor delay the application reveal. `safe.html` must remain self-contained: its first phase unregisters all service workers for the origin, then replaces itself with the directly rendered `/safe` phase without fetching the bundle or registering a worker. The direct phase repeats unregistration defensively but does not initialize a worker; returning to `/` may install the current worker again. The rendered index removes only the internal safe-mode query marker from `/safe` in browser history. Initial application stylesheets are all non-render-blocking.
- `js/icons.js` owns the native `<x-icon>` element. First-party WebUI and bundled-plugin markup must use `<x-icon name="lowercase_snake_case"></x-icon>` for static Material Symbols and `:name="expression"` for Alpine-driven names; do not put ligature text inside the element or author new `.material-symbols-outlined` spans. The element uses the single local WOFF2 font rather than per-icon SVG requests, validates names, defaults unlabeled icons to `aria-hidden="true"`, and retains the legacy Material class internally so established selectors continue to apply. The shared vendor CSS constrains both `<x-icon>` and legacy ligature spans to a clipped 1:1 em square and keeps them transparent until the icon face is confirmed after the installed application document finishes parsing. `.material-symbols-outlined` and `.material-icons-outlined` spans remain supported for third-party plugin compatibility but are not the first-party authoring API.
- Component HTML loaded by the shared loader may include `<title>`, module scripts, body content, and scoped styles; modal content uses the same loader path.
- Do not bypass WebSocket origin/auth/CSRF assumptions from frontend code.
- `index.js` rechecks the selected context after asynchronous snapshot hooks and message rendering; an older snapshot must not replace selection or sidebar state after a chat switch or creation.
- Avoid editing vendored files unless intentionally updating the vendor asset.
- Startup scripts in `index.html` must be local and non-parser-blocking: use ES modules, `defer`, or `async` for every script with `src`.
- Baseline main and login pages must load scripts, styles, fonts, and images from same-origin vendored or first-party assets so they remain usable without internet access.
- Native checkboxes use dark surfaces and the `--color-input` accent in dark mode; the mixed state uses the native light-scheme mark for contrast; retain native checkmarks, indeterminate marks, keyboard focus, disabled behavior, and light-mode appearance. This shared rule lives in `index.css`.
- `index.css` renders every `<x-icon name="stop">` as a filled, subtly rounded square using `currentColor`, retaining the shared icon box and font-loading visibility guard.
- Rubik (`--font-family-main`) is the default WebUI text and control font; use the code/mono font tokens only for code, logs, paths, and fixed-width data.
- Hover, focus, and active border treatments should follow existing neutral border/background patterns; avoid hard-coded blue border highlights unless matching an established specialized surface.
- Keep transient UI affordances such as Bootstrap tooltips and notification toasts above normal and legacy modal layers while confirmation dialogs remain on top.

## Work Guidance

- Put component-specific markup and styles under `components/`; put reusable frontend infrastructure under `js/`; put shared visual primitives under `css/`.
- Keep UI text and controls consistent with existing components.
- Use notifications for user-facing success, warning, and error feedback where the app already uses notification flows.
- Coordinate API payload changes with backend handlers and tests.

## Verification

- Run targeted WebUI/frontend tests when available.
- Manually smoke-test visible UI changes with `python run_ui.py` when behavior cannot be covered by tests.
- Verify desktop and mobile layout for substantial UI changes.

## Child DOX Index

Direct child DOX files:

| Child | Scope |
| --- | --- |
| [components/AGENTS.md](components/AGENTS.md) | Alpine component HTML, component stores, and component-local styles. |
| [css/AGENTS.md](css/AGENTS.md) | Shared WebUI stylesheet modules. |
| [js/AGENTS.md](js/AGENTS.md) | Shared frontend JavaScript modules and client-side infrastructure. |
| [public/AGENTS.md](public/AGENTS.md) | First-party static WebUI images, icons, splash art, and PWA assets. |
| [vendor/AGENTS.md](vendor/AGENTS.md) | Vendored third-party browser libraries. |
