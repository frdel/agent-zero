from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_onboarding_contains_unified_provider_step():
    html = (PROJECT_ROOT / "plugins/_onboarding/webui/onboarding.html").read_text(encoding="utf-8")
    store = (PROJECT_ROOT / "plugins/_onboarding/webui/onboarding-store.js").read_text(encoding="utf-8")
    gate_store = (PROJECT_ROOT / "webui/components/chat/model-gate-store.js").read_text(encoding="utf-8")

    assert "Cloud" in html
    assert "Local" in html
    assert "Welcome to Agent Zero" in html
    assert "Choose your AI provider" in store

    # The illustrated Cloud/Local path screen is gone: one merged provider step.
    assert "Choose how to use AI models in Agent Zero" not in html + store
    assert "path-card" not in html
    assert "cloud-card.webp" not in html
    assert "local-card.webp" not in html
    assert not (PROJECT_ROOT / "plugins/_onboarding/webui/assets/cloud-card.webp").exists()
    assert not (PROJECT_ROOT / "plugins/_onboarding/webui/assets/local-card.webp").exists()
    assert "choosePath" not in html + store + gate_store
    assert "isStep('connect')" in html
    assert "isStep('path')" not in html
    assert "isStep('cloud')" not in html
    assert "isStep('local')" not in html

    # Cloud/Account/Local segmented switch on the merged step.
    assert "mode-switch" in html
    assert "setProviderMode('cloud')" in html
    assert "setProviderMode('account')" in html
    assert "setProviderMode('local')" in html
    assert "providerMode === 'cloud'" in html
    assert "providerMode === 'account'" in html
    assert "providerMode === 'local'" in html
    assert html.index("setProviderMode('cloud')") < html.index("setProviderMode('account')") < html.index("setProviderMode('local')")
    assert '{ step: "connect", label: "Choose provider" }' in store

    # Cloud pane lists every provider directly and only mentions API keys;
    # accounts live in their own pane.
    assert "Connect with an API key" in html
    assert "cloudProviders()" in html
    assert "Click here if you don't see your provider" not in html
    assert "moreCloudOpen" not in html + store
    assert "API key or account connection" not in html

    # The chat model gate presets the mode before the modal opens (no flash).
    assert "presetMode" in store
    assert "onboardingStore.presetMode = this.choice;" in gate_store
    assert "applyOnboardingChoice" not in gate_store

    assert "oauthProviderCards()" in html + store
    assert "selectOAuthProvider(provider.provider_id)" in html
    assert "Connect one or more account-backed providers." not in html
    assert "Connect ChatGPT/Codex Account" not in html
    assert "Main model" in html
    assert "Refresh model list" in html
    assert "Search or enter Utility Model" in html

    # The utility model is an intentional choice: no "same as main" shortcut.
    assert "Use same as Main Model" not in html
    assert "sameAsMain" not in html + store
    assert "Advanced Settings" in html
    assert "selectedProviderName() + ' Docs'" in html
    assert "openSelectedProviderDocs" in html + store
    assert "Connect account" in html + store
    assert "oauthAccountActionLabel" in html + store
    assert "connectOAuth" in html + store
    assert "submitOAuthManualCallback" in html + store
    assert 'const OAUTH_START_API = "/plugins/_oauth/start_login";' in store
    assert "/plugins/_oauth/start_device_login" not in store
    assert "provider-description" not in html
    assert "main-model-field" in html
    assert "wide-inline-field" in html
    assert "utility-panel" in html
    assert "showApiBaseField()" in html + store
    assert "localGuidance()" in html + store


def test_onboarding_closes_before_opening_advanced_model_settings():
    store = (PROJECT_ROOT / "plugins/_onboarding/webui/onboarding-store.js").read_text(
        encoding="utf-8"
    )
    method = store.split("  async openAdvancedSettings() {", 1)[1].split("\n  },", 1)[0]

    close_call = "await window.closeModal?.();"
    open_call = "await modelConfigStore.openPresetEditor("

    assert close_call in method
    assert open_call in method
    assert method.index(close_call) < method.index(open_call)


