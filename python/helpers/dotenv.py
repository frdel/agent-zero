import os
import re
from .files import get_abs_path
from dotenv import load_dotenv as _load_dotenv


def load_dotenv():
    _load_dotenv(get_dotenv_file_path())


def get_dotenv_file_path():
    return get_abs_path(".env")

def get_dotenv_value(key: str):
    load_dotenv()
    return os.getenv(key)

def save_dotenv_value(key: str, value: str):
    dotenv_path = get_dotenv_file_path()
    with open(dotenv_path, "r+") as f:
        lines = f.readlines()
        found = False
        for i, line in enumerate(lines):
            if re.match(rf"^\s*{key}\s*=", line):
                lines[i] = f"{key}={value}\n"
                found = True
        if not found:
            lines.append(f"\n{key}={value}")
        f.seek(0)
        f.writelines(lines)
        f.truncate()
