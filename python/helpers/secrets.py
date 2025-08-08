import re
import threading
import base64
import time
from dataclasses import dataclass
from typing import Dict, Optional, List, Literal
from python.helpers.rfc_files import (
    get_abs_path,
    read_file_base64,
    write_file_base64,
)
from python.helpers.errors import RepairableException


@dataclass
class EnvLine:
    raw: str
    type: Literal["pair", "comment", "blank", "other"]
    key: Optional[str] = None
    value: Optional[str] = None
    key_part: Optional[str] = None  # original left side including whitespace up to '='


class StreamingSecretsFilter:
    """Stateful streaming filter that masks secrets on the fly.

    - Replaces full secret values with placeholders §§KEY§§ when detected.
    - Holds the longest suffix of the current buffer that matches any secret prefix
      (with minimum trigger length of 3) to avoid leaking partial secrets across chunks.
    - On finalize(), any unresolved partial is masked with '***'.
    """

    def __init__(self, key_to_value: Dict[str, str], min_trigger: int = 3):
        self.min_trigger = max(1, int(min_trigger))
        # Map value -> key for placeholder construction
        self.value_to_key: Dict[str, str] = {
            v: k for k, v in key_to_value.items() if isinstance(v, str) and v
        }
        # Only keep non-empty values
        self.secret_values: List[str] = [v for v in self.value_to_key.keys() if v]
        # Precompute all prefixes for quick suffix matching
        self.prefixes: set[str] = set()
        for v in self.secret_values:
            for i in range(self.min_trigger, len(v) + 1):
                self.prefixes.add(v[:i])
        self.max_len: int = max((len(v) for v in self.secret_values), default=0)

        # Internal buffer of pending text that is not safe to flush yet
        self.pending: str = ""

    def _replace_full_values(self, text: str) -> str:
        """Replace all full secret values with placeholders in the given text."""
        # Sort by length desc to avoid partial overlaps
        for val in sorted(self.secret_values, key=len, reverse=True):
            if not val:
                continue
            key = self.value_to_key.get(val, "")
            if key:
                text = text.replace(val, f"§§{key}§§")
        return text

    def _longest_suffix_prefix(self, text: str) -> int:
        """Return length of longest suffix of text that is a known secret prefix.
        Returns 0 if none found (or only shorter than min_trigger)."""
        max_check = min(len(text), self.max_len)
        for length in range(max_check, self.min_trigger - 1, -1):
            suffix = text[-length:]
            if suffix in self.prefixes:
                return length
        return 0

    def process_chunk(self, chunk: str) -> str:
        if not chunk:
            return ""

        self.pending += chunk

        # Replace any full secret occurrences first
        self.pending = self._replace_full_values(self.pending)

        # Determine the longest suffix that could still form a secret
        hold_len = self._longest_suffix_prefix(self.pending)
        if hold_len > 0:
            # Flush everything except the hold suffix
            emit = self.pending[:-hold_len]
            self.pending = self.pending[-hold_len:]
        else:
            # Safe to flush everything
            emit = self.pending
            self.pending = ""

        return emit

    def finalize(self) -> str:
        """Flush any remaining buffered text. If pending contains an unresolved partial
        (i.e., a prefix of a secret >= min_trigger), mask it with *** to avoid leaks."""
        if not self.pending:
            return ""

        hold_len = self._longest_suffix_prefix(self.pending)
        if hold_len > 0:
            safe = self.pending[:-hold_len]
            # Mask unresolved partial
            result = safe + "***"
        else:
            result = self.pending
        self.pending = ""
        return result


