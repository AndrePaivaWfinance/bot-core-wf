# config/__init__.py
from .settings import BotConfig as Settings, BotConfig

def get_settings():
    # compat: alguns módulos antigos podem chamar get_settings()
    return BotConfig()

__all__ = ["BotConfig", "Settings", "get_settings"]
