# Behaviour Adjustment Plugin DOX

## Purpose

- Own the `behaviour_adjustment` tool and the behavior rules system-prompt injection.

## Ownership

- `tools/behaviour_adjustment.py` owns ruleset merge, normalization, and persistence.
- `extensions/python/system_prompt/_20_behaviour_prompt.py` owns rules injection at the front of the system prompt.
- `prompts/` owns the tool prompt, default ruleset, merge templates, update confirmation, and the rules system fragment.
- `plugin.yaml` and `README.md` own metadata and docs.

## Local Contracts

- Rules persist at `behaviour.md` inside the memory subdirectory resolved by `plugins._memory.helpers.memory`; the cross-plugin import is intentional and matches the bundled cross-plugin helper precedent.
- `normalize_ruleset` strips code fences and `!!!` markers, splits glued headings, dedupes structural lines case-insensitively, and collapses blank runs.
- The system-prompt extension inserts at index 0; extension ordering by filename keeps this plugin's `_20_` file stable.

## Verification

- Import the tool in the framework runtime and run the behaviour contract tests after changes.

## Child DOX Index

No child DOX files.
