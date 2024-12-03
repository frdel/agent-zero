# from . import files

import json


def truncate_text(agent, output, threshold=1000):
    threshold = int(threshold)
    if not threshold or len(output) <= threshold:
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


def truncate_dict_by_ratio(agent, data: dict|list|str, threshold_chars: int, truncate_to: int):
    threshold_chars = int(threshold_chars)
    truncate_to = int(truncate_to)
    
    def process_item(item):
        if isinstance(item, dict):
            truncated_dict = {}
            cumulative_size = 0

            for key, value in item.items():
                processed_value = process_item(value)
                serialized_value = json.dumps(processed_value, ensure_ascii=False)
                size = len(serialized_value)

                if cumulative_size + size > threshold_chars:
                    truncated_dict[key] = truncate_text(
                        agent, serialized_value, truncate_to
                    )
                else:
                    cumulative_size += size
                    truncated_dict[key] = processed_value

            return truncated_dict

        elif isinstance(item, list):
            truncated_list = []
            cumulative_size = 0

            for value in item:
                processed_value = process_item(value)
                serialized_value = json.dumps(processed_value, ensure_ascii=False)
                size = len(serialized_value)

                if cumulative_size + size > threshold_chars:
                    truncated_list.append(
                        truncate_text(agent, serialized_value, truncate_to)
                    )
                else:
                    cumulative_size += size
                    truncated_list.append(processed_value)

            return truncated_list

        elif isinstance(item, str):
            if len(item) > threshold_chars:
                return truncate_text(agent, item, truncate_to)
            return item

        else:
            return item

    return process_item(data)
