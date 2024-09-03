import re
import traceback
import asyncio

def handle_error(e: Exception):
    # if asyncio.CancelledError, re-raise
    if isinstance(e, asyncio.CancelledError):
        raise e
    
def format_error(e: Exception, max_entries=2):
    traceback_text = traceback.format_exc()
    # Split the traceback into lines
    lines = traceback_text.split('\n')
    
    # Find all "File" lines
    file_indices = [i for i, line in enumerate(lines) if line.strip().startswith("File ")]
    
    # If we found at least one "File" line, keep up to max_entries
    if file_indices:
        start_index = max(0, len(file_indices) - max_entries)
        trimmed_lines = lines[file_indices[start_index]:]
    else:
        # If no "File" lines found, just return the original traceback
        return traceback_text
    
    # Find the error message at the end
    error_message = ""
    for line in reversed(trimmed_lines):
        if re.match(r'\w+Error:', line):
            error_message = line
            break
    
    # Combine the trimmed traceback with the error message
    result = "Traceback (most recent call last):\n" + '\n'.join(trimmed_lines)
    if error_message:
        result += f"\n\n{error_message}"
    
    return result