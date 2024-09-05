import threading, time, models, os
from ansio import application_keypad, mouse_input, raw_input
from ansio.input import InputEvent, get_input_event
from agent import Agent, AgentConfig
from python.helpers.print_style import PrintStyle
from python.helpers.files import read_file
from python.helpers import files
import python.helpers.timed_input as timed_input
from python.helpers.template_manager import load_templates
# from promptflow.tracing import start_trace


input_lock = threading.Lock()
os.chdir(files.get_abs_path("./work_dir")) #change CWD to work_dir


def initialize():
    
    # main chat model used by agents (smarter, more accurate)
    # chat_llm = models.get_ollama_chat(model_name="gemma2:latest", temperature=0)
    """
    Initialize the agent system.

    This function sets up the agent system by:
    1. Setting up the main chat model used by agents.
    2. Setting up the utility model used by agents.
    3. Setting up the embedding model used by agents.
    4. Creating the agent configuration.
    5. Loading templates.
    6. Creating the first agent.
    7. Starting the chat loop.

    The chat model, utility model, and embedding model can be changed by uncommenting the respective lines.
    The agent configuration can be changed by modifying the AgentConfig object.
    """
    chat_llm = models.get_azure_openai_chat(deployment_name="gpt-4o", temperature=0)
    # chat_llm = models.get_groq_chat(model_name="llama-3.1-70b-versatile", temperature=0)
    
    # utility model used for helper functions (cheaper, faster)
    utility_llm = chat_llm # change if you want to use a different utility model

    # embedding model used for memory
    embedding_llm = models.get_azure_openai_embedding(deployment_name="text-embedding-3-small")
    # embedding_llm = models.get_pinecone_embedding(model_name="multilingual-e5-large")
    # embedding_llm = models.get_ollama_embedding(model_name="nomic-embed-text")
     

    # agent configuration
    config = AgentConfig(
        chat_model = chat_llm,
        utility_model = utility_llm,
        embeddings_model = embedding_llm,
        # memory_subdir = "",
        auto_memory_count = 0,
        # auto_memory_skip = 2,
        # rate_limit_seconds = 60,
        # rate_limit_requests = 30,
        # rate_limit_input_tokens = 0,
        # rate_limit_output_tokens = 0,
        # msgs_keep_max = 25,
        # msgs_keep_start = 5,
        # msgs_keep_end = 10,
        # max_tool_response_length = 3000,
        # response_timeout_seconds = 60,
        code_exec_docker_enabled = True,
        code_exec_docker_name = "agent-zero-exe",
        code_exec_docker_image = " frdel/agent-zero-exe:latest",
        code_exec_docker_ports = { "8022/tcp": 8022 },
        code_exec_docker_volumes = { files.get_abs_path("work_dir"): {"bind": "/root", "mode": "rw"} },

    )
    
    # Load templates
    templates = load_templates()


    # create the first agent
    agent0 = Agent( number = 0, config = config )

    # start the chat loop
    chat(agent0)

def display_templates(agent: Agent):
    templates = agent.get_data("templates")
    PrintStyle(background_color="#6C3483", font_color="white", bold=True, padding=True).print("Available Templates:")
    for i, template in enumerate(templates, 1):
        PrintStyle(font_color="white").print(f"{i}. {template.name}")
    PrintStyle(font_color="white").print("To use a template, type 'use template [template name]'")


