# Behavior Adjustment Plugin DOX

## Purpose

- Own the `behavior_adjustment` tool and the behavior rules system-prompt injection.

## Ownership

- `tools/behavior_adjustment.py` owns ruleset merge, normalization, and persistence.
- The tool logs its message as type `behavior_adjustment` with an `icon://psychology Adjusting behavior` headline; `extensions/webui/get_message_handler/` owns the `BEH` badge presentation and `extensions/webui/get_process_step_types/` registers the type.
- `extensions/python/system_prompt/_20_behavior_prompt.py` owns rules injection at the front of the system prompt.
- `prompts/` owns the tool prompt, default ruleset, merge templates, update confirmation, and the rules system fragment.
- `plugin.yaml` and `README.md` own metadata and docs.

## Local Contracts

- Rules persist at `behavior.md` inside the memory subdirectory resolved by `plugins._memory.helpers.memory`; the cross-plugin import is intentional and matches the bundled cross-plugin helper precedent.
- `normalize_ruleset` strips code fences and `!!!` markers, splits glued headings, dedupes structural lines case-insensitively, and collapses blank runs.
- The system-prompt extension inserts at index 0; extension ordering by filename keeps this plugin's `_20_` file stable.

## Work Guidance

- Keep behavioral rules durable, merged, and free of duplicates; the utility model owns merging, the tool owns persistence.
- Coordinate prompt changes between the tool prompt and the merge templates.
- Rules files are plugin-owned state; never edit them by hand outside the tool flow.

## Verification

- Import the tool in the framework runtime and run the behavior contract tests after changes.

## Child DOX Index

No child DOX files.
