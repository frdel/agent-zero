import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read(*parts: str) -> str:
    return (PROJECT_ROOT / Path(*parts)).read_text(encoding="utf-8")


def test_full_log_replays_replace_existing_message_dom():
    index_js = read("webui", "index.js")
    messages_js = read("webui", "js", "messages.js")

    assert "snapshot.logs?.[0]?.no === 0" in index_js
    assert "msgs.resetMessageRenderState();" in index_js
    assert "export function resetMessageRenderState" in messages_js
    assert "normalized.sort(" in messages_js


def test_root_responses_render_markdown_during_streaming():
    messages_js = read("webui", "js", "messages.js")

    assert "const renderMarkdown = kvps?.finished !== false;" not in messages_js
    assert "markdown: true," in messages_js
    assert "latex: true," in messages_js


def test_message_ordering_uses_a_bounded_tail_first_renderer_cache():
    messages_js = read("webui", "js", "messages.js")
    message_window_js = read("webui", "js", "message-window.js")

    assert 'from "./message-window.js"' in messages_js
    assert "_messageWindow.compactTailIfNeeded()" in messages_js
    assert "_messageWindow.visibleMessages()" in messages_js
    assert "class MessageWindow" in message_window_js
    assert "showTail()" in message_window_js
    assert "shiftOlder()" in message_window_js
    assert "shiftNewer()" in message_window_js
    assert "_messageWindowFollowTail" in messages_js
    assert "_messageWindow.showTail()" in messages_js


def test_virtual_paging_uses_passive_loaders_and_cancels_stale_scrolling():
    messages_js = read("webui", "js", "messages.js")
    scroller_js = read("webui", "js", "scroller.js")
    loading_css = read("webui", "css", "loading-indicators.css")

    assert "createMessageWindowIndicator" in messages_js
    assert 'indicator.setAttribute("role", "status")' in messages_js
    assert "createThreeBubbleLoader({ active: isLoading })" in messages_js
    assert "@keyframes three-bubble-loader-jump" in loading_css
    assert "Load ${Math.min" not in messages_js
    assert "export function cancelPendingScroll" in scroller_js
    assert "cancelPendingScroll(history)" in messages_js


def test_context_switch_uses_three_bubble_chat_loading_splash():
    index_html = read("webui", "index.html")
    index_js = read("webui", "index.js")
    messages_js = read("webui", "js", "messages.js")
    messages_css = read("webui", "css", "messages.css")
    loading_js = read("webui", "js", "loading-indicators.js")
    loading_css = read("webui", "css", "loading-indicators.css")
    welcome_html = read("webui", "components", "welcome", "welcome-screen.html")

    splash = re.search(
        r'<div id="chat-loading-splash"(?P<body>.*?)</div>',
        index_html,
        flags=re.DOTALL,
    )
    assert splash
    assert "for (let index = 0; index < 3; index += 1)" in loading_js
    assert "createThreeBubbleLoader({ active: true })" in index_js
    assert "createThreeBubbleLoader({ active: isLoading })" in messages_js
    assert "beginChatLoading(id)" in index_js
    assert "id !== loadingContext" in index_js
    assert "finishChatLoading(snapshot.context)" in index_js
    assert "CHAT_LOADING_TEST_MIN_DURATION_MS" not in index_js
    assert "const CHAT_LOADING_SPLASH_DELAY_MS = 300" in index_js
    assert "chatLoadingSplashVisible = true" in index_js
    assert "@keyframes chat-loading-splash-fade-in" in messages_css
    splash_css = re.search(
        r"\.chat-loading-splash \{(?P<body>.*?)\}",
        messages_css,
        flags=re.DOTALL,
    )
    assert splash_css and "background" not in splash_css.group("body")
    index_css = read("webui", "index.css")
    assert "'chat-active': $store.welcomeStore" in index_html
    assert "#right-panel.chat-active" in index_css
    assert "background-color 0.2s ease-out" in index_css
    assert "background: var(--color-background)" not in welcome_html
    assert "--three-bubble-loader-delay: 0.16s" in loading_css
    assert "--three-bubble-loader-delay: 0.32s" in loading_css
    assert "animation-delay: var(--three-bubble-loader-delay)" in loading_css


def test_utility_prefixed_process_groups_are_not_hidden_from_partial_dom_state():
    messages_js = read("webui", "js", "messages.js")
    preferences_js = read(
        "webui",
        "components",
        "sidebar",
        "bottom",
        "preferences",
        "preferences-store.js",
    )
    process_group_css = read(
        "webui",
        "components",
        "messages",
        "process-group",
        "process-group.css",
    )

    assert 'else if (log.type === "util")' in messages_js
    assert 'group.classList.remove("utility-only")' in messages_js
    assert "isUtilityOnlyProcessGroup" not in messages_js
    assert "group.hidden" not in messages_js
    assert '"show-utility-messages"' in preferences_js
    assert ".show-utility-messages .process-group.utility-only" in process_group_css
    assert ".process-step.message-util {" in process_group_css
    assert ".show-utility-messages .process-step.message-util" in process_group_css


def test_unknown_message_types_fall_back_to_draw_message_tool():
    messages_js = read("webui", "js", "messages.js")

    assert "return drawMessageTool;" in messages_js
    assert "return drawMessageDefault;" not in messages_js


def test_gen_steps_disable_smooth_scrolling():
    messages_js = read("webui", "js", "messages.js")

    assert 'smooth: code !== "GEN" && !isMassRender()' in messages_js


def test_message_actions_put_copy_before_speak():
    sources = [
        read("webui", "js", "messages.js"),
        read(
            "plugins",
            "_browser",
            "extensions",
            "webui",
            "get_tool_message_handler",
            "browser-tool-handler.js",
        ),
    ]

    for source in sources:
        lines = source.splitlines()
        for index, line in enumerate(lines):
            if 'createActionButton("speak"' not in line:
                continue
            preceding_actions = [
                match.group(1)
                for candidate in lines[max(0, index - 12) : index]
                if (match := re.search(r'createActionButton\("(detail|copy|speak)"', candidate))
            ]
            assert preceding_actions and preceding_actions[-1] == "copy"
