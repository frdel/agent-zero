import { createStore } from "/js/AlpineStore.js";
import { callJsonApi } from "/js/api.js";
import { createDurabilityState } from "/components/durability/durability-state.js";

export const store = createStore("durabilityStore", createDurabilityState(
  (payload) => callJsonApi("/durability", payload),
));
