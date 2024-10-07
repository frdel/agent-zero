# Installation

This guide provides comprehensive instructions for installing Agent Zero on various operating systems. Choose the section that corresponds to your OS:

## Windows

### Quick Start

1. **Install Anaconda or Miniconda:** Download and install the appropriate version for your system from [here](https://docs.anaconda.com/anaconda/install/). Choose Miniconda for a minimal installation or Anaconda for a full distribution.
2. **Create an Environment:** Open Anaconda Navigator (or use the `conda` command in your terminal), create a new environment named `agent-zero`, and select Python 3.11 or higher.
3. **Install Docker Desktop:** Download and install Docker Desktop from [here](https://www.docker.com/products/docker-desktop/).
4. **Download Agent Zero:** Download the latest release (zip file) from the [GitHub releases page](https://github.com/frdel/agent-zero/releases). Extract the zip file to a directory of your choice.
5. **Configure API Keys:** Duplicate `example.env` and rename it to `.env`. Add your API keys for OpenAI (or other providers) inside this file.
6. **Install Requirements:** Open a terminal in the Agent Zero directory (within your activated `agent-zero` environment) and run: `pip install -r requirements.txt`
7. **Run Agent Zero (Web UI):**  In your terminal, execute: `python run_ui.py`
8. **Access the Web UI:** Open the URL displayed in the terminal in your web browser (usually `http://127.0.0.1:50001`).

### Detailed Guide with Video

For a more in-depth guide with visual instructions, including screenshots and explanations for each step, please refer to the [Windows Installation Tips & Quick-Start](./windows_detailed.md). This expanded guide covers common installation pitfalls and troubleshooting steps.


## macOS

1. **Install Miniconda:**  Download the pkg installer from [here](https://docs.anaconda.com/miniconda/#miniconda-latest-installer-links) and follow the on-screen instructions.
2. **Install Docker Desktop:** Download the dmg image from [here](https://www.docker.com/products/docker-desktop/) and drag the Docker application to your Applications folder.  Create a Docker Hub account if you don't already have one.
3. **Download Agent Zero:** Download the latest release from the [GitHub releases page](https://github.com/frdel/agent-zero/releases) and extract the zip file.
4. **Open Terminal:** Navigate to the Agent Zero directory in your terminal.
5. **Create Conda Environment:** Run: `conda create -n a0 python=3.12 -y`
6. **Activate Environment:** Run: `conda activate a0`
7. **Install Requirements:** Run: `pip install -r requirements.txt`
8. **Configure API Keys:** Create a `.env` file and add your API keys.
9. **Run Agent Zero (Web UI):** Run: `python run_ui.py`
10. **Access the Web UI:** Open the URL displayed in your terminal.

**Troubleshooting Docker Image Push on macOS:** If you encounter errors while pushing the Docker image, refer to the [Docker Push Troubleshooting section](./macos_docker_push.md).



## Linux

1. **Install Python:** Use your distribution's package manager to install Python 3.12 or higher.  For example, on Ubuntu/Debian: `sudo apt install python3.12`
2. **Install Docker:** Install Docker Desktop or Docker CE using your distribution's instructions. Ensure the Docker service is running: `sudo systemctl start docker`
3. **Install Miniconda:** Download the appropriate installer for your distribution from [here](https://docs.anaconda.com/miniconda/#miniconda-latest-installer-links) and follow the instructions.
4. **Navigate to Agent Zero Directory:** Open your terminal and change the directory to the extracted Agent Zero folder.
5. **Create Conda Environment:** Run: `conda create -n a0 python=3.12`
6. **Activate Environment:** Run: `conda activate a0`
7. **Install Requirements:** Run: `pip install -r requirements.txt`
8. **Configure API Keys:** Create a `.env` file in the project root and add your API keys.
9. **Run Agent Zero (Web UI):** Run: `python run_ui.py`
10. **Access the Web UI:** Open the URL displayed in your terminal.


## Video Tutorial (v0.7)

For a video walkthrough of the latest features and installation process, check out this [YouTube video](https://www.youtube.com/watch?v=U_Gl0NPalKA).



## Running on All Hosts (Not Just Localhost)

To access the Agent Zero Web UI from other devices on your network, modify `run_ui.py`:

1. Add `host="0.0.0.0"` before `port=port` in the `app.run()` command.  Alternatively, use your private IP address if you want to restrict access.
2. Access the Web UI from another device using `$YOUR_PRIVATE_IP:50001` as the URL.