def test_onboarding_provider_grid_names_are_present_in_metadata():
    provider_yaml = (PROJECT_ROOT / "conf/model_providers.yaml").read_text(encoding="utf-8")
    provider_ui = (PROJECT_ROOT / "plugins/_onboarding/webui/onboarding-providers.js").read_text(encoding="utf-8")
    model_metadata = (PROJECT_ROOT / "plugins/_model_config/provider_metadata.yaml").read_text(encoding="utf-8")

    assert "TOP_CLOUD_PROVIDER_IDS" in provider_ui
    assert '"venice"' in provider_ui
    assert '"xai"' in provider_ui
    assert '"nebius"' in provider_ui
    assert provider_ui.index('"venice"') < provider_ui.index('"zai"')
    assert provider_ui.index('"xai"') > provider_ui.index("MORE_CLOUD_PROVIDER_IDS")
    assert 'name: "Google"' in provider_ui
    assert 'docs_url: "https://openrouter.ai/workspaces/default/keys"' in provider_ui
    assert 'docs_url: "https://ai.google.dev/gemini-api/docs/api-key"' in provider_ui
    assert 'docs_url: "https://docs.venice.ai/guides/getting-started/generating-api-key"' in provider_ui
    assert 'docs_url: "https://docs.tokenfactory.nebius.com/api-reference/introduction"' in provider_ui
    assert 'docs_url: "https://lmstudio.ai/docs/developer/core/authentication"' in provider_ui
    assert 'logo: "/plugins/_onboarding/webui/assets/provider-logos/llama-cpp.svg"' in provider_ui
    assert 'docs_url: "https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md"' in provider_ui
    assert 'default_api_base: "http://host.docker.internal:8080/v1"' in provider_ui
    assert 'logo: "/plugins/_onboarding/webui/assets/provider-logos/omlx.svg"' in provider_ui
    assert 'docs_url: "https://github.com/jundot/omlx#readme"' in provider_ui
    assert 'default_api_base: "http://host.docker.internal:8000/v1"' in provider_ui
    assert 'logo: "/plugins/_onboarding/webui/assets/provider-logos/vllm.svg"' in provider_ui
    assert 'docs_url: "https://docs.vllm.ai/en/stable/serving/online_serving/"' in provider_ui
    assert 'logo: "/plugins/_onboarding/webui/assets/provider-logos/apiroute.svg"' in provider_ui
    assert 'logo: "/plugins/_onboarding/webui/assets/provider-logos/cerebras.svg"' in provider_ui
    assert 'docs_url: "https://inference-docs.cerebras.ai/quickstart"' in provider_ui
    assert 'default_chat_model: "claude-3-7-sonnet-20250219"' in provider_ui
    assert 'default_chat_model: "gpt-oss-120b"' in provider_ui
    assert 'docs_url: ""' in provider_ui
    assert "api_key_mode: none" in model_metadata
    assert "api_key_mode: optional" in model_metadata
    assert "Ollama Cloud" in provider_yaml
    assert "https://ollama.com/v1" in provider_yaml
    assert "llama.cpp" in provider_yaml
    assert "http://host.docker.internal:8080/v1" in provider_yaml
    assert "oMLX" in provider_yaml
    assert "http://host.docker.internal:8000/v1" in provider_yaml
    assert "vLLM" in provider_yaml
    assert "Nebius Token Factory" in provider_yaml
    assert "https://api.tokenfactory.nebius.com/v1" in provider_yaml
    assert not (PROJECT_ROOT / "plugins/_model_config/conf/model_providers.yaml").exists()

    for name in [
        "OpenRouter",
        "Agent Zero API",
        "OpenAI",
        "Anthropic",
        "Google",
        "DeepSeek",
        "xAI",
        "Moonshot AI",
        "Nebius Token Factory",
        "Z.AI",
        "Mistral AI",
        "Azure OpenAI",
        "llama.cpp",
        "oMLX",
        "vLLM",
    ]:
        assert name in provider_yaml + provider_ui

    for name in ["Ollama Cloud", "AWS Bedrock", "Groq", "Cerebras", "API Route"]:
        assert name in provider_yaml + provider_ui

    for forbidden in [
        "onboarding_category",
        "onboarding_rank",
        "short_description",
        "setup_url",
        "api_key_url",
        "docs_url",
        "logo:",
        "api_key_mode",
        "model_list_autoload",
        "default_chat_model",
        "default_utility_model",
        "default_api_base",
    ]:
        assert forbidden not in provider_yaml

    for logo in [
        "deepseek.svg",
        "google-gemini.svg",
        "groq.svg",
        "sambanova.png",
        "cometapi.ico",
        "apiroute.svg",
        "cerebras.svg",
        "github-copilot.svg",
        "llama-cpp.svg",
        "zai-logo.svg",
        "omlx.svg",
        "vllm.svg",
    ]:
        assert logo in provider_ui

    assert (PROJECT_ROOT / "plugins/_onboarding/webui/assets/provider-logos/llama-cpp.svg").exists()
    assert (PROJECT_ROOT / "plugins/_onboarding/webui/assets/provider-logos/apiroute.svg").exists()
    assert (PROJECT_ROOT / "plugins/_onboarding/webui/assets/provider-logos/cerebras.svg").exists()
    assert (PROJECT_ROOT / "plugins/_onboarding/webui/assets/provider-logos/omlx.svg").exists()
    assert (PROJECT_ROOT / "plugins/_onboarding/webui/assets/provider-logos/vllm.svg").exists()


