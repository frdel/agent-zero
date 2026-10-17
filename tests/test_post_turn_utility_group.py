"""Regression tests for post-turn utility process-group completion.

Root cause (2026-08-02): the memory plugin's monologue_end extensions
(_50_memorize_fragments, _51_memorize_solutions) log a utility item when the
agent loop ends and then fill it in from a background task. By that point the
turn's process group was already completed by the final response, so the Web
UI opened a new process group for these items. That group (a) contains no
agent steps, so its title stayed on the "Processing..." placeholder, and (b)
was never marked complete by any later event, so its steps kept the in-flight
"shiny" animation and the phase never received an END badge — a finished turn
looked like it was still running.

Fix: the backend marks the utility item with a ``finished`` kvp on every
terminal update path (and keeps these post-turn items off the status bar with
``update_progress="none"``), and the Web UI closes the process group when a
utility step arrives with ``kvps.finished`` and falls back to the last step's
title for groups without agent steps.

These tests run the real ``memorize()`` coroutines against stubbed
agents/log items and assert the terminal marker is emitted, and extract the
real ``updateProcessGroupHeader``/``isProcessGroupComplete``/
``completeLastProcessGroup`` functions from ``webui/js/messages.js`` into a
Node harness with a minimal fake DOM to assert group completion and title
fallback. Both halves fail on the pre-fix implementation, making them
discriminating.
"""

import asyncio
import importlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

MESSAGES_JS = PROJECT_ROOT / "webui" / "js" / "messages.js"

NODE_AVAILABLE = shutil.which("node") is not None
requires_node = pytest.mark.skipif(not NODE_AVAILABLE, reason="node not available")


def _load_extension_module(name: str):
    return importlib.import_module(
        f"plugins._memory.extensions.python.monologue_end.{name}"
    )


class FakeLogItem:
    """Records every update() call so tests can inspect terminal markers."""

    def __init__(self):
        self.updates: list[dict] = []
        self.streams: list[dict] = []

    def update(self, **kwargs):
        self.updates.append(kwargs)

    def stream(self, **kwargs):
        self.streams.append(kwargs)


class FakeLog:
    def __init__(self):
        self.warnings: list[dict] = []

    def log(self, **kwargs):
        self.warnings.append(kwargs)
        return FakeLogItem()


def _make_agent(utility_response=None, utility_error: Exception | None = None):
    """Agent stub exposing only what memorize() touches."""

    async def call_utility_model(**kwargs):
        if utility_error is not None:
            raise utility_error
        return utility_response

    return SimpleNamespace(
        history=[],
        context=SimpleNamespace(log=FakeLog()),
        read_prompt=lambda *a, **k: "system prompt",
        concat_messages=lambda history: "chat text",
        call_utility_model=call_utility_model,
    )


def _patch_plugin_config(monkeypatch, mod, consolidation: bool):
    import helpers.plugins as plugins_mod

    monkeypatch.setattr(
        plugins_mod,
        "get_plugin_config",
        lambda plugin, agent=None, **kwargs: {
            "memory_memorize_enabled": True,
            "memory_memorize_consolidation": consolidation,
            "memory_memorize_replace_threshold": 0,
        },
    )


def _patch_memory_db(monkeypatch, mod):
    """Replace Memory.get with an async stub DB (non-consolidation path)."""
    inserted: list[str] = []

    class FakeDB:
        async def delete_documents_by_query(self, **kwargs):
            return []

        async def insert_text(self, text, metadata=None):
            inserted.append(text)
            return "id"

    async def fake_get(agent):
        return FakeDB()

    monkeypatch.setattr(mod.Memory, "get", staticmethod(fake_get))
    return inserted


