import subprocess
from python.helpers import dotenv, runtime, settings
import string
import random

print("Preparing environment...")

# generate random root password if not set (for SSH)
root_pass = dotenv.get_dotenv_value(dotenv.KEY_ROOT_PASSWORD)
if not root_pass:
    root_pass = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
    dotenv.save_dotenv_value(dotenv.KEY_ROOT_PASSWORD, root_pass)
print("Changing root password...")
settings.set_root_password(root_pass)