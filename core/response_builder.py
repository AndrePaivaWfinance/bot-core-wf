from typing import Dict, Any
from config.settings import Settings
from personality.personality_loader import PersonalityLoader
from utils.logger import get_logger

logger = get_logger(__name__)

class ResponseBuilder:
    def __init__(self, settings: Settings, personality_loader: PersonalityLoader):
        self.settings = settings
        self.personality_loader = personality_loader
    
    async def build_response(
        self,
        raw_response: str,
        metadata: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build a formatted response with personality and metadata"""
        personality = await self.personality_loader.get_personality()
        
        # Apply personality templates if available
        formatted_response = self._apply_personality_template(raw_response, personality)
        
        # Add metadata
        response = {
            "response": formatted_response,
            "metadata": {
                **metadata,
                "bot_id": self.settings.bot.id,
                "bot_name": self.settings.bot.name,
                "personality": self.settings.bot.personality_template
            }
        }
        
        logger.debug("Built response", response_metadata=response["metadata"])
        return response
    
    def _apply_personality_template(self, response: str, personality: Dict[str, Any]) -> str:
        """Apply personality-specific formatting to the response"""
        if not personality.get("templates"):
            return response
        
        # Apply greeting template if it's the first message in conversation
        if "short_term_memory" not in personality or len(personality.get("short_term_memory", [])) == 0:
            greeting = personality.get("templates", {}).get("greeting", "")
            if greeting:
                return f"{greeting} {response}"
        
        # Apply signature if available
        signature = personality.get("templates", {}).get("signature", "")
        if signature:
            response = f"{response}\n\n{signature}"
        
        return response