import { outputSpeedLabel } from "/plugins/_context_window/webui/output-speed.js";

// Shows each finished model call's output speed on its process step. The type
// is not checked: a plain-text Responses answer turns its generation item into
// a response, and a subordinate's response is still drawn as a step.
export default async function showOutputSpeed(context) {
  for (const { args, result } of context?.results || []) {
    const header = result?.step?.querySelector(":scope > .process-step-header");
    if (!header) continue;

    const label = outputSpeedLabel(args?.kvps?.output_speed);
    let badge = header.querySelector(":scope > .step-output-speed");
    if (!label) {
      badge?.remove();
      continue;
    }
    if (!badge) {
      badge = document.createElement("span");
      badge.className = "step-output-speed";
      const title = header.querySelector(":scope > .step-title");
      if (title) title.after(badge);
      else header.append(badge);
    }
    badge.textContent = label.text;
    badge.title = label.title;
  }
}
