from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def test_welcome_screen_embeds_shared_new_chat_composer() -> None:
    welcome = _read("webui/components/welcome/welcome-screen.html")
    welcome_store = _read("webui/components/welcome/welcome-store.js")
    index = _read("webui/index.html")
    discovery_cards = _read(
        "plugins/_discovery/extensions/webui/welcome-actions-end/discovery-cards.html"
    )
    discovery_store = _read("plugins/_discovery/webui/discovery-store.js")

    assert 'class="welcome-composer"' in welcome
    assert 'path="chat/attachments/inputPreview.html"' in welcome
    assert 'path="chat/input/chat-bar-input.html"' in welcome
    assert "x-text=\"$store.welcomeStore.heroSubtitle\"" in welcome
    assert "Hello! I'm Agent Zero" in welcome
    assert "is-setup-required" not in welcome
    assert "welcome-setup-composer" not in welcome
    assert "Configure your models to start chatting" not in welcome
    assert "Start Onboarding" not in welcome
    assert "openBlockingSetup()" not in welcome
    assert '.filter((b) => b.id !== "missing-api-key")' in welcome_store
    assert "get heroSubtitle()" in welcome_store
    assert 'return "How can I help you today?";' in welcome_store
    assert '<h2>Quick Actions</h2>' in welcome
    assert 'class="welcome-lower-grid"' in welcome
    assert 'x-extension id="welcome-actions-end"' in welcome
    assert "grid-template-columns: repeat(4, minmax(0, 1fr));" in welcome
    assert '"accounts accounts channels channels"' in welcome
    assert '"system system system system"' in welcome
    assert "align-items: stretch;" in welcome
    assert ".welcome-lower-grid .discovery-slot {\n            display: contents;" in welcome
    assert ".welcome-lower-grid .discovery-account-card {\n            grid-area: accounts;" in welcome
    assert "grid-area: system;" in welcome
    assert ".welcome-composer .input-row {\n            min-height: 4.9rem;" in welcome
    assert "border-radius: 8px;" in welcome
    assert 'aria-label="Refresh System Resources"' in welcome
    assert "refreshBanners(true)" in welcome
    assert 'aria-label="Dismiss System Resources"' in welcome
    assert "dismissBanner($store.welcomeStore.systemResourceBanner?.id || 'system-resources')" in welcome
    assert "welcome-panel-status-icon" not in welcome
    assert "monitoring" not in welcome
    assert ".welcome-banner {\n            --welcome-banner-accent: #2f6bff;" in welcome
    assert "grid-template-columns: auto minmax(0, 1fr) auto auto;" in welcome
    assert ".welcome-banner.banner-warning {\n            --welcome-banner-accent: #f59e0b;" in welcome
    assert "border-left: 4px" not in welcome
    assert 'class="welcome-banner-cta"' in welcome
    assert "executeBannerAction(banner.cta_action)" in welcome
    assert "executeBannerAction(action)" in welcome_store
    assert "handleBannerHtmlClick($event)" in welcome
    assert "handleBannerHtmlClick(event)" in welcome_store
    assert "[data-banner-action]" in welcome_store
    assert 'action.startsWith("open-modal:")' in welcome_store
    assert 'const hashIndex = path.indexOf("#");' in welcome_store
    assert 'history.replaceState(null, "", `#${hash}`);' in welcome_store
    assert ".welcome-banner-html .btn,\n        .welcome-banner-html button" in welcome
    assert "background-color: var(--color-highlight);" in welcome
    assert 'aria-label="Dismiss Connect Channels"' in discovery_cards
    assert "dismissFeatureCards()" in discovery_cards
    assert "dismissFeatureCards() {" in discovery_store
    assert 'class="discovery-feature-card"\n                                type="button"' in discovery_cards
    assert "`${card.cta_text || 'Connect'} ${card.title}`" in discovery_cards
    assert "discovery-feature-card > .btn" not in discovery_cards
    assert "discovery-feature-head" not in discovery_cards
    assert "discovery-account-header" in discovery_cards
    assert "discovery-account-cta" in discovery_cards
    assert "discovery-account-icon" not in discovery_cards
    assert "some(b => b.id === 'missing-api-key')" not in discovery_cards

    assert "x-if=\"$store.welcomeStore && $store.welcomeStore.isVisible\"" in index
    assert "x-if=\"!$store.welcomeStore || !$store.welcomeStore.isVisible\"" in index
    assert "Connect Channels" in discovery_cards
    assert "oauthAccountCards" in discovery_cards
    assert "discovery-account-card" in discovery_cards
    assert "topHeroCards" not in discovery_cards
    assert "bottomHeroCards" not in discovery_cards
    assert "radial-gradient" not in welcome


