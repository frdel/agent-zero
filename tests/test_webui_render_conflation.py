"""Regression tests for the Web UI chat-render conflation fix.

Root cause (2026-08-02): ``setMessages`` chained one full render per incoming
snapshot. Streaming pushes (debounced at 25ms server-side) can arrive far
faster than renders complete, so the render queue grew unboundedly during an
active turn. The chat body then lagged behind in real time and only caught up
long after the agent had finished — a completed workflow looked like it was
still running (CLI vs Web UI split-brain). A page refresh "fixed" it by
discarding the backlog.

The fix accumulates pending deltas and drains them in as few renders as
possible. These tests extract the real ``setMessages`` implementation from
``webui/js/messages.js``, run it in Node with a controlled slow renderer, and
assert both conflation (fewer renders than pushes) and completeness (no
dropped or reordered messages). On the pre-fix implementation the conflation
assertions fail, making the tests discriminating.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

MESSAGES_JS = PROJECT_ROOT / "webui" / "js" / "messages.js"

NODE_AVAILABLE = shutil.which("node") is not None
requires_node = pytest.mark.skipif(not NODE_AVAILABLE, reason="node not available")


def _extract_set_messages_block() -> str:
    """Extract the conflation state declarations + setMessages function from
    the real source so the behavioral test exercises shipped code. On pre-fix
    sources the state declarations do not exist; extract just the function so
    the harness can still demonstrate the un-conflated behavior."""
    js = MESSAGES_JS.read_text(encoding="utf-8")
    state_start = js.find("let _messageRenderRunning")
    func_start = js.find("export function setMessages(")
    assert func_start != -1, "setMessages not found in webui/js/messages.js"
    prefix = js[state_start:func_start] if -1 < state_start < func_start else ""

    # brace-count setMessages to its matching close
    body_start = js.find("{", func_start)
    depth = 0
    for pos in range(body_start, len(js)):
        char = js[pos]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return prefix + js[func_start : pos + 1]
    raise AssertionError("setMessages body is unbalanced")


def _build_harness(tmp_path: Path) -> Path:
    block = _extract_set_messages_block()
    harness = f"""
// --- stubs for the module-scope state messages.js normally provides ---
var _messageRenderGeneration = 0;
var _messageRenderQueue = Promise.resolve();

const renders = [];
let renderDelayMs = 5;
async function setMessagesNow(messages, generation) {{
  // simulate a slow renderer (markdown + DOM work)
  await new Promise((resolve) => setTimeout(resolve, renderDelayMs));
  renders.push(messages.map((m) => m.no));
}}

// --- shipped implementation under test ---
{block}

// --- driver: 60 rapid pushes of one-message deltas, like a streaming turn ---
// Yield periodically so drains start and renders run while later pushes keep
// arriving — this exercises the in-flight accumulation path, not just the
// burst path.
const PUSHES = 60;
const tasks = [];
for (let i = 0; i < PUSHES; i++) {{
  tasks.push(setMessages([{{ no: i, id: "m" + i, type: "agent" }}]));
  if (i % 2 === 1) await new Promise((resolve) => setTimeout(resolve, 1));
}}
await Promise.all(tasks);

const flat = renders.flat();
const unique = [...new Set(flat)];
const result = {{
  pushes: PUSHES,
  renderCalls: renders.length,
  renderedCount: flat.length,
  uniqueRendered: unique.length,
  ordered: flat.every((v, i, a) => i === 0 || a[i - 1] <= v),
  complete: unique.length === PUSHES && unique.every((v, i) => v === i),
}};
console.log(JSON.stringify(result));
"""
    path = tmp_path / "harness.mjs"
    path.write_text(harness, encoding="utf-8")
    return path


def _run_harness(tmp_path: Path) -> dict:
    harness = _build_harness(tmp_path)
    proc = subprocess.run(
        ["node", str(harness)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, f"node harness failed: {proc.stderr[:500]}"
    return json.loads(proc.stdout.strip().splitlines()[-1])


@requires_node
def test_streaming_pushes_are_conflated(tmp_path):
    """60 rapid pushes must not produce 60 renders; the queue must not grow
    one render per push (that was the unbounded-backlog bug)."""
    result = _run_harness(tmp_path)
    assert result["renderCalls"] < result["pushes"] // 2, (
        f"expected heavy conflation, got {result['renderCalls']} renders "
        f"for {result['pushes']} pushes"
    )


@requires_node
def test_conflation_drops_no_messages(tmp_path):
    """Every pushed message must still be rendered exactly once overall."""
    result = _run_harness(tmp_path)
    assert result["complete"], (
        f"incomplete render: {result['uniqueRendered']}/{result['pushes']} "
        "unique messages rendered"
    )
    assert result["ordered"], "messages rendered out of order"


def test_setmessages_has_conflation_guard():
    """Structural guard for no-node environments: the accumulation buffer and
    the in-flight early return must both exist in the shipped source."""
    js = MESSAGES_JS.read_text(encoding="utf-8")
    assert "_messageRenderPending" in js, "pending-delta accumulator missing"
    assert "if (_messageRenderRunning)" in js, "in-flight conflation guard missing"
    assert "await setMessagesNow(batch, generation)" in js, (
        "drain loop must render accumulated batches"
    )
