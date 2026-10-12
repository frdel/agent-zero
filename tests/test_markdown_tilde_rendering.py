from pathlib import Path
import subprocess


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read(*parts: str) -> str:
    return PROJECT_ROOT.joinpath(*parts).read_text(encoding="utf-8")


def extract_js_function(source: str, name: str) -> str:
    start = source.find(f"function {name}(")
    if start < 0:
        raise AssertionError(f"Could not find JavaScript function: {name}")
    brace = source.find("{", start)
    depth = 0
    index = brace
    while index < len(source):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
        index += 1
    raise AssertionError(f"Could not find complete JavaScript function: {name}")


def run_node(script: str) -> str:
    return subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    ).stdout


def test_safe_markdown_pins_double_tilde_strikethrough() -> None:
    safe = read("webui", "js", "safe-markdown.js")

    assert "function forceDoubleTildeStrikethrough(markedInstance)" in safe
    assert "forceDoubleTildeStrikethrough(marked);" in safe
    assert "/^~~(?=" in safe


def test_single_tildes_render_literally_and_double_tildes_strike() -> None:
    safe = read("webui", "js", "safe-markdown.js")
    override = extract_js_function(safe, "forceDoubleTildeStrikethrough")
    vendor = PROJECT_ROOT / "webui" / "vendor" / "marked" / "marked.esm.js"

    script = f"""
import {{ marked }} from {str(vendor)!r};
{override}
forceDoubleTildeStrikethrough(marked);
const sentence = marked.parse(
  "Plugin saves ~66 ms per warm turn. On a 3-10 s turn that's **~1-2% end-to-end**.",
  {{ breaks: true }},
);
const strike = marked.parse("~~removed~~", {{ breaks: true }});
console.log(JSON.stringify({{ sentence, strike }}));
"""

    result = __import__("json").loads(run_node(script))

    assert "~66 ms" in result["sentence"]
    assert "~1-2%" in result["sentence"]
    assert "<strong>~1-2% end-to-end</strong>" in result["sentence"]
    assert "<del>" not in result["sentence"]
    assert "<del>removed</del>" in result["strike"]
