# Operate Agent Zero

Agent Zero can use its own HTTP API to operate existing application features for the user: create and manage projects, create chats, select profiles, start work, manage scheduled tasks, and use plugin features. A request such as "create a project and start a research chat in it" can be completed directly through these APIs.

Use an available agent tool when it already handles the requested operation, such as scheduling. Use the application API for administration or features without a suitable tool. Follow the user's requested scope and existing permissions; an HTTP route is not a way around blocked capabilities. Routine steps needed for an authorized outcome do not need separate confirmation.

Compose existing features to complete the outcome: a research workspace can combine project instructions, a Researcher chat, and a saved recurring task; a new custom profile can be created through Agent Editor, selected in a fresh chat, and given its assignment. Persist the returned IDs, verify each transition, and start execution only when the requested outcome includes it.

## Source Anchors

- Routing/auth/CSRF: `/a0/helpers/api.py`, `/a0/helpers/ui_server.py`, `/a0/api/csrf_token.py`.
- Projects: `/a0/api/projects.py`, `/a0/helpers/projects.py`.
- Chats: `/a0/api/chat_create.py`, `/a0/api/agent_profile_set.py`, `/a0/api/poll.py`, `/a0/helpers/state_snapshot.py`.
- Starting work: `/a0/api/message.py`, `/a0/api/message_async.py`, `/a0/api/api_message.py`.
- Tasks: `/a0/api/scheduler_task_create.py`, `/a0/api/scheduler_task_update.py`, `/a0/helpers/task_scheduler.py`.
- Other routes: `/a0/api/` and `/a0/plugins/<plugin>/api/`; inspect each handler and its nearest DOX before unfamiliar operations.

## Connect To The Correct Instance

Discover the origin from the running instance, Docker mapping, or explicit configuration. From a container, `localhost` means that container, not the user's host. Do not assume the host-published port is also the internal port. See `architecture-runtime.md`.

Most WebUI endpoints require a session and CSRF token, even for POST requests that only read data:

1. Reuse an authorized authenticated session. If login is enabled, the normal login is form POST `/login` with `username` and `password`; use configured or user-authorized credentials and retain the session cookies.
2. GET `/api/csrf_token` from the same origin and cookie jar. From a terminal client, include `Origin` or `Referer`.
3. Retain the returned cookies and send the returned `token` as `X-CSRF-Token` on subsequent requests.
4. Keep credentials, tokens, session cookies, and returned secret/configuration fields out of chat and logs.

With login disabled, session cookies and CSRF are still required for protected routes. A successful HTTP response containing the login HTML is not an API success. Keep authentication and CSRF enabled.

This standard-library client works with a session cookie jar. Set `A0_WEBUI_ORIGIN` to the verified origin; authenticate the same client before fetching CSRF if login is enabled.

```python
import http.cookiejar
import json
import os
import urllib.request

origin = os.environ["A0_WEBUI_ORIGIN"].rstrip("/")
cookies = http.cookiejar.CookieJar()
client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
csrf = None

def api(path, payload=None):
    headers = {"Origin": origin, "Content-Type": "application/json"}
    if csrf:
        headers["X-CSRF-Token"] = csrf
    request = urllib.request.Request(
        origin + "/api/" + path,
        data=None if payload is None else json.dumps(payload).encode(),
        headers=headers,
    )
    with client.open(request, timeout=30) as response:
        if response.headers.get_content_type() != "application/json":
            raise RuntimeError("Expected JSON; check origin and session login")
        result = json.load(response)
    if result.get("ok") is False or result.get("success") is False or result.get("error"):
        raise RuntimeError("API operation failed; inspect its error privately")
    return result

csrf = api("csrf_token")["token"]
```

HTTP errors raise exceptions. Some handlers return HTTP 200 with an `error` or `ok: false`; check the body too. Others return data without an `ok` field. After a timeout, inspect state before retrying a create or start request: the server may already have accepted it.

## Identify Scope Before Acting

Use `POST /api/poll` with `{}` to discover `contexts` and `tasks`. Context records include `id`, `name`, `project`, `agent_profile`, `running`, and `paused`. Match the requested target or use an ID returned by your own earlier call. Do not assume the newest chat is the current/user-requested chat. If the target remains ambiguous, clarify it.

A separate shell Python process does not share the WebUI process's in-memory `AgentContext` objects. Importing `AgentContext` there is not a substitute for HTTP calls to the running server.

IDs are not interchangeable:

