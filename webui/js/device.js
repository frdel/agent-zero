/**
 * Detects the input type: 'pointer' (e.g., mouse, supports hover) or 'touch' (e.g., finger, no reliable hover).
 * On hybrids, resolves based on first user interaction (mouse vs. touch).
 * @returns {Promise<string>} Resolves to 'pointer' or 'touch'.
 */
// Module variable to store detected input type
let detectedInputType;

// Detects and stores the input type: 'pointer' or 'touch'. On hybrids, resolves on first user interaction.
export function determineInputType() {
  return new Promise((resolve) => {
    let inputType = "pointer"; // Default (overridden below)
    let resolved = false;

    // Helper to resolve and clean up listeners
    const resolveType = (type) => {
      if (resolved) return;
      resolved = true;
      inputType = type;
      detectedInputType = type; // store in module variable
      resolve(inputType);
      // Remove listeners to avoid memory leaks
      document.removeEventListener("touchstart", onTouch, { passive: true });
      document.removeEventListener("mousemove", onMouse, { passive: true });
      document.removeEventListener("mouseenter", onMouse, { passive: true });
    };

    // Dynamic listeners for hybrids (detect first interaction)
    const onTouch = () => resolveType("touch");
    const onMouse = () => resolveType("pointer");

    // Static detection (inspired by detect-it: https://github.com/rafgraph/detect-it)
    // Step 1: Check for touch capability (touchOnly or hybrid)
    const hasTouch = () => {
      if ("maxTouchPoints" in navigator) return navigator.maxTouchPoints > 0;
      if (window.matchMedia)
        return window.matchMedia("(any-pointer: coarse)").matches;
      return "ontouchstart" in window || navigator.msMaxTouchPoints > 0;
    };

    // Step 2: Check for pointer/hover capability (pointerOnly or hybrid)
    const hasPointer = () => {
      if (window.matchMedia) {
        const finePointer = window.matchMedia("(any-pointer: fine)").matches;
        const hover = window.matchMedia("(any-hover: hover)").matches;
        return finePointer || hover;
      }
      return false; // Fallback: Assume no pointer if media queries unavailable
    };

    const touchSupported = hasTouch();
    const pointerSupported = hasPointer();

    if (touchSupported && !pointerSupported) {
      // Touch-only (e.g., phones)
      resolveType("touch");
    } else if (!touchSupported && pointerSupported) {
      // Pointer-only (e.g., desktops)
      resolveType("pointer");
    } else if (touchSupported && pointerSupported) {
      // Hybrid: Wait for first interaction to determine usageDit is the user's active input
      // Default to pointer, but add listeners if hybrid
      inputType = "pointer"; // Default for hybrids until interaction
      document.addEventListener("touchstart", onTouch, { passive: true });
      document.addEventListener("mousemove", onMouse, { passive: true });
      document.addEventListener("mouseenter", onMouse, { passive: true });
      // Optional: Timeout fallback (e.g., after 10s, assume pointer for hybrids)
      setTimeout(() => resolveType("pointer"), 10000);
    } else {
      // Rare fallback: No touch or pointer detected (assume pointer)
      resolveType("pointer");
    }
  });
}

// Exported function to get the detected input type (defaults to 'pointer' if undetermined)
export function getInputType() {
  return detectedInputType || "pointer";
}