def test_nebius_provider_config_uses_native_route_with_token_factory_endpoint():
    provider_path = PROJECT_ROOT / "conf/model_providers.yaml"
    provider_config = yaml.safe_load(provider_path.read_text(encoding="utf-8"))
    nebius = provider_config["chat"]["nebius"]

    assert nebius["name"] == "Nebius Token Factory"
    assert nebius["litellm_provider"] == "nebius"
    assert nebius["kwargs"]["api_base"] == "https://api.tokenfactory.nebius.com/v1"
    assert nebius["models_list"]["endpoint_url"] == "/models"
    assert "api_key_mode" not in nebius


def test_nvidia_nim_is_a_first_class_provider():
    provider_config = yaml.safe_load(
        (PROJECT_ROOT / "conf/model_providers.yaml").read_text(encoding="utf-8")
    )
    provider_ui = (PROJECT_ROOT / "plugins/_onboarding/webui/onboarding-providers.js").read_text(
        encoding="utf-8"
    )

    for model_type in ("chat", "embedding"):
        provider = provider_config[model_type]["nvidia_nim"]
        assert provider["litellm_provider"] == "nvidia_nim"
        assert provider["models_list"]["endpoint_url"] == (
            "https://integrate.api.nvidia.com/v1/models"
        )

    assert '"nvidia_nim"' in provider_ui
    assert "https://docs.api.nvidia.com/nim/reference/llm-apis" in provider_ui


def test_discovery_auto_modal_extension_contains_required_guards():
    content = (PROJECT_ROOT / "plugins/_discovery/extensions/webui/initFw_end/auto-modal.js").read_text(encoding="utf-8")

    assert "auto_modal_path" in content
    assert "chat-created" in content
    assert "modalAlreadyOpen" in content
    assert "discovery_auto_modal_closed" in content
    assert "auto_modal_surfaces" in content


def test_onboarding_success_filters_oauth_discovery_cards():
    content = (
        PROJECT_ROOT
        / "plugins/_discovery/extensions/webui/onboarding-success-end/discovery-cards.html"
    ).read_text(encoding="utf-8")

    assert "discovery-codex-oauth" in content
    assert "discovery-oauth-accounts" in content
    assert "includes(card.id)" in content