| Operation | Request ID field | Returned identity |
|---|---|---|
| `chat_create` | Optional `new_context`, `current_context` | `ctxid` |
| `projects` activate/deactivate | `context_id`; activate also needs project `name` | Verify through `poll` |
| `agent_profile_set` | `context_id`, `agent_profile` | `agent_profile` |
| `message_async`, `poll`, `history_get`, `pause`, `stop`, `chat_remove` | `context` | Context-dependent response |
| `chat_export` | `ctxid` | `ctxid`, `content` |
| `scheduler_task_update`, `scheduler_task_run`, `scheduler_task_delete` | `task_id` | Use `task.uuid` from creation/listing |

## Projects And Chats

Creating a project creates its workspace and metadata. Activating it assigns that project to a particular chat. There is no single global "active project" for every chat.

Project operations use POST `/api/projects`:

| `action` | Other fields | Purpose |
|---|---|---|
| `list`, `list_options` | None | Discover project names/titles |
| `load` | `name` | Read editable project data |
| `create` | `project` object with `name`, title/instructions as needed | Create workspace |
| `clone` | `project` with `name`, `git_url`, optional `git_token` | Clone a repository as a project |
| `update` | `project` with existing `name` and edits | Update project metadata/instructions |
| `activate` | `context_id`, `name` | Assign project to chat |
| `deactivate` | `context_id` | Clear chat's project assignment |
| `file_structure` | `name`, optional `settings` | Inspect project tree |
| `delete` | `name` | Delete project files and detach its chats |

List before create; reuse a matching project when that is what the user wants. Choose a fresh, simple directory name for a new project. Load before updates and preserve unrelated fields, especially variables, secrets, MCP settings, and plugin-owned metadata. Do not print a whole loaded project object.

Example: ensure a project exists, then create an idle chat in it. Replace the illustrative name/title/instructions with the requested values.

```python
name = "research-workspace"
existing = api("projects", {"action": "list"})["data"]
if not any(project["name"] == name for project in existing):
    created = api("projects", {
        "action": "create",
        "project": {"name": name, "title": "Research Workspace",
                    "description": "Research and source notes",
                    "instructions": "Cite sources and distinguish evidence from inference."},
    })
    name = created["data"]["name"]

ctxid = api("chat_create", {})["ctxid"]
api("projects", {"action": "activate", "context_id": ctxid, "name": name})
snapshot = api("poll", {"context": ctxid, "log_from": 0, "notifications_from": 0})
chat = next(item for item in snapshot["contexts"] if item["id"] == ctxid)
assert chat["project"]["name"] == name
```

`chat_create` can inherit project and model override from `current_context`, subject to settings. Omit that field for an independent chat; activate the intended project explicitly. `new_context` may supply a fresh ID, but reusing an existing ID does not guarantee a new chat. Creation alone does not run a model or guarantee that the user's currently selected browser tab switches to it.

For a specialized chat, list available profiles and then call:

```python
api("agent_profile_set", {"context_id": ctxid, "agent_profile": "researcher"})
```

Use an available profile ID in that project's scope and verify `agent_profile` through `poll`. The endpoint rejects profile changes while a chat is running. Creating a profile and selecting it for a chat are separate operations.

## Start, Observe, And Control Chat Work

- `POST /api/message_async` with `{"context": ctxid, "text": "<assigned work>"}` starts processing and returns acceptance plus `context`; it does not return task completion.
- `POST /api/message` uses the same payload but waits for the model result. Do not synchronously call it against the same chat that is making the request.
- Poll the target with `context`, `log_from`, and `notifications_from`; inspect its `running` state and logs, then use `history_get` or `chat_export` for results. Reset cursors when log/notification GUIDs change. Use bounded polling rather than a tight loop.
- `pause` uses `{"context": ctxid, "paused": true}`; `false` resumes. `stop` terminates the current run. `chat_reset` resets the conversation; `chat_remove` deletes it and can remove tasks bound to that context.
- Message queue endpoints (`message_queue_add`, `message_queue_remove`, `message_queue_send`) support follow-ups. Inspect their handlers before use; queued messages may later be consumed by the running agent.

Starting a chat run or manually running a saved task consumes model resources and may execute tools. Do it when requested or needed for the user's assigned outcome, not as a side effect of merely creating or inspecting a chat. Send independent work to another chat and avoid recursive delegation back to the caller.

The external API is a different contract: `POST /api/api_message` uses `X-API-KEY` with `message`, optional `context_id`, `project_name`, `agent_profile`, and attachments. It waits for a result and returns `context_id`/`response`. Its project/profile options apply when creating a context; it is not the general WebUI session API. Check `/a0/api/api_message.py` rather than mixing its fields with `message_async`.

## Saved Tasks And Schedules

