# How to install Agent Zero on Windows and MacOS
- Agent Zero is not an app. It's a framework. It's made to be customized, edited, enhanced. Therefore you need to install the necessary components to run it.
- I will provide step by step instructions along with a video for this tutorial on how to make Agent Zero work on Windows and MacOS.

[![Video](thumb_play.png)](https://youtu.be/8H7mFsvxKYQ)

## Reminders:
1. You don't need to install Python, Conda will take care of that for you.
2. You don't need API keys, Agent Zero can run with local models, but for this tutorial I will leave it to the default OpenAI API. Local models will be covered in another tutorial.
3. You don't need Visual Studio Code or any other code editor, but it's easier to navigate and edit files if you have one.
4. Docker is not mandatory, but running Agent Zero without docker is actually more complicated and can be very dangerous, so I will be showing the easier and recommended way to do it - with Docker Desktop application.
5. Git/Github is not mandatory, you can download the framework files in browser. I will not be showing how to use Git in this tutorial.


## 1. Install Conda (miniconda)
- Conda is a python environment manager, it will help you keep your projects and installations separated. Full Conda has many more features, but you only need "miniconda".

1. Go to the download page of miniconda [here](https://docs.anaconda.com/miniconda/#miniconda-latest-installer-links). If the link does not work, just search the web for "miniconda download".
2. Based on your operating system, download the right installer of miniconda. For MacOS select the version with "pkg" at the end.

<img src="image-1.png" alt="miniconda download win" width="500"/>
<img src="image-5.png" alt="miniconda download macos" width="500"/>
<br><br>

3. Run the installer and go through the installation process, here you can leave everything to default and just click Next, Next... The same goes for MacOS with the "pkg" graphical installer.

<img src="image.png" alt="miniconda install" width="200"/>
<img src="image-2.png" alt="miniconda install" width="200"/>
<img src="image-3.png" alt="miniconda install" width="200"/>
<img src="image-4.png" alt="miniconda install" width="200"/>
<br><br>

4. After the installation is complete, you should have "Anaconda Powershell Prompt" installed on your Windows machine. On MacOS, when you open the Terminal application in your Applications folder and type "conda --version", you should see the version installed.

<img src="image-6.png" alt="miniconda installed" height="100"/>
<img src="image-7.png" alt="miniconda installed" height="100"/>
<br><br>

## 2. Install Docker (Docker Desktop application)
- Simply put, Docker is a way of running virtual computers on your machine. These are lightweight, disposable and isolated from your operating system, so it is a way to sandbox Agent Zero.
- Agent Zero only connects to the Docker container when it needs to execute code and commands. The frameworks itself runs on your machine.
- Running Agent Zero without docker is possible, but more complicated and dangerous, I will not be covering that in this tutorial.
- Docker has a desktop application with GUI for all major operating system, so I will be using that.

1. Go to the download page of Docker Desktop [here](https://www.docker.com/products/docker-desktop/). If the link does not work, just search the web for "docker desktop download".
2. Download the version for your operating system. Don't be tricked by the seemingly missing windows intel/amd version, it's the button itself, not in the dropdown menu.

<img src="image-8.png" alt="docker download" width="200"/>
<br><br>

3. Run the installer and go through the installattion process. It should be even shorter than Conda installation, you can leave everything to default. On MacOS, the installer is a "dmg" image, so just drag and drop the application to your Applications folder like always.

<img src="image-9.png" alt="docker install" width="300"/>
<img src="image-10.png" alt="docker install" width="300"/>

<img src="image-12.png" alt="docker install" width="300"/>
<br><br>


4. Once installed, you should see Docker Desktop application on your Windows/Mac machine. 

<img src="image-11.png" alt="docker installed" height="100"/>
<img src="image-13.png" alt="docker installed" height="100"/>
<br><br>

5. Create account in the application.
No need to create images or containers, the framework will do that for you. However, this requires you to be signed in to the Docker Hub, so create a free account in the Docker Desktop application, you will be prompted when the application first runs.

## 3. Download Agent Zero
- You can clone the Agent Zero repository (https://github.com/frdel/agent-zero) from GitHub if you know how to use git. In this tutorial I will just show how to download the files.

1. Go to the Agent Zero releases [here](https://github.com/frdel/agent-zero/releases).
2. The latest release is on the top of the list, click the "Source Code (zip)" button under "Assets" to download it.

<img src="image-14.png" alt="agent zero download" width="500"/>
<br><br>

3. Extract the downloaded archive where you want to have it. I will extract them to "agent-zero" folder on my Desktop - "C:\Users\frdel\Desktop\agent-zero" on Windows and "/Users/frdel/Desktop/agent-zero" on MacOS.


## 4. Set up Conda environment
- Now that we have the project files and Conda, we can create **virtual Python environment** for this project, activate it and install requirements.

1. Open your **"Anaconda Powershell Prompt"** application on windows or **"Terminal"** application on MacOS.
2. In the terminal, navigate to your Agent Zero folder using **"cd"** command. Replace the path with your actual Agent Zero folder path.
~~~
cd C:\Users\frdel\Desktop\agent-zero
~~~
You should see your folder has changed on the next terminal line.

<img src="image-15.png" alt="agent zero cd" height="100"/>
<img src="image-16.png" alt="agent zero cd" height="100"/>
<br><br>

3. Create Conda environment using command **"conda create"**. After **"-n"** is your environment name, you can choose your own, i will use **"a0"** - short for Agent Zero. After **"python"** is the Python version that Conda will install for you into this environment, right now, 3.12 works fine. **-y** skips confirmations.
~~~
conda create -n a0 python=3.12 -y
~~~

4. Once done, activate the new environment for this terminal window by another command:
~~~
conda activate a0
~~~
And you should see that the **(base)** on the left has changed to **(a0)**. This means that this terminal now uses the new **a0** virtual environment and all packages will be installed into this environment.

<img src="image-17.png" alt="conda env" height="200"/>
<img src="image-18.png" alt="conda env" height="200"/>
<br><br>

> ⚠️ If you open a new terminal window, you will need to activate the environment with "conda activate a0" again for that window.

5. Install requirements using **"pip"**. Pip is a Python package manager. We can install all required packages from requirements.txt file using command:
~~~
pip install -r requirements.txt
~~~
This might take some time. If you get any errors regarding version conflicts and compatibility, double check that your environment is activated and that you created that environment with the correct Python version.

<img src="image-19.png" alt="conda reqs" height="200"/>
<br><br>

## 5. Configure Agent Zero
- Now we can configure Agent Zero - select models, settings, API Keys etc.
- I will leave the default configuration using OpenAI API and I will just provide my OpenAI API key in the **.env** file.

1. Find the **"example.env"** file in your Agent Zero folder and edit the contents. I will put my OpenAI API key after **"API_KEY_OPENAI="**. If you have API keys for other service providers, add them as needed.
2. Rename the **"example.env"** file to **".env"**. This is important, only this exact "**.env**" file name is valid.

<img src="image-20.png" alt="conda reqs" height="200"/>
<br><br>

3. (Optional) Change models or setting in **"initialize.py"** file if needed.

## 6. Run Agent Zero
- Setup done. It's time to test Agent Zero. Let's double check:

1. Make sure you have the **"a0"** Conda environment still active in your current terminal window. You can see that on the left of each terminal line like **(a0)** or **(base)**. If not, activate again with **"conda activate a0"** command again.
2. Make sure your terminal is looking into the Agent Zero folder. If not, navigate to it with **"cd"** command again with your path.
3. Run the **Docker Desktop application** you installed and just leave it running in the background. No need to create images or containers, the framework will do that for you. However, this requires you to be signed in to the Docker Hub, so sign in in the Docker Desktop application, if you haven't already.
4. Run the Agent Zero with Web UI:
~~~
python run_ui.py
~~~

<img src="image-21.png" alt="run ui" height="200"/>
<br><br>

5. Open the URL shown in terminal in your web browser. You should see the Agent Zero interface. The first time it needs to execute code, Docker image will be downloaded and deployed, this might take some time. Be patient when seeing "Initializing docker container agent-zero-exe for safe code execution...".

<img src="image-22.png" alt="run ui" width="400"/>
<img src="image-23.png" alt="run ui" width="400"/>
<br><br>



