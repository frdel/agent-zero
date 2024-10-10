# from . import files

def truncate_text(agent, output, threshold=1000):
    if len(output) <= threshold:
        return output

    # Adjust the file path as needed
    placeholder = agent.read_prompt("fw.msg_truncated.md", length=(len(output) - threshold))
    # placeholder = files.read_file("./prompts/default/fw.msg_truncated.md", length=(len(output) - threshold))

    start_len = (threshold - len(placeholder)) // 2
    end_len = threshold - len(placeholder) - start_len

    truncated_output = output[:start_len] + placeholder + output[-end_len:]
    return truncated_output