# Slash Commands In Channel Integrations

Use this reference when adding Agent Zero commands to a chat transport. Reuse the command catalog and resolver; keep channel authentication, conversation binding, menus, and delivery in your plugin.

Access to the catalog does **not** automatically implement every command's channel behavior. A command returns text and/or effects, and a script can change state during resolution. Your adapter must handle those effects and report platform limits honestly.

## Source Owners And Runtime Requirement

- [Commands helper](../../../plugins/_commands/helpers/commands.py): `list_context_commands`, `parse_slash_invocation`, `resolve_command_invocation`, scope precedence, template rendering, and script execution.
- [Bundled commands](../../../plugins/_commands/commands/connector_commands.py): existing operations and effect producers, including `/stop`.
- [Integration controls](../../../helpers/integration_commands.py): a smaller fixed registry of transport controls and aliases. It is not the full command catalog.
- [Telegram adapter](../../../plugins/_telegram_integration/helpers/slash_commands.py) and [settings menus](../../../plugins/_telegram_integration/helpers/settings_ui.py): inline menus and channel effect handling.
- [WhatsApp adapter](../../../plugins/_whatsapp_integration/helpers/slash_commands.py) and [message handler](../../../plugins/_whatsapp_integration/helpers/handler.py): text menus, confirmed compaction, attachments, and persisted chat selection.
- [Backend command hook](../../../plugins/_commands/extensions/python/_functions/agent/AgentContext/_process_chain/start/_10_resolve_slash_command.py): automatic resolution when a message reaches `AgentContext._process_chain`.

Run these Python APIs inside the Agent Zero **framework process**, where the channel's registered `AgentContext` exists. Importing them in an unrelated bot process does not connect that process to the live context registry. Keep a separately hosted bot's integration entry point authenticated and resolve commands on the Agent Zero side.

This guide targets a runtime with `commands.list_context_commands`. Verify that API exists on the actual installation before declaring compatibility; do not assume a release number. On older installations, require a compatible core or implement and test an explicitly scoped compatibility path. Do not silently replace it with an unfiltered global catalog.

Community plugins may import shipped core helpers using `plugins._commands...`; their own modules still use `usr.plugins.<plugin_name>...` when installed under `usr/plugins/`. Do not import another transport's adapter or add its SDK just to access commands.

## The Receive Path

1. Enforce your existing sender, channel, server/thread, role, and authorization rules **before resolution**. A user allowed to chat is not automatically allowed to run Python-backed commands or change global plugin settings. The resolver is not an authorization boundary.
2. Find or create the authorized conversation's context through your existing binding. Never accept an arbitrary remote `context_id`, command-file path, or project name without checking that binding.
3. Normalize only your transport syntax, such as this bot's mention prefix. Preserve slash text, multiline arguments, and attachment captions. Ignore bot echoes and messages addressed to another bot.
4. Discover and resolve against the current context. Route execution controls such as `/stop` before your ordinary busy-message queue. Preserve custom overrides before applying special behavior for bundled commands.
5. Apply result effects, send control feedback, and submit any resulting prompt through the normal message/attachment/queue path. A control-only result must not start an unnecessary model turn.

## Minimal Resolver Example

This is the **resolution step**, not a complete bot. Call it only after your integration has authorized the request. It returns `None` for ordinary text, raises for an unknown/unavailable leading command, and returns the shared resolution object for a known command.

```python
from agent import AgentContext
from helpers import projects
from plugins._commands.helpers import commands


async def resolve_channel_command(context: AgentContext, text: str):
    if AgentContext.get(context.id) is not context:
        raise ValueError("Use this conversation's registered AgentContext.")

    invocation = commands.parse_slash_invocation(text)
    name = invocation["command_name"]
    if not name:
        return None

    catalog = commands.list_context_commands(context)
    command = next((item for item in catalog if item["name"] == name), None)
    if command is None:
        if text.lstrip().startswith("/"):
            raise ValueError(f"Unknown or unavailable command: /{name}")
        return None

    return await commands.resolve_command_invocation(
        path=command["path"],
        slash_text=text,
        project_name=projects.get_context_project_name(context) or "",
        context_id=context.id,
    )
```

Use `list_context_commands(context)` for help and menus too. It retains the effective precedence: project → global → bundled Commands definitions → other enabled plugin definitions, filtering owning plugins for the context. Menu fields include `name`, `description`, and `argument_hint`. Rebuild or revalidate choices when clicked; project/profile changes can invalidate an earlier menu.

`source_scope_key == "builtin"` identifies bundled Commands definitions. Only apply bundled-name special cases when the effective entry is actually bundled. A user-defined `/new`, `/plugins`, or `/compact` must retain its custom implementation. Plugin-provided commands such as `/goal` and `/rename` should execute their owning scripts, not a copied implementation.

Legacy integration controls can remain as explicit additions, with their own access rules and help. Check the effective catalog first, so a fixed registry or unknown-command guard does not swallow custom or newly added commands. Pass your integration name when using `integration_commands` to avoid exposing another transport's controls.

`resolve_message_command(text, context_id=...)` is a convenience API used by the generic backend hook. It currently lists effective commands directly rather than using `list_context_commands`. For a channel adapter, the example above makes the enabled-context catalog check explicit. Neither helper supplies channel authorization.

## Interpret The Result

The returned object has `command`, `invocation`, and `result`; `result` contains `text` and `effects`. Start with `result["text"]`, then process effects **in order**.

