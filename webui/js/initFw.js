import * as _modals from "./modals.js";
import * as _components from "./components.js";

await import("../vendor/alpine/alpine.min.js");
await import("../vendor/alpine/alpine.collapse.min.js");

// add x-destroy directive
Alpine.directive(
  "destroy",
  (el, { expression }, { evaluateLater, cleanup }) => {
    const onDestroy = evaluateLater(expression);
    cleanup(() => onDestroy());
  }
);

// Wait for all modules to load before starting Alpine.js
await new Promise(resolve => {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', resolve);
  } else {
    resolve();
  }
});

// Give a small delay to ensure all module scripts have loaded
await new Promise(resolve => setTimeout(resolve, 100));

console.log("Starting Alpine.js...");
// Start Alpine.js only if not already started
try {
  Alpine.start();
} catch (error) {
  if (error.message && error.message.includes('already been initialized')) {
    console.log("Alpine.js already started, skipping initialization");
  } else {
    console.error("Error starting Alpine.js:", error);
  }
}