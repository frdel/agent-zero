# Contribute A Plugin

Use after the user has chosen community contribution. If local versus community is still unclear, ask before preparing publication. Respect an existing publication request; do not repeat consent questions for each routine step. If only preparation was requested, prepare reviewable files and leave external publication pending.

## Two Repositories, Two Manifests

| Artifact | Location | Purpose |
|---|---|---|
| Plugin implementation and `plugin.yaml` | Plugin's own repository root | Installed runtime code |
| `index.yaml` and optional thumbnail | `agent0ai/a0-plugins/plugins/<name>/` | Discovery entry pointing to that repository |

The plugin contents must be at its repository root, not inside a nested plugin folder. Keep README, LICENSE, manifest and implementation together. Do not submit runtime code, credentials, configs, caches or user data to the Index repository.

Authoritative sources:
- [Plugin Index README and submission rules](https://github.com/agent0ai/a0-plugins)
- [Recommended tags](https://github.com/agent0ai/a0-plugins/blob/main/TAGS.md)
- `scripts/validate_plugin_submission.py` in a current Index checkout
- `/a0/plugins/AGENTS.md` and this skill's `review.md`

Check the current rules before submission; copied limits and examples can age.

## Prepare And Verify The Plugin

1. Complete the requested feature and review it using `review.md`. Verify the intended live runtime and retain evidence.
2. Resolve repository owner/name and public visibility from the user's instructions; ask only for a missing decision. Use an existing repository when appropriate.
3. Keep `plugin.yaml:name`, the runtime folder name and Index folder name identical. Community names use `^[a-z0-9_]+$` and cannot start with `_`.
4. Include a root LICENSE and a README covering purpose, installation, configuration, external services/costs, usage and cleanup. Capture relevant screenshots without private data.
5. Stage only plugin source. Inspect the actual diff, branch and remote before committing or pushing within the user's authorization. Use real subject/body paragraphs, not literal backslash-n sequences.
6. Verify the published repository's default branch has the expected root `plugin.yaml`, matching name and LICENSE. Do not assume the default branch is `main`.

Local plugin metadata does not prove that the public repository contains the same version. Verify remote contents before making the Index entry.

## Prepare The Index Entry

Fetch the current generated Index through the discovery workflow in `a0-manage-plugin`. Check both the intended folder name and canonical repository URL. If this plugin is already listed, update its existing entry rather than creating a duplicate. Compare related plugins and describe what this one adds.

Use a current fork/checkout of `agent0ai/a0-plugins`, with a branch for this plugin only. A new submission adds `plugins/<name>/index.yaml`:

```yaml
title: My Plugin
description: What this plugin lets the user do.
github: https://github.com/OWNER/REPOSITORY
tags:
  - tools
  - workflow
```

Optional `screenshots` are full reachable image URLs. An optional square thumbnail belongs beside `index.yaml`, not inside a new assets folder. Check current allowed formats and size limits.

Current baseline constraints to recheck against the validator:
- Required: `title`, `description`, `github`; optional: `tags`, `screenshots`.
- Title up to 50 characters; description up to 500; complete `index.yaml` up to 2000.
- Up to five tags and five screenshots; screenshots up to 2 MB each.
- Thumbnail at most 20 KB, square, named `thumbnail` with an allowed PNG/JPEG/WebP extension.
- Only the entry and optional thumbnail in the plugin's Index folder; no runtime `plugin.yaml` there.

## Validate And Submit

1. Inspect the Index diff and ensure it contains only this plugin's entry/assets.
2. Ensure the validator has a current generated Index snapshot for duplicate checks; use the Index repository's download script when needed.
3. The validator reads a committed Git range. After the authorized commit, set `BASE_SHA` to the intended upstream base and `HEAD_SHA` to the submission commit, then run the current `scripts/validate_plugin_submission.py`. Inspect its workflow for any other required inputs; `PR_AUTHOR` and GitHub authentication can affect checks.
4. Resolve actual validator failures rather than guessing from old examples. Verify the remote manifest name and public asset URLs.
5. Push the intended branch and create the Index PR within the user's publication authorization. Use a temporary body file with `gh pr create --body-file` for multiline text.
6. Read back the PR URL, diff and CI results. Fix submission failures, and report whether it is pending review or actually merged.

Creating the plugin repository, submitting the Index PR, passing CI and merging are distinct results. Do not describe a plugin as available in the Plugin Hub until the generated Index contains it.
