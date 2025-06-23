import * as _modals from "./modals.js";
import * as _components from "./components.js";

await import("./alpine.min.js");

// Import attachments store
console.log('initFw.js: About to import attachments store...');
import { store as attachmentsStore } from "../components/chat/attachments/attachmentsStore.js";
console.log('initFw.js: Attachments store imported:', attachmentsStore);

// add x-destroy directive
Alpine.directive(
  "destroy",
  (el, { expression }, { evaluateLater, cleanup }) => {
    const onDestroy = evaluateLater(expression);
    cleanup(() => onDestroy());
  }
);

// Initialize attachments store when Alpine.js is ready
function initializeAttachmentsStore() {
  console.log('Attempting to initialize attachments store...');
  if (window.Alpine && Alpine.store('chatAttachments')) {
    console.log('chatAttachments store found, initializing...');
    Alpine.store('chatAttachments').initialize();
    return true;
  } else {
    console.log('Alpine or store not ready yet, will retry...');
    return false;
  }
}

// Try multiple initialization approaches
document.addEventListener('alpine:init', () => {
  console.log('Alpine.js alpine:init event fired');
  setTimeout(() => initializeAttachmentsStore(), 100);
});

// Also try when Alpine is fully initialized
document.addEventListener('alpine:initialized', () => {
  console.log('Alpine.js alpine:initialized event fired');
  initializeAttachmentsStore();
});

// Fallback: try after a delay
setTimeout(() => {
  if (!initializeAttachmentsStore()) {
    console.log('Retrying attachments store initialization after delay...');
    setTimeout(initializeAttachmentsStore, 1000);
  }
}, 500);
