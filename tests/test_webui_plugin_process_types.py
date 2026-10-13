"""Real DOM regressions; requires Playwright and an installed Chromium browser."""

import mimetypes
from pathlib import Path
from urllib.parse import urlparse

import pytest


playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def page():
    # Serve repository assets entirely in-process: no backend, keys, or user data.
    html = """<!doctype html><html><head>
    <link rel="stylesheet" href="/index.css">
    <link rel="stylesheet" href="/css/messages.css">
    <link rel="stylesheet" href="/components/messages/process-group/process-group.css">
    <script src="/vendor/katex/katex.min.js"></script>
    <script src="/vendor/katex/katex.auto-render.min.js"></script>
    <style>#chat-history {width: 100%; height: 700px; overflow: auto;}</style>
    <script>globalThis.runtimeInfo = {webuiExtensions: {js: {
      get_process_step_types: [
        '/plugins/_text_editor/extensions/webui/get_process_step_types/text-editor-types.js',
        '/plugins/_code_execution/extensions/webui/get_process_step_types/code-exe-types.js'
      ],
      get_message_handler: [
        '/plugins/_text_editor/extensions/webui/get_message_handler/_10_text_editor_handler.js',
        '/plugins/_code_execution/extensions/webui/get_message_handler/code-exe-handler.js'
      ]
    }, html: {}}};</script>
    </head><body><div id="chat-history"></div></body></html>"""

    def serve(route):
        path = urlparse(route.request.url).path
        if path == "/":
            route.fulfill(content_type="text/html", body=html)
            return
        asset = ROOT / (path.lstrip("/") if path.startswith("/plugins/")
                        else "webui/" + path.lstrip("/"))
        if asset.is_file():
            route.fulfill(path=asset, content_type=mimetypes.guess_type(asset)[0])
        else:
            route.abort()

    with playwright.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except playwright.Error as error:
            if "Executable doesn't exist" in str(error):
                pytest.skip("Install a Playwright Chromium browser to run DOM regressions.")
            raise
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.route("**/*", serve)
        page.goto("http://render.test/")
        page.evaluate("""async () => {
          window.msgs = await import('/js/messages.js');
          window.prefs = (await import('/components/sidebar/bottom/preferences/preferences-store.js')).store;
          window.historyEl = document.getElementById('chat-history');
          window.row = (no, type, extra = {}) => ({no, id: `row-${no}`, type,
            heading: `${type} heading`, content: `${type} content`, kvps: {}, ...extra});
          window.check = (condition, message) => { if (!condition) throw new Error(message); };
          window.visible = element => element && getComputedStyle(element).display !== 'none';
        }""")
        yield page
        browser.close()


def test_action_buttons_keep_order_and_mounted_nodes_during_updates(page):
    page.evaluate("""async () => {
      const {createActionButton, syncActionButtons} = await import(
        '/components/messages/action-buttons/simple-action-buttons.js');
      const bar = document.createElement('div');
      const expand = document.createElement('button');
      expand.className = 'expand-btn';
      const plugin = document.createElement('button');
      bar.append(expand, plugin);
      document.body.append(bar);
      const buttons = names => names.map(name => createActionButton(name));
      const order = () => [...bar.querySelectorAll('.action-button')]
        .map(button => button.dataset.actionKey.split(':')[0]).join(',');
      try {
        syncActionButtons(bar, buttons(['detail', 'copy', 'speak']));
        check(order() === 'detail,copy,speak', 'new action bar reversed its actions');
        const mounted = [...bar.querySelectorAll('.action-button')];
        mounted[1].focus();
        const observer = new MutationObserver(() => {});
        observer.observe(bar, {childList:true});
        syncActionButtons(bar, buttons(['detail', 'copy', 'speak']));
        check(observer.takeRecords().length === 0, 'stream update remounted unchanged buttons');
        observer.disconnect();
        check(document.activeElement === mounted[1], 'stream update lost button focus');
        syncActionButtons(bar, buttons(['detail', 'other', 'speak']));
        check(order() === 'detail,other,speak', 'replacement moved behind a retained action');
        check(bar.querySelector('.action-speak') === mounted[2], 'unchanged trailing action was remounted');
        syncActionButtons(bar, buttons(['copy', 'speak']));
        check(order() === 'copy,speak', 'omitting an action changed the remaining order');
        check(expand.parentNode === bar && plugin.parentNode === bar, 'extension or collapse action was removed');
        check(bar.lastChild === plugin, 'standard actions moved behind the plugin action');
      } finally {
        bar.remove();
      }
    }""")


