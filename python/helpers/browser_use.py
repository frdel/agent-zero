from python.helpers import env_helper as dotenv
dotenv.save_dotenv_value("ANONYMIZED_TELEMETRY", "false")
import browser_use
import browser_use.utils