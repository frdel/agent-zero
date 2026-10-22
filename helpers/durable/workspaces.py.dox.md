# Managed workspace adapter

`workspaces.py` captures bounded current project files into immutable encrypted
`ResourceManager` references. Capture returns a versioned manifest without
publishing it; the coordinator owns checkpoint coupling and manifest CAS. The
manifest records the Git revision, dirty/untracked/deleted paths, executable
bits, explicit cache/VCS exclusions and a deterministic content digest. Restored
trees retain revision provenance through `project_override(..., manifest=...)`.

The adapter transfers no Git objects/configuration or archives. Real environment
and credential files, private-key/token patterns, nonempty project connection
configuration, symlinks, hardlinks, special files, Git submodules/conflicts,
changing inputs and excessive counts/sizes produce payload-free `WorkspaceHeld`
reasons. Empty/comment-only environment templates may travel. Safe ignored files
are included so ignored runtime inputs do not silently disappear. Limits are
2000 file/directory entries, 8 MiB per file, 64 MiB total and 32 path components.
Empty directories are retained. Git helper output and runtime are bounded;
external diff/text conversion, hooks and fsmonitor helpers are disabled.

Restore requires a current execution claim and resource encryption key before
filesystem writes. It reserves an absent destination exclusively, builds it with
private files/directories, verifies resource bytes and rechecks ownership before
returning. Existing directories, owner checkouts and unsafe paths are never
merged or replaced. Partial output is removed on failure. Managed directories
are local execution projections; the coordinator owns their lifecycle cleanup.

`project_override(name, path, manifest=None)` redirects matching project lookup
through a ContextVar; unrelated tasks/projects retain ordinary paths. Use it
before project-aware reconstruction/hooks and keep it across the worker turn.
`managed_project(manager, manifest)` restores a fresh per-context `tmp/` directory
and applies that override. Neither helper changes the process working directory.

Run `tests/test_durable_workspaces.py` with the framework runtime. Its optional
disposable PostgreSQL case verifies real encrypted resource custody, publication
CAS and reset fencing; no owner checkout or live provider is used.
