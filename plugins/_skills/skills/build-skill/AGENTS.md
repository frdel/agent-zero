# Build Skill DOX

## Purpose

- Own the workflow for creating, improving, auditing, and refactoring Agent Zero skills.
- Keep skill format guidance aligned with runtime discovery and loading.

## Ownership

- `SKILL.md` owns standard skill shape, writing rules, placement rules, and validation guidance.

## Local Contracts

- Every skill folder must contain `SKILL.md`.
- Keep frontmatter and directory-shape guidance synchronized with skill loader behavior.
- Prefer plugin-scoped skills when the workflow is owned by a plugin.

## Work Guidance

- Update this skill when skill metadata, discovery, or validation behavior changes.
- Keep frontmatter examples aligned with runtime-supported discovery fields such as `triggers`.
- Keep examples concise and avoid duplicating long reference material in the skill body.

## Verification

- Manually read `SKILL.md` for stale test commands and format assumptions.
- Run skill runtime tests when changing skill loader contracts.

## Child DOX Index

No child DOX files.
