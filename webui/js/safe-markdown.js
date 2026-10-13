import DOMPurify from "/vendor/dompurify/purify.es.mjs";
import { marked } from "/vendor/marked/marked.esm.js";
import { addBlankTargetsToLinks } from "/js/html-links.js";

// Strikethrough needs double tildes like GitHub so single-tilde approximations stay literal prose
function forceDoubleTildeStrikethrough(markedInstance) {
  markedInstance.use({
    tokenizer: {
      del(src) {
        const cap = /^~~(?=[^\s~])((?:\\.|[^\\])*?(?:\\.|[^\s~\\]))~~(?=[^~]|$)/.exec(src);
        if (!cap) return;
        return {
          type: "del",
          raw: cap[0],
          text: cap[1],
          tokens: this.lexer.inlineTokens(cap[1]),
        };
      },
    },
  });
}

forceDoubleTildeStrikethrough(marked);

const GITHUB_REPO_ROUTE_PREFIXES = new Set([
  "actions",
  "blob",
  "branches",
  "commit",
  "commits",
  "compare",
  "discussions",
  "issues",
  "labels",
  "milestones",
  "packages",
  "projects",
  "pulls",
  "raw",
  "releases",
  "security",
  "tags",
  "tree",
  "wiki",
]);

const DOMPURIFY_CONFIG = Object.freeze({
  USE_PROFILES: { html: true },
  FORBID_TAGS: ["script", "iframe", "object", "embed", "svg", "math"],
});

const DATA_IMAGE_URL_PATTERN =
  /^data:image\/(?:png|jpe?g|gif|webp|bmp);base64,[a-z0-9+/=\s]+$/i;

function getDompurifyConfig(options = {}) {
  const config = { ...DOMPURIFY_CONFIG };
  if (options.allowLatex) {
    config.ADD_TAGS = ["latex"];
  }
  return config;
}

function parseGithubRepoContext(githubUrl) {
  if (!githubUrl || typeof githubUrl !== "string") return null;

  let repoUrl;
  try {
    repoUrl = new URL(githubUrl.trim().replace(/\.git$/i, ""));
  } catch {
    return null;
  }

  if (repoUrl.hostname !== "github.com") return null;

  const [owner, repo] = repoUrl.pathname
    .replace(/^\/+|\/+$/g, "")
    .split("/");
  if (!owner || !repo) return null;

  return { owner, repo };
}

function shouldSkipRebase(value) {
  return (
    !value ||
    value.startsWith("#") ||
    value.startsWith("//") ||
    /^[a-zA-Z][a-zA-Z\d+.-]*:/.test(value)
  );
}

function resolveRepoPath(value) {
  if (shouldSkipRebase(value)) return null;
  try {
    const resolved = new URL(value, "https://repo-root.invalid/");
    return `${resolved.pathname.replace(/^\/+/, "")}${resolved.search}${resolved.hash}`;
  } catch {
    return null;
  }
}

function isGithubRepoRoutePath(repoPath) {
  const pathOnly = repoPath
    .split(/[?#]/, 1)[0]
    .replace(/^\/+|\/+$/g, "");
  if (!pathOnly) return false;
  const firstSegment = pathOnly.split("/")[0].toLowerCase();
  return GITHUB_REPO_ROUTE_PREFIXES.has(firstSegment);
}

function isSafeUrlValue(value, attributeName, options = {}) {
  const normalized = String(value || "").trim();
  if (!normalized) return true;
  if (
    options.allowDataImages &&
    attributeName === "src" &&
    DATA_IMAGE_URL_PATTERN.test(normalized)
  ) {
    return true;
  }
  if (
    normalized.startsWith("#") ||
    normalized.startsWith("/") ||
    normalized.startsWith("./") ||
    normalized.startsWith("../") ||
    normalized.startsWith("?")
  ) {
    return true;
  }

  try {
    const url = new URL(normalized, "https://sanitizer.invalid/");
    if (url.origin === "https://sanitizer.invalid") {
      return true;
    }

    const protocol = url.protocol.toLowerCase();
    if (protocol === "http:" || protocol === "https:") return true;
    if (attributeName === "href" && (protocol === "mailto:" || protocol === "tel:")) {
      return true;
    }
  } catch {
    return false;
  }

  return false;
}

function stripUnsafeUrlAttributes(html, options = {}) {
  const doc = new DOMParser().parseFromString(html, "text/html");

  doc.querySelectorAll("[href], [src]").forEach((element) => {
    for (const attributeName of ["href", "src"]) {
      if (!element.hasAttribute(attributeName)) continue;
      const value = element.getAttribute(attributeName) || "";
      if (!isSafeUrlValue(value, attributeName, options)) {
        element.removeAttribute(attributeName);
      }
    }
  });

  return doc.body.innerHTML;
}

export function sanitizeHtml(html, options = {}) {
  if (!html || typeof html !== "string") return "";
  const sanitized = DOMPurify.sanitize(html, getDompurifyConfig(options));
  return stripUnsafeUrlAttributes(sanitized, options);
}

export function rebaseGithubReadmeHtml(html, githubUrl, branch) {
  if (!html || typeof html !== "string" || !branch) return html;

  const repoContext = parseGithubRepoContext(githubUrl);
  if (!repoContext) return html;

  const { owner, repo } = repoContext;
  const repoWebBase = `https://github.com/${owner}/${repo}`;
  const repoBlobBase = `${repoWebBase}/blob/${branch}`;
  const repoRawBase = `https://raw.githubusercontent.com/${owner}/${repo}/${branch}`;
  const doc = new DOMParser().parseFromString(html, "text/html");

  // Single-segment links like "releases" are ambiguous, so README rebasing
  // needs an explicit GitHub repo-route allowlist instead of a single base URL.
  doc.querySelectorAll("a[href]").forEach((anchor) => {
    const href = (anchor.getAttribute("href") || "").trim();
    const repoPath = resolveRepoPath(href);
    if (!repoPath) return;
    const base = isGithubRepoRoutePath(repoPath) ? repoWebBase : repoBlobBase;
    anchor.setAttribute("href", `${base}/${repoPath}`);
  });

  doc.querySelectorAll("img[src]").forEach((image) => {
    const src = (image.getAttribute("src") || "").trim();
    const repoPath = resolveRepoPath(src);
    if (!repoPath) return;
    image.setAttribute("src", `${repoRawBase}/${repoPath}`);
  });

  return doc.body.innerHTML;
}

export function renderSafeMarkdown(markdown, options = {}) {
  if (!markdown) return "";

  const { githubUrl = "", branch = "", openExternalLinksInNewTab = true } = options;

  let html = marked.parse(markdown, { breaks: true });
  if (githubUrl && branch) {
    html = rebaseGithubReadmeHtml(html, githubUrl, branch);
  }

  html = sanitizeHtml(html, options);

  if (openExternalLinksInNewTab) {
    html = addBlankTargetsToLinks(html);
  }

  return html;
}
