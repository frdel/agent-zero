import yaml
from python.helpers import files
from typing import List, Dict, Optional, TypedDict


# Type alias for UI option items
class FieldOption(TypedDict):
    value: str
    label: str

class ProviderManager:
    _instance = None
    _raw: Optional[Dict[str, List[Dict[str, str]]]] = None  # full provider data
    _options: Optional[Dict[str, List[FieldOption]]] = None  # UI-friendly list

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        if self._raw is None or self._options is None:
            self._load_providers()

    def _load_providers(self):
        """Loads provider configurations from the YAML file and normalises them."""
        try:
            config_path = files.get_abs_path("conf/model_providers.yaml")
            with open(config_path, "r", encoding="utf-8") as f:
                raw_yaml = yaml.safe_load(f) or {}
        except (FileNotFoundError, yaml.YAMLError):
            raw_yaml = {}

        # ------------------------------------------------------------
        # Normalise the YAML so that internally we always work with a
        # list-of-dicts [{id, name, ...}] for each provider type.  This
        # keeps existing callers unchanged while allowing the new nested
        # mapping format in the YAML (id -> { ... }).
        # ------------------------------------------------------------
        normalised: Dict[str, List[Dict[str, str]]] = {}

        for p_type, providers in (raw_yaml or {}).items():
            items: List[Dict[str, str]] = []

            if isinstance(providers, dict):
                # New format: mapping of id -> config
                for pid, cfg in providers.items():
                    entry = {"id": pid, **(cfg or {})}
                    items.append(entry)
            elif isinstance(providers, list):
                # Legacy list format – use as-is
                items.extend(providers or [])

            normalised[p_type] = items

        # Save raw
        self._raw = normalised

        # Build UI-friendly option list (value / label)
        self._options = {}
        for p_type, providers in normalised.items():
            opts: List[FieldOption] = []
            for p in providers:
                pid = (p.get("id") or p.get("value") or "").lower()
                name = p.get("name") or p.get("label") or pid
                if pid:
                    opts.append({"value": pid, "label": name})
            self._options[p_type] = opts

    def get_providers(self, provider_type: str) -> List[FieldOption]:
        """Returns a list of providers for a given type (e.g., 'chat', 'embedding')."""
        return self._options.get(provider_type, []) if self._options else []


    def get_raw_providers(self, provider_type: str) -> List[Dict[str, str]]:
        """Return raw provider dictionaries for advanced use-cases."""
        return self._raw.get(provider_type, []) if self._raw else []

    def get_provider_config(self, provider_type: str, provider_id: str) -> Optional[Dict[str, str]]:
        """Return the metadata dict for a single provider id (case-insensitive)."""
        provider_id_low = provider_id.lower()
        for p in self.get_raw_providers(provider_type):
            if (p.get("id") or p.get("value", "")).lower() == provider_id_low:
                return p
        return None


def get_providers(provider_type: str) -> List[FieldOption]:
    """Convenience function to get providers of a specific type."""
    return ProviderManager.get_instance().get_providers(provider_type)


def get_raw_providers(provider_type: str) -> List[Dict[str, str]]:
    """Return full metadata for providers of a given type."""
    return ProviderManager.get_instance().get_raw_providers(provider_type)


def get_provider_config(provider_type: str, provider_id: str) -> Optional[Dict[str, str]]:
    """Return metadata for a single provider (None if not found)."""
    return ProviderManager.get_instance().get_provider_config(provider_type, provider_id) 