class SecretsManager:
    SECRETS_FILE = "tmp/secrets.env"
    PLACEHOLDER_PATTERN = r"§§([A-Z_][A-Z0-9_]*)§§"
    MASK_VALUE = "***"

    _instance: Optional["SecretsManager"] = None
    _secrets_cache: Optional[Dict[str, str]] = None
    _last_raw_text: Optional[str] = None

    @classmethod
    def get_instance(cls) -> "SecretsManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._lock = threading.RLock()
        # instance-level override for secrets file
        self._secrets_file_rel = self.SECRETS_FILE
        self.secrets_file_path = get_abs_path(self._secrets_file_rel)

    def set_secrets_file(self, relative_path: str):
        """Override the relative secrets file location (useful for tests)."""
        with self._lock:
            self._secrets_file_rel = relative_path
            self.secrets_file_path = get_abs_path(self._secrets_file_rel)
            self.clear_cache()

    def read_secrets_raw(self) -> str:
        """Read raw secrets file content via RFC wrappers (inside container)."""
        attempts = 3
        delay = 0.15
        last_exc: Exception | None = None
        for _ in range(attempts):
            try:
                b64 = read_file_base64(self._secrets_file_rel)
                content = base64.b64decode(b64.encode("utf-8")).decode("utf-8")
                # snapshot full raw, including comments and non-pair lines
                self._last_raw_text = content
                return content
            except FileNotFoundError:
                self._last_raw_text = ""
                return ""
            except Exception as e:
                last_exc = e
                time.sleep(delay)
                delay *= 1.5
        # After retries, try a local filesystem fallback before raising
        try:
            abs_path = get_abs_path(self._secrets_file_rel)
            with open(abs_path, "rb") as f:
                content = f.read().decode("utf-8")
                self._last_raw_text = content
                return content
        except FileNotFoundError:
            self._last_raw_text = ""
            return ""
        except Exception:
            if last_exc:
                raise last_exc
            return ""

    def _write_secrets_raw(self, content: str):
        """Write raw secrets file content via RFC wrappers (inside container)."""
        b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        attempts = 3
        delay = 0.15
        last_exc: Exception | None = None
        for _ in range(attempts):
            try:
                write_file_base64(self._secrets_file_rel, b64)
                return
            except Exception as e:
                last_exc = e
                time.sleep(delay)
                delay *= 1.5
        # Local fallback write before raising
        try:
            abs_path = get_abs_path(self._secrets_file_rel)
            import os
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, "wb") as f:
                f.write(content.encode("utf-8"))
            return
        except Exception:
            if last_exc:
                raise last_exc
            raise

    def load_secrets(self) -> Dict[str, str]:
        """Load secrets from file, return key-value dict"""
        with self._lock:
            if self._secrets_cache is not None:
                return self._secrets_cache

            secrets: Dict[str, str] = {}
            try:
                content = self.read_secrets_raw()
                # keep raw snapshot for future save merge without reading again
                self._last_raw_text = content
                if content:
                    secrets = self.parse_env_content(content)
            except Exception:
                # On unexpected RFC failure, keep empty cache rather than crash
                secrets = {}

            self._secrets_cache = secrets
            return secrets

    def save_secrets(self, secrets_content: str):
        """Save secrets content to file and update cache"""
        with self._lock:
            # Ensure write through RFC wrappers (UTF-8)
            self._write_secrets_raw(secrets_content)
            # Update cache
            self._secrets_cache = self.parse_env_content(secrets_content)
            # Update raw snapshot
            self._last_raw_text = secrets_content

    def save_secrets_with_merge(self, submitted_content: str):
        """Merge submitted content with existing file preserving comments, order and supporting deletion.
        - Existing keys keep their value when submitted as MASK_VALUE (***).
        - Keys present in existing but omitted from submitted are deleted.
        - New keys with non-masked values are appended at the end.
        """
        with self._lock:
            # Prefer in-memory snapshot to avoid disk reads during save
            if self._last_raw_text is not None:
                existing_text = self._last_raw_text
            else:
                try:
                    existing_text = self.read_secrets_raw()
                except Exception as e:
                    # If read fails and submitted contains masked values, abort to avoid losing values/comments
                    if self.MASK_VALUE in submitted_content:
                        raise RepairableException(
                            "Saving secrets failed because existing secrets could not be read to preserve masked values and comments. Please retry."
                        ) from e
                    # No masked values, safe to treat as new file
                    existing_text = ""
            merged_lines = self._merge_env(existing_text, submitted_content)
            merged_text = self._serialize_env_lines(merged_lines)
            self.save_secrets(merged_text)

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

    def create_streaming_filter(self) -> StreamingSecretsFilter:
        """Create a streaming-aware secrets filter snapshotting current secret values."""
        return StreamingSecretsFilter(self.load_secrets())

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
        """Get content with values masked for frontend display (preserves comments and unrecognized lines)"""
        if not content:
            return ""

        # Parse content for known keys
        secrets = self.parse_env_content(content)
        lines_out: List[str] = []

        for line in content.splitlines():
            if '=' in line and not re.match(r"^\s*#", line):
                key_part = line.split('=', 1)[0]
                key = key_part.strip()
                if key in secrets and secrets[key] != "":
                    lines_out.append(f"{key_part}={self.MASK_VALUE}")
                else:
                    lines_out.append(line)
            else:
                lines_out.append(line)

        return '\n'.join(lines_out)

    def parse_env_content(self, content: str) -> Dict[str, str]:
        """Parse .env format content into key-value dict (ignores comments but does not rely on skipping them in regex)."""
        env: Dict[str, str] = {}
        for env_line in self.parse_env_lines(content):
            if env_line.type == "pair" and env_line.key is not None:
                env[env_line.key] = env_line.value or ""
        return env

    # Backward-compatible alias for callers using the old private method name
    def _parse_env_content(self, content: str) -> Dict[str, str]:
        return self.parse_env_content(content)

    def clear_cache(self):
        """Clear the secrets cache"""
        with self._lock:
            self._secrets_cache = None

    # ---------------- Internal helpers for parsing/merging ----------------

    def parse_env_lines(self, content: str) -> List[EnvLine]:
        """Parse env file into a list of EnvLine objects preserving comments and order."""
        lines: List[EnvLine] = []
        # Pair: not starting with '#' or '=', capture original key part and value
        pair_re = re.compile(r"^(\s*[^#=\s][^=]*?)\s*=\s*(.*)$")
        comment_re = re.compile(r"^\s*#(.*)$")

        for raw in content.splitlines():
            if raw.strip() == "":
                lines.append(EnvLine(raw=raw, type="blank"))
                continue

            m_pair = pair_re.match(raw)
            if m_pair:
                key_part = m_pair.group(1)
                value = m_pair.group(2)
                key = key_part.strip()
                # Remove optional surrounding quotes
                value = value.strip().strip('"').strip("'")
                lines.append(
                    EnvLine(raw=raw, type="pair", key=key, value=value, key_part=key_part)
                )
                continue

            if comment_re.match(raw):
                lines.append(EnvLine(raw=raw, type="comment"))
                continue

            lines.append(EnvLine(raw=raw, type="other"))

        return lines

    def _serialize_env_lines(self, lines: List[EnvLine]) -> str:
        out: List[str] = []
        for ln in lines:
            if ln.type == "pair" and ln.key is not None:
                left = ln.key_part if ln.key_part is not None else ln.key
                val = ln.value if ln.value is not None else ""
                out.append(f"{left}={val}")
            else:
                out.append(ln.raw)
        return "\n".join(out)

    def _merge_env(self, existing_text: str, submitted_text: str) -> List[EnvLine]:
        """Merge using submitted content as the base to preserve its comments and structure.
        Behavior:
        - Iterate submitted lines in order and keep them (including comments/blanks/other).
        - For pair lines:
            - If key exists in existing and submitted value is MASK_VALUE (***), use existing value.
            - If key is new and value is MASK_VALUE, skip (ignore masked-only additions).
            - Otherwise, use submitted value as-is.
        - Keys present only in existing and not in submitted are deleted (not added).
        This preserves comments and arbitrary lines from the submitted content and persists them.
        """
        existing_lines = self.parse_env_lines(existing_text)
        submitted_lines = self.parse_env_lines(submitted_text)

        existing_pairs: Dict[str, EnvLine] = {
            ln.key: ln for ln in existing_lines if ln.type == "pair" and ln.key is not None
        }

        merged: List[EnvLine] = []
        for sub in submitted_lines:
            if sub.type != "pair" or sub.key is None:
                # Preserve submitted comments/blanks/other verbatim
                merged.append(sub)
                continue

            key = sub.key
            submitted_val = sub.value or ""

            if key in existing_pairs and submitted_val == self.MASK_VALUE:
                # Replace mask with existing value, keep submitted key formatting
                existing_val = existing_pairs[key].value or ""
                merged.append(
                    EnvLine(
                        raw=f"{(sub.key_part or key)}={existing_val}",
                        type="pair",
                        key=key,
                        value=existing_val,
                        key_part=sub.key_part or key,
                    )
                )
            elif key not in existing_pairs and submitted_val == self.MASK_VALUE:
                # Masked-only new key -> ignore
                continue
            else:
                # Use submitted value as-is
                merged.append(sub)

        return merged
