import { createStore } from "/js/AlpineStore.js";
import { toggleCssProperty } from "/js/css.js";

const model = {
  settings: {},

  async init() {
    this.settings =
      JSON.parse(localStorage.getItem("messageResizeSettings") || "null") ||
      this._getDefaultSettings();
    this._applyAllSettings();
  },

  _getDefaultSettings() {
    return {
      "message": { minimized: false, maximized: false },
      "message-agent": { minimized: true, maximized: false },
      "message-agent-response": { minimized: false, maximized: true },
    };
  },

  getSetting(className) {
    return this.settings[className] || { minimized: false, maximized: false };
  },

  _getDefaultSetting() {
    return { minimized: false, maximized: false };
  },

  _setSetting(className, setting) {
    this.settings[className] = setting;
    localStorage.setItem(
      "messageResizeSettings",
      JSON.stringify(this.settings)
    );
  },

  _applyAllSettings() {
    for (const [className, setting] of Object.entries(this.settings)) {
      this._applySetting(className, setting);
    }
  },

  async minimizeMessageClass(className, event) {
    const set = this.getSetting(className);
    set.minimized = !set.minimized;
    this._setSetting(className, set);
    this._applySetting(className, set);
    this._applyScroll(event);
  },

  async maximizeMessageClass(className, event) {
    const set = this.getSetting(className);
    if (set.minimized) return this.minimizeMessageClass(className, event); // if minimized, unminimize first
    set.maximized = !set.maximized;
    this._setSetting(className, set);
    this._applySetting(className, set);
    this._applyScroll(event);
  },

  _applyScroll(event) {
    if (!event || !event.target) {
      return;
    }
    
    // Store the element reference to avoid issues with event being modified
    const targetElement = event.target;
    const clickY = event.clientY;
    
    // Use requestAnimationFrame for smoother timing with browser rendering
    // requestAnimationFrame(() => {
        try {
          // Get fresh measurements after potential re-renders
          const rect = targetElement.getBoundingClientRect();
          const viewHeight = window.innerHeight || document.documentElement.clientHeight;
          
          // Get chat history element
          const chatHistory = document.getElementById('chat-history');
          if (!chatHistory) {
            return;
          }
          
          // Get chat history position
          const chatRect = chatHistory.getBoundingClientRect();
          
          // Calculate element's middle position relative to chat history
          const elementHeight = rect.height;
          const elementMiddle = rect.top + (elementHeight / 2);
          const relativeMiddle = elementMiddle - chatRect.top;
          
          // Calculate target scroll position
          let scrollTop;
          
          if (typeof clickY === 'number') {
            // Calculate based on click position
            const clickRelativeToChat = clickY - chatRect.top;
            // Add current scroll position and adjust to keep element middle at click position
            scrollTop = chatHistory.scrollTop + relativeMiddle - clickRelativeToChat;
          } else {
            // Position element middle at 50% from the top of chat history viewport (center)
            const targetPosition = chatHistory.clientHeight * 0.5;
            scrollTop = chatHistory.scrollTop + relativeMiddle - targetPosition;
          }
          
          // Apply scroll with instant behavior
          chatHistory.scrollTo({
            top: scrollTop,
            behavior: "auto"
          });
        } catch (e) {
          // Silent error handling
        }
    // });
  },

  _applySetting(className, setting) {
    toggleCssProperty(
      `.${className} .message-body`,
      "max-height",
      setting.maximized ? "unset" : "30em"
    );
    toggleCssProperty(
      `.${className} .message-body`,
      "overflow-y",
      setting.maximized ? "hidden" : "auto"
    );
    toggleCssProperty(
      `.${className} .message-body`,
      "display",
      setting.minimized ? "none" : "block"
    );
  },
};

const store = createStore("messageResize", model);

export { store };