def test_preset_switch_preserves_composer_and_saved_chat_draft(page):
    page.evaluate("""async () => {
      const input = (await import('/components/chat/input/input-store.js')).store;
      const chats = (await import('/components/sidebar/chats/chats-store.js')).store;
      const {switcherState, switcherMethods} = await import('/plugins/_model_config/webui/switcher-mixin.js');
      const previousFetch = window.fetch, previousAlpine = window.Alpine, previousChat = chats.selected;
      const requests = [];
      const editor = document.createElement('div');
      editor.id = 'chat-input';
      editor.contentEditable = 'true';
      document.body.append(editor);
      try {
        chats.selected = 'draft-chat';
        window.fetch = async (url, options) => {
          if (url === '/api/csrf_token') return new Response(JSON.stringify({ok:true, token:'fixture'}));
          requests.push(JSON.parse(options.body));
          return new Response(JSON.stringify({ok:true, preset_name:'Fast'}));
        };
        input.mountEditor(editor);
        input.message = 'An unfinished prompt\\nwith a second line';
        const draft = input.message;
        window.Alpine = {store: name => name === 'chats' ? {selected:'draft-chat'} : undefined};
        const switcher = {...switcherState, ...switcherMethods,
          loadSwitcherState: async () => ({allowed:true, presets:[{name:'Fast'}],
            override:{preset_name:'Fast'}, configuredPreset:'Default', effectivePreset:'Fast'})};
        check(await switcher.selectPresetSwitch('draft-chat', 'Fast'), 'preset switch failed');
        await switcher.refreshSwitcher('draft-chat');
        check(switcher.switcherEffectivePreset === 'Fast', 'preset selection did not change');
        check(requests[0].context_id === 'draft-chat', 'preset switch targeted another chat');
        check(input.message === draft && editor.textContent === draft, 'preset switch cleared the composer');
        check(sessionStorage.getItem('a0:chat-draft:draft-chat') === draft, 'preset switch erased session recovery');
      } finally {
        window.fetch = previousFetch;
        window.Alpine = previousAlpine;
        input.unmountEditor(editor);
        chats.selected = previousChat;
        editor.remove();
      }
    }""")


