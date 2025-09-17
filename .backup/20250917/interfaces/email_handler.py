from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from config.settings import Settings
from core.brain import BotBrain
from interfaces.base_interface import BaseInterface
from utils.logger import get_logger

logger = get_logger(__name__)

class EmailHandlerInterface(BaseInterface):
    def __init__(self, settings: Settings, brain: BotBrain):
        super().__init__(settings, brain)
    
    def _setup_routes(self):
        @self.router.post("/interfaces/email/messages")
        async def email_message_handler(message: Dict[str, Any]):
            return await self.handle_message(message)
    
    async def handle_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle an incoming email message"""
        # Add email-specific metadata
        email_metadata = {
            "channel": "email",
            "email_headers": message.get("headers", {})
        }
        
        response = await self._process_message(message, "email")
        response["metadata"].update(email_metadata)
        
        logger.debug("Processed email message", user_id=message.get("user_id"))
        return response