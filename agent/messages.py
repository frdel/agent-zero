# agent/agent.py


class AgentContext:
    def __init__(self, prompt_reader):
        self.prompt_reader = prompt_reader

    def read_prompt(self, prompt_name, length):
        # Implement the logic to read the prompt
        # For example, you could read from a file or a database
        # This is a placeholder implementation
        return f"{{{prompt_name} with length {length}}}"


# from . import files


def truncate_text(agent, output, threshold=1000):
    if len(output) <= threshold:
        return output

    # Adjust the file path as needed
    placeholder = agent.read_prompt(
        "fw.msg_truncated.md", length=(len(output) - threshold)
    )
    # placeholder = files.read_file("./prompts/default/fw.msg_truncated.md", length=(len(output) - threshold))

    start_len = (threshold - len(placeholder)) // 2
    end_len = threshold - len(placeholder) - start_len

    truncated_output = output[:start_len] + placeholder + output[-end_len:]
    return truncated_output