@pytest.mark.parametrize("mode", ["collapsed", "current", "expanded"])
@pytest.mark.parametrize("replay", [False, True])
@pytest.mark.parametrize("enabled", [False, True])
def test_plugin_declarations_match_live_and_replayed_dom(page, mode, replay, enabled):
    page.evaluate("""async ({mode, replay, enabled}) => {
      const cache = await import('/js/cache.js');
      const extensions = await import('/js/extensions.js');
      const area = 'frontend_extensions_js(extensions)(plugins)';
      const handlers = await extensions.loadJsExtensions('get_message_handler');
      const declarations = await extensions.loadJsExtensions('get_process_step_types');
      const custom = {path: 'test-plugin', module: {
        default(data) {
          if (['custom_step', 'second_custom_step'].includes(data.type)) {
            data.handler = log => msgs.drawProcessStep({
              id: log.id, title: log.heading, code: 'TEST', content: log.content, log,
            });
          } else if (data.type === 'custom_note') {
            data.handler = msgs.drawMessageDefault;
          }
        },
      }};
      try {
        extensions.clearCache();
        cache.add(area, 'get_message_handler', enabled ? [...handlers, custom] : []);
        cache.add(area, 'get_process_step_types', enabled ? [...declarations, {
          path: 'test-types', module: { default({processStepTypes}) {
            for (const type of ['custom_step', 'second_custom_step', 'unhandled_step']) processStepTypes.add(type);
          }},
        }] : []);
        prefs.detailMode = mode;
        prefs.showUtils = false;
        for (const type of ['code_exe', 'text_editor', 'custom_step', 'second_custom_step', 'unhandled_step', 'custom_note', 'unknown']) {
          const isStep = !(enabled && type === 'custom_note');
          msgs.resetMessageRenderState();
          const logs = [row(0, 'user'), row(1, 'agent'), row(2, type)];
          if (replay) logs.push(row(3, 'util'));
          await msgs.setMessages(logs);
          if (!replay) await msgs.setMessages([row(3, 'util')]);
          const group = historyEl.querySelector('.process-group');
          check(visible(group), `${type}: memory search hid previous process group`);
          check(!!group.querySelector(`#process-step-${type}-row-2`) === isStep, `${type}: classification disagrees with renderer`);
          check(!!group.querySelector('#process-step-util-row-3') === isStep, `${type}: utility crossed standalone boundary`);
          prefs.showUtils = true;
          check(visible(historyEl.querySelector('#process-step-util-row-3')), `${type}: utility toggle`);
          prefs.showUtils = false;
          await msgs.setMessages([row(4, 'response', {kvps: {finished: true}})]);
          check(historyEl.textContent.includes('response content'), `${type}: root response missing`);
        }
      } finally {
        cache.add(area, 'get_message_handler', handlers);
        cache.add(area, 'get_process_step_types', declarations);
      }
    }""", {"mode": mode, "replay": replay, "enabled": enabled})


def test_plugin_types_refresh_after_extension_cache_invalidation(page):
    page.evaluate("""async () => {
      const extensions = await import('/js/extensions.js');
      const manifest = runtimeInfo.webuiExtensions.js;
      const paths = manifest.get_message_handler;
      const typePaths = manifest.get_process_step_types;
      try {
        for (const enabled of [true, false, true]) {
          manifest.get_message_handler = enabled ? paths : [];
          manifest.get_process_step_types = enabled ? typePaths : [];
          extensions.clearCache();
          msgs.resetMessageRenderState();
          await msgs.setMessages([row(0, 'util'), row(1, 'text_editor')]);
          const group = historyEl.querySelector('.process-group:not(.utility-only)');
          check(group && visible(group), 'disabled plugin fallback lost process grouping');
          check(group.querySelector('#process-step-util-row-0'), 'utility lookahead missed plugin or fallback type');
          check(!!group.querySelector('.TXT') === enabled, 'stale handler survived extension invalidation');
        }
      } finally {
        manifest.get_message_handler = paths;
        manifest.get_process_step_types = typePaths;
        extensions.clearCache();
      }
    }""")


@pytest.mark.parametrize("step_type", ["text_editor", "unknown_step"])
def test_process_group_paging_preserves_hidden_utilities(page, step_type):
    page.evaluate("""async (stepType) => {
      prefs.showUtils = false;
      msgs.resetMessageRenderState();
      const logs = [row(0, 'user'), row(1, 'util')];
      for (let no = 2; no < 126; no++) logs.push(row(no, stepType));
      await msgs.setMessages(logs);
      await msgs.setMessages([row(126, 'util')]);
      const group = historyEl.querySelector('.process-group');
      check(visible(group), 'capped plugin group became hidden');
      check(group.querySelectorAll('.process-step').length === 50, 'process step cap');
    }""", step_type)
    page.locator('.process-group-show-more').click()
    page.wait_for_function("document.querySelectorAll('.process-step').length === 100")
    page.locator('.process-group-show-more').click()
    page.wait_for_function("document.querySelectorAll('.process-step').length === 126")
    page.evaluate("""async () => {
      await msgs.setMessages([row(127, 'response', {kvps: {finished: true}})]);
      await msgs.setMessages([row(128, 'util')]);
      const group = historyEl.querySelector('.process-group');
      check(visible(group) && group.querySelector('.process-group-response'), 'completion disappeared');
      check(!group.querySelector('#process-step-util-row-128'), 'post-response utility reopened group');
    }""")


