import { createStore } from "/js/AlpineStore.js";
import { callJsonApi } from "/js/api.js";
import { store as modelConfigStore } from "/plugins/_model_config/webui/model-config-store.js";
import { store as onboardingStore } from "/plugins/_onboarding/webui/onboarding-store.js";
import { toastFrontendError } from "/components/notifications/notification-store.js";

const ONBOARDING_MODAL_PATH = "/plugins/_onboarding/webui/onboarding.html";
const STORAGE_KEY = "a0:model-gate-pending:v1";
const SYNTHETIC_MESSAGE_NO_BASE = Number.MAX_SAFE_INTEGER - 2;

export const store = createStore("modelGate", {
  active: false,
  connected: false,
  connectedLabel: "",
  accountConnected: false,
  accountLabel: "",
  pending: null,
  gateMessageId: "",
  choice: "",
  dispatching: false,
  _initialized: false,

  get introText() {
    if (this.connected) {
      return `Model connected: ${this.connectedLabel || "ready"}`;
    }
    if (this.accountConnected) {
      return `${this.accountLabel || "Your AI account"} is connected. Choose Main and Utility models and I'll answer right away.`;
    }
    return "I'm ready to work on this — I just need a model to think with. Pick one and I'll answer right away.";
  },

  init() {
    if (this._initialized) return;
    this._initialized = true;
    this.restorePending();
    document.addEventListener("onboarding-configured", () => {
      void this.dispatchPendingIfConfigured();
    });
    document.addEventListener("model-configured", () => {
      void this.dispatchPendingIfConfigured();
    });
    document.addEventListener("model-setup-changed", () => {
      void this.dispatchPendingIfConfigured();
    });
    document.addEventListener("modal-closed", () => {
      if (this.active && !this.connected) {
        this.choice = "";
        this.savePending();
        void this.dispatchPendingIfConfigured();
      }
    });
  },

  async canSendToModel() {
    try {
      const data = await callJsonApi("/plugins/_model_config/model_config_get", {});
      this.applyModelStatus(data);
      if (!data?.model_configured) await this.refreshConnectedAccountState();
      return !!data?.model_configured;
    } catch (error) {
      console.error("Could not check model configuration:", error);
      return true;
    }
  },

  async refreshConnectedAccountState() {
    try {
      const { store: oauthConfigStore } = await import("/plugins/_oauth/webui/oauth-config-store.js");
      await oauthConfigStore.loadStatus();
      const account = oauthConfigStore.connectedProviderCards()[0] || null;
      this.accountConnected = Boolean(account);
      this.accountLabel = account?.short_name || account?.display_name || account?.provider_id || "";
      return this.accountConnected;
    } catch (error) {
      console.error("Could not check connected accounts:", error);
      this.accountConnected = false;
      this.accountLabel = "";
      return false;
    }
  },

  applyModelStatus(data = {}) {
    modelConfigStore.modelConfigured = !!data.model_configured;
    modelConfigStore.modelConfiguredLabel = data.model_configured_label || "";
    this.connectedLabel = data.model_configured_label || this.connectedLabel || "";
  },

  start({ message, attachments, messageId, context }) {
    this.init();
    this.active = true;
    this.connected = false;
    this.pending = { message, attachments, messageId, context };
    this.gateMessageId = this.gateMessageId || `model-gate-${messageId}`;
    this.savePending();
  },

  syntheticMessages(currentContext) {
    this.init();
    if (!this.active || !this.pending || this.pending.context !== currentContext) return [];
    return [
      {
        no: SYNTHETIC_MESSAGE_NO_BASE,
        id: this.pending.messageId,
        type: "user",
        content: this.pending.message,
        kvps: { attachments: this.pending.attachments },
      },
      {
        no: SYNTHETIC_MESSAGE_NO_BASE + 1,
        id: this.gateMessageId,
        type: "model_setup_gate",
      },
    ];
  },

  mergeSyntheticMessages(logs, currentContext) {
    this.init();
    const synthetic = this.syntheticMessages(currentContext);
    return synthetic.length ? [...(logs || []), ...synthetic] : logs;
  },

  onCardCreate() {
    this.init();
    void this.dispatchPendingIfConfigured();
  },

  openOnboarding(choice) {
    this.choice = ["local", "account"].includes(choice) ? choice : "cloud";
    this.savePending();
    onboardingStore.presetMode = this.choice;
    const modalPromise = window.openModal?.(ONBOARDING_MODAL_PATH);
    void Promise.resolve(modalPromise).then(() => this.dispatchPendingIfConfigured());
  },

  async openAdvancedModelConfiguration() {
    try {
      const data = await callJsonApi("/plugins/_model_config/model_config_get", {});
      await modelConfigStore.openPresetEditor(
        data?.selected_preset || data?.configured_preset || "Default"
      );
      await this.dispatchPendingIfConfigured();
    } catch (error) {
      console.error("Could not open model preset editor:", error);
      void toastFrontendError(
        error?.message || "Could not open model presets.",
        "Advanced model configuration"
      );
    }
  },

  async dispatchPendingIfConfigured() {
    this.init();
    if (this.dispatching || !this.pending) return;
    const configured = await this.canSendToModel();
    if (!configured) return;

    const pending = this.pending;
    this.pending = null;
    this.connected = true;
    this.dispatching = true;
    this.clearSavedPending();
    try {
      await globalThis.sendMessage?.({
        skipExtensions: true,
        preserveInput: true,
        message: pending.message,
        attachments: pending.attachments,
        messageId: pending.messageId,
        context: pending.context,
      });
    } finally {
      this.dispatching = false;
    }
  },

  savePending() {
    const message = String(this.pending?.message || "").trim();
    const context = String(this.pending?.context || "");
    const messageId = String(this.pending?.messageId || "");
    const attachments = Array.isArray(this.pending?.attachments) ? this.pending.attachments : [];
    if (!message || !context || !messageId || attachments.length) {
      this.clearSavedPending();
      return;
    }

    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
        pending: { message, attachments: [], messageId, context },
        gateMessageId: this.gateMessageId || `model-gate-${messageId}`,
        choice: this.choice,
      }));
    } catch (_error) {
      // Session storage can be unavailable in private or locked-down browser modes.
    }
  },

  restorePending() {
    if (this.pending) return;

    let saved = null;
    try {
      saved = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || "null");
    } catch (_error) {
      this.clearSavedPending();
      return;
    }

    const message = String(saved?.pending?.message || "").trim();
    const context = String(saved?.pending?.context || "");
    const messageId = String(saved?.pending?.messageId || "");
    if (!message || !context || !messageId) {
      this.clearSavedPending();
      return;
    }

    this.active = true;
    this.connected = false;
    this.pending = { message, attachments: [], messageId, context };
    this.gateMessageId = String(saved?.gateMessageId || `model-gate-${messageId}`);
    this.choice = ["local", "cloud", "account"].includes(saved?.choice) ? saved.choice : "";
  },

  clearSavedPending() {
    try {
      sessionStorage.removeItem(STORAGE_KEY);
    } catch (_error) {
      // Ignore unavailable storage; the in-memory gate state is still authoritative.
    }
  },

});
