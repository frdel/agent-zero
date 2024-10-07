# Installation

This guide provides comprehensive instructions for installing Agent Zero on various operating systems. Choose the section that corresponds to your OS:

## Windows

### Quick Start

1. **Install Anaconda or Miniconda:** Download and install the appropriate version for your system from [here](https://docs.anaconda.com/anaconda/install/).  Miniconda is a smaller installation, while Anaconda includes a broader set of packages.
2. **Create an Environment:**  Open Anaconda Navigator (or use the `conda` command in your terminal) and create a new environment named `agent-zero` with Python 3.11 or higher.
3. **Install Docker Desktop:** Download and install Docker Desktop from [here](https://www.docker.com/products/docker-desktop/).
4. **Download Agent Zero:**  Download the latest release zip file from the [GitHub releases page](https://github.com/frdel/agent-zero/releases).  Extract the zip to your desired location.
5. **Configure API Keys:** Copy `example.env`, rename it to `.env`, and add your API keys (OpenAI or other providers).
6. **Install Requirements:**  In your activated `agent-zero` environment, navigate to the Agent Zero directory in your terminal and run:  `pip install -r requirements.txt`
7. **Run Agent Zero (Web UI):**  Execute `python run_ui.py` in your terminal.
8. **Access the Web UI:**  Open the URL shown in the terminal (typically `http://127.0.0.1:50001`) in your web browser.


### Detailed Guide with Screenshots

The README file provides a detailed, step-by-step walkthrough of the Windows installation process, including helpful screenshots.  It also offers tips for beginners and addresses common installation issues.  Refer to the README within the project root folder for this comprehensive guide.  (This assumes you will embed the relevant sections of the README directly into your MkDocs project or link to it appropriately.)


## macOS

1. **Install Miniconda:** Download the pkg installer and follow the instructions.
2. **Install Docker Desktop:** Download the dmg image, drag Docker to Applications, and create a Docker Hub account.
3. **Download Agent Zero:** Download the latest release zip and extract it.
4. **Open Terminal:** Navigate to the Agent Zero directory.
5. **Create Conda Environment:** `conda create -n a0 python=3.12 -y`
6. **Activate Environment:**  `conda activate a0`
7. **Install Requirements:** `pip install -r requirements.txt`
8. **Configure API Keys:** Create a `.env` file and add your keys.
9. **Run Agent Zero (Web UI):** `python run_ui.py`
10. **Access the Web UI:** Open the displayed URL.


### Troubleshooting Docker Image Push on macOS

If you experience issues pushing Docker images on macOS, such as authentication errors or repository not found errors, follow these steps:

1. **Verify Repository:** Check if the `frdel/agent-zero-exe` repository exists on Docker Hub under your account. Create it if it doesn't exist.
2. **Check Docker Credentials:** Log out of Docker Hub (`docker logout`) and log back in using your Docker Hub username (not email address) and password (`docker login`).
3. **Verify Permissions:** Ensure your Docker Hub account has push access to the repository.
4. **Check Image Name and Tag:** Double-check the image name and tag in your `docker push` command. It should be `frdel/agent-zero-exe:latest` or similar.

For more detailed Docker troubleshooting information and solutions to other potential errors, consult the Docker documentation and online resources.



## Linux


1. **Install Python:** Use your distribution's package manager (e.g., `apt`, `yum`, `dnf`) to install Python 3.12 or higher.
2. **Install Docker:**  Install Docker Desktop or Docker CE and ensure the service is running (`sudo systemctl start docker`).
3. **Install Miniconda:**  Download the appropriate installer for your distribution and follow the instructions.
4. **Navigate to Agent Zero Directory:** Use the `cd` command in your terminal.
5. **Create Conda Environment:** `conda create -n a0 python=3.12`
6. **Activate Environment:** `conda activate a0`
7. **Install Requirements:** `pip install -r requirements.txt`
8. **Configure API Keys:** Create a `.env` file and add your keys.
9. **Run Agent Zero (Web UI):** `python run_ui.py`
10. **Access the Web UI:** Open the displayed URL.



## Video Tutorial (v0.7)

A video walkthrough demonstrating the installation process and showcasing the latest features in Agent Zero v0.7 is available on [YouTube](https://www.youtube.com/watch?v=U_Gl0NPalKA).


## Running on All Hosts (Not Just Localhost)


To make the Agent Zero Web UI accessible from other devices on your network, modify `run_ui.py`:

1. Add `host="0.0.0.0"` (or your private IP address for restricted access) to the `app.run()` command, before the `port` argument.
2. Access the Web UI from other devices using `$YOUR_PRIVATE_IP:50001`.