from helpers import dotenv, migration, runtime, settings
import string
import random
import sys
from helpers.print_style import PrintStyle


def _retire_legacy_collabora_runtime() -> None:
    if not any(arg.lower() == "--dockerized=true" for arg in sys.argv):
        return

    try:
        from plugins._office import hooks as office_hooks

        result = office_hooks.retire_collabora_web_runtime(force=True)
    except Exception as exc:
        PrintStyle.warning("Legacy Collabora runtime cleanup failed:", exc)
        return

    if result.get("errors"):
        PrintStyle.warning("Legacy Collabora runtime cleanup reported errors:", result["errors"])
    elif result.get("removed"):
        PrintStyle.info("Legacy Collabora runtime retired:", result)


PrintStyle.standard("Preparing environment...")

migration.migrate_dotenv()
dotenv.load_dotenv()

try:

    _retire_legacy_collabora_runtime()
    runtime.initialize()

    # generate random root password if not set (for SSH)
    root_pass = dotenv.get_dotenv_value(dotenv.KEY_ROOT_PASSWORD)
    if not root_pass:
        root_pass = "".join(random.choices(string.ascii_letters + string.digits, k=32))
        PrintStyle.standard("Changing root password...")
    settings.set_root_password(root_pass)

except Exception as e:
    PrintStyle.error(f"Error in preload: {e}")
