import os, re, sys

def read_file(relative_path, **kwargs):
    absolute_path = get_abs_path(relative_path)  # Construct the absolute path to the target file

    with open(absolute_path) as f:
        content = remove_code_fences(f.read())

    # Replace placeholders with values from kwargs
    for key, value in kwargs.items():
        placeholder = "{{" + key + "}}"
        strval = str(value)
        # strval = strval.encode('unicode_escape').decode('utf-8')
        # content = re.sub(re.escape(placeholder), strval, content)
        content = content.replace(placeholder, strval)

    return content

def remove_code_fences(text):
    return re.sub(r'~~~\w*\n|~~~', '', text)

def get_abs_path(*relative_paths):
    return os.path.join(get_base_dir(), *relative_paths)

def exists(*relative_paths):
    path = get_abs_path(*relative_paths)
    return os.path.exists(path)


def get_base_dir():
    # Get the base directory from the current file path
    base_dir = os.path.dirname(os.path.abspath(os.path.join(__file__,"../../")))
    return base_dir