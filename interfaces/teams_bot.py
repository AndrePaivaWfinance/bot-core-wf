from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Request
from config.settings import Settings
from core.brain import BotBrain
from interfaces.base_interface import BaseInterface
from utils.logger import get_logger

logger = get_logger(__name__)

class TeamsBotInterface(BaseInterface):
    def __init__(self, settings: Settings, brain: BotBrain):
        super().__init__(settings, brain)
    
    def _setup_routes(self):
        @self.router.post("/interfaces/teams/messages")
        async def teams_message_handler(request: Request, message: Dict[str, Any]):
            return await self.handle_message(message)
    
    async def handle_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle an incoming Teams message"""
        # Add Teams-specific metadata
        teams_metadata = {
            "channel": "teams",
            "teams_context": message.get("teams_context", {})
        }
        
        response = await self._process_message(message, "teams")
        response["metadata"].update(teams_metadata)
        
        logger.debug("Processed Teams message", user_id=message.get("user_id"))
        return response