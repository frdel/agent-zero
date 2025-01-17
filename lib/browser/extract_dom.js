function extractDOM([
  selectorLabel = "",
  selectorName = "data-a0sel3ct0r",
  guidName = "data-a0gu1d",
]) {
  let elementCounter = 0;
  const time = new Date().toISOString().slice(11, -1).replace(/[:.]/g, "");
  const ignoredTags = [
    "style",
    "script",
    "meta",
    "link",
    "svg",
    "noscript",
    "path",
  ];

  // Convert number to base64 and trim unnecessary chars
  function toBase64(num) {
    const chars =
      "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
    let result = "";

    do {
      result = chars[num & 63] + result;
      num = num >> 6;
    } while (num > 0);

    return result;
  }

  function isElementVisible(element) {
    // Return true for non-element nodes
    if (element.nodeType !== Node.ELEMENT_NODE) {
      return true;
    }

    const computedStyle = window.getComputedStyle(element);

    // Check if element is hidden via CSS
    if (
      computedStyle.display === "none" ||
      computedStyle.visibility === "hidden" ||
      computedStyle.opacity === "0"
    ) {
      return false;
    }

    // Check for hidden input type
    if (element.tagName === "INPUT" && element.type === "hidden") {
      return false;
    }

    // Check for hidden attribute
    if (
      element.hasAttribute("hidden") ||
      element.getAttribute("aria-hidden") === "true"
    ) {
      return false;
    }

    return true;
  }

  function convertAttribute(tag, attr) {
    let out = {
      name: attr.name,
      value:
        typeof attr.value == "string" ? attr.value : JSON.stringify(attr.value),
    };

    //excluded attributes
    if (["srcset"].includes(out.name)) return null;
    if (out.name.startsWith("data-") && out.name != selectorName) return null;

    if (out.name == "src" && out.value.startsWith("data:"))
      out.value = "data...";

    return out;
  }

  function traverseNodes(node, depth = 0, visited = new Set()) {
    // Safety checks
    if (!node) return "";
    if (depth > 1000) return "<!-- Max depth exceeded -->";

    const guid = node.getAttribute?.(guidName);
    if (guid && visited.has(guid)) {
      return `<!-- Circular reference detected at guid: ${guid} -->`;
    }

    let content = "";
    const tagName = node.tagName ? node.tagName.toLowerCase() : "";

    // Skip ignored tags
    if (tagName && ignoredTags.includes(tagName)) {
      return "";
    }

    if (node.nodeType === Node.ELEMENT_NODE) {
      // Add unique ID to the actual DOM element
      if (tagName) {
        const no = elementCounter++;
        const selector = `${no}${selectorLabel}`;
        const guid = `${time}-${selector}`;
        node.setAttribute(selectorName, selector);
        node.setAttribute(guidName, guid);
        visited.add(guid);
      }

      content += `<${tagName}`;

      // Add invisible attribute if element is not visible
      if (!isElementVisible(node)) {
        content += " invisible";
      }

      for (let attr of node.attributes) {
        const out = convertAttribute(tagName, attr);
        if (out) content += ` ${out.name}="${out.value}"`;
      }

      content += ">";

      // Handle iframes
      if (tagName === "iframe") {
        try {
          const frameId = elementCounter++;
          node.setAttribute(selectorName, frameId);
          content += `<!-- IFrame Content Placeholder ${frameId} -->`;
        } catch (e) {
          console.warn("Error marking iframe:", e);
        }
      }

      if (node.shadowRoot) {
        content += "<!-- Shadow DOM Start -->";
        for (let shadowChild of node.shadowRoot.childNodes) {
          content += traverseNodes(shadowChild, depth + 1, visited);
        }
        content += "<!-- Shadow DOM End -->";
      }

      for (let child of node.childNodes) {
        content += traverseNodes(child, depth + 1, visited);
      }

      content += `</${tagName}>`;
    } else if (node.nodeType === Node.TEXT_NODE) {
      content += node.textContent;
    } else if (node.nodeType === Node.COMMENT_NODE) {
      content += `<!--${node.textContent}-->`;
    }

    return content;
  }

  const fullHTML = traverseNodes(document.documentElement);
  return fullHTML;
}
