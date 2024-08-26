import threading
import time
import models
import os
from agent import Agent, AgentConfig
from python.helpers.print_style import PrintStyle
from python.helpers.files import read_file
from python.helpers import files
import python.helpers.timed_input as timed_input

# Check if the 'ansio' module is available; if not, handle input differently
try:
    from ansio import application_keypad, mouse_input, raw_input
    from ansio.input import InputEvent, get_input_event
except ImportError:
    import sys
    sys.stderr.write("Warning: 'ansio' module not found. Input handling will be limited.\n")
    application_keypad = mouse_input = raw_input = None
    InputEvent = get_input_event = None

input_lock = threading.Lock()
os.chdir(files.get_abs_path("./work_dir"))  # Change CWD to work_dir

def initialize():
    # Main chat model used by agents (smarter, more accurate)
    chat_llm = models.get_openai_chat(model_name="gpt-4o-mini", temperature=0)
    utility_llm = chat_llm
    embedding_llm = models.get_openai_embedding(model_name="text-embedding-3-small")

    # Agent configuration
    config = AgentConfig(
        chat_model=chat_llm,
        utility_model=utility_llm,
        embeddings_model=embedding_llm,
        code_exec_docker_enabled=True,
        code_exec_ssh_enabled=True,
    )

    # Create the first agent
    agent0 = Agent(number=0, config=config)

    # Start the chat loop
    chat(agent0)

def analyze_sentiment(text):
    from textblob import TextBlob
    blob = TextBlob(text)
    return blob.sentiment.polarity

def extract_entities(text):
    import spacy
    nlp = spacy.load("en_core_web_sm")
    doc = nlp(text)
    return [(ent.text, ent.label_) for ent in doc.ents]

def chat(agent: Agent):
    while True:
        with input_lock:
            timeout = agent.get_data("timeout")
            if not timeout:
                PrintStyle(background_color="#6C3483", font_color="white", bold=True, padding=True).print(f"User message ('e' to leave):")
                import readline
                user_input = input("> ")
                PrintStyle(font_color="white", padding=False, log_only=True).print(f"> {user_input}")
            else:
                PrintStyle(background_color="#6C3483", font_color="white", bold=True, padding=True).print(f"User message ({timeout}s timeout, 'w' to wait, 'e' to leave):")
                import readline
                user_input = timeout_input("> ", timeout=timeout)
                
                if not user_input:
                    user_input = read_file("prompts/fw.msg_timeout.md")
                    PrintStyle(font_color="white", padding=False).stream(f"{user_input}")
                else:
                    user_input = user_input.strip()
                    if user_input.lower() == "w":
                        user_input = input("> ").strip()
                    PrintStyle(font_color="white", padding=False, log_only=True).print(f"> {user_input}")

        if user_input.lower() == 'e':
            break

        sentiment = analyze_sentiment(user_input)
        entities = extract_entities(user_input)

        PrintStyle(font_color="cyan").print(f"Sentiment: {sentiment}")
        PrintStyle(font_color="cyan").print(f"Entities: {entities}")

        assistant_response = agent.message_loop(user_input)
        PrintStyle(font_color="white", background_color="#1D8348", bold=True, padding=True).print(f"{agent.agent_name}: response:")
        PrintStyle(font_color="white").print(f"{assistant_response}")

def intervention():
    if Agent.streaming_agent and not Agent.paused:
        Agent.paused = True
        PrintStyle(background_color="#6C3483", font_color="white", bold=True, padding=True).print(f"User intervention ('e' to leave, empty to continue):")
        import readline
        user_input = input("> ").strip()
        PrintStyle(font_color="white", padding=False, log_only=True).print(f"> {user_input}")
        if user_input.lower() == 'e':
            os._exit(0)
        if user_input:
            Agent.streaming_agent.intervention_message = user_input
        Agent.paused = False

def capture_keys():
    global input_lock
    intervent = False
    while True:
        if intervent:
            intervention()
        intervent = False
        time.sleep(0.1)
        if Agent.streaming_agent:
            with input_lock:
                if application_keypad and mouse_input and raw_input and get_input_event:
                    event: InputEvent | None = get_input_event(timeout=0.1)
                    if event and (event.shortcut.isalpha() or event.shortcut.isspace()):
                        intervent = True
                        continue

def timeout_input(prompt, timeout=10):
    return timed_input.timeout_input(prompt=prompt, timeout=timeout)

if __name__ == "__main__":
    print("Initializing framework...")
    threading.Thread(target=capture_keys, daemon=True).start()
    initialize()
