import threading
import time
import models
import os
from typing import TYPE_CHECKING, Optional, Callable, Any, Union, cast

if TYPE_CHECKING:
    from ansio import application_keypad  # type: ignore
    from ansio.input import InputEvent, get_input_event  # type: ignore
else:
    try:
        from ansio import application_keypad  # type: ignore
        from ansio.input import InputEvent, get_input_event  # type: ignore
    except ImportError:
        application_keypad = None
        InputEvent = None
        get_input_event = None

from agent import Agent, AgentConfig
from python.helpers.print_style import PrintStyle
from python.helpers.files import read_file
from python.helpers import files
import python.helpers.timed_input as timed_input


input_lock = threading.Lock()
os.chdir(files.get_abs_path("./work_dir"))  # change CWD to work_dir

# Custom types for conditionally imported variables
AppKeypadType = Union[Callable[[], Any], None]
GetInputEventType = Union[Callable[[], Optional[Any]], None]

# Assign the imported variables to our custom types
app_keypad: AppKeypadType = globals().get("application_keypad")
get_input_event_func: GetInputEventType = globals().get("get_input_event")


def initialize() -> None:
    # main chat model used by agents (smarter, more accurate)
    chat_llm = models.get_openai_chat(model_name="gpt-4o-mini", temperature=0)

    # utility model used for helper functions (cheaper, faster)
    utility_llm = chat_llm  # change if you want to use a different utility model

    # embedding model used for memory
    embedding_llm = models.get_openai_embedding(model_name="text-embedding-3-small")

    # agent configuration
    config = AgentConfig(
        chat_model=chat_llm,
        utility_model=utility_llm,
        embeddings_model=embedding_llm,
        auto_memory_count=0,
        code_exec_docker_enabled=True,
        code_exec_ssh_enabled=True,
    )

    # create the first agent
    agent0 = Agent(number=0, config=config)

    # start the chat loop
    chat(agent0)


# Main conversation loop
def chat(agent: Agent) -> None:
    # start the conversation loop
    while True:
        # ask user for message
        with input_lock:
            timeout: Optional[int] = getattr(agent.config, "timeout", None)
            if timeout is None:  # if agent wants to wait for user input forever
                PrintStyle(
                    background_color="#6C3483",
                    font_color="white",
                    bold=True,
                    padding=True,
                ).print("User message ('e' to leave):")
                user_input: Optional[str] = input("> ")
                PrintStyle(font_color="white", padding=False, log_only=True).print(
                    f"> {user_input}"
                )
            else:  # otherwise wait for user input with a timeout
                PrintStyle(
                    background_color="#6C3483",
                    font_color="white",
                    bold=True,
                    padding=True,
                ).print(
                    f"User message ({timeout}s timeout, 'w' to wait, 'e' to leave):"
                )
                user_input = timeout_input("> ", timeout=timeout)

                if user_input is None:
                    user_input = read_file("prompts/fw.msg_timeout.md")
                    PrintStyle(font_color="white", padding=False).stream(
                        f"{user_input}"
                    )
                else:
                    user_input = user_input.strip()
                    if user_input.lower() == "w":  # the user needs more time
                        user_input = input("> ").strip()
                    PrintStyle(font_color="white", padding=False, log_only=True).print(
                        f"> {user_input}"
                    )

        # exit the conversation when the user types 'exit'
        if user_input is not None and user_input.lower() == "e":
            break

        # send message to agent0,
        message_loop = getattr(agent, "message_loop", lambda _: "")
        assistant_response = message_loop(cast(str, user_input))

        # print agent0 response
        PrintStyle(
            font_color="white", background_color="#1D8348", bold=True, padding=True
        ).print(f"{agent.agent_name}: response:")
        PrintStyle(font_color="white").print(f"{assistant_response}")


# User intervention during agent streaming
def intervention() -> None:
    if getattr(Agent, "streaming_agent", None) and not getattr(Agent, "paused", False):
        Agent.paused = True  # type: ignore
        PrintStyle(
            background_color="#6C3483", font_color="white", bold=True, padding=True
        ).print("User intervention ('e' to leave, empty to continue):")

        user_input = input("> ").strip()
        PrintStyle(font_color="white", padding=False, log_only=True).print(
            f"> {user_input}"
        )

        if user_input.lower() == "e":
            os._exit(0)  # exit the conversation when the user types 'exit'
        if user_input:
            if getattr(Agent, "streaming_agent", None):
                Agent.streaming_agent.intervention_message = user_input  # type: ignore
        Agent.paused = False  # type: ignore


# Capture keyboard input to trigger user intervention
def capture_keys() -> None:
    intervent = False
    while True:
        if intervent:
            intervention()
        intervent = False
        time.sleep(0.1)

        if (
            getattr(Agent, "streaming_agent", None)
            and app_keypad
            and get_input_event_func
        ):
            with input_lock:
                with app_keypad():
                    event = get_input_event_func()
                    if (
                        event
                        and hasattr(event, "shortcut")
                        and (event.shortcut.isalpha() or event.shortcut.isspace())
                    ):
                        intervent = True
                        continue


# User input with timeout
def timeout_input(prompt: str, timeout: int = 10) -> Optional[str]:
    return timed_input.timeout_input(prompt=prompt, timeout=timeout)


if __name__ == "__main__":
    print("Initializing framework...")

    # Start the key capture thread for user intervention during agent streaming
    threading.Thread(target=capture_keys, daemon=True).start()

    # Start the chat
    initialize()