def test_subordinate_response_with_shared_gen_id_preserves_gen_step(page):
    page.evaluate("""async () => {
      for (const replay of [false, true]) {
        msgs.resetMessageRenderState();
        const logs = [row(0, 'user'), row(1, 'agent', {content: 'thinking out loud'}),
          row(1, 'response', {agentno: 1, heading: 'A1: Responding', content: 'subordinate answer'})];
        if (replay) await msgs.setMessages(logs);
        else { await msgs.setMessages(logs.slice(0, 2)); await msgs.setMessages([logs[2]]); }
        const gen = historyEl.querySelector('#process-step-agent-row-1');
        const res = historyEl.querySelector('#process-step-response-row-1');
        check(gen && gen.textContent.includes('agent heading'), 'GEN step was wiped by the shared-id response');
        check(res && res.textContent.includes('A1:'), 'subordinate response step missing');
        check(gen !== res, 'shared id collapsed GEN and response into one step');
      }
    }""")


def test_context_reset_during_plugin_module_loading(page):
    page.route('**/plugins/delayed-handler.js', lambda route: route.fulfill(
        content_type='text/javascript', body='''
        await new Promise(resolve => { globalThis.releasePlugin = resolve; });
        export default function ({processStepTypes}) { processStepTypes.add('delayed_step'); }
        '''))
    page.evaluate("""async () => {
      window.extensions = await import('/js/extensions.js');
      window.originalHandlerPaths = runtimeInfo.webuiExtensions.js.get_process_step_types;
      runtimeInfo.webuiExtensions.js.get_process_step_types = ['/plugins/delayed-handler.js'];
      extensions.clearCache();
      msgs.resetMessageRenderState();
      window.pendingRender = msgs.setMessages([row(0, 'agent')]);
    }""")
    page.wait_for_function('typeof releasePlugin === "function"')
    page.evaluate("""async () => {
      try {
        msgs.resetMessageRenderState();
        releasePlugin();
        await pendingRender;
        check(!historyEl.querySelector('.message-container'), 'old chat rendered after context reset');
        check(msgs.getMessageWindowState().total === 0, 'old chat leaked into raw-log cache');
      } finally {
        runtimeInfo.webuiExtensions.js.get_process_step_types = originalHandlerPaths;
        extensions.clearCache();
      }
    }""")



def test_context_reset_during_fallback_resolution(page):
    page.evaluate("""async () => {
      window.handlerCache = await import('/js/cache.js');
      const extensions = await import('/js/extensions.js');
      window.originalHandlers = await extensions.loadJsExtensions('get_message_handler');
      handlerCache.add('frontend_extensions_js(extensions)(plugins)', 'get_message_handler', [
        ...originalHandlers, {path: 'delayed-fallback', module: {default: async data => {
          if (data.type === 'delayed_fallback') await new Promise(resolve => { window.releaseFallback = resolve; });
        }}},
      ]);
      msgs.resetMessageRenderState();
      window.pendingRender = msgs.setMessages([row(0, 'delayed_fallback')]);
    }""")
    page.wait_for_function('typeof releaseFallback === "function"')
    page.evaluate("""async () => {
      try {
        msgs.resetMessageRenderState();
        releaseFallback();
        await pendingRender;
        check(msgs.getMessageWindowState().total === 0, 'stale fallback resolution repopulated cache');
        check(!historyEl.querySelector('.message-container'), 'stale fallback resolution rendered old chat');
        await msgs.setMessages([row(0, 'user')]);
        check(historyEl.querySelector('#message-row-0'), 'new chat did not resume');
      } finally {
        handlerCache.add('frontend_extensions_js(extensions)(plugins)', 'get_message_handler', originalHandlers);
      }
    }""")


