from conda.base.context import context

from anaconda_anon_usage import patch


def test_new_user_agent():
    patch.main(plugin=True)
    assert context.user_agent is not None
    for term in ["conda/", "aau/", "e/", "c/", "s/"]:
        assert term in context.user_agent


def test_user_agent_no_token(monkeypatch):
    monkeypatch.setattr(patch, "token_string", lambda prefix: "")
    patch.main(plugin=True)
    assert "conda/" in context.user_agent
    assert "aau/" not in context.user_agent


def test_main_already_patched():
    response = patch.main(plugin=True)
    assert response
    response = patch.main(plugin=True)
    assert not response


def test_main_info():
    patch.main(plugin=True)
    tokens = dict(t.split("/", 1) for t in context.user_agent.split(" "))
    tokens["c"] = tokens["e"] = tokens["s"] = "."
    from conda.cli import main_info

    info_dict = main_info.get_info_dict()
    assert info_dict["user_agent"] == context.user_agent
    info_str = main_info.get_main_info_str(info_dict)
    ua_strs = [
        x.strip().split(" : ", 1)[-1]
        for x in info_str.splitlines()
        if x.lstrip().startswith("user-agent : ")
    ]
    assert ua_strs
    token2 = dict(t.split("/", 1) for t in ua_strs[0].split(" "))
    assert token2 == tokens
