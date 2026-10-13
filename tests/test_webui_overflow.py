"""Exercise x-overflow with real Alpine scopes, layout, and plugin-style insertion."""

import mimetypes
from pathlib import Path
import tempfile
from urllib.parse import urlparse

import pytest

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]


def serve_page(page, html):
    def serve(route):
        path = urlparse(route.request.url).path
        if path == "/":
            route.fulfill(content_type="text/html", body=html)
        else:
            asset = ROOT / "webui" / path.lstrip("/")
            route.fulfill(path=asset, content_type=mimetypes.guess_type(asset)[0])

    page.route("**/*", serve)


def test_overflow_preserves_original_controls_and_plugin_menus():
    html = """<!doctype html><html><head>
      <link rel="stylesheet" href="/index.css">
      <link rel="stylesheet" href="/vendor/google/google-icons.css">
      <link rel="stylesheet" href="/css/buttons.css">
      <link rel="stylesheet" href="/css/overflow.css">
      <style>
        body { padding: 20px; }
        #row { display: flex; gap: 8px; width: 600px; margin-top: 400px; }
        .control { position: relative; }
        .control > button { width: 130.125px; height: 32px; }
        .panel { position: absolute; bottom: 100%; width: 240px; padding: 12px;
                 background: var(--color-panel); border: 1px solid gray; }
        .test-avatar { display: inline-grid; place-items: center; width: 24px; height: 24px; border-radius: 50%; }
        .test-avatar img { width: 100%; height: 100%; }
        .test-ring { position: relative; display: inline-grid; place-items: center; }
        .test-ring svg { position: absolute; inset: 0; width: 100%; height: 100%; fill: none; stroke: blue; }
        .test-ring > span { font-size: 8px; }
        .plugin, x-extension, x-component { display: contents; }
      </style>
      <script type="module">
        import { registerOverflow } from '/js/overflow.js';
        document.addEventListener('alpine:init', () => registerOverflow(Alpine));
        await import('/vendor/alpine/alpine.min.js');
      </script>
    </head><body x-data="{ mounted: true, chosen: '', initials: 'D', avatarColor: 'blue', avatarImage: null, usage: '19%', ring: '19 100' }">
      <button id="outside">Outside</button>
      <template x-if="mounted">
        <div id="row" x-overflow x-data="{ model: false, agent: false, context: false }">
          <div class="control" @click.outside="model = false">
            <button id="model" @click="model = !model">Model</button>
            <div id="model-panel" class="panel" x-show="model" style="display:none">
              <button @click="chosen = 'Model'; model = false">Default preset</button>
            </div>
          </div>
          <div class="control" @click.outside="agent = false">
            <button id="agent" @click="agent = !agent">
              <span class="test-avatar" data-overflow-icon aria-hidden="true"
                    x-init="window.avatarMounts = (window.avatarMounts || 0) + 1"
                    :style="`background:${avatarColor}`">
                <img x-show="avatarImage" :src="avatarImage" alt="">
                <span x-show="!avatarImage" x-text="initials"></span>
              </span>
              Agent
            </button>
            <div id="agent-panel" class="panel" x-show="agent" style="display:none">
              <button @click="chosen = 'Agent'; agent = false">Default agent</button>
            </div>
          </div>
          <x-extension><x-component class="plugin-slot"></x-component></x-extension>
          <div class="control" @click.outside="context = false">
            <button id="usage" class="test-ring" style="width:28px;height:28px" data-overflow-icon
                    data-overflow-label="Context window" @click="context = !context">
              <svg viewBox="0 0 36 36" aria-hidden="true"><circle cx="18" cy="18" r="15" :stroke-dasharray="ring"></circle></svg>
              <span x-text="usage"></span>
            </button>
            <div class="panel" x-show="context" style="display:none">Context details</div>
          </div>
        </div>
      </template>
    </body></html>"""

    with playwright.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except playwright.Error as error:
            if "Executable doesn't exist" in str(error):
                pytest.skip("An installed Playwright Chromium browser is required.")
            raise
        page = browser.new_page(viewport={"width": 900, "height": 700}, has_touch=True)
        serve_page(page, html)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto("http://overflow.test/")
        page.wait_for_selector("#model")
        page.evaluate("""() => {
          document.querySelector('.plugin-slot').innerHTML = `
            <div class="plugin" x-data="{ open: false, custom: '' }">
              <div class="control" @click.outside="open = false">
                <button id="effort" @click="open = !open"><span class="material-symbols-outlined" aria-hidden="true">psychology</span>Reasoning effort</button>
                <div id="effort-panel" class="panel" x-show="open" style="display:none">
                  <button @click="chosen = 'Auto'; open = false">Auto</button>
                  <button @click="chosen = 'High'; open = false">High</button>
                  <input x-model="custom" aria-label="Custom effort">
                </div>
              </div>
            </div>`;
          window.originalEffort = document.getElementById('effort');
        }""")
        page.wait_for_selector("#effort")
        more = page.get_by_role("button", name="More controls", exact=True)
        playwright.expect(more).to_be_hidden()
        page.evaluate("document.getElementById('row').style.width = '220px'")
        playwright.expect(more).to_be_visible()
        assert more.evaluate("el => getComputedStyle(el).borderTopWidth") == "0px"
        more.hover()
        assert more.evaluate("el => getComputedStyle(el).boxShadow") == "none"
        assert more.locator("x-icon").evaluate("el => parseFloat(getComputedStyle(el).fontSize)") == 24
        more.click()
        menu = page.get_by_role("menu", name="More controls")
        playwright.expect(menu.locator(".overflow-label")).to_have_text(["Agent", "Reasoning effort", "Context window"])
        avatar = menu.locator(".test-avatar")
        ring = menu.locator(".test-ring")
        playwright.expect(avatar).to_have_text("D")
        playwright.expect(ring).to_have_text("19%")
        assert avatar.evaluate("el => getComputedStyle(el).backgroundColor") == "rgb(0, 0, 255)"
        assert menu.locator(".overflow-icon button, [id=agent], [id=usage], [x-init]").count() == 0
        assert menu.locator('.overflow-icon x-icon[name="psychology"]').count() == 1
        page.evaluate("""() => {
          Object.assign(Alpine.$data(document.body), {initials:'R', avatarColor:'red', usage:'42%', ring:'42 100'});
        }""")
        playwright.expect(avatar).to_have_text("R")
        playwright.expect(ring).to_have_text("42%")
        playwright.expect(ring.locator("circle")).to_have_attribute("stroke-dasharray", "42 100")
        assert avatar.evaluate("el => getComputedStyle(el).backgroundColor") == "rgb(255, 0, 0)"
        page.evaluate("Alpine.$data(document.body).avatarImage = 'data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs='")
        playwright.expect(avatar.locator("img")).to_be_visible()
        playwright.expect(avatar.locator("span")).to_be_hidden()
        assert page.evaluate("window.avatarMounts") == 1
        effort = menu.get_by_role("menuitem", name="Reasoning effort")
        effort.hover()
        playwright.expect(page.get_by_label("Custom effort")).to_be_visible()
        effort.click()
        playwright.expect(page.get_by_label("Custom effort")).to_be_hidden()
        effort.dispatch_event("pointermove", {"pointerType": "mouse"})
        playwright.expect(effort).to_have_attribute("aria-expanded", "false")
        page.mouse.move(0, 0)
        effort.hover()
        playwright.expect(page.get_by_label("Custom effort")).to_be_visible()
        effort.click()
        playwright.expect(page.get_by_label("Custom effort")).to_be_hidden()
        effort.tap()
        playwright.expect(page.get_by_label("Custom effort")).to_be_visible()
        effort.tap()
        playwright.expect(page.get_by_label("Custom effort")).to_be_hidden()
        effort.press("Enter")
        playwright.expect(page.get_by_label("Custom effort")).to_be_visible()
        page.get_by_label("Custom effort").fill("custom-value")
        page.get_by_label("Custom effort").press("ArrowLeft")
        playwright.expect(page.get_by_label("Custom effort")).to_be_focused()
        page.get_by_label("Custom effort").press("Escape")
        playwright.expect(menu).to_be_visible()
        playwright.expect(effort).to_be_focused()
        effort.press("Enter")
        playwright.expect(page.get_by_label("Custom effort")).to_be_visible()
        playwright.expect(page.get_by_label("Custom effort")).to_have_value("custom-value")
        page.get_by_role("button", name="High", exact=True).click()
        playwright.expect(menu).to_be_hidden()
        assert page.evaluate("Alpine.$data(document.body).chosen") == "High"
        assert page.evaluate("document.getElementById('effort') === window.originalEffort")

        # Both built-in and plugin actions keep their original scoped handlers.
        more.press("ArrowDown")
        agent = menu.get_by_role("menuitem", name="Agent", exact=True)
        playwright.expect(agent).to_be_focused()
        agent.press("ArrowRight")
        option = page.get_by_role("button", name="Default agent", exact=True)
        playwright.expect(option).to_be_focused()
        option.click()
        assert page.evaluate("Alpine.$data(document.body).chosen") == "Agent"
        playwright.expect(menu).to_be_hidden()

        # Attribute/text changes and controls inserted after mount are observed.
        page.evaluate("document.getElementById('effort').disabled = true")
        more.click()
        playwright.expect(effort).to_be_disabled()
        page.evaluate("document.getElementById('effort').disabled = false; document.getElementById('effort').textContent = 'Effort: High'")
        effort = menu.get_by_role("menuitem", name="Effort: High")
        playwright.expect(effort).to_be_enabled()
        effort.press("Enter")
        page.get_by_role("button", name="Outside").click()
        playwright.expect(menu).to_be_hidden()
        playwright.expect(page.get_by_label("Custom effort")).to_be_hidden()

        # Closing before Alpine has displayed a submenu must cancel the pending open.
        page.evaluate("""() => {
          document.querySelector('.overflow-trigger').click();
          document.querySelector('.overflow-menu button:last-child').click();
          document.querySelector('.overflow-trigger').click();
        }""")
        playwright.expect(menu).to_be_hidden()

        # Resizing restores the same nodes and removes the overflow affordance.
        page.evaluate("document.getElementById('row').style.width = '600px'")
        playwright.expect(more).to_be_hidden()
        page.locator("#effort").click()
        playwright.expect(page.get_by_label("Custom effort")).to_have_value("custom-value")
        assert page.locator("#effort-panel").get_attribute("popover") is None
        page.get_by_role("button", name="Outside").click()

        # A shrink-wrapped row must also notice its parent gaining space.
        page.evaluate("""() => {
          document.getElementById('row').style.cssText = 'width:fit-content;max-width:100%';
          document.body.style.width = '220px';
        }""")
        playwright.expect(more).to_be_visible()
        page.evaluate("document.body.style.width = '900px'")
        playwright.expect(more).to_be_hidden()
        page.evaluate("document.body.style.width = ''")

        # At phone widths every menu, including the first control, stays on screen.
        page.set_viewport_size({"width": 320, "height": 600})
        page.evaluate("document.getElementById('row').style.width = '120px'")
        more.click()
        model = menu.get_by_role("menuitem", name="Model", exact=True)
        playwright.expect(model.locator(".overflow-icon")).to_be_hidden()
        assert model.evaluate("""el => {
          const label = el.querySelector('.overflow-label');
          return Math.abs(label.getBoundingClientRect().left - el.getBoundingClientRect().left - parseFloat(getComputedStyle(el).paddingLeft)) < 1;
        }""")
        model.hover()
        page.wait_for_selector("#model-panel:popover-open")
        for selector in [".overflow-menu", ".overflow-panel"]:
            bounds = page.locator(selector).bounding_box()
            assert bounds and bounds["x"] >= 0 and bounds["x"] + bounds["width"] <= 320
            assert bounds["y"] >= 0 and bounds["y"] + bounds["height"] <= 600
        page.get_by_role("button", name="Default preset", exact=True).click()
        assert page.evaluate("Alpine.$data(document.body).chosen") == "Model"

        more.click()
        effort.hover()
        page.wait_for_selector("#effort-panel:popover-open")
        effort.click()
        playwright.expect(page.get_by_label("Custom effort")).to_be_hidden()
        page.evaluate("""() => {
          document.getElementById('row').style.overflow = 'hidden';
          const panel = document.getElementById('effort-panel');
          panel.style.width = '600px';
          panel.insertAdjacentHTML('beforeend', '<div style="height:800px"></div><button id="last-option">Last option</button>');
        }""")
        effort.press("Enter")
        page.wait_for_selector("#effort-panel:popover-open")
        for width, height in [(420, 575), (320, 360), (390, 664), (844, 390)]:
            page.set_viewport_size({"width": width, "height": height})
            page.wait_for_function("""() => {
              const r = document.querySelector('.overflow-panel').getBoundingClientRect();
              return r.left >= 8 && r.right <= innerWidth - 8 && r.top >= 8 && r.bottom <= innerHeight - 8;
            }""")
            page.locator("#last-option").scroll_into_view_if_needed()
            assert page.locator("#last-option").evaluate("""el => {
              const r = el.getBoundingClientRect();
              return document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2) === el;
            }""")
            assert effort.evaluate("""el => {
              const r = el.getBoundingClientRect();
              return el.contains(document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2));
            }""")
        effort.click()
        playwright.expect(page.get_by_label("Custom effort")).to_be_hidden()
        effort.press("Enter")
        page.wait_for_selector("#effort-panel:popover-open")
        page.evaluate("document.querySelector('.plugin-slot').replaceChildren()")
        playwright.expect(menu.locator(".overflow-label")).to_have_text(["Model", "Agent", "Context window"])
        page.evaluate("Alpine.$data(document.body).mounted = false")
        playwright.expect(page.locator(".overflow-trigger, .overflow-panel, .overflow-menu")).to_have_count(0)
        assert errors == []
        browser.close()


