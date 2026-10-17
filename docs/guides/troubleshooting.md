# Troubleshooting and FAQ
This page addresses frequently asked questions (FAQ) and provides troubleshooting steps for common issues encountered while using Agent Zero.

## Frequently Asked Questions
**1. How do I ask Agent Zero to work directly on my files or dirs?**
- Place the files/dirs in `/a0/usr`. Agent Zero will be able to perform tasks on them.

**2. When I input something in the chat, nothing happens. What's wrong?**
- Check if you have set up API keys in the Settings page. If not, the application cannot call LLM providers.

**3. I get "Invalid model ID." What does that mean?**
- Verify the **provider** and **model naming**. For example, `openai/gpt-5.3` is correct for OpenRouter, but **incorrect** for the native OpenAI provider, which goes without prefix.

**4. Does ChatGPT Plus include API access?**
- No. ChatGPT Plus does not include API credits. You must provide an OpenAI API key in Settings.

**5. Where is chat history stored?**
- Chat history lives at `/a0/usr/chats/` inside the container.

**6. How do I integrate open-source models with Agent Zero?**
Refer to the [Choosing your LLMs](../setup/installation.md#installing-and-using-ollama-local-models) section for configuring local models (Ollama, LM Studio, etc.).

> [!TIP]
> Some LLM providers offer free usage tiers, for example Groq, Mistral, SambaNova, API Route, or CometAPI.

**7. How can I make Agent Zero retain memory between sessions?**
Use **Settings -> Backup & Restore** and avoid mapping the entire `/a0` directory. See [How to update Agent Zero](../setup/installation.md#how-to-update-agent-zero).

**8. My browser tool fails or says Chromium is missing. What now?**

In normal Docker installs, the Browser already includes what it needs.

If you are running a local development checkout, Agent Zero can install the
browser the first time it is needed. To install it ahead of time, run this from
the project root after installing Python requirements:

```bash
PLAYWRIGHT_BROWSERS_PATH=tmp/playwright patchright install chromium --no-shell
```

If **Bring Your Own Browser** mode fails:

- keep A0 CLI connected to the chat;
- restart or reconnect A0 CLI after enabling remote debugging in a browser;
- run `/browser status` in A0 CLI;
- check that Browser settings still say **Bring Your Own Browser**;
- check **Page content access** if page text or screenshots are blocked.

See the [Browser Guide](browser.md) for Browser settings and host-browser
behavior. If you need a different external browser tool, see
[MCP Setup](mcp-setup.md).

**9. My secrets disappeared after a backup restore.**
Secrets are stored in `/a0/usr/secrets.env` and are not always included in backup archives. Copy them manually.

**10. Where can I find more documentation or tutorials?**
- Join the Agent Zero [Skool](https://www.skool.com/agent-zero) or [Discord](https://discord.gg/B8KZKNsPpj) community.

**11. How do I adjust API rate limits?**
Use the model rate limit fields in Settings, under the Main Model and Utility
Model sections, to set request, input, and output limits.

**12. My `code_execution_tool` doesn't work, what's wrong?**
- Ensure Docker is installed and running.
- On macOS, grant Docker Desktop access to your project files.
- Verify that the Docker image is updated.

**13. Can Agent Zero interact with external APIs or services (e.g., WhatsApp)?**
Yes. Start with [API Integration](api-integration.md) for one-off services or
[MCP Setup](mcp-setup.md) when the service already has MCP support.

## Troubleshooting

**Installation**
- **Docker Issues:** If Docker containers fail to start, consult the Docker documentation and verify your Docker installation and configuration. On macOS, ensure you've granted Docker access to your project files in Docker Desktop's settings as described in the [Installation guide](../setup/installation.md#step-1-install-docker-desktop). Verify that the Docker image is updated.
- **Web UI not reachable:** Ensure at least one host port is mapped to container port `80`. If you used `0:80`, check the assigned port in Docker Desktop.

**Usage**

- **Terminal commands not executing:** Ensure the Docker container is running and properly configured.  Check SSH settings if applicable. Check if the Docker image is updated by removing it from Docker Desktop app, and subsequently pulling it again.
- **Agent Zero stuck on the update screen or not starting after an update:** If the browser stays on the updating screen for multiple minutes, reload the current browser window first. If the UI still does not come back, restart the Docker container. If it still does not recover, queue another self-update for the next startup and inspect the updater log.

From the host, find the container name:

```bash
docker ps
```

Open a shell inside the container:

```bash
docker exec -it <container> /bin/bash
```

Queue an update for the next startup attempt with the recovery script in `/exe`:

```bash
/exe/trigger_self_update.sh
```

That default command writes `/exe/a0-self-update.yaml` with `main` and `latest`, so the next startup tries the newest release in the current installed major version. You can also specify the branch, version, and backup settings:

```bash
/exe/trigger_self_update.sh ready latest
/exe/trigger_self_update.sh main v1.10 --backup-dir /root/update-backups --backup-name usr-recovery.zip
/exe/trigger_self_update.sh development latest --no-backup
```

You can run the same commands directly from the host without opening a shell:

```bash
docker exec -it <container> /exe/trigger_self_update.sh
docker exec -it <container> /exe/trigger_self_update.sh ready latest
docker exec -it <container> tail -n 200 /exe/a0-self-update.log
docker exec -it <container> cat /exe/a0-self-update-status.yaml
```

The recovery command only schedules the update. Restart the container or let Agent Zero start again, then check `/exe/a0-self-update.log` and `/exe/a0-self-update-status.yaml` to see what happened.

* **Error Messages:** Pay close attention to the error messages displayed in the Web UI or terminal.  They often provide valuable clues for diagnosing the issue. Refer to the specific error message in online searches or community forums for potential solutions.

* **Performance Issues:** If Agent Zero is slow or unresponsive, it might be due to resource limitations, network latency, or the complexity of your prompts and tasks, especially when using local models.
