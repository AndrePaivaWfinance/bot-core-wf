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
