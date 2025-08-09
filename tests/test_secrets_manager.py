import re
import pytest

from python.helpers import runtime
from python.helpers.secrets import SecretsManager
from python.helpers.rfc_files import file_exists


@pytest.fixture()
def secrets_manager_tmp(monkeypatch):
    # Run RFC file ops locally
    monkeypatch.setattr(runtime, "is_development", lambda: False)

    # Fresh singleton
    SecretsManager._instance = None  # type: ignore[attr-defined]
    mgr = SecretsManager.get_instance()

    # Use a test-specific secrets file
    mgr.set_secrets_file("tmp/tests_secrets.env")

    # Cleanup before/after
    if file_exists(mgr.SECRETS_FILE):
        mgr.save_secrets("")
    yield mgr
    if file_exists(mgr.SECRETS_FILE):
        mgr.save_secrets("")


def test_merge_preserve_comments_keep_update_delete_new(secrets_manager_tmp: SecretsManager):
    mgr = secrets_manager_tmp

    existing = (
        "# Top comment\n"
        "\n"
        "KEY1=old1\n"
        "# Inline comment for key2\n"
        "KEY2=old2\n"
        "SOME=\"with spaces\"\n"
        "OTHER='single quotes'\n"
        "# Tail comment\n"
    )

    mgr.save_secrets(existing)

    # Submitted content: keep KEY1 (masked), update KEY2, add NEWKEY, delete SOME and OTHER by omission
    submitted = (
        "# Submitted header (should not appear because we preserve existing order)\n"
        "KEY1=***\n"
        "KEY2=new2\n"
        "NEWKEY=newv\n"
    )

    mgr.save_secrets_with_merge(submitted)

    merged_text = mgr.read_secrets_raw()

    # Comments from existing preserved
    assert "# Top comment" in merged_text
    assert "# Inline comment for key2" in merged_text
    assert "# Tail comment" in merged_text

    # KEY1 kept old value
    assert re.search(r"^\s*KEY1\s*=\s*old1\s*$", merged_text, re.MULTILINE)
    # KEY2 updated
    assert re.search(r"^\s*KEY2\s*=\s*new2\s*$", merged_text, re.MULTILINE)
    # New key appended
    assert re.search(r"^\s*NEWKEY\s*=\s*newv\s*$", merged_text, re.MULTILINE)
    # Deleted keys not present
    assert "SOME=" not in merged_text
    assert "OTHER=" not in merged_text

    # Dict load reflects final values
    secrets = mgr.load_secrets()
    assert secrets.get("KEY1") == "old1"
    assert secrets.get("KEY2") == "new2"
    assert secrets.get("NEWKEY") == "newv"
    assert "SOME" not in secrets and "OTHER" not in secrets


def test_masking_functions(secrets_manager_tmp: SecretsManager):
    mgr = secrets_manager_tmp

    mgr.save_secrets("API_TOKEN=abc123\nDB_PASS=super-secret\n")

    # Mask values in arbitrary text
    text = "use abc123 and then super-secret please"
    masked = mgr.mask_values(text)
    assert "abc123" not in masked and "super-secret" not in masked
    assert "§§API_TOKEN§§" in masked and "§§DB_PASS§§" in masked

    # Masked content preserves comments and masks only values
    content = "# c\nAPI_TOKEN=abc123\nX=\nDB_PASS=super-secret\n"
    masked_content = mgr.get_masked_content(content)
    assert "# c" in masked_content
    assert re.search(r"^API_TOKEN\s*=\s*\*\*\*$", masked_content, re.MULTILINE)
    assert re.search(r"^DB_PASS\s*=\s*\*\*\*$", masked_content, re.MULTILINE)
    # Empty values remain empty
    assert re.search(r"^X\s*=\s*$", masked_content, re.MULTILINE)

    # Placeholder replacement
    replaced = mgr.replace_placeholders("Use §§API_TOKEN§§ now")
    assert replaced == "Use abc123 now"


def test_streaming_full_secret_spanning_chunks(secrets_manager_tmp: SecretsManager):
    mgr = secrets_manager_tmp
    # Set a predictable secret value
    mgr.save_secrets("DB_PASS=supersecret\n")

    filt = mgr.create_streaming_filter()

    chunks = ["Start ", "sup", "erse", "cret", " end"]
    emitted = [filt.process_chunk(ch) for ch in chunks]
    tail = filt.finalize()

    combined = "".join(emitted) + tail

    # Raw secret should never appear in any emitted part nor tail
    assert all("supersecret" not in part for part in emitted)
    assert "supersecret" not in tail

    # Should produce placeholder once secret completes across chunks
    assert combined == "Start §§DB_PASS§§ end"


def test_streaming_unresolved_partial_masked_on_finalize(secrets_manager_tmp: SecretsManager):
    mgr = secrets_manager_tmp
    mgr.save_secrets("DB_PASS=supersecret\n")

    filt = mgr.create_streaming_filter()

    e1 = filt.process_chunk("foo ")
    e2 = filt.process_chunk("sup")  # prefix of secret, should be held
    tail = filt.finalize()

    # First emission is safe content, second emission should be empty (held)
    assert e1 == "foo "
    assert e2 == ""
    # Finalize should mask the unresolved partial with ***
    assert tail == "***"
    assert "sup" not in (e1 + e2 + tail)
