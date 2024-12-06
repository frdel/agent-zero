from python.helpers import dotenv, runtime, settings
import string
import random

print("Preparing environment...")

try:

    runtime.initialize()

    # generate random root password if not set (for SSH)
    root_pass = dotenv.get_dotenv_value(dotenv.KEY_ROOT_PASSWORD)
    if not root_pass:
        root_pass = "".join(random.choices(string.ascii_letters + string.digits, k=32))
    print("Changing root password...")
    settings.set_root_password(root_pass)

except Exception as e:
    print(f"Error in preload: {e}")