| Effect | Channel behavior |
|---|---|
| `replace_input` | Replace the pending agent prompt with `effect.text`. |
| `append_input` | Append `effect.text` to that prompt. |
| `send_message` | Use `effect.text` as the agent prompt, retaining the current prompt when empty. This requests an agent turn, not a platform API call with the raw effect. |
| `toast`, `show_markdown` | Send `message` or `content` as channel feedback using safe formatting and platform length limits. |
| `goal_changed` | The goal script has already changed state. Refresh a channel display if one exists; do not create/update the goal again. |
| `new_chat`, `select_chat` | Create/select and persist the channel's context binding. Preserve prior history on `/new`; validate the target's channel/user ownership on selection. |
| `reset_chat`, `clear_transcript` | Distinguish resetting agent context from clearing visible platform messages. Implement and document the chosen channel behavior; do not claim to delete messages you left visible. |
| `pause_agent`, `nudge_agent` | Use the existing Agent Zero run controls against the authorized context. Do not queue them as ordinary prompts. |
| `compact_chat` | Show stats and obtain a confirmation tied to the current idle context. Reuse the [compactor](../../../plugins/_chat_compaction/helpers/compactor.py), including its backup/error behavior. |
| `attach_files`, `copy_transcript` | Use the platform's attachment workflow and/or deliver a transcript document. Keep temporary export files alive until delivery finishes, then clean them up. |
| `open_modal`, `open_plugin_config`, `open_agent_editor` | Adapt to channel menus or explain the WebUI requirement. An HTML path is not a remotely opened window. |
| `test_agent_profile` | Follow the command's requested profile using the existing profile-selection/creation owners and an explicit channel session policy. |
| `computer_use` | Present the effect's fallback guidance. Host permission changes remain owned by A0 Launcher/CLI. |
| Unknown effect | Report the unsupported action; do not silently report success or invent an implementation. |

After effects, deliver nonempty rendered text through your usual authorized `UserMessage` path, retaining attachments. Keep the existing busy-run queue/intervention distinction. If nothing remains to send to the agent, return control feedback and stop.

Resolution is executable: a script may already have renamed a chat, changed a goal, stopped a task, or changed configuration before returning effects. Resolve once. If delivery fails, retry delivery of the saved result, not command execution. If an effect is unsupported after resolution, report that limit without implying that earlier side effects were rolled back. Use platform event IDs to prevent duplicate execution when your transport redelivers events.

For native settings menus, reuse [plugin configuration/toggle APIs](../../../helpers/plugins.py), [tool policy and its canonical catalog](../../../helpers/tool_policy.py), and [Agent Editor's sparse change-plan writer](../../../plugins/_agent_editor/helpers/editor.py). Preserve required tools, current scopes, existing operator authorization, and a way to control the integration after settings changes. Validate menu selections at action time; do not trust stale list indices for permission changes.

## Avoid Resolving Twice

Do not prepend sender headers before parsing the original command: they hide prefix commands, and a postfix command can accidentally capture the header as an argument. Telegram and WhatsApp resolve first, then add their existing envelope with a closing marker; the wrapped/queued result no longer looks like a prefix or postfix command to the backend hook.

An integration that intentionally sends trusted text directly to `context.communicate` needs a tested once-only handoff if it adds eager resolution. Do not invent a `UserMessage` "already resolved" flag: the current backend hook does not consume one. Preserve the integration's existing message and trust semantics when choosing that handoff. Test rendered text ending in another command and queued delivery, not only the original slash input.

## Native Platform Commands And Plain Chat

Treat platform command registration and Agent Zero command execution as separate concerns. A native platform-command interaction needs an adapter from its selected command/options into this same resolution and effect path. Importing the catalog alone does not register platform commands or handle interaction replies. Verify the installed SDK's registration, acknowledgement, and follow-up requirements before implementing that surface.

For a message bridge, preserve its existing mention normalization, server/channel/thread allowlists, bot-echo suppression, rate limits, and authorization policy. Apply that policy before executing a command, just as for other user-requested operations.

Maintain explicit bindings for the chosen conversation boundary, such as server + channel/thread + user or an intentionally shared channel. Replies, buttons, selected profiles, and queued messages must use that binding. Never show or switch another channel's private contexts just because they exist in `AgentContext.all()`.

Use the Telegram/WhatsApp modules as source examples for effect adaptation, not drop-in cross-platform libraries. Keep native registrations and menus in your community plugin and refresh them through its normal lifecycle. A paginated text menu is a valid fallback when native commands cannot represent the whole dynamic project catalog.

## Verify Compatibility

- Exercise prefix and postfix commands, multiline arguments, custom overrides, disabled plugins, ordinary inline paths, and unknown leading commands. Ensure control-only commands make no model call.
- Check first-message context creation, attachment captions, busy-run queueing, `/stop` during a run, `/new` history preservation, and selection after a restart.
- Reject unauthorized senders, forged/stale menu choices, and cross-conversation context IDs before any script or mutation. Test redelivered event IDs without executing twice.
- Check feedback, effects, permission changes, compaction confirmation, and file exports—not just successful resolution. Keep host-only and unsupported UI actions explicit.
- Use the actual framework runtime and real channel for a targeted smoke test. Mock platform delivery for deterministic tests; do not use production credentials in fixtures.

Current examples and checks: [Telegram tests](../../../tests/test_telegram_commands.py), [WhatsApp tests](../../../tests/test_whatsapp_commands.py), and [bridge transport tests](../../../tests/test_whatsapp_bridge.mjs). Do not claim full platform compatibility from a list of command names alone.
