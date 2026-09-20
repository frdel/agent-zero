# Scheduled Tasks Skill DOX

## Purpose

- Own the workflow for managing Agent Zero scheduled, planned, and adhoc tasks.
- Keep scheduler tool usage and date/time guidance accurate.

## Ownership

- `SKILL.md` owns scheduler action descriptions, schedule field guidance, safety rules, and examples.

## Local Contracts

- Inspect existing tasks before create, update, delete, or run operations.
- Use cron-like `schedule` fields for recurring tasks and ISO datetimes in `plan` for planned tasks.
- Do not create recursive scheduling prompts or run scheduled tasks unless the user asks.

## Work Guidance

- Update this skill when scheduler tool actions, field names, or timezone behavior changes.
- Keep examples valid JSON tool arguments.

## Verification

- Manually read `SKILL.md` for stale scheduler action names and date guidance.

## Child DOX Index

No child DOX files.
