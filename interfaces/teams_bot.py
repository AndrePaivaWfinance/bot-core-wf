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
<<<<<<< HEAD
        return response
=======
        return response

    async def on_turn(self, turn_context):
        message_text = turn_context.activity.text
        message = {
            "text": message_text,
            "user_id": getattr(turn_context.activity.from_property, "id", None),
            "teams_context": {
                "conversation": getattr(turn_context.activity.conversation, "id", None),
                "channel_id": getattr(turn_context.activity.channel_id, None),
                "service_url": getattr(turn_context.activity.service_url, None)
            }
        }
        response = await self.handle_message(message)
        await turn_context.send_activity(response.get("text", ""))
>>>>>>> resgate-eb512f