@pytest.mark.parametrize(
    "module_name,empty_heading",
    [
        ("_50_memorize_fragments", "No useful information to memorize."),
        ("_51_memorize_solutions", "No successful solutions to memorize."),
    ],
)
def test_empty_utility_result_marks_log_item_finished(
    monkeypatch, module_name, empty_heading
):
    """An empty utility-model result is a terminal path: it must emit the
    finished kvp so the Web UI can close the post-turn process group."""
    mod = _load_extension_module(module_name)
    _patch_plugin_config(monkeypatch, mod, consolidation=False)
    _patch_memory_db(monkeypatch, mod)

    ext = mod.MemorizeMemories(agent=None) if module_name.startswith("_50") else mod.MemorizeSolutions(agent=None)
    ext.agent = _make_agent(utility_response="[]")
    log_item = FakeLogItem()

    asyncio.run(ext.memorize(loop_data=None, log_item=log_item))

    assert log_item.updates, "memorize() never updated the log item"
    final = log_item.updates[-1]
    assert final.get("heading") == empty_heading
    assert final.get("finished") is True, (
        "terminal update lacks finished=True; the Web UI process group "
        "would stay open forever"
    )


@pytest.mark.parametrize(
    "module_name,response",
    [
        ("_50_memorize_fragments", '["The user prefers concise final reports.", "The project requires full test runs before release."]'),
        ("_51_memorize_solutions", '[{"problem": "p", "solution": "s"}]'),
    ],
)
def test_successful_memorization_marks_finished_after_inserts(
    monkeypatch, module_name, response
):
    """Successful memorization (non-consolidation path) must insert all
    entries first and only then emit the terminal finished marker."""
    mod = _load_extension_module(module_name)
    _patch_plugin_config(monkeypatch, mod, consolidation=False)
    inserted = _patch_memory_db(monkeypatch, mod)

    cls = mod.MemorizeMemories if module_name.startswith("_50") else mod.MemorizeSolutions
    ext = cls(agent=None)
    ext.agent = _make_agent(utility_response=response)
    log_item = FakeLogItem()

    asyncio.run(ext.memorize(loop_data=None, log_item=log_item))

    assert inserted, "nothing was inserted into the memory DB"
    finished_updates = [u for u in log_item.updates if u.get("finished") is True]
    assert len(finished_updates) == 1, (
        f"expected exactly one terminal finished update, got {len(finished_updates)}"
    )
    assert log_item.updates[-1].get("finished") is True
    # the finished marker must not hijack the status bar
    assert log_item.updates[-1].get("update_progress") == "none"


@pytest.mark.parametrize(
    "module_name",
    ["_50_memorize_fragments", "_51_memorize_solutions"],
)
def test_utility_model_error_still_closes_group_without_status_bar_hijack(
    monkeypatch, module_name
):
    """On failure the item must still be marked finished (no orphaned group)
    and the warning must not take over the status bar after the turn ended."""
    mod = _load_extension_module(module_name)
    _patch_plugin_config(monkeypatch, mod, consolidation=False)
    _patch_memory_db(monkeypatch, mod)

    cls = mod.MemorizeMemories if module_name.startswith("_50") else mod.MemorizeSolutions
    ext = cls(agent=None)
    ext.agent = _make_agent(utility_error=RuntimeError("provider exploded"))
    log_item = FakeLogItem()

    asyncio.run(ext.memorize(loop_data=None, log_item=log_item))

    assert log_item.updates[-1].get("finished") is True
    assert log_item.updates[-1].get("update_progress") == "none"
    warnings = ext.agent.context.log.warnings
    assert len(warnings) == 1
    assert warnings[0]["type"] == "warning"
    assert warnings[0].get("update_progress") == "none"


@pytest.mark.parametrize(
    "module_name,create_heading",
    [
        ("_50_memorize_fragments", "Memorizing new information..."),
        ("_51_memorize_solutions", "Memorizing succesful solutions..."),
    ],
)
def test_execute_creates_log_item_off_status_bar(module_name, create_heading):
    """The synchronous log item creation at monologue end must pass
    update_progress="none" so post-turn bookkeeping never hijacks progress."""
    import inspect

    mod = _load_extension_module(module_name)
    cls = mod.MemorizeMemories if module_name.startswith("_50") else mod.MemorizeSolutions
    source = inspect.getsource(cls.execute)
    log_call_pos = source.find("context.log.log(")
    assert log_call_pos != -1
    call_src = source[log_call_pos : source.find(")", log_call_pos)]
    assert 'update_progress="none"' in call_src
    assert create_heading in call_src


