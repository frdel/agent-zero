import threading, time, models, os
from ansio import application_keypad, mouse_input, raw_input
from ansio.input import InputEvent, get_input_event
from agent import Agent, AgentConfig
from python.helpers.print_style import PrintStyle
from python.helpers.files import read_file
from python.helpers import files
import python.helpers.timed_input as timed_input


input_lock = threading.Lock()
os.chdir(files.get_abs_path("./work_dir")) #change CWD to work_dir


def initialize():
    
    # main chat model used by agents (smarter, more accurate)

    # chat_llm = models.get_groq_llama70b(temperature=0.2)
    # chat_llm = models.get_groq_llama70b_json(temperature=0.2)
    # chat_llm = models.get_groq_llama8b(temperature=0.2)
    # chat_llm = models.get_openai_gpt35(temperature=0)
    # chat_llm = models.get_openai_gpt4o(temperature=0)
    chat_llm = models.get_openai_chat(temperature=0)
    # chat_llm = models.get_anthropic_opus(temperature=0)
    # chat_llm = models.get_anthropic_sonnet(temperature=0)
    # chat_llm = models.get_anthropic_sonnet_35(temperature=0)
    # chat_llm = models.get_anthropic_haiku(temperature=0)
    # chat_llm = models.get_ollama_dolphin()
    # chat_llm = models.get_ollama(model_name="gemma2:27b")
    # chat_llm = models.get_ollama(model_name="llama3:8b-text-fp16")
    # chat_llm = models.get_ollama(model_name="gemma2:latest")
    # chat_llm = models.get_ollama(model_name="qwen:14b")
    # chat_llm = models.get_google_chat()
    # chat_llm = models.get_azure_openai_gpt4o(temperature=0)


    # utility model used for helper functions (cheaper, faster)
    utility_llm = models.get_openai_chat(temperature=0)
    # utility_llm = models.get_azure_openai_gpt35(temperature=0)
    
    # embedding model used for memory
    embedding_llm = models.get_embedding_openai()
    # embedding_llm = models.get_azure_openai_embedding()
    # embedding_llm = models.get_embedding_hf()

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
        # code_exec_docker_name = "agent-zero-exe",
        # code_exec_docker_image = "frdel/agent-zero-exe:latest",
        # code_exec_docker_ports = { "22/tcp": 50022 }
        # code_exec_docker_volumes = { files.get_abs_path("work_dir"): {"bind": "/root", "mode": "rw"} }
        code_exec_ssh_enabled = True,
        # code_exec_ssh_addr = "localhost",
        # code_exec_ssh_port = 50022,
        # code_exec_ssh_user = "root",
        # code_exec_ssh_pass = "toor",
        # additional = {},
    )
    
    # create the first agent
    agent0 = Agent( number = 0, config = config )

    # start the chat loop
    chat(agent0)


# Main conversation loop
def chat(agent:Agent):
    
    # start the conversation loop  
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