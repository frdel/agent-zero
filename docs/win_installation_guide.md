
## Setup

### General Installation Information

   Start here if you are experienced using Python, Docker, Environments, installing requirements, and working with a Github project.

1. **Required API keys:**

    At the moment, the only recommended API key is for https://www.perplexity.ai/ API. Perplexity is used as a convenient web search tool and has not yet been replaced by an open-source alternative. If you do not have an API key for Perplexity, leave it empty in the .env file and Perplexity will not be used.

    Note: Chat models and embedding models can be executed locally via Ollama, LMStudio and HuggingFace or via API as well.

2. **Enter your API keys:**
    
    Enter your API keys into a **.env** file, which is a file used to keep your API keys private. Create the file in the agent-zero root folder or duplicate and rename the included **example.env**. The example file included contains examples for entering each API key type, shown below.

~~~.env
API_KEY_OPENAI=YOUR-API-KEY-HERE
API_KEY_ANTHROPIC=
API_KEY_GROQ=
API_KEY_PERPLEXITY=
API_KEY_GOOGLE=

TOKENIZERS_PARALLELISM=true
PYDEVD_DISABLE_FILE_VALIDATION=1
~~~

Or you can export your API keys in the terminal session:

~~~bash
export API_KEY_PERPLEXITY="your-api-key-here"
export API_KEY_OPENAI="your-api-key-here"
~~~

3. **Install Dependencies:**

~~~bash
pip install -r requirements.txt
~~~

1. **Choose your chat, utility and embeddings model:**
- In the **main.py** file, right at the start of the **chat()** function, you can see how the chat model and embedding model are set.
- You can choose between online models (OpenAI, Anthropic, Groq) or offline (Ollama, HuggingFace) for both.

1. **Run Docker:**
- Easiest way is to install Docker Desktop application and just run it. The rest will be handled by the framework itself.

## Run the program
- Just run the **main.py** file in Python:
~~~bash
python main.py
~~~
- Or run it in debug mode in VS Code using the **debug** button in the top right corner of the editor. I have provided config files for VS Code for this purpose.


### Windows Installation Tips & Quick-Start

Start here for a step-by-step with explanations.

1. **Download and Install Anaconda**

   * We're going to install something called an environment manager. The environment manager has a GUI and although it looks complicated, it's pretty easy to set up.
   * An Environment is a way of using Python that lets you use different software versions and requirements for different programs. An Environment Manager lets you create and switch between the different environments.
   * Follow the excellent guide here: **How To Install Anaconda**. https://www.askpython.com/python/examples/install-python-with-conda
   * or Download and install Anaconda Distribution directly if you prefer https://www.anaconda.com/download/
   * Your computer will need to reboot at least once or twice and you will need Administrator access.
2. **Create an Anaconda Environment**

   * Open Anaconda Navigator.
   * On the left hand side, click **Environments**
   * You will see an existing environment called base(root)
   * At the bottom of the middle column, click **Create**
   * Name the environment **Agent-Zero**
   * Select **Python** package
   * Select version **3.11.9** from the dropdown
   * Click **Create**
   * **Wait**

    At the bottom right you will see a flashing blue progress bar while Anaconda creates your environment. This process installs Python and a basic set of common packages. It should only take a few minutes.

    * Wait for installation of the environment to finish
    * In the middle column you should see your new environment
    * Click the green circle with the white triangle inside of it and select **Open Terminal**
    * A system terminal window should open and you should see something like this:
```(Agent-Zero) C:\Users\yourUserName>```
    * The (Agent-Zero) at the beginning of the prompt tells you that you are running inside of the Agent-Zero environment that you created

   * confirm that python is functioning properly by typing:
```
(Agent-Zero) C:\Users\yourUserName>python --version
Python 3.11.9
```
If your terminal window replies with the Python version number as shown above, you have succeeded installing Anaconda and Python. Great work! Get a snack.

1. **Download Agent-Zero**

If you have already downloaded the zip file archive of the Agent-Zero project, skip ahead.

* Click the green button labeled **<> Code** at the top of the agent-zero github page
* Click **Download Zip**
* **Unzip** the entire contents of the file to a **folder on your computer**

4. **Download Docker Desktop**

Docker is a program that allows you to create unique environments for your applications. The advantage to this is that the programs running in Docker cannot have any access to your computer unless you specifically allow it. https://www.docker.com/products/docker-desktop/

Agent-Zero uses Docker to run programs because it can do so safely. If there are errors, your computer won't be affected.

* Install Docker Desktop using the link above
* Use default settings
* Reboot as required by the installer
* That's it for Docker! Agent-Zero will do the rest with Docker. It's pretty cool.

5. **Configure Agent-Zero**

* Right Click on the file **example.env** in the Agent-Zero root folder
* Select **Open With**
* Select **Notepad** or your preferred text editor
* You should see a small text file that resembles this:
~~~example.env
API_KEY_OPENAI=YOUR-API-KEY-HERE
API_KEY_ANTHROPIC=
API_KEY_GROQ=
API_KEY_PERPLEXITY=
API_KEY_GOOGLE=

TOKENIZERS_PARALLELISM=true
PYDEVD_DISABLE_FILE_VALIDATION=1
~~~
* Select File | **Save as... **
* From the **Save as Type** drop-down at the bottom of the Save As dialog window, select **Save as Type All Files**
* Name the file **.env** and select **save**
* Enter your API key(s) for your preferred models (https://help.openai.com/en/articles/4936850-where-do-i-find-my-openai-api-key)
* Save and Close your new .env file
* Note that the file should be simply ".env" and you might not even be able to see it

!!! If you see a file named .env.txt that is **wrong** Make sure to select the type All Files when saving.

6. Configure API Preferences

If you entered an openAI API key earlier, you may skip this step. If you entered an alternative key, 
* Right Click on the file **main.py** in the Agent-Zero root folder
* Select **Open With**
* Select **Notepad** or your preferred text editor
* Scroll about 20 lines down from the top until you see lines that look like this: *chat_llm = models.get_*
* Comment out the openAI model and enable the model that corresponds to your API key
* Save

1. **Install Requirements (Dependencies)**

* Open **Anaconda Navigator** and navigate to your Environment
    * Click the green circle with the white triangle inside of it and select **Open Terminal**

* Reopen your new environment's **terminal window**
    * Click the green circle with the white triangle inside of it and select **Open Terminal**
    * A system terminal window should open and you should see something like this

~~~
(Agent-Zero) C:\Users\yourUserName>
~~~

* Navigate to the agent-zero folder

~~~
(Agent-Zero) C:\Users\yourUserName>cd c:\projects\agent-zero
~~~

* Install the necessary packages required by Agent-Zero from the file requirements.txt. The requirements file has a list of specific software needed for agent-zero to operate. We will be using "pip", a tool for downloading software for Python.

~~~
(Agent-Zero) C:\projects\agent-zero>pip install -r requirements.txt
~~~

* You will see a ton of text scrolling down the screen while pip downloads and installs your software.
* It will take a while. Be patient.
* pip is finished when you see your command prompt again at the bottom of the screen
 
If all of the requirements installed succesfully, you can proceed to run the program.

* Open Anaconda Navigator
* Activate the Agent-Zero environment by double clicking on its name
* click Open Terminal
* Navigate to the agent-zero folder
* Type **python main.py** and press enter

```
(Agent-Zero) C:\Users\yourUserName>cd c:\projects\agent-zero
(Agent-Zero) C:\projects\agent-zero\python main.py
Initializing framework...

User message ('e' to leave):

```