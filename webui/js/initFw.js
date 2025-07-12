import * as _modals from "./modals.js";
import * as _components from "./components.js";
import "./notificationStore.js";

await import("../vendor/alpine/alpine.min.js");

// add x-destroy directive
Alpine.directive(
  "destroy",
  (el, { expression }, { evaluateLater, cleanup }) => {
    const onDestroy = evaluateLater(expression);
    cleanup(() => onDestroy());
  }
);

// Initialize notification store when Alpine is ready
document.addEventListener('alpine:init', () => {
  // Initialize the notification store
  setTimeout(() => {
    if (Alpine.store('notificationStore')) {
      Alpine.store('notificationStore').initialize();
    }
  }, 100);
});
