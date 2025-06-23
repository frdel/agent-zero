import * as _modals from "./modals.js";
import * as _components from "./components.js";

await import("./alpine.min.js");

// Import attachments store
import { store as attachmentsStore } from "../components/chat/attachments/attachmentsStore.js";

// add x-destroy directive
Alpine.directive(
  "destroy",
  (el, { expression }, { evaluateLater, cleanup }) => {
    const onDestroy = evaluateLater(expression);
    cleanup(() => onDestroy());
  }
);

// Initialize attachments store when Alpine.js is ready
document.addEventListener('alpine:init', () => {
  // Store is already created via createStore in attachmentsStore.js
  // Just call initialize to set up event handlers
  if (Alpine.store('chatAttachments')) {
    Alpine.store('chatAttachments').initialize();
  }
});