def test_welcome_composer_can_create_a_chat_before_sending() -> None:
    input_store = _read("webui/components/chat/input/input-store.js")
    chats_store = _read("webui/components/sidebar/chats/chats-store.js")
    index_js = _read("webui/index.js")
    gate_store = _read("webui/components/chat/model-gate-store.js")
    gate_component = _read("webui/components/chat/model-setup-gate.html")

    assert 'return "Ask anything to start a new chat";' in input_store
    assert "if (!chatsStore.selected" in input_store
    assert "await chatsStore.newChat()" in input_store
    optimistic_user = 'await setMessages([{ id: messageId, type: "user"'
    assert index_js.count(optimistic_user) == 1
    assert index_js.index(optimistic_user) < index_js.index("if (hasAttachments)")
    assert "return response.ctxid;" in chats_store
    assert 'return "arrow_forward";' in input_store
    assert "modelGateStore.canSendToModel()" in index_js
    assert "modelGateStore.mergeSyntheticMessages(snapshot.logs, context)" in index_js
    assert 'type: "model_setup_gate"' in gate_store
    assert 'STORAGE_KEY = "a0:model-gate-pending:v1"' in gate_store
    assert "SYNTHETIC_MESSAGE_NO_BASE = Number.MAX_SAFE_INTEGER - 2" in gate_store
    assert "return synthetic.length ? [...(logs || []), ...synthetic] : logs;" in gate_store
    assert "restorePending()" in gate_store
    assert "savePending()" in gate_store
    assert "clearSavedPending()" in gate_store
    assert "sessionStorage.setItem(STORAGE_KEY" in gate_store
    assert "sessionStorage.getItem(STORAGE_KEY)" in gate_store
    assert "sessionStorage.removeItem(STORAGE_KEY)" in gate_store
    assert 'import("/plugins/_oauth/webui/oauth-config-store.js")' in gate_store
    assert "refreshConnectedAccountState()" in gate_store
    assert "accountConnected" in gate_store
    assert "accountLabel" in gate_store
    assert "oauthConfigStore.connectedProviderCards()[0] || null" in gate_store
    assert "autoApplyConnectedProviderIfNeeded" not in gate_store
    assert "void this.dispatchPendingIfConfigured();" in gate_store
    assert "this.choice = \"\";" in gate_store
    assert 'document.addEventListener("model-configured"' in gate_store
    assert 'document.addEventListener("model-setup-changed"' in gate_store
    assert "bypassModelGate: true" in gate_store
    assert "modelConfigStore.openPresetEditor(" in gate_store
    assert 'openPluginConfig("_oauth"' not in gate_store
    assert "Your message sends automatically once a model is connected." in gate_component
    assert "openOnboarding('cloud')" in gate_component
    assert "openOnboarding('account')" in gate_component
    assert "openOnboarding('local')" in gate_component
    assert gate_component.index("openOnboarding('cloud')") < gate_component.index("openOnboarding('account')") < gate_component.index("openOnboarding('local')")
    assert "openOauthConfiguration" not in gate_component
    assert "Show accounts" not in gate_component
    assert "model-gate-accounts" not in gate_component
    assert "Choose models" in gate_component
    assert "Advanced model configuration" in gate_component
    assert "Advanced settings" not in gate_component
    assert "model-gate-fields" not in gate_component
    assert "Connect model" not in gate_component
    assert "accountsOpen" not in gate_store
    assert "saveInlineSetup" not in gate_store
    assert """.model-gate-card {
      display: grid;
      gap: 0.75rem;
    }""" in gate_component
    # The composer never hard-blocks sending: the in-chat gate guides users instead.
    assert "Connect a model to send" not in input_store
    assert "blocked" not in input_store
    assert "sendDisabled" not in input_store
    assert "isBlockingSend" not in gate_store
    assert "isBlockingSend" not in index_js


def test_welcome_composer_does_not_overlap_idle_progress_placeholder() -> None:
    input_store = _read("webui/components/chat/input/input-store.js")

    assert "!!chatsStore.selected &&\n      state !== \"all\"" in input_store
    assert '!(state === "stop" && messageQueueStore?.hasQueue)' in input_store


def test_welcome_composer_buttons_keep_target_geometry_without_glow() -> None:
    chat_bar = _read("webui/components/chat/input/chat-bar-input.html")
    mic_css = _read("plugins/_whisper_stt/webui/whisper-stt.css")

    assert "#send-button {\n      order: 2;\n      border-radius: 12px;" in chat_bar
    assert "background-color: var(--color-highlight);" in chat_bar
    assert "background-color: #e67e22;" in chat_bar
    assert "linear-gradient" not in chat_bar
    assert "#microphone-button {\n  order: 1;" in mic_css
    assert "border-radius: 12px;" in mic_css
    assert "background-color: transparent;" in mic_css
    assert "#microphone-button.mic-inactive {\n  color: grey;" in mic_css
    assert "background-color: grey;" not in mic_css
    assert "#microphone-button.mic-listening {\n  color: red;" in mic_css
    assert "#microphone-button.mic-recording {\n  color: green;" in mic_css
    assert "#microphone-button.mic-activating svg" in mic_css
    assert "rgba(34, 68, 255" not in chat_bar
    assert "rgba(217, 119, 6" not in chat_bar


def test_welcome_hover_and_focus_borders_use_neutral_tokens() -> None:
    surfaces = "\n".join(
        [
            _read("webui/components/welcome/welcome-screen.html"),
            _read("webui/components/chat/input/chat-bar-input.html"),
            _read("plugins/_discovery/extensions/webui/welcome-actions-end/discovery-cards.html"),
        ]
    )

    assert "#315cf6" not in surfaces
    assert "rgba(34, 68, 255" not in surfaces
    assert "linear-gradient" not in surfaces
    assert "border-color: color-mix(in srgb, var(--color-primary" not in surfaces
    assert "border-color: var(--color-primary" not in surfaces
    assert "border-color: color-mix(in srgb, var(--color-border) 88%, var(--color-text) 12%)" in surfaces


def test_composer_creates_visual_code_blocks_from_entered_fence() -> None:
    chat_bar = _read("webui/components/chat/input/chat-bar-input.html")
    input_store = _read("webui/components/chat/input/input-store.js")

    assert 'contenteditable="true"' in chat_bar
    assert "font-family: var(--font-family-main" in chat_bar
    assert ".composer-code-content" in chat_bar
    assert "font-family: var(--font-family-code" in chat_bar
    assert "FENCE_LINE_RE" in input_store
    assert "_tryCreateCodeBlock($event)" in input_store
    assert 'data-code-block' in input_store
    assert "handlePaste($event)" in input_store
    assert "_insertPlainText(text)" in input_store
    assert "is-code-context" not in chat_bar
    assert "_isCaretInsideFence" not in input_store