# ---------------------------------------------------------------------------
# Frontend: updateProcessGroupHeader / completeLastProcessGroup behavior
# ---------------------------------------------------------------------------


def _extract_function(js: str, signature: str) -> str:
    start = js.find(signature)
    assert start != -1, f"{signature} not found in webui/js/messages.js"
    body_start = js.find("{", start)
    depth = 0
    for pos in range(body_start, len(js)):
        char = js[pos]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return js[start : pos + 1]
    raise AssertionError(f"{signature} body is unbalanced")


def _build_node_harness(tmp_path: Path) -> Path:
    js = MESSAGES_JS.read_text(encoding="utf-8")
    blocks = [
        _extract_function(js, "function truncateText("),
        _extract_function(js, "export function cleanStepTitle("),
        _extract_function(js, "function updateProcessGroupHeader("),
        _extract_function(js, "function isProcessGroupComplete("),
        _extract_function(js, "export function completeLastProcessGroup("),
    ]
    shipped = "\n\n".join(blocks)
    harness = """
// --- minimal fake DOM ------------------------------------------------------
class FakeClassList {
  constructor(owner) { this.owner = owner; this.set = new Set(); }
  add(...cs) { cs.forEach((c) => this.set.add(c)); }
  remove(...cs) { cs.forEach((c) => this.set.delete(c)); }
  contains(c) { return this.set.has(c); }
  toggle(c, force) {
    const on = force === undefined ? !this.set.has(c) : Boolean(force);
    on ? this.set.add(c) : this.set.delete(c);
  }
}

class FakeElement {
  constructor(tag = "div") {
    this.tag = tag;
    this.children = [];
    this.attrs = {};
    this.classList = new FakeClassList(this);
    this.dataset = {};
    this.textContent = "";
    this.title = "";
    this.outerHTML = "";
  }
  get className() { return [...this.classList.set].join(" "); }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  hasAttribute(k) { return k in this.attrs; }
  _matches(sel) {
    if (sel.startsWith(".")) return this.classList.contains(sel.slice(1));
    if (sel.startsWith("[")) {
      const m = sel.match(/^\\[([^=\\]]+)(?:="([^"]*)")?\\]$/);
      if (!m) return false;
      const val = this.getAttribute(m[1]);
      return m[2] === undefined ? val !== null : val === m[2];
    }
    return false;
  }
  _all() {
    const out = [];
    const walk = (el) => { out.push(el); el.children.forEach(walk); };
    this.children.forEach(walk);
    return out;
  }
  querySelector(sel) {
    // support compound ".a .b" and ".a.b" selectors used by shipped code
    if (sel.startsWith(":scope ")) sel = sel.slice(7);
    const parts = sel.split(/\\s+/);
    let candidates = [this];
    for (const part of parts) {
      const next = [];
      const classes = part.split(".").filter(Boolean);
      const attrMatch = part.match(/\\.[^\\[]*(\\[.*)$/);
      for (const el of candidates) {
        for (const d of el._all()) {
          let ok = classes.length
            ? classes.every((c) => d.classList.contains(c))
            : d._matches(part);
          if (ok && attrMatch) ok = d._matches(attrMatch[1]);
          if (ok) next.push(d);
        }
      }
      candidates = next;
    }
    return candidates[0] || null;
  }
  querySelectorAll(sel) {
    // support ".a.b" and ".sel[attr="v"]" compound selectors
    const attrMatch = sel.match(/^(\\.[^\\[]*)?(\\[.*)$/);
    let base = sel;
    let attr = null;
    if (attrMatch && attrMatch[2]) { base = attrMatch[1] || ""; attr = attrMatch[2]; }
    const classes = base.split(".").filter(Boolean);
    return this._all().filter((d) => {
      let ok = classes.length ? classes.every((c) => d.classList.contains(c)) : true;
      if (ok && attr) ok = d._matches(attr);
      return ok;
    });
  }
  appendChild(c) { this.children.push(c); return c; }
}

function makeStep({ type, title, shiny = false }) {
  const step = new FakeElement();
  step.classList.add("process-step");
  step.setAttribute("data-log-type", type);
  step.setAttribute("data-step-code", type === "agent" ? "GEN" : "UTL");
  const titleEl = new FakeElement();
  titleEl.classList.add("step-title");
  if (shiny) titleEl.classList.add("shiny-text");
  titleEl.textContent = title;
  step.appendChild(titleEl);
  return step;
}

function makeGroup(steps) {
  const group = new FakeElement();
  group.classList.add("process-group");
  const header = new FakeElement();
  header.classList.add("process-group-header");
  const title = new FakeElement();
  title.classList.add("group-title");
  title.textContent = "Processing...";
  const badge = new FakeElement();
  badge.classList.add("step-badge");
  const metrics = new FakeElement();
  metrics.classList.add("group-metrics");
  header.appendChild(title); header.appendChild(badge); header.appendChild(metrics);
  group.appendChild(header);
  steps.forEach((s) => group.appendChild(s));
  return { group, title, badge };
}

// --- module-scope stubs the shipped functions rely on ----------------------
var _lastGroup = null;
function getLastProcessGroup() { return _lastGroup; }
function getUserHour12() { return false; }
function getUserTimezone() { return "UTC"; }
function formatDateTime(iso) { return iso; }

// --- shipped implementation under test -------------------------------------
__SHIPPED__

// --- driver ----------------------------------------------------------------
const results = {};

// Case 1: utility-only group (post-turn memory memorization) — title must
// fall back to the last step's heading instead of staying "Processing...".
{
  const steps = [
    makeStep({ type: "util", title: "Memorizing new information...", shiny: true }),
    makeStep({ type: "util", title: "No useful information to memorize.", shiny: true }),
  ];
  const { group, title, badge } = makeGroup(steps);
  _lastGroup = group;
  updateProcessGroupHeader(group);
  results.utilTitle = title.textContent;
  results.utilBadgeBeforeComplete = badge.outerHTML;

  // backend terminal update arrives with kvps.finished → drawMessageUtil
  // calls completeLastProcessGroup()
  completeLastProcessGroup();
  results.utilCompleted = isProcessGroupComplete(group);
  results.utilBadgeAfterComplete = badge.outerHTML;
  results.utilShinyRemaining = group.querySelectorAll(".step-title.shiny-text").length;
}

// Case 2: regression guard — a group with agent steps still takes its title
// from the last agent step, not from a later utility step.
{
  const steps = [
    makeStep({ type: "agent", title: "A0: Reading storage code" }),
    makeStep({ type: "util", title: "3 memories found" }),
  ];
  const { group, title } = makeGroup(steps);
  _lastGroup = group;
  updateProcessGroupHeader(group);
  results.mixedTitle = title.textContent;
}

console.log(JSON.stringify(results));
"""
    harness = harness.replace("__SHIPPED__", shipped)
    path = tmp_path / "group_header_harness.mjs"
    path.write_text(harness, encoding="utf-8")
    return path


@requires_node
def test_utility_only_group_completes_and_titles_from_last_step(tmp_path):
    harness = _build_node_harness(tmp_path)
    proc = subprocess.run(
        ["node", str(harness)], capture_output=True, text=True, timeout=60
    )
    assert proc.returncode == 0, f"node harness failed:\n{proc.stderr}"
    results = json.loads(proc.stdout.strip().splitlines()[-1])

    # title fallback: last utility step heading, not the placeholder
    assert results["utilTitle"] == "No useful information to memorize.", (
        "utility-only group title did not fall back to the last step heading"
    )
    # completion: group closed, END badge set, shiny animation removed
    assert results["utilCompleted"] is True
    assert "END" in results["utilBadgeAfterComplete"]
    assert results["utilShinyRemaining"] == 0
    # mixed groups still prefer the last agent step heading
    assert results["mixedTitle"] == "A0: Reading storage code"
