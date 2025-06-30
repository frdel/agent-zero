// Create and keep a reference to a dynamic stylesheet for runtime CSS changes
let dynamicStyleSheet;
{
  const style = document.createElement("style");
  style.appendChild(document.createTextNode(""));
  document.head.appendChild(style);
  dynamicStyleSheet = style.sheet;
}

export function toggleCssProperty(selector, property, value) {
  // Get the stylesheet that contains the class
  const styleSheets = document.styleSheets;

  // Iterate through all stylesheets to find the class
  for (let i = 0; i < styleSheets.length; i++) {
    const styleSheet = styleSheets[i];
    let rules;
    try {
      rules = styleSheet.cssRules || styleSheet.rules;
    } catch (e) {
      // Skip stylesheets we cannot access due to CORS/security restrictions
      continue;
    }
    if (!rules) continue;

    for (let j = 0; j < rules.length; j++) {
      const rule = rules[j];
      if (rule.selectorText == selector) {
        _applyCssToRule(rule, property, value);
        return;
      }
    }
  }
  // If not found, add it to the dynamic stylesheet
  const ruleIndex = dynamicStyleSheet.insertRule(
    `${selector} {}`,
    dynamicStyleSheet.cssRules.length
  );
  const rule = dynamicStyleSheet.cssRules[ruleIndex];
  _applyCssToRule(rule, property, value);
}

// Helper to apply/remove a CSS property on a rule
function _applyCssToRule(rule, property, value) {
    if (value === undefined) {
      rule.style.removeProperty(property);
    } else {
      rule.style.setProperty(property, value);
    }
  }