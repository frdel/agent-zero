from .files import get_abs_path
from dotenv import load_dotenv as _load_dotenv

def load_dotenv():
    dotenv_path = get_abs_path(".env")
    _load_dotenv(dotenv_path)