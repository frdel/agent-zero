"""Recovery of completed provider-hosted operations from normalized outcomes."""

# These are provider results, not instructions for a local tool or connector.
# Unknown/native action item types must use their own execution boundary.
COMPLETED_TYPES = frozenset({"web_search_call", "file_search_call", "code_interpreter_call",
                             "image_generation_call", "mcp_call"})
TERMINAL_STATUSES = frozenset({"completed", "failed"})


def validate(result):
    from helpers.durable.runtime import RecoveryHeld
    for item in result.builtin_items:
        if item.type in {"computer_call", "mcp_approval_request"}:
            continue  # Local actions use ordinary tool receipts; approval stays denied.
        if item.type not in COMPLETED_TYPES or item.data.get("status") not in TERMINAL_STATUSES:
            raise RecoveryHeld("provider_builtin_request_requires_reconciliation")


def log_id(turn, index):
    return f"{turn.run_id}:{turn.agent.loop_data.iteration}:hosted:{index}"
