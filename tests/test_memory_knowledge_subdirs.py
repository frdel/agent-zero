from helpers import projects
from plugins._memory.helpers.memory import get_knowledge_subdirs_by_memory_subdir


def test_project_knowledge_is_not_added_to_the_configured_subdirs(monkeypatch):
    monkeypatch.setattr(
        projects, "get_project_meta", lambda name, *sub: f"/projects/{name}/knowledge"
    )
    configured = ["default", "custom"]

    alpha = get_knowledge_subdirs_by_memory_subdir("projects/alpha", configured)
    beta = get_knowledge_subdirs_by_memory_subdir("projects/beta", configured)
    default = get_knowledge_subdirs_by_memory_subdir("default", configured)

    assert alpha == ["default", "custom", "/projects/alpha/knowledge"]
    assert beta == ["default", "custom", "/projects/beta/knowledge"]
    assert default == ["default", "custom"]
    assert configured == ["default", "custom"]
