import re
import sys
import time

def sanitize_string(s: str, encoding: str = "utf-8") -> str:
    # Replace surrogates and invalid unicode with replacement character
    if not isinstance(s, str):
        s = str(s)
    return s.encode(encoding, 'replace').decode(encoding, 'replace')

def calculate_valid_match_lengths(first: bytes | str, second: bytes | str, 
                                  deviation_threshold: int = 5, 
                                  deviation_reset: int = 5, 
                                  ignore_patterns: list[bytes|str] = [],
                                  debug: bool = False) -> tuple[int, int]:
    
    first_length = len(first)
    second_length = len(second)

    i, j = 0, 0
    deviations = 0
    matched_since_deviation = 0
    last_matched_i, last_matched_j = 0, 0  # Track the last matched index

    def skip_ignored_patterns(s, index):
        """Skip characters in `s` that match any pattern in `ignore_patterns` starting from `index`."""
        while index < len(s):
            for pattern in ignore_patterns:
                match = re.match(pattern, s[index:])
                if match:
                    index += len(match.group(0))
                    break
            else:
                break
        return index

    while i < first_length and j < second_length:
        # Skip ignored patterns
        i = skip_ignored_patterns(first, i)
        j = skip_ignored_patterns(second, j)

        if i < first_length and j < second_length and first[i] == second[j]:
            last_matched_i, last_matched_j = i + 1, j + 1  # Update last matched position
            i += 1
            j += 1
            matched_since_deviation += 1

            # Reset the deviation counter if we've matched enough characters since the last deviation
            if matched_since_deviation >= deviation_reset:
                deviations = 0
                matched_since_deviation = 0
        else:
            # Determine the look-ahead based on the remaining deviation threshold
            look_ahead = deviation_threshold - deviations

            # Look ahead to find the best match within the remaining deviation allowance
            best_match = None
            for k in range(1, look_ahead + 1):
                if i + k < first_length and j < second_length and first[i + k] == second[j]:
                    best_match = ('i', k)
                    break
                if j + k < second_length and i < first_length and first[i] == second[j + k]:
                    best_match = ('j', k)
                    break

            if best_match:
                if best_match[0] == 'i':
                    i += best_match[1]
                elif best_match[0] == 'j':
                    j += best_match[1]
            else:
                i += 1
                j += 1

            deviations += 1
            matched_since_deviation = 0

            if deviations > deviation_threshold:
                break

        if debug:
            output = (
                f"First (up to {last_matched_i}): {first[:last_matched_i]!r}\n"
                "\n"
                f"Second (up to {last_matched_j}): {second[:last_matched_j]!r}\n"
                "\n"
                f"Current deviation: {deviations}\n"
                f"Matched since last deviation: {matched_since_deviation}\n"
                + "-" * 40 + "\n"
            )
            sys.stdout.write("\r" + output)
            sys.stdout.flush()
            time.sleep(0.01)  # Add a short delay for readability (optional)

    # Return the last matched positions instead of the current indices
    return last_matched_i, last_matched_j

def format_key(key: str) -> str:
    """Format a key string to be more readable.
    Converts camelCase and snake_case to Title Case with spaces."""
    # First replace non-alphanumeric with spaces
    result = ''.join(' ' if not c.isalnum() else c for c in key)
    
    # Handle camelCase
    formatted = ''
    for i, c in enumerate(result):
        if i > 0 and c.isupper() and result[i-1].islower():
            formatted += ' ' + c
        else:
            formatted += c
            
    # Split on spaces and capitalize each word
    return ' '.join(word.capitalize() for word in formatted.split())

def dict_to_text(d: dict) -> str:
    parts = []
    for key, value in d.items():
        parts.append(f"{format_key(str(key))}:")
        parts.append(f"{value}")
        parts.append("")  # Add empty line between entries
    
    return "\n".join(parts).rstrip()  # rstrip to remove trailing newline

def truncate_text(text: str, length: int, at_end: bool = True, replacement: str = "...") -> str:
    orig_length = len(text)
    if orig_length <= length:
        return text
    if at_end:
         return text[:length] + replacement
    else:
        return replacement + text[-length:]
    