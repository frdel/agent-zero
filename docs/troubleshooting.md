# Troubleshooting and FAQ
This page addresses frequently asked questions (FAQ) and provides troubleshooting steps for common issues encountered while using Agent Zero.

## Frequently Asked Questions
**1. How do I ask Agent Zero to work directly on my files or dirs?**
-   Place the files/dirs in the `work_dir` directory. Agent Zero will be able to perform tasks on them. The `work_dir` directory is located in the root directory of the Docker Container.

**2. When I input something in the chat, nothing happens. What's wrong?**
-   Check if you have set up API keys in the Settings page. If not, the application will not be able to communicate with the endpoints it needs to run LLMs and to perform tasks.

**3. How do I integrate open-source models with Agent Zero?**
Refer to the [Choosing your LLMs](installation.md#installing-and-using-ollama-local-models) section of the documentation for detailed instructions and examples for configuring different LLMs. Local models can be run using Ollama or LM Studio.

> [!TIP]
> Some LLM providers offer free usage of their APIs, for example Groq, Mistral or SambaNova.

**6. How can I make Agent Zero retain memory between sessions?**
Refer to the [How to update Agent Zero](installation.md#how-to-update-agent-zero) section of the documentation for instructions on how to update Agent Zero while retaining memory and data.

**7. Where can I find more documentation or tutorials?**
-   Join the Agent Zero [Skool](https://www.skool.com/agent-zero) or [Discord](https://discord.gg/B8KZKNsPpj) community for support and discussions.

**8. How do I adjust API rate limits?**
Modify the `rate_limit_seconds` and `rate_limit_requests` parameters in the `AgentConfig` class within `initialize.py`.

**9. My code_execution_tool doesn't work, what's wrong?**
-   Ensure you have Docker installed and running.  If using Docker Desktop on macOS, grant it access to your project files in Docker Desktop's settings.  Check the [Installation guide](installation.md#4-install-docker-docker-desktop-application) for more details.
-   Verify that the Docker image is updated.

**10. Can Agent Zero interact with external APIs or services (e.g., WhatsApp)?**
Extending Agent Zero to interact with external APIs is possible by creating custom tools or solutions. Refer to the documentation on creating them. 

## Troubleshooting

**Installation**
- **Docker Issues:** If Docker containers fail to start, consult the Docker documentation and verify your Docker installation and configuration.  On macOS, ensure you've granted Docker access to your project files in Docker Desktop's settings as described in the [Installation guide](installation.md#4-install-docker-docker-desktop-application). Verify that the Docker image is updated.

**Usage**

- **Terminal commands not executing:** Ensure the Docker container is running and properly configured.  Check SSH settings if applicable. Check if the Docker image is updated by removing it from Docker Desktop app, and subsequently pulling it again.

* **Error Messages:** Pay close attention to the error messages displayed in the Web UI or terminal.  They often provide valuable clues for diagnosing the issue. Refer to the specific error message in online searches or community forums for potential solutions.

* **Performance Issues:** If Agent Zero is slow or unresponsive, it might be due to resource limitations, network latency, or the complexity of your prompts and tasks, especially when using local models.