Prefer the `scheduler` tool when available; load `scheduled-tasks` for detailed scheduling. The HTTP API also manages the same saved tasks, including a project association selected at creation.

- List: POST `scheduler_tasks_list` with `{}`; result is `tasks`.
- Create: POST `scheduler_task_create` with `name`, `prompt`, optional `system_prompt`, `attachments`, and `project_name`.
- Type is selected by payload: a nonempty `schedule` creates a recurring task; otherwise a nonempty `plan` creates a planned task; neither creates an adhoc task. Do not send both.
- Recurring `schedule` is an object with cron strings `minute`, `hour`, `day`, `month`, `weekday`, plus an IANA `timezone`. Use the user's intended timezone.
- HTTP planned shape is `{"plan": {"todo": ["<future ISO datetime with UTC offset>"]}}`, not the scheduler tool's list shorthand. Verify returned planned dates.
- Update: POST `scheduler_task_update` with `task_id` and changed fields such as `name`, `prompt`, `schedule`, `plan`, or `state`. `state: "disabled"` disables; `state: "idle"` re-enables.
- Run now: POST `scheduler_task_run` with `task_id`. Acceptance is not completion; check the returned task and later list state/results.
- Delete: POST `scheduler_task_delete` with `task_id`. This also handles a running task and its dedicated context.

Creation uses a dedicated context; `project_name` cannot be changed through the update endpoint. Top-level `timezone` also updates runtime localization, so use explicit planned offsets or `schedule.timezone` when that is the intended scope. Do not copy tool-only fields such as `dedicated_context` into HTTP payloads and assume they are honored.

For a saved draft that must not run automatically, create an adhoc task and disable it:

```python
task = api("scheduler_task_create", {
    "name": "Research draft", "prompt": "<work to run when requested>",
    "project_name": name,
})["task"]
task_id = task["uuid"]
api("scheduler_task_update", {"task_id": task_id, "state": "disabled"})
saved = next(t for t in api("scheduler_tasks_list", {})["tasks"] if t["uuid"] == task_id)
assert saved["state"] == "disabled"
```

Do not use a due recurring schedule as a draft and hope to disable it before execution. Do not reset/delete the caller's own active chat to manage another task.

## Other Application Features

These are discovery starting points, not interchangeable payloads. Read the handler and the corresponding skill before changing state. Plugin routes depend on the plugin being enabled.

| Feature | API entry point | Guidance |
|---|---|---|
| Profile catalog and editor | `agents` (`action: list`); `plugins/_agent_editor/agent_editor` | Editor supports scoped list/load, quick_create, plan/save and lifecycle operations. Inspect its plan before applying complex edits. Use `a0-create-agent` for creation. |
| Skills | `skills`; `plugins/_skills/skills_catalog` | Catalog manages per-chat visibility and activation. Loading adds instructions to history; hiding is not unloading, and deactivate/clear are rejected. |
| Slash commands | `plugins/_commands/commands` | List effective commands by `context_id`; get/save/duplicate/delete in the intended scope. Use `commands-create-slash-command`. |
| Plugins | `plugins_list`, `plugins` | Inspect configuration and activation by plugin/project/profile. Use `a0-manage-plugin`; plugin execution/install/removal has wider effects than reading configuration. |
| Files | `get_work_dir_files`, `edit_work_dir_file`, upload/download/rename endpoints | Several reads use GET/query parameters; uploads use multipart. Use the appropriate file/Office tool when available. |
| Settings and MCP | `settings_get`, `settings_set`, `mcp_servers_status`, `mcp_servers_apply` | Scope changes carefully; preserve unowned settings and secrets. Do not treat a global settings update as a chat-only change. |
| Backups and updates | `backup_*`, `self_update_*`, `restart` | Inspect previews/defaults and source contracts. Restore, restart and self-update can disrupt other work; perform only for the requested maintenance outcome. |
| Notifications | `notification_create`, `notifications_history`, `notifications_mark_read` | Use the notification tool when available; avoid clearing other notifications as cleanup. |

For a feature not listed here, find the WebUI's actual request and read the matching handler. Do not guess routes from button labels or emulate state by editing scheduler/chat/project storage behind the running server.

## Verify And Report

Check the returned identity and read back the actual state: project name, chat project/profile, task UUID/state, or saved feature configuration. Distinguish created, activated, started, completed, and visible in the user's selected UI. Report what happened and provide the relevant names/IDs without dumping private state.

For smoke tests, use unique disposable records, avoid model execution unless required, and delete only records created by the test. Verify cleanup through the same listing endpoints. A successful CRUD test does not prove a model run, scheduled execution, external integration, or every listed feature works.