def test_model_switcher_menus_fit_short_windows_and_remain_scrollable():
    component = (ROOT / "plugins/_model_config/extensions/webui/chat-input-progress-start/model-switcher.html").read_text()
    component = component.split("</script>", 1)[1]
    html = """<!doctype html><html><head>
      <link rel="stylesheet" href="/index.css">
      <link rel="stylesheet" href="/css/buttons.css">
      <link rel="stylesheet" href="/css/overflow.css">
      <script type="module">
        import { registerOverflow } from '/js/overflow.js';
        document.addEventListener('alpine:init', () => {
          registerOverflow(Alpine);
          Alpine.store('chats', { selected: 'test', selectedContext: { agent_profile: 'agent0' } });
          Alpine.store('modelConfig', {
            switcherAllowed: true, switcherLoading: false, switcherOverride: null,
            switcherEffectivePreset: 'Preset 0', agentProfilesLoading: false,
            switcherPresets: Array.from({length: 20}, (_, i) => ({
              name: `Preset ${i}`, chat: {provider: 'test', name: 'main-model'},
              utility: {provider: 'test', name: 'utility-model'},
              embedding: {provider: 'test', name: 'embedding-model'},
            })),
            refreshSwitcher() {}, loadAgentProfiles() {},
            getSwitcherLabel() { return this.switcherEffectivePreset; },
            selectPresetSwitch(chat, name) { this.switcherEffectivePreset = name; },
            getAgentProfileVisual() { return {color: 'gray', initials: 'A0', url: ''}; },
            getAgentProfileList() {
              return Array.from({length: 20}, (_, i) => ({key: `agent${i}`, label: `Agent ${i}`}));
            },
          });
        });
        await import('/vendor/alpine/alpine.min.js');
      </script>
    </head><body>
      <div id="composer" style="position:fixed; bottom:120px; left:20px; right:20px;">
    """ + component + "</div></body></html>"

    with playwright.sync_playwright() as p:
        try:
            browser = p.chromium.launch(ignore_default_args=["--hide-scrollbars"])
        except playwright.Error as error:
            if "Executable doesn't exist" in str(error):
                pytest.skip("An installed Playwright Chromium browser is required.")
            raise
        page = browser.new_page(viewport={"width": 912, "height": 780})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        serve_page(page, html)
        page.goto("http://switcher.test/")
        page.wait_for_selector(".model-switcher-btn")

        def assert_menu_fits(selector):
            page.wait_for_function("""selector => {
              const r = document.querySelector(selector).getBoundingClientRect();
              return r.top >= 8 && r.bottom <= innerHeight - 8
                && r.left >= 8 && r.right <= innerWidth - 8 && r.height > 0;
            }""", arg=selector)

        for trigger, selector in [
            (".model-switcher-btn", ".model-switcher-dropdown"),
            (".agent-profile-btn", ".agent-profile-dropdown"),
        ]:
            page.locator(trigger).click()
            menu = page.locator(selector)
            assert_menu_fits(selector)
            for height in [780, 440, 280, 780]:
                page.set_viewport_size({"width": 912, "height": height})
                assert_menu_fits(selector)
                assert menu.evaluate("el => el.scrollHeight > el.clientHeight")
                assert menu.evaluate("el => getComputedStyle(el).scrollbarWidth") == "thin"
            assert menu.bounding_box()["height"] == 550
            page.set_viewport_size({"width": 912, "height": 440})
            assert_menu_fits(selector)
            bounds = menu.bounding_box()
            page.mouse.move(bounds["x"] + bounds["width"] - 6, bounds["y"] + 32)
            page.mouse.down()
            page.mouse.move(bounds["x"] + bounds["width"] - 6, bounds["y"] + bounds["height"] - 18, steps=12)
            page.mouse.up()
            page.wait_for_function("""selector => {
              const el = document.querySelector(selector);
              return el.scrollTop >= el.scrollHeight - el.clientHeight - 1;
            }""", arg=selector)
            menu.hover()
            page.mouse.wheel(0, -10000)
            page.wait_for_function("selector => document.querySelector(selector).scrollTop === 0", arg=selector)
            page.locator(trigger).click()

        # The original panel must also fit when opened through the overflow menu.
        page.set_viewport_size({"width": 390, "height": 440})
        page.evaluate("document.getElementById('composer').style.width = '80px'")
        more = page.get_by_role("button", name="More controls", exact=True)
        playwright.expect(more).to_be_visible()
        more.click()
        page.get_by_role("menuitem", name="Preset 0").click()
        page.wait_for_selector(".model-switcher-dropdown:popover-open")
        assert_menu_fits(".model-switcher-dropdown")
        last_preset = page.locator(".model-switcher-preset-name").get_by_text("Preset 19", exact=True)
        last_preset.scroll_into_view_if_needed()
        last_preset.click()
        playwright.expect(page.locator(".model-switcher-label")).to_have_text("Preset 19")
        assert errors == []
        browser.close()


