from inputimeout import inputimeout, TimeoutOccurred

def timeout_input(prompt, timeout=15):
    try:
        import readline
        user_input = inputimeout(prompt=prompt, timeout=timeout)
        return user_input
    except TimeoutOccurred:
        return ""