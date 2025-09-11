from abc import ABC, abstractmethod
from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from config.settings import Settings
from core.brain import BotBrain
from utils.logger import get_logger

logger = get_logger(__name__)

class BaseInterface(ABC):
    def __init__(self, settings: Settings, brain: BotBrain):
        self.settings = settings
        self.brain = brain
        self.router = APIRouter()
        self._setup_routes()
    
    @abstractmethod
    def _setup_routes(self):
        """Set up the FastAPI routes for this interface"""
        pass
    
    @abstractmethod
    async def handle_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle an incoming message through this interface"""
        pass
    
    async def _process_message(self, message: Dict[str, Any], channel: str) -> Dict[str, Any]:
        """Process a message through the brain"""
        try:
            user_id = message.get("user_id")
            user_message = message.get("message")
            
            if not user_id or not user_message:
                raise HTTPException(status_code=400, detail="user_id and message are required")
            
            response = await self.brain.think(user_id, user_message, channel)
            return response
            
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))