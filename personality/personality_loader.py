from typing import Dict, Any
import yaml
from pathlib import Path
from config.settings import Settings
from utils.logger import get_logger

logger = get_logger(__name__)

class PersonalityLoader:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.personality = None
        self.templates_path = Path("personality/templates")
        
        # Load personality
        self._load_personality()
    
    def _load_personality(self):
        """Load personality from YAML file"""
        personality_file = self.templates_path / self.settings.bot.personality_template
        
        if not personality_file.exists():
            # Fallback to base template
            personality_file = self.templates_path / "base_template.yaml"
            logger.warning(f"Personality template {self.settings.bot.personality_template} not found, using base template")
        
        try:
            with open(personality_file, 'r') as f:
                self.personality = yaml.safe_load(f)
            logger.debug(f"Loaded personality: {self.settings.bot.personality_template}")
        except Exception as e:
            logger.error(f"Failed to load personality: {str(e)}")
            self.personality = self._create_default_personality()
    
    def _create_default_personality(self) -> Dict[str, Any]:
        """Create a default personality if loading fails"""
        return {
            "name": "Assistant",
            "style": "helpful",
            "traits": ["helpful", "friendly", "knowledgeable"],
            "limitations": ["I don't have personal experiences", "I can't perform physical actions"],
            "templates": {
                "greeting": "Hello! How can I help you today?",
                "signature": "Best regards,\nYour Assistant"
            }
        }
    
    async def get_personality(self) -> Dict[str, Any]:
        """Get the loaded personality"""
        return self.personality or self._create_default_personality()
    
    async def get_personality_context(self) -> Dict[str, Any]:
        """Get personality as context for LLM"""
        personality = await self.get_personality()
        
        # Format personality for LLM context
        context = {
            "personality": {
                "name": personality.get("name", "Assistant"),
                "style": personality.get("style", "helpful"),
                "traits": personality.get("traits", []),
                "limitations": personality.get("limitations", [])
            }
        }
        
        # Add templates if available
        if "templates" in personality:
            context["personality"]["templates"] = personality["templates"]
        
        return context