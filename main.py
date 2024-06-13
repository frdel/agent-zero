import threading, sys, time, readline, models, os
from ansio import application_keypad, mouse_input, raw_input
from ansio.input import InputEvent, get_input_event
from agent import Agent
from tools.helpers.print_style import PrintStyle
from tools.helpers.files import read_file
from pytimedinput import timedInput as timed_input
from tools.helpers import files


input_lock = threading.Lock()

os.chdir(files.get_abs_path("./work_dir")) #change CWD to work_dir

# Main conversation loop
def chat():

    # chat model used for agents
    # chat_llm = models.get_groq_llama70b(temperature=0.2)
    chat_llm = models.get_openai_gpt35(temperature=0)
    # chat_llm = models.get_openai_gpt4o(temperature=0)
    # chat_llm = models.get_anthropic_opus(temperature=0)
    # chat_llm = models.get_anthropic_sonnet(temperature=0)
    # chat_llm = models.get_anthropic_haiku(temperature=0)
    # chat_llm = models.get_ollama_dolphin()

    # embedding model used for memory
    # embedding_llm = models.get_embedding_openai()
    embedding_llm = models.get_embedding_hf()

    # initial configuration
    Agent.configure(
            model_chat = chat_llm, 
            model_embedding = embedding_llm,
            #memory_subdir=""
            #memory_results=3
            )
    
    # create the first agent
    agent0 = Agent()

    # start the conversation loop  
    while True:
        # ask user for message
        with input_lock:
            timeout = agent0.get_data("timeout") # how long the agent is willing to wait
            if not timeout: # if agent wants to wait for user input forever
                PrintStyle(background_color="#6C3483", font_color="white", bold=True, padding=True).print(f"User message ('exit' to leave):")        
                user_input = input("> ")
                PrintStyle(font_color="white", padding=False, log_only=True).print(f"> {user_input}") 
                
            else: # otherwise wait for user input with a timeout
                PrintStyle(background_color="#6C3483", font_color="white", bold=True, padding=True).print(f"User message ({timeout}s timeout, 'wait' to wait, 'exit' to leave):")        
                user_input = timed_input("> ", timeout=timeout)
                                    
                if user_input[1]:
                    user_input = read_file("prompts/fw.msg_timeout.md")
                    PrintStyle(font_color="white", padding=False).stream(f"{user_input}")        
                else:
                    user_input = user_input[0].strip()
                    if user_input.lower()=="wait": # the user needs more time
                        user_input = input("> ").strip()
                    PrintStyle(font_color="white", padding=False, log_only=True).print(f"> {user_input}")        
                    
                    

        # exit the conversation when the user types 'exit'
        if user_input.lower() == 'exit': break

        # send message to agent0, 
        assistant_response = agent0.message_loop(user_input)
        
        # print agent0 response
        PrintStyle(font_color="white",background_color="#1D8348", bold=True, padding=True).print(f"{agent0.name}: reponse:")        
        PrintStyle(font_color="white").print(f"{assistant_response}")        
                        

# User intervention during agent streaming
def intervention():
    if Agent.streaming_agent and not Agent.paused:
        Agent.paused = True # stop agent streaming
        PrintStyle(background_color="#6C3483", font_color="white", bold=True, padding=True).print(f"User intervention ('exit' to leave, empty to continue):")        

        import readline
        user_input = input("> ").strip()
        PrintStyle(font_color="white", padding=False, log_only=True).print(f"> {user_input}")        
        
        if user_input.lower() == 'exit': os._exit(0) # exit the conversation when the user types 'exit'
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

if __name__ == "__main__":
    print("Initializing framework...")

    # Start the key capture thread for user intervention during agent streaming
    threading.Thread(target=capture_keys, daemon=True).start()

    # Start the chat
    chat()