def test_browser_zoom_does_not_create_false_overflow():
    html = """<!doctype html><html><head>
      <link rel="stylesheet" href="/index.css">
      <link rel="stylesheet" href="/css/buttons.css">
      <link rel="stylesheet" href="/css/overflow.css">
      <style>
        #host { width: 600px; }
        #row { display:flex; width:fit-content; max-width:100%; gap:8px; }
        #row > button:not(.overflow-trigger) { width:130.125px; }
      </style>
      <script type="module">
        import { registerOverflow } from '/js/overflow.js';
        document.addEventListener('alpine:init', () => registerOverflow(Alpine));
        await import('/vendor/alpine/alpine.min.js');
      </script>
    </head><body x-data><div id="host"><div id="row" x-overflow>
      <button>Model</button><button>Reasoning effort</button><button>Agent</button><button>Context</button>
    </div></div></body></html>"""

    # Browser zoom requires a full Chromium and an isolated persistent profile.
    with tempfile.TemporaryDirectory(prefix="overflow-zoom-") as profile, playwright.sync_playwright() as p:
        if not Path(p.chromium.executable_path).is_file():
            pytest.skip("Full Playwright Chromium is required for browser zoom.")
        with p.chromium.launch_persistent_context(profile, executable_path=p.chromium.executable_path, headless=True) as context:
            settings = context.new_page()
            settings.goto("chrome://settings/appearance")
            page = context.new_page()
            serve_page(page, html)
            page.goto("http://overflow.test/")
            page.wait_for_selector(".overflow-trigger", state="attached")
            more = page.get_by_role("button", name="More controls", exact=True)
            for zoom in [1, 1.1, 1.5, 1.75, 1]:
                settings.evaluate("zoom => new Promise(r => chrome.settingsPrivate.setDefaultZoom(zoom, r))", zoom)
                page.wait_for_function("zoom => Math.abs(devicePixelRatio - zoom) < .01", arg=zoom)
                page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
                playwright.expect(more).to_be_hidden()
                playwright.expect(page.locator(".overflow-hidden")).to_have_count(0)
                page.evaluate("document.getElementById('host').style.width = '220px'")
                playwright.expect(more).to_be_visible()
                page.evaluate("document.getElementById('host').style.width = '600px'")
                playwright.expect(more).to_be_hidden()
