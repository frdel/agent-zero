from . import files


def truncate_text(output, threshold=1000):
    if len(output) <= threshold:
        return output

    # Adjust the file path as needed
    placeholder = files.read_file("./prompts/fw.msg_truncated.md", removed_chars=(len(output) - threshold))

    start_len = (threshold - len(placeholder)) // 2
    end_len = threshold - len(placeholder) - start_len

    truncated_output = output[:start_len] + placeholder + output[-end_len:]
    return truncated_output