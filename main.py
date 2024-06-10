import threading, sys, time, readline, models
from ansio import application_keypad, mouse_input, raw_input
from ansio.input import InputEvent, get_input_event
from agent import Agent
from tools.helpers.print_style import PrintStyle

input_lock = threading.Lock()

# Main conversation loop
def chat():

    # chat model used for agents
    # chat_llm = models.get_groq_llama70b(temperature=0.2)
    chat_llm = models.get_openai_gpt35()
    # chat_llm = models.get_openai_gpt4o()
    # chat_llm = models.get_anthropic_sonnet()
    # chat_llm = models.get_anthropic_haiku()
    # chat_llm = models.get_ollama_dolphin()

    # embedding model used for memory
    embedding_llm = models.get_embedding_openai()

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
        PrintStyle(background_color="#6C3483", font_color="white", bold=True, padding=True).print(f"User message ('exit' to leave):")        
        # while input_lock: time.sleep(0.1)
        with input_lock:
            user_input = input("> ").strip()

        # exit the conversation when the user types 'exit'
        if user_input.lower() == 'exit': break

        # send message to agent0, 
        assistant_response = agent0.process_message(user_input)
        
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
        if user_input.lower() == 'exit': sys.exit() # exit the conversation when the user types 'exit'
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