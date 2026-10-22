# Agent Editor

Agent Editor provides the deterministic Easy modal and Advanced workspace for
Agent Zero profiles. It reads the existing layered profile architecture and
writes only sparse overrides in the selected Global or project profile layer.

The editor never invokes a model. Tool and skill controls are backed by the
central runtime policy owners, and every save is previewed as exact file writes
and deletions before the same validated plan is applied.

Easy and Advanced use the same segmented capability policy: On pins an item
allowed, Off pins it blocked, and Default follows the profile's Tools, MCPs, or
Skills default switch. Easy places each chooser below its default switch;
Advanced gives Tools, MCPs, and Skills separate searchable sections and adds
retained unavailable entries plus ACE-based prompt editing.

Main prompt sections such as Tips open ready to edit under readable titles,
with their customization status beside the title. A compact Saves to row shows
the destination and copy action; variable hints appear below the editor.
Save preserves Markdown and its template placeholders exactly; the runtime
continues to supply dynamic values when the agent runs.

Global agents and customizations live under `usr/agents/<profile-id>` and apply
across projects. Project-scoped agents and customizations live under
`usr/projects/<project>/.a0proj/agents/<profile-id>`, inherit the Global layer,
and can be removed without changing it.

Manage agents can duplicate the effective profile into the selected scope and
toggle whether each profile is available there. Project availability reuses
`.a0proj/agents.json`; Global availability is a sparse profile override.
The selected scope must always keep at least one profile available.
The bundled `default` profile remains the internal inheritance baseline and is
not offered as a selectable or editable profile.
