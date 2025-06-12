import * as _modals from "./modals.js";
import * as _components from "./components.js";

// Wait for Alpine.js to be available before adding directive
document.addEventListener('DOMContentLoaded', () => {
  // Ensure Alpine is loaded before adding directives
  if (typeof Alpine !== 'undefined') {
    // add x-destroy directive
    Alpine.directive(
      "destroy",
      (el, { expression }, { evaluateLater, cleanup }) => {
        const onDestroy = evaluateLater(expression);
        cleanup(() => onDestroy());
      }
    );
  } else {
    // Wait for Alpine to load
    const checkAlpine = setInterval(() => {
      if (typeof Alpine !== 'undefined') {
        clearInterval(checkAlpine);
        // add x-destroy directive
        Alpine.directive(
          "destroy",
          (el, { expression }, { evaluateLater, cleanup }) => {
            const onDestroy = evaluateLater(expression);
            cleanup(() => onDestroy());
          }
        );
      }
    }, 100);
  }
});
