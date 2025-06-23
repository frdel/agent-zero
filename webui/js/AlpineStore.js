// Track all created stores
const stores = new Map();

/**
 * Creates a store that can be used to share state between components.
 * Uses initial state object and returns a proxy to it that uses Alpine when initialized
 * @template T
 * @param {string} name
 * @param {T} initialState
 * @returns {T}
 */
export function createStore(name, initialState) {
  console.log('createStore called for:', name);
  const proxy = new Proxy(initialState, {
    set(target, prop, value) {
      const store = globalThis.Alpine?.store(name);
      if (store) store[prop] = value;
      else target[prop] = value;
      return true;
    },
    get(target, prop) {
      return target[prop];
    }
  });

  if (globalThis.Alpine) {
    console.log('Alpine available, registering store immediately:', name);
    globalThis.Alpine.store(name, initialState);
  } else {
    console.log('Alpine not available, waiting for alpine:init for store:', name);
    document.addEventListener("alpine:init", () => {
      console.log('alpine:init fired, registering store:', name);
      Alpine.store(name, initialState);
    });
  }

  // Store the proxy
  stores.set(name, proxy);
  console.log('Store proxy created and stored for:', name);

  return /** @type {T} */ (proxy); // explicitly cast for linter support
}

/**
 * Get an existing store by name
 * @template T
 * @param {string} name
 * @returns {T | undefined}
 */
export function getStore(name) {
  return /** @type {T | undefined} */ (stores.get(name));
}