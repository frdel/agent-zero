from pathlib import Path
import shutil
import subprocess

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MESSAGES_JS = PROJECT_ROOT / "webui" / "js" / "messages.js"


def test_standard_latex_delimiters_survive_markdown_preprocessing():
    if not shutil.which("node"):
        pytest.skip("Node.js is required to execute the LaTeX delimiter regression.")

    source = MESSAGES_JS.read_text(encoding="utf-8")
    converter_start = source.index("function convertLatexDelimiters(")
    converter_end = source.index("\nfunction renderLatexElements", converter_start)
    function_source = source[converter_start:converter_end]

    script = rf"""
{function_source}

function assertEqual(actual, expected) {{
  if (actual !== expected) {{
    throw new Error(`Expected ${{JSON.stringify(expected)}}, got ${{JSON.stringify(actual)}}`);
  }}
}}

const encode = (value) =>
  Array.from(value, (char) => `&#${{char.codePointAt(0)}};`).join('');

assertEqual(
  convertLatexDelimiters(String.raw`\[x^2 < y & z > 0\]`),
  `<latex data-display="true">${{encode('x^2 < y & z > 0')}}</latex>`,
);
assertEqual(
  convertLatexDelimiters(String.raw`Before \(x+y\) after`),
  `Before <latex>${{encode('x+y')}}</latex> after`,
);
assertEqual(
  convertLatexDelimiters(String.raw`$$\sum_n a_n$$`),
  `<latex data-display="true">${{encode(String.raw`\sum_n a_n`)}}</latex>`,
);
const protectedCode =
  'Inline `' + String.raw`\(not_math\)` + '` and:\n' +
  '```tex\n' + String.raw`\[also_not_math\]` + '\n```';
assertEqual(convertLatexDelimiters(protectedCode), protectedCode);
"""
    subprocess.run(["node", "--input-type=module", "-e", script], check=True)


def test_katex_renderer_uses_text_content_and_display_metadata():
    source = MESSAGES_JS.read_text(encoding="utf-8")

    assert "if (latex) processedContent = convertLatexDelimiters(processedContent)" in source
    assert "renderLatexElements(contentDiv)" in source
    assert "globalThis.katex.render(element.textContent, element" in source
    assert 'displayMode: element.dataset.display === "true"' in source
    assert "drawKvpsIncremental(stepDetailScroll, kvps)" in source
    assert "drawKvpsIncremental(stepDetailScroll, kvps, latex)" not in source
    assert "renderLatexText(result.kvpsTable)" not in source
    assert "globalThis.renderMathInElement(" not in source
