from typing import Dict, Any, Optional
import re
from utils.logger import get_logger

logger = get_logger(__name__)

class MessageRouter:
    def __init__(self):
        self.intent_patterns = {
            "api_call": [
                r"(call|invoke|execute|run).*(api|endpoint|service)",
                r"(get|post|put|delete).*(http|https|api)",
                r"fetch.*data.*from",
                r"make.*request.*to"
            ],
            "generate_report": [
                r"(generate|create|make).*(report|summary|document)",
                r"report.*about",
                r"summarize.*data"
            ],
            "get_help": [
                r"help.*me",
                r"what.*can.*you.*do",
                r"how.*to.*use",
                r"show.*commands"
            ]
        }
    
    async def route_intent(self, message: str, context: Dict[str, Any]) -> Optional[str]:
        """Route message to appropriate intent"""
        message_lower = message.lower()
        
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, message_lower):
                    logger.debug(f"Routed message to intent: {intent}", message=message)
                    return intent
        
        logger.debug("No specific intent matched, using default")
        return None
    
    async def should_use_skill(self, intent: str, context: Dict[str, Any]) -> bool:
        """Determine if a skill should be used for this intent"""
        # Simple heuristic: use skills for specific intents
        skill_intents = ["api_call", "generate_report"]
        return intent in skill_intents