---
name: setup-a0-cli
description: "Install, connect or troubleshoot A0 CLI host access, local files and remote tools."
triggers:
  - "install A0"
  - "connect local files"
  - "enable host connector"
  - "A0 CLI setup"
  - "host vs container"
---

# A0 CLI Host Setup

`a0` runs on the user's host machine; Agent Zero stays in Docker or its sandbox.

## Keep The Conversation Short

- Match the user's brevity. For a brief question, reply with one short sentence and at most one command block.
- Give only the next useful step, then wait for the result. Do not dump installation, connection, fallback, troubleshooting, and success details into one response.
- Ask only for information needed now. For a fresh install, ask only which host OS they use. Ask about previous commands and errors only when they say they already tried or something failed.
- Do not add headings, checklists, expected-output prose, warnings, alternatives, or explanations unless they help with the user's current step or the user asks for detail.

## Fresh Install

If the host OS is unknown, ask only:

> Which computer are you installing it on: Windows, macOS, or Linux?

Once known, give the matching command and tell them to run `a0` when it finishes.

macOS / Linux host terminal:

```bash
curl -LsSf https://raw.githubusercontent.com/agent0ai/a0-connector/main/install.sh | sh
```

Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/agent0ai/a0-connector/main/install.ps1 | iex
```

If the user is inside `/a0`, `docker exec`, or another container shell, stop there: tell them to exit and run the installer in their normal computer terminal. Do not give container installation commands.

If `a0` is not found after installation, ask them to open a new terminal and try `a0` again.

## Connect

Running `a0` opens a host picker and discovers local Docker instances when possible. Tell the user to select the instance it finds.

If manual entry is needed:

- Use the exact URL the user currently uses to open Agent Zero, including its actual port.
- Never guess, prescribe, or describe any port as common or default. Do not turn a documentation example into the user's address.
- If the URL is unknown, ask the user to copy it from their browser or Docker's published-port mapping.
- A tunnel URL is pasted exactly as shown and does not need a port appended.

Mention `AGENT_ZERO_HOST` only if the user asks to prefill the picker. Use their exact known URL, never an invented example.

## Troubleshoot Only When Needed

- For a failed attempt, ask for the command, whether it ran on the host or in Docker, and the exact output.
- If the installer URL is unreachable but `uv` works, use:

  ```bash
  uv tool install --upgrade git+https://github.com/agent0ai/a0-connector
  ```

- A connector `404` usually means the running Agent Zero build lacks the bundled `_a0_connector`; tell the user to update Agent Zero.
- If discovery fails, ask for the exact Agent Zero URL or suggest a Flare Tunnel only then. The Flare Tunnel flow is `Settings > External Services > Flare Tunnel` → `Create Tunnel` → paste the shown HTTPS URL into `a0`.

## Response Examples

User: "How to enable host connector"

> Which computer are you installing it on: Windows, macOS, or Linux?

User: "Linux"

> Run this in your normal Linux terminal, then run `a0` and select the Agent Zero instance it finds.
>
> ```bash
> curl -LsSf https://raw.githubusercontent.com/agent0ai/a0-connector/main/install.sh | sh
> ```

User: "It asks for a custom URL"

> Paste the exact URL you currently use to open Agent Zero in your browser, including its port.
