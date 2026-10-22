"""Explicit built-in execution adapters; unknown effects never gain replay rights."""
from helpers.durable import execution, sessions


def implementation(tool, args):
    for module in (execution, sessions):
        if module.supports(tool, args):
            return module
    return None
