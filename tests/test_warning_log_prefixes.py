from pathlib import Path

_FILES = [
    "agent.py",
    "extensions/python/message_loop_result/_05_truncated_response.py",
    "extensions/python/message_loop_result/_20_empty_response.py",
    "extensions/python/message_loop_result/_30_repeat_response.py",
    "plugins/_context_doctor/extensions/python/message_loop_result/_10_context_doctor.py",
]


def test_warning_log_rows_have_no_agent_prefix():
    root = Path(__file__).resolve().parents[1]
    for name in _FILES:
        lines = (root / name).read_text().splitlines()
        for index, line in enumerate(lines):
            if 'type="warning"' not in line:
                continue
            span = lines[index : index + 6]
            for entry in span:
                assert "agent_name}" not in entry, f"{name}:{index + 1} keeps an agent prefix"
