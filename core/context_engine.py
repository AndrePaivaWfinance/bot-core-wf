from typing import Dict, Any, List
from config.settings import Settings
from memory.short_term import ShortTermMemory
from memory.long_term import LongTermMemory
from memory.learning import LearningSystem
from memory.retrieval import RetrievalSystem
from personality.personality_loader import PersonalityLoader
from utils.logger import get_logger

logger = get_logger(__name__)

class ContextEngine:
    def __init__(
        self,
        settings: Settings,
        short_term_memory: ShortTermMemory,
        long_term_memory: LongTermMemory,
        learning_system: LearningSystem,
        retrieval_system: RetrievalSystem,
        personality_loader: PersonalityLoader
    ):
        self.settings = settings
        self.short_term_memory = short_term_memory
        self.long_term_memory = long_term_memory
        self.learning_system = learning_system
        self.retrieval_system = retrieval_system
        self.personality_loader = personality_loader
    
    async def build_context(self, user_id: str, message: str) -> Dict[str, Any]:
        """Build comprehensive context for the LLM"""
        context = {}
        
        # Add personality context
        personality_context = await self.personality_loader.get_personality_context()
        context.update(personality_context)
        
        # Add short-term memory context
        short_term_context = await self.short_term_memory.get_context(user_id)
        context.update(short_term_context)
        
        # Add long-term memory context
        if self.settings.memory.long_term.enabled:
            long_term_context = await self.long_term_memory.retrieve_relevant_memories(user_id, message)
            context.update({"long_term_memories": long_term_context})
        
        # Add learning context
        if self.settings.memory.learning.enabled:
            learning_context = await self.learning_system.apply_learning(user_id)
            context.update(learning_context)
        
        # Add retrieval context (RAG)
        retrieval_context = await self.retrieval_system.retrieve_relevant_documents(message)
        context.update({"retrieved_documents": retrieval_context})
        
        # Add current message
        context.update({
            "current_message": message,
            "user_id": user_id
        })
        
        logger.debug(f"Built context for user {user_id}", context_keys=list(context.keys()))
        return context