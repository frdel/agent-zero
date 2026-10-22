# Infection Check Plugin DOX

## Purpose

- Own prompt-injection safety checks over streamed reasoning/response content before tool execution.

## Ownership

- `helpers/checker.py` owns safety analysis orchestration and gate behavior.
- `extensions/` owns stream collection and tool-execution blocking hooks.
- `default_config.yaml`, `plugin.yaml`, `README.md`, and `webui/` own settings, metadata, behavior notes, and config UI.

## Local Contracts

- Preserve configured `thoughts` and `complete` analysis modes.
- Tool execution must wait for required safety verdicts.
- Shared durability mode stores exact background inference references and frozen clarification rounds. A detached broker may finish after framework-worker death; a lost broker with an unknown verdict holds the tool gate. Do not cancel that observer and issue a fresh safety request or treat interruption as approval. Only known verdicts may advance clarification or mark a tool passed.
- Do not log or expose chain-of-thought or sensitive prompt content beyond intended warning flows.

## Work Guidance

- Keep termination and clarification loops bounded and explicit.

## Verification

- Smoke-test ok, clarify, and terminate verdicts around tool execution after changes.

## Child DOX Index

No child DOX files.
