---
name: build-skill
description: "Create, rename, move, audit, test or refine Agent Zero skills and reusable workflows."
---

# Build Skill

Skills are small folders that teach Agent Zero a repeatable workflow. Keep the always-visible metadata precise, keep `SKILL.md` lean, and move detailed material into scripts, references, or assets only when the task needs it.

## Standard Shape

Every skill folder must be named exactly like the skill and contain `SKILL.md`.

```text
skill-name/
├── SKILL.md
├── scripts/      # optional deterministic helpers
├── references/   # optional details loaded only when needed
└── assets/       # optional output resources or templates
```

The frontmatter should contain `name`, `description`, and optional `triggers` when lexical discovery needs phrases that do not fit naturally in the description:

```yaml
---
name: skill-name
description: What the skill does and when to use it.
triggers:
  - "user phrase that should surface this skill"
---
```

Use lowercase letters, digits, and hyphens. Prefer short verb-led names such as `build-skill`, `review-plugin`, or `host-file-editing`.

## Workflow

1. Identify two or three real user requests that should trigger the skill.
2. Decide whether the skill belongs in the bundled `_skills` collection (`plugins/_bundled_skills/skills/`) or inside a specific plugin's `plugins/<plugin>/skills/` directory.
3. Write the frontmatter description with the core trigger condition and key context; add `triggers` for short user phrases that should rank highly in skill search or relevant-skill recall.
4. Keep the body focused on procedure, contracts, failure handling, and the files/scripts to load next.
5. Move long examples, schemas, policies, or variant-specific detail to one-level-deep `references/` files.
6. Add scripts only for deterministic or repeatedly rewritten operations, and test representative scripts.
7. Validate by searching, loading, and using the skill on a median-user prompt.

## Placement

Use plugin-scoped skills when the skill exists to explain a plugin-owned tool or UI surface. Examples: Browser workflows belong under `_browser`; A0 CLI host tools belong under `_a0_connector`; Desktop canvas workflows belong under `_desktop`.

Use the bundled `_skills` collection for Agent Zero framework workflows that are not owned by one plugin, such as building skills, developing core features, or managing community plugins; its skills carry a `/a0/plugins/_bundled_skills/skills/...` runtime path even though they are core-maintained.

## Writing Rules

- Put trigger language in frontmatter, not in a body section. Use `description` for the compact always-visible purpose and `triggers` for phrase matches used by search and relevant-skill recall.
- Do not add README, changelog, quick reference, or install guide files inside the skill.
- Avoid compatibility aliases in prompts or skill bodies when renaming; update references to the new name.
- Prefer concise examples over long prose.
- Do not duplicate the same guidance in both `SKILL.md` and references.
- When multiple skills could apply, keep each skill's responsibility narrow and name the handoff clearly.

## Validation

Run targeted checks after edits:

```bash
conda run -n a0 pytest tests/test_skills_runtime.py tests/test_tool_action_contracts.py -q
```

Also exercise the live path when the skill changes agent-facing tool behavior:

```text
1. Ask a short ordinary prompt that should discover the skill.
2. Confirm the agent uses skills_tool search/load when appropriate.
3. Confirm it calls the intended tool only after the skill is loaded when the tool is skill-gated.
```
