# DOX Workflow

## Source Anchors

- Root DOX contract: `/a0/AGENTS.md`
- Skill parent contract: `/a0/plugins/_skills/skills/AGENTS.md`
- Local skill contract: `/a0/plugins/_skills/skills/a0-development/AGENTS.md`
- Reference-file contract: `/a0/plugins/_skills/skills/a0-development/references/AGENTS.md`
- File-level DOX examples: `/a0/api/*.py.dox.md`, `/a0/tools/*.py.dox.md`, `/a0/helpers/*.py.dox.md`

## Before Editing

1. Read the root `AGENTS.md`.
2. Identify every path you expect to touch.
3. Walk from the root to each target path.
4. Read every `AGENTS.md` found on that route.
5. If a parent `AGENTS.md` lists a child whose scope contains the path, read that child and continue.
6. Use the nearest `AGENTS.md` as the local contract. Parent docs still apply.
7. If docs conflict, the closer doc controls local details, but no child weakens DOX.

Do not rely on memory for DOX. Re-read the current files.

## When To Update DOX

Update the nearest owning `AGENTS.md` when a meaningful change affects:

- Purpose, ownership, responsibilities, or scope.
- Durable structure, directories, file contracts, or child indexes.
- Runtime behavior, required inputs/outputs, side effects, or verification rules.
- User or agent workflow rules.
- Creation, deletion, rename, or movement of an `AGENTS.md` file.

Update parent docs when parent-level structure or child indexes change. Remove stale or contradictory text rather than explaining old history.

Small implementation edits that do not change contracts may leave DOX unchanged, but still perform the DOX closeout pass and say why docs stayed unchanged.

Do not create or update DOX under ignored `usr/` or `tmp/` unless explicitly requested.

## File-Level DOX

Some directories require per-file `.dox.md` companions:

| Directory | Requirement |
|---|---|
| `api/` | Every direct `*.py` endpoint or `ws_*.py` module must have matching `*.py.dox.md`. |
| `tools/` | Every direct `*.py` tool module must have matching `*.py.dox.md`. |
| `helpers/` | Many helper modules use file-level DOX; follow `helpers/AGENTS.md` before changing helper behavior. |

When adding, deleting, renaming, or behaviorally changing one of those files, update the companion DOX in the same change.

## Closeout

1. Re-check changed paths against the DOX chain.
2. Update nearest owning docs and affected parents or children.
3. Refresh affected Child DOX Index tables.
4. Remove stale or contradictory text.
5. Run relevant verification from the nearest DOX.
6. Report docs intentionally left unchanged and why.

## Practical Verification

- `git diff --check` for whitespace.
- Targeted tests named by the relevant DOX file.
- Manual read-through for skill/reference link changes.
- Shell coverage checks for file-level DOX when touching `api/` or `tools/`.
- Runtime or live-container proof when the user asks about the running Dockerized system.
