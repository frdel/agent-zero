# Agent Zero

[![Join our Discord](https://img.shields.io/badge/Discord-Join%20our%20server-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.gg/B8KZKNsPpj) [![Subscribe on YouTube](https://img.shields.io/badge/YouTube-Subscribe-red?style=for-the-badge&logo=youtube&logoColor=white)](https://www.youtube.com/@AgentZeroFW) [![Connect on LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-blue?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/jan-tomasek/) [![Follow on X.com](https://img.shields.io/badge/X.com-Follow-1DA1F2?style=for-the-badge&logo=x&logoColor=white)](https://x.com/JanTomasekDev)



[![Intro Video](/docs/intro_vid.jpg)](https://www.youtube.com/watch?v=C9n8zFpaV3I)

**Personal and organic AI framework**
- Agent Zero is not a predefined agentic framework. It is designed to be dynamic, organically growing, and learning as you use it.
- Agent Zero is fully transparent, readable, comprehensible, customizable and interactive.
- Agent Zero uses the computer as a tool to accomplish its (your) tasks.

## Key concepts
1. **General-purpose assistant**
- Agent Zero is not pre-programmed for specific tasks (but can be). It is meant to be a general-purpose personal assistant. Give it a task, and it will gather information, execute commands and code, cooperate with other agent instances, and do its best to accomplish it.
- It has a persistent memory, allowing it to memorize previous solutions, code, facts, instructions, etc., to solve tasks faster and more reliably in the future.

2. **Computer as a tool**
- Agent Zero uses the operating system as a tool to accomplish its tasks. It has no single-purpose tools pre-programmed. Instead, it can write its own code and use the terminal to create and use its own tools as needed.
- The only default tools in its arsenal are online search, memory features, communication (with the user and other agents), and code/terminal execution. Everything else is created by the agent itself or can be extended by the user.
- Tool usage functionality has been developed from scratch to be the most compatible and reliable, even with very small models.

3. **Multi-agent cooperation**
- Every agent has a superior agent giving it tasks and instructions. Every agent then reports back to its superior.
- In the case of the first agent, the superior is the human user; the agent sees no difference.
- Every agent can create its subordinate agent to help break down and solve subtasks. This helps all agents keep their context clean and focused.

4. **Completely customizable and extensible**
- Almost nothing in this framework is hard-coded. Nothing is hidden. Everything can be extended or changed by the user.
- The whole behavior is defined by a system prompt in the **prompts/agent.system.md** file. Change this prompt and change the framework dramatically.
- The framework does not guide or limit the agent in any way. There are no hard-coded rails that agents have to follow.
- Every prompt, every small message template sent to the agent in its communication loop, can be found in the **prompts/** folder and changed.
- Every default tool can be found in the **python/tools/** folder and changed or copied to create new predefined tools.
- Of course, it is open-source (except for some tools like Perplexity, but that will be replaced with an open-source alternative as well in the future).

5. **Communication is key**
- Give your agent a proper system prompt and instructions, and it can do miracles.
- Agents can communicate with their superiors and subordinates, asking questions, giving instructions, and providing guidance. Instruct your agents in the system prompt on how to communicate effectively.
- The terminal interface is real-time streamed and interactive. You can stop and intervene at any point. If you see your agent heading in the wrong direction, just stop and tell it right away.
- There is a lot of freedom in this framework. You can instruct your agents to regularly report back to superiors asking for permission to continue. You can instruct them to use point-scoring systems when deciding when to delegate subtasks. Superiors can double-check subordinates' results and dispute. The possibilities are endless.

![Agent Zero](docs/splash_wide.png)

## Nice features to have
- Output is very clean, colorful, readable and interactive; nothing is hidden.
- The same colorful output you see in the terminal is automatically saved to HTML file in **logs/** folder for every session.
- Agent output is streamed in real-time, allowing the user to read along and intervene at any time.
- No coding is required, only prompting and communication skills.
- With a solid system prompt, the framework is reliable even with small models, including precise tool usage.

![Time example](docs/time_example.jpg)

## Keep in mind
1. **Agent Zero can be dangerous!**
With proper instruction, Agent Zero is capable of many things, even potentially dangerous to your computer, data, or accounts. Always run Agent Zero in an isolated environment (like the built in docker container) and be careful what you wish for.

2. **Agent Zero is not pre-programmed; it is prompt-based.**
The whole framework contains only a minimal amount of code and does not guide the agent in any way.
Everything lies in the system prompt in the **prompts/** folder. Here you can rewrite the whole framework behavior to your needs.
If your agent fails to communicate properly, use tools, reason, use memory, find answers - just instruct it better.

3. **If you cannot provide the ideal environment, let your agent know.**
Agent Zero is made to be used in an isolated virtual environment (for safety) with some tools preinstalled and configured.
If you cannot provide all the necessary conditions or API keys, just change the system prompt and tell your agent what operating system and tools are at its disposal. Nothing is hard-coded; if you do not tell your agent about a certain tool, it will not know about it and will not try to use it.

## Known problems
1. The system prompt sucks. You can do better. If you do, help me please :)
2. The communication between agent and terminal in docker container via SSH can sometimes break and stop producing outputs. Sometimes it is because the agent runs something like "server.serve_forever()" which causes the terminal to hang, sometimes a random error can occur. Restarting the agent and/or the docker container helps.
3. The agent can break his operating system. Sometimes the agent can deactivate virtual environment, uninstall packages, change config etc. Again, removing the docker container and cleaning up the **work_dir/** is enough to fix that.

## Ideal environment
- **Docker container**: The perfect environment to run Agent Zero is the built-in docker container. The agent can download the image **frdel/agent-zero-exe** on its own and start the container, you only need to have docker running (like the Docker Desktop application).
- **Python**: Python has to be installed on the system to run the framework.
- **Internet access**: The agent will need internet access to use its online knowledge tool and execute commands and scripts requiring a connection. If you do not need your agent to be online, you can alter its prompts in the **prompts/** folder and make it fully local.

## Setup
1. **Required API keys:**
- At the moment, the only recommended API key is for https://www.perplexity.ai/ API. Perplexity is used as a convenient web search tool and has not yet been replaced by an open-source alternative. If you do not have an API key for Perplexity, leave it empty in the .env file and Perplexity will not be used.
- Chat models and embedding models can be executed locally via Ollama and HuggingFace or via API as well.

2. **Enter your API keys:**
- You can enter your API keys into the **.env** file, which you can copy from **example.env**
- Or you can export your API keys in the terminal session:
~~~bash
export API_KEY_PERPLEXITY="your-api-key-here"
export API_KEY_OPENAI="your-api-key-here"
~~~

3. **Install dependencies with the following terminal command:**
~~~bash
pip install -r requirements.txt
~~~

3. **Choose your chat, utility and embeddings model:**
- In the **main.py** file, right at the start of the **chat()** function, you can see how the chat model and embedding model are set.
- You can choose between online models (OpenAI, Anthropic, Groq) or offline (Ollama, HuggingFace) for both.

4. **run Docker:**
- Easiest way is to install Docker Desktop application and just run it. The rest will be handled by the framework itself.

## Run the program
- Just run the **main.py** file in Python:
~~~bash
python main.py
~~~
- Or run it in debug mode in VS Code using the **debug** button in the top right corner of the editor. I have provided config files for VS Code for this purpose.

# NVIDIA Docker Setup on Ubuntu WSL2

This guide provides simple instructions for setting up NVIDIA Docker on Ubuntu within WSL2 (Windows Subsystem for Linux 2). It is written for beginners who may not be familiar with technical terms or complex setups.

## Prerequisites

Before you start, make sure you have the following:

- **Windows 11**: The latest version of Windows, with WSL2 enabled. WSL2 allows you to run a Linux system on your Windows computer.
- **NVIDIA GPU**: A graphics card from NVIDIA with the latest drivers installed on Windows. This lets you use your GPU for faster computing.
- **Docker Desktop**: A program that allows you to run applications in containers. Make sure it's set to use WSL2.

## Installation Steps

1. **Install Ubuntu on WSL2**  
   First, make sure you have an Ubuntu system installed and running on WSL2. You can install Ubuntu from the Microsoft Store.

2. **Install NVIDIA Docker Toolkit**  
   The following steps should be entered into your Ubuntu terminal:

   - **Add NVIDIA Docker Repository Key**  
     This command adds a key that allows your system to trust the NVIDIA software. Enter this in the Ubuntu terminal:  
     '''sh
     curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | gpg --dearmor | sudo tee /usr/share/keyrings/nvidia-archive-keyring.gpg > /dev/null
     '''

   - **Set Up the CUDA Repository**  
     These commands set up the source from where you will download NVIDIA software. Enter them one by one in the Ubuntu terminal:  
     '''sh
     export distribution=$(. /etc/os-release; echo $ID$VERSION_ID)
     export ARCH=$(dpkg --print-architecture)
     sudo tee /etc/apt/sources.list.d/nvidia-docker.list > /dev/null <<EOF
     deb [signed-by=/usr/share/keyrings/nvidia-archive-keyring.gpg] https://nvidia.github.io/libnvidia-container/stable/ubuntu${distribution}/${ARCH} /
     deb [signed-by=/usr/share/keyrings/nvidia-archive-keyring.gpg] https://nvidia.github.io/nvidia-container-runtime/stable/ubuntu${distribution}/${ARCH} /
     deb [signed-by=/usr/share/keyrings/nvidia-archive-keyring.gpg] https://nvidia.github.io/nvidia-docker/ubuntu${distribution}/${ARCH} /
     EOF
     '''

   - **Update and Install NVIDIA Docker**  
     This installs the NVIDIA Docker software. Enter these commands in the Ubuntu terminal:  
     '''sh
     sudo apt-get update
     sudo apt-get install -y nvidia-docker2
     '''

3. **Restart Docker Daemon**  
   After installation, restart Docker to apply changes. Enter this in the Ubuntu terminal:  
   '''sh
   sudo systemctl restart docker
   '''

4. **Add User to Docker Group**  
   This step allows you to use Docker without typing `sudo` each time. Enter this command in the Ubuntu terminal:  
   '''sh
   sudo usermod -aG docker $USER
   '''  
   After running the command, log out of your Ubuntu session and log back in for this change to take effect.

5. **Test NVIDIA Docker Installation**  
   To verify that NVIDIA Docker is set up correctly, run the following command in the Ubuntu terminal:  
   '''sh
   docker run --rm --gpus all nvidia/cuda:11.0.3-base-ubuntu20.04 nvidia-smi
   '''  
   If successful, you should see information about your NVIDIA GPU.

## Troubleshooting Tips

1. **Permission Denied Errors**:  
   If you get a "permission denied" error, make sure you've logged out and back in after adding yourself to the Docker group.

2. **Repository Not Found (404 Error)**:  
   Double-check the commands you used to set up the CUDA repository. If you're using a specific version of Ubuntu, like 22.04 (`jammy`), ensure you're using the correct URLs.

3. **Manifest Unknown Error**:  
   This means the Docker image tag you tried to use doesn't exist. Check the available tags on the [NVIDIA Docker Hub](https://hub.docker.com/r/nvidia/cuda/tags).

4. **Docker Not Starting or GPU Not Detected**:  
   Make sure Docker Desktop is configured to use WSL2 and that GPU sharing is enabled. You can check Docker Desktop settings on your Windows machine.

5. **Check System Compatibility**:  
   Ensure your Windows system, WSL2 setup, and NVIDIA GPU drivers are all up to date.

6. **Further Assistance**:  
   For more help, refer to the [official NVIDIA Docker documentation](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html).

