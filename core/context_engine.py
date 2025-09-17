from typing import Dict, Any, List, Optional
from config.settings import Settings
from memory.learning import LearningSystem
from memory.retrieval import RetrievalSystem
from personality.personality_loader import PersonalityLoader
from utils.logger import get_logger

logger = get_logger(__name__)

class ContextEngine:
    """
    Context Engine - Atualizado para nova arquitetura
    Removidas dependências de short_term e long_term memory
    """
    
    def __init__(
        self,
        settings: Settings,
        short_term_memory: Optional[Any],  # DEPRECATED - pode ser None
        long_term_memory: Optional[Any],   # DEPRECATED - pode ser None
        learning_system: LearningSystem,
        retrieval_system: RetrievalSystem,
        personality_loader: PersonalityLoader
    ):
        self.settings = settings
        self.learning_system = learning_system
        self.retrieval_system = retrieval_system
        self.personality_loader = personality_loader
        
        # Log sobre dependências deprecated
        if short_term_memory is None and long_term_memory is None:
            logger.info("✅ ContextEngine initialized with new architecture (no legacy memory)")
        else:
            logger.warning("⚠️ ContextEngine still using legacy memory components")
    
    async def build_context(self, user_id: str, message: str) -> Dict[str, Any]:
        """Build comprehensive context - NOVA ARQUITETURA"""
        context = {}
        
        # Add personality context
        try:
            personality_context = await self.personality_loader.get_personality_context()
            context.update(personality_context)
            logger.debug("✅ Personality context added")
        except Exception as e:
            logger.error(f"Failed to load personality: {str(e)}")
        
        # Add learning context
        if self.settings.memory.learning.get("enabled", False):
            try:
                learning_context = await self.learning_system.apply_learning(user_id)
                context.update(learning_context)
                logger.debug("✅ Learning context added")
            except Exception as e:
                logger.debug(f"Learning context not available: {str(e)}")
        
        # Add retrieval context (RAG)
        try:
            retrieval_context = await self.retrieval_system.retrieve_relevant_documents(message)
            context.update({"retrieved_documents": retrieval_context})
            logger.debug(f"✅ Retrieved {len(retrieval_context)} documents")
        except Exception as e:
            logger.debug(f"Retrieval context not available: {str(e)}")
        
        # Add current message
        context.update({
            "current_message": message,
            "user_id": user_id
        })
        
        logger.debug(f"Built context for user {user_id}", context_keys=list(context.keys()))
        return context