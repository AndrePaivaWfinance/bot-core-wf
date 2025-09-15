<<<<<<< HEAD
# config/__init__.py
from .settings import BotConfig as Settings, BotConfig

def get_settings():
    # compat: alguns módulos antigos podem chamar get_settings()
    return BotConfig()

__all__ = ["BotConfig", "Settings", "get_settings"]
=======
"""
Configuration management.
Includes settings and Azure-specific configuration.
"""

from .settings import Settings, get_settings
from .azure_config import AzureConfig

__all__ = [
    'Settings',
    'get_settings',
    'AzureConfig'
]
>>>>>>> resgate-eb512f
