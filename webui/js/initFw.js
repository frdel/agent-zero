import * as _modals from "./modals.js";
import * as _components from "./components.js";

await import("../vendor/alpine/alpine.min.js");

// add x-destroy directive
Alpine.directive(
  "destroy",
  (el, { expression }, { evaluateLater, cleanup }) => {
    const onDestroy = evaluateLater(expression);
    cleanup(() => onDestroy());
  }
);
