from typing import Dict, List, Any
import re
from config.settings import Settings
from memory.long_term import LongTermMemory
from utils.logger import get_logger

logger = get_logger(__name__)

class LearningSystem:
    def __init__(self, settings: Settings, long_term_memory: LongTermMemory):
        self.settings = settings
        self.long_term_memory = long_term_memory
        self.correction_patterns = [
            r"(no|not|wrong|incorrect).*(that|this|it)",
            r"actually.*(it|that|this)",
            r"correction:",
            r"that's.*not.*right"
        ]
    
    async def learn_from_interaction(self, user_id: str, interaction: Dict[str, Any]):
        """Learn from user interactions, especially corrections"""
        if not self.settings.memory.learning.enabled:
            return
        
        message = interaction.get("input", "")
        response = interaction.get("output", "")
        confidence = interaction.get("confidence", 0.5)
        
        # Check if this is a correction
        is_correction = await self._is_correction(message)
        
        if is_correction and confidence < self.settings.memory.learning.min_confidence:
            # Store correction for future reference
            await self.long_term_memory.store(
                user_id,
                "correction",
                {
                    "incorrect_response": response,
                    "corrected_input": message,
                    "context": interaction.get("context", {})
                },
                importance=0.8  # Corrections are important
            )
            logger.debug(f"Stored correction for user {user_id}")
        
        # Detect preferences
        preferences = await self._detect_preferences(message)
        if preferences:
            for preference_type, preference_value in preferences.items():
                await self.long_term_memory.store(
                    user_id,
                    "preference",
                    {
                        "type": preference_type,
                        "value": preference_value,
                        "context": interaction.get("context", {})
                    },
                    importance=0.6
                )
                logger.debug(f"Stored preference for user {user_id}", preference_type=preference_type)
    
    async def apply_learning(self, user_id: str) -> Dict[str, Any]:
        """Apply learned knowledge to the current context"""
        if not self.settings.memory.learning.enabled:
            return {}
        
        learning_context = {}
        
        # Get recent corrections
        corrections = await self.long_term_memory.retrieve(user_id, "correction", limit=3)
        if corrections:
            learning_context["corrections"] = corrections
        
        # Get user preferences
        preferences = await self.long_term_memory.retrieve(user_id, "preference", limit=5)
        if preferences:
            learning_context["preferences"] = preferences
        
        logger.debug(f"Applied learning for user {user_id}", learning_keys=list(learning_context.keys()))
        return learning_context
    
    async def _is_correction(self, message: str) -> bool:
        """Detect if a message is a correction"""
        message_lower = message.lower()
        for pattern in self.correction_patterns:
            if re.search(pattern, message_lower):
                return True
        return False
    
    async def _detect_preferences(self, message: str) -> Dict[str, Any]:
        """Detect user preferences from message"""
        preferences = {}
        message_lower = message.lower()
        
        # Simple preference detection
        if "don't like" in message_lower or "dislike" in message_lower:
            # Extract what the user doesn't like
            preferences["dislikes"] = message
        
        if "like" in message_lower and "don't" not in message_lower:
            # Extract what the user likes
            preferences["likes"] = message
        
        if "prefer" in message_lower:
            # Extract preferences
            preferences["preferences"] = message
        
        return preferences