@pytest.mark.parametrize("mode", ["collapsed", "current", "expanded"])
@pytest.mark.parametrize("replay", [False, True])
def test_utility_group_promotion_keeps_one_visible_group_and_unique_id(page, mode, replay):
    page.evaluate("""async ({mode, replay}) => {
      prefs.detailMode = mode;
      prefs.showUtils = false;
      for (const type of ['agent', 'text_editor', 'code_exe', 'unknown_step']) {
        msgs.resetMessageRenderState();
        const logs = [row(0, 'user'), row(1, 'util'), row(2, type)];
        if (replay) await msgs.setMessages(logs);
        else {
          await msgs.setMessages(logs.slice(0, 2));
          check(!visible(historyEl.querySelector('.process-group')), 'utility-only group should start hidden');
          await msgs.setMessages([logs[2]]);
        }
        const group = historyEl.querySelector('.process-group');
        check(visible(group), `${type}: first substantive step did not reveal utility group`);
        check(historyEl.querySelectorAll('.process-group').length === 1, `${type}: promotion split the group`);
        check(historyEl.querySelectorAll(`[id="${group.id}"]`).length === 1, 'process group ID belongs to multiple nodes');
        check(document.getElementById(group.id) === group, 'ID lookup must return the process group itself');
        await msgs.setMessages([row(2, type, {heading: 'Updated step'}), row(3, 'util')]);
        check(visible(group), 'streaming update hid the promoted group');
        await msgs.setMessages([row(4, 'response')]);
        check(group.querySelector('.process-group-response'), 'response detached from promoted group');
      }
    }""", {"mode": mode, "replay": replay})


@pytest.mark.parametrize("replay", [False, True])
@pytest.mark.parametrize("boundary", ["user", "error", "hint", "model_setup_gate", "custom_note"])
def test_process_group_lookup_stops_at_standalone_tail(page, replay, boundary):
    page.evaluate("""async ({replay, boundary}) => {
      const cache = await import('/js/cache.js');
      const extensions = await import('/js/extensions.js');
      const area = 'frontend_extensions_js(extensions)(plugins)';
      const handlers = await extensions.loadJsExtensions('get_message_handler');
      cache.add(area, 'get_message_handler', [...handlers, {path: 'standalone-test', module: {
        default(data) { if (data.type === 'custom_note') data.handler = msgs.drawMessageDefault; },
      }}]);
      try {
        prefs.showUtils = false;
        for (const nextType of ['util', 'agent', 'warning', 'rate_limit', 'response']) {
          msgs.resetMessageRenderState();
          const logs = [row(0, 'user'), row(1, 'agent'), row(2, boundary), row(3, nextType)];
          if (replay) await msgs.setMessages(logs);
          else for (const log of logs) await msgs.setMessages([log]);
          const first = historyEl.querySelector('#process-step-agent-row-1').closest('.process-group');
          const next = historyEl.querySelector('#process-step-util-row-3, #process-step-agent-row-3, #process-step-warning-row-3, #process-step-rate_limit-row-3, #message-row-3');
          check(visible(first), `${boundary} -> ${nextType}: hid previous process group`);
          check(next && !first.contains(next), `${boundary} -> ${nextType}: crossed standalone boundary`);
          const boundaryElement = historyEl.querySelector('#message-row-2');
          check(boundaryElement.compareDocumentPosition(next) & Node.DOCUMENT_POSITION_FOLLOWING,
            `${boundary} -> ${nextType}: reordered messages`);
        }
      } finally {
        cache.add(area, 'get_message_handler', handlers);
      }
    }""", {"replay": replay, "boundary": boundary})
