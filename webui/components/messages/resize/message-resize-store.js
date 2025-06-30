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
      "message-agent": { minimized: true, maximized: false },
      "messsage-code-exec": { minimized: false, maximized: false },
    };
  },

  _getSetting(className) {
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
    const set = this._getSetting(className);
    set.minimized = !set.minimized;
    this._setSetting(className, set);
    this._applySetting(className, set);
    this._applyScroll(event);
  },

  async maximizeMessageClass(className, event) {
    const set = this._getSetting(className);
    if (set.minimized) return this.minimizeMessageClass(className, event); // if minimized, unminimize first
    set.maximized = !set.maximized;
    this._setSetting(className, set);
    this._applySetting(className, set);
    this._applyScroll(event);
  },

  _applyScroll(event) {
    event.target.scrollIntoView({ behavior: "smooth" });
  },

  _applySetting(className, setting) {
    toggleCssProperty(
      `.${className} .message-body`,
      "max-height",
      setting.maximized ? undefined : "30em"
    );
    toggleCssProperty(
      `.${className} .message-body`,
      "overflow-y",
      setting.maximized ? undefined : "auto"
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
