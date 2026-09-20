import re
from pathlib import Path

from helpers import skills


ROOT = Path(__file__).resolve().parents[1]


def test_plugin_entrypoints_load_references_and_replace_retired_skills(monkeypatch):
    candidates = [skills.skill_from_markdown(path) for path in ROOT.glob("plugins/_bundled_skills/skills/*/SKILL.md")]
    assert all(candidates)
    monkeypatch.setattr(skills, "list_skills", lambda *args, **kwargs: candidates)
    for query, expected in [
        ("create plugin", "a0-create-plugin"),
        ("publish plugin", "a0-create-plugin"),
        ("review plugin", "a0-create-plugin"),
        ("plugin not loading", "a0-create-plugin"),
        ("recommend plugins", "a0-manage-plugin"),
        ("scan plugin index", "a0-manage-plugin"),
        ("install plugin", "a0-manage-plugin"),
    ]:
        assert skills.search_skills(query, limit=1)[0].name == expected, query
    for retired in ("a0-plugin-router", "a0-contribute-plugin", "a0-review-plugin", "a0-debug-plugin"):
        assert retired not in {skill.name for skill in candidates}
    for name in ("a0-create-plugin", "a0-manage-plugin"):
        folder = ROOT / "plugins" / "_bundled_skills" / "skills" / name
        refs = set(re.findall(r"(?<!/)references/[a-z-]+\.md", (folder / "SKILL.md").read_text()))
        assert refs
        for ref in refs:
            assert (folder / ref).is_file(), ref


def test_index_discovery_example_handles_nulls_and_bounds_output(capsys):
    text = (ROOT / "plugins/_bundled_skills/skills/a0-manage-plugin/references/discovery.md").read_text()
    blocks = re.findall(r"```python\n(.*?)\n```", text, re.S)
    entries = {
        "source_search": {"title": "Source Search", "tags": None, "description": None},
        "web_notes": {"title": None, "description": "Web research", "tags": ["notes"]},
        "calendar": {"title": "Calendar", "tags": None},
        "invalid": None,
    }
    entries.update({f"search_{i}": {"tags": None} for i in range(25)})
    calls = []

    def api(path, payload):
        calls.append((path, payload))
        return {"success": True, "index": {"plugins": entries}, "installed_plugins": ["source_search"]}

    namespace = {"api": api}
    for block in blocks:
        exec(compile(block, "discovery.md", "exec"), namespace)
    assert calls == [("plugins/_plugin_installer/plugin_install", {"action": "fetch_index"})]
    matches = namespace["matches"]
    assert len(matches) == 27
    assert matches[0]["installed"] is True
    assert matches[1]["title"] == "web_notes"
    assert "calendar" not in {entry["id"] for entry in matches}
    assert "search_24" not in capsys.readouterr().out
