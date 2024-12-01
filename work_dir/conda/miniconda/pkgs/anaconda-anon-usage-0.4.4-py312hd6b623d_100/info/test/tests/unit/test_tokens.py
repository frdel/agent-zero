from os.path import exists

from anaconda_anon_usage import tokens, utils


def test_client_token(aau_token_path):
    assert not exists(aau_token_path)
    assert tokens.client_token() != ""
    assert exists(aau_token_path)


def test_environment_token_without_monkey_patching():
    assert tokens.environment_token() is not None


def test_environment_token_with_target_prefix(tmpdir):
    prefix_token = tokens.environment_token(prefix=tmpdir)
    assert prefix_token is not None
    assert prefix_token != tokens.environment_token()


def test_token_string():
    token_string = tokens.token_string()
    assert "aau/" in token_string
    assert "c/" in token_string
    assert "s/" in token_string
    assert "e/" in token_string


def test_token_string_disabled():
    token_string = tokens.token_string(enabled=False)
    assert "aau/" in token_string
    assert "c/" not in token_string
    assert "s/" not in token_string
    assert "e/" not in token_string


def test_token_string_no_client_token(monkeypatch):
    monkeypatch.setattr(tokens, "environment_token", lambda prefix: "env_token")
    monkeypatch.setattr(tokens, "_saved_token", lambda fpath, what: "")

    token_string = tokens.token_string()
    assert "c/" not in token_string
    assert "s/" in token_string
    assert "e/env_token" in token_string


def test_token_string_no_environment_token(
    monkeypatch,
):
    monkeypatch.setattr(tokens, "environment_token", lambda prefix: "")

    token_string = tokens.token_string()
    assert "c/" in token_string
    assert "s/" in token_string
    assert "e/" not in token_string


def test_token_string_full_readonly(monkeypatch):
    monkeypatch.setattr(utils, "READ_CHAOS", "ce")
    monkeypatch.setattr(utils, "WRITE_CHAOS", "ce")
    token_string = tokens.token_string()
    assert "c/" not in token_string
    assert "s/" in token_string
    assert "e/" not in token_string


def test_token_string_env_readonly(monkeypatch):
    monkeypatch.setattr(utils, "READ_CHAOS", "e")
    monkeypatch.setattr(utils, "WRITE_CHAOS", "e")

    token_string = tokens.token_string()
    assert "c/" in token_string
    assert "s/" in token_string
    assert "e/" not in token_string
