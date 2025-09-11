"""
Interface handlers for different communication channels.
Includes base interface, Teams bot, and email handler.
"""

from .base_interface import BaseInterface
from .teams_bot import TeamsBotInterface
from .email_handler import EmailHandlerInterface

__all__ = [
    'BaseInterface',
    'TeamsBotInterface',
    'EmailHandlerInterface'
]