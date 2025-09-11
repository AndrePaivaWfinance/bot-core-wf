# config/settings.py
import os, re, copy, yaml
from typing import Any, Dict

ENV_PATTERN = re.compile(r"\$\{([^}]+)\}")

def _expand_env(value: Any) -> Any:
    if isinstance(value, str):
        m = ENV_PATTERN.search(value)
        if m:
            var = m.group(1)
            return os.getenv(var, "")
        return value
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    return value

class BotConfig:
    def __init__(self, config_path: str = "bot_config.yaml"):
        self.config = self._load_config(config_path)
        self._apply_env_overrides()

    def _load_config(self, path: str) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        # 1) expande ${ENV}
        expanded = _expand_env(raw)
        return expanded

    def _apply_env_overrides(self):
        # 2) overrides específicos que frequentemente precisamos
        llm = self.config.get("llm", {})
        if "primary_llm" in llm:
            p = llm["primary_llm"]
            p["endpoint"] = os.getenv("AZURE_OPENAI_ENDPOINT", p.get("endpoint", ""))
            p["api_key"]  = os.getenv("AZURE_OPENAI_KEY", p.get("api_key", ""))

        fb = llm.get("fallback_llm", {})
        if fb:
            fb["api_key"] = os.getenv("CLAUDE_API_KEY", fb.get("api_key", ""))

        cosmos = self.config.get("cosmos", {})
        cosmos["endpoint"] = os.getenv("AZURE_COSMOS_ENDPOINT", cosmos.get("endpoint", ""))
        cosmos["key"]      = os.getenv("AZURE_COSMOS_KEY", cosmos.get("key", ""))

        blob = self.config.get("blob_storage", {})
        blob["connection_string"] = os.getenv("AZURE_STORAGE_CONNECTION", blob.get("connection_string", ""))

        # (Opcional) achatar referências usadas no código legado:
        self.config["primary_llm"] = llm.get("primary_llm", {})
        self.config["fallback_llm"] = llm.get("fallback_llm", {})
