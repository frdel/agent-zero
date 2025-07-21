import os
import re
from typing import Dict, Optional
from .files import get_abs_path
from .dotenv import get_dotenv_value, save_dotenv_value

class SecretsManager:
    SECRETS_FILE = "tmp/secrets.env"
    PLACEHOLDER_PATTERN = r"§§([A-Z_][A-Z0-9_]*)§§"
    MASK_VALUE = "***"

    _instance: Optional["SecretsManager"] = None
    _secrets_cache: Optional[Dict[str, str]] = None

    @classmethod
    def get_instance(cls) -> "SecretsManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.secrets_file_path = get_abs_path(self.SECRETS_FILE)

    def load_secrets(self) -> Dict[str, str]:
        """Load secrets from file, return key-value dict"""
        if self._secrets_cache is not None:
            return self._secrets_cache

        secrets = {}
        if os.path.exists(self.secrets_file_path):
            with open(self.secrets_file_path, 'r') as f:
                content = f.read()
                secrets = self._parse_env_content(content)

        self._secrets_cache = secrets
        return secrets

    def save_secrets(self, secrets_content: str):
        """Save secrets content to file and update cache"""
        os.makedirs(os.path.dirname(self.secrets_file_path), exist_ok=True)
        with open(self.secrets_file_path, 'w') as f:
            f.write(secrets_content)

        # Update cache
        self._secrets_cache = self._parse_env_content(secrets_content)

    def get_keys(self) -> list[str]:
        """Get list of secret keys"""
        secrets = self.load_secrets()
        return list(secrets.keys())

    def get_secrets_for_prompt(self) -> str:
        """Get formatted string of secret keys for system prompt"""
        keys = self.get_keys()
        if not keys:
            return ""

        keys_list = ", ".join([f"§§{key}§§" for key in keys])
        return f"Available secret placeholders: {keys_list}"

    def replace_placeholders(self, text: str) -> str:
        """Replace secret placeholders with actual values"""
        if not text:
            return text

        secrets = self.load_secrets()

        def replacer(match):
            key = match.group(1)
            if key in secrets:
                return secrets[key]
            else:
                # Try common variations for user convenience
                variations = self._get_key_variations(key)
                for variation in variations:
                    if variation in secrets:
                        return secrets[variation]

                from agent import RepairableException
                # Show both the original key and available alternatives
                available_keys = ', '.join(secrets.keys())
                suggested_variations = [f"§§{var}§§" for var in variations if var in secrets]

                error_msg = f"Secret placeholder '§§{key}§§' not found in secrets store.\n"
                error_msg += f"Available secrets: {available_keys}"

                if suggested_variations:
                    error_msg += f"\nDid you mean: {', '.join(suggested_variations)}?"

                raise RepairableException(error_msg)

        return re.sub(self.PLACEHOLDER_PATTERN, replacer, text)

    def _get_key_variations(self, key: str) -> list[str]:
        """Generate common variations of a key name for better UX"""
        variations = []

        # Common API key variations
        if key == "OPENAI_API_KEY":
            variations.extend(["API_KEY_OPENAI", "OPENAI_KEY", "OPENAI"])
        elif key == "API_KEY_OPENAI":
            variations.extend(["OPENAI_API_KEY", "OPENAI_KEY", "OPENAI"])
        elif key == "ANTHROPIC_API_KEY":
            variations.extend(["API_KEY_ANTHROPIC", "ANTHROPIC_KEY", "ANTHROPIC"])
        elif key == "API_KEY_ANTHROPIC":
            variations.extend(["ANTHROPIC_API_KEY", "ANTHROPIC_KEY", "ANTHROPIC"])
        elif key == "GOOGLE_API_KEY":
            variations.extend(["API_KEY_GOOGLE", "GOOGLE_KEY", "GOOGLE"])
        elif key == "API_KEY_GOOGLE":
            variations.extend(["GOOGLE_API_KEY", "GOOGLE_KEY", "GOOGLE"])

        # General pattern variations
        if "_API_KEY" in key:
            # Convert SERVICE_API_KEY to API_KEY_SERVICE
            service = key.replace("_API_KEY", "")
            variations.append(f"API_KEY_{service}")
        elif "API_KEY_" in key:
            # Convert API_KEY_SERVICE to SERVICE_API_KEY
            service = key.replace("API_KEY_", "")
            variations.append(f"{service}_API_KEY")

        return variations

    def mask_values(self, text: str) -> str:
        """Replace actual secret values with placeholders in text"""
        if not text:
            return text

        secrets = self.load_secrets()
        result = text

        # Sort by length (longest first) to avoid partial replacements
        for key, value in sorted(secrets.items(), key=lambda x: len(x[1]), reverse=True):
            if value and len(value.strip()) > 0:
                result = result.replace(value, f"§§{key}§§")

        return result

    def get_masked_content(self, content: str) -> str:
        """Get content with values masked for frontend display"""
        if not content:
            return ""

        secrets = self._parse_env_content(content)
        lines = []

        for line in content.splitlines():
            if '=' in line and not line.strip().startswith('#'):
                key_part = line.split('=', 1)[0]
                key = key_part.strip()
                if key in secrets and secrets[key]:
                    lines.append(f"{key_part}={self.MASK_VALUE}")
                else:
                    lines.append(line)
            else:
                lines.append(line)

        return '\n'.join(lines)

    def _parse_env_content(self, content: str) -> Dict[str, str]:
        """Parse .env format content into key-value dict"""
        secrets = {}
        line_pattern = re.compile(r"\s*([^#][^=]*)\s*=\s*(.*)")

        for line in content.splitlines():
            match = line_pattern.match(line)
            if match:
                key, value = match.groups()
                # Remove optional surrounding quotes
                value = value.strip().strip('"').strip("'")
                secrets[key.strip()] = value

        return secrets

    def clear_cache(self):
        """Clear the secrets cache"""
        self._secrets_cache = None