# Main conversation loop
def chat(agent:Agent):
    
    # start the conversation loop  
    """
    Main conversation loop with the user.

    This function starts the main conversation loop with the user. It prints a prompt and waits for the user to enter a message. The message is then sent to the agent, which will respond. The response is then printed to the user. The loop continues until the user types 'e' to leave.

    The conversation loop waits for user input with a timeout, specified in the agent's configuration. If the timeout is reached without the user entering a message, a "waiting for message" prompt is printed. If the user enters 'w' at this prompt, the conversation loop waits again for the same duration. If the user enters anything else, the conversation loop continues with the entered message.

    If the user types 'use template [template name]', the conversation loop will print the template information and continue with the entered message. If the user types 'templates', the conversation loop will print a list of available templates and continue with the entered message.
    """
    while True:
        # ask user for message
        with input_lock:
            timeout = agent.get_data("timeout") # how long the agent is willing to wait
            if not timeout: # if agent wants to wait for user input forever
                PrintStyle(background_color="#6C3483", font_color="white", bold=True, padding=True).print(f"User message ('e' to leave):")        
                import readline # this fixes arrow keys in terminal
                user_input = input("> ")
                PrintStyle(font_color="white", padding=False, log_only=True).print(f"> {user_input}") 
                
            else: # otherwise wait for user input with a timeout
                PrintStyle(background_color="#6C3483", font_color="white", bold=True, padding=True).print(f"User message ({timeout}s timeout, 'w' to wait, 'e' to leave):")        
                import readline # this fixes arrow keys in terminal
                # user_input = timed_input("> ", timeout=timeout)
                user_input = timeout_input("> ", timeout=timeout)
                                    
                if not user_input:
                    user_input = read_file("prompts/fw.msg_timeout.md")
                    PrintStyle(font_color="white", padding=False).stream(f"{user_input}")        
                else:
                    user_input = user_input.strip()
                    if user_input.lower()=="w": # the user needs more time
                        user_input = input("> ").strip()
                    PrintStyle(font_color="white", padding=False, log_only=True).print(f"> {user_input}")        

        if user_input.lower().startswith('use template'):
            template_name = user_input[12:].strip()
            templates = agent.get_data("templates")
            template = next((t for t in templates if t.name.lower() == template_name.lower()), None)
            if template:
                user_input = f"Execute template: {template.name}\nURL: {template.url}\nNavigation Goal: {template.navigation_goal}\nData Extraction Goal: {template.data_extraction_goal}"
            else:
                PrintStyle(font_color="red").print(f"Template '{template_name}' not found.")
                continue
                    
                    

        # exit the conversation when the user types 'exit'
        if user_input.lower() == 'e': break

        # send message to agent0, 
        assistant_response = agent.message_loop(user_input)
        
        # print agent0 response
        PrintStyle(font_color="white",background_color="#1D8348", bold=True, padding=True).print(f"{agent.agent_name}: reponse:")        
        PrintStyle(font_color="white").print(f"{assistant_response}")        
                        

# User intervention during agent streaming
def intervention():
    if Agent.streaming_agent and not Agent.paused:
        Agent.paused = True # stop agent streaming
        PrintStyle(background_color="#6C3483", font_color="white", bold=True, padding=True).print(f"User intervention ('e' to leave, empty to continue):")        

        import readline # this fixes arrow keys in terminal
        user_input = input("> ").strip()
        PrintStyle(font_color="white", padding=False, log_only=True).print(f"> {user_input}")        
        
        if user_input.lower() == 'e': os._exit(0) # exit the conversation when the user types 'exit'
        if user_input: Agent.streaming_agent.intervention_message = user_input # set intervention message if non-empty
        Agent.paused = False # continue agent streaming 
    

# Capture keyboard input to trigger user intervention
def capture_keys():
        global input_lock
        intervent=False            
        while True:
            if intervent: intervention()
            intervent = False
            time.sleep(0.1)
            
            if Agent.streaming_agent:
                # with raw_input, application_keypad, mouse_input:
                with input_lock, raw_input, application_keypad:
                    event: InputEvent | None = get_input_event(timeout=0.1)
                    if event and (event.shortcut.isalpha() or event.shortcut.isspace()):
                        intervent=True
                        continue

# User input with timeout
def timeout_input(prompt, timeout=10):
    return timed_input.timeout_input(prompt=prompt, timeout=timeout)

if __name__ == "__main__":
    print("Initializing framework...")

    # Start the key capture thread for user intervention during agent streaming
    threading.Thread(target=capture_keys, daemon=True).start()

    # Start the chat
    initialize()