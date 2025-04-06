import sys
from inputimeout import inputimeout, TimeoutOccurred

def timeout_input(prompt, timeout=10):
    try:
        if sys.platform != "win32": import readline
        user_input = inputimeout(prompt=prompt, timeout=timeout)
        return user_input
    except TimeoutOccurred:
        return ""