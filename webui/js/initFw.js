import * as initializer from "./initializer.js"
import * as _modals from "./modals.js";
import * as _components from "./components.js";

// initialize required elements
await initializer.initialize()

// import alpine library
await import("../vendor/alpine/alpine.min.js");

// add x-destroy directive to alpine
Alpine.directive(
  "destroy",
  (el, { expression }, { evaluateLater, cleanup }) => {
    const onDestroy = evaluateLater(expression);
    cleanup(() => onDestroy());
  }
);
