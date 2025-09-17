from typing import Dict, List, Any, Optional
import re
from config.settings import Settings
from utils.logger import get_logger

logger = get_logger(__name__)

class LearningSystem:
    """Sistema de aprendizado - ATUALIZADO para nova arquitetura"""
    
    def __init__(self, settings: Settings, long_term_memory: Optional[Any] = None):
        self.settings = settings
        # Removida dependência obrigatória de long_term_memory
        self.long_term_memory = long_term_memory  # Pode ser None
        logger.info("Learning system initialized - DISABLED for Phase 1")
        
        if long_term_memory is None:
            logger.info("✅ LearningSystem using new architecture (no legacy dependency)")
    
    async def learn_from_interaction(self, user_id: str, interaction: Dict[str, Any]):
        """DESABILITADO - Será implementado na Fase 4"""
        logger.debug(f"Learning from interaction for {user_id} (DISABLED)")
        return
    
    async def apply_learning(self, user_id: str) -> Dict[str, Any]:
        """DESABILITADO - Será implementado na Fase 4"""
        logger.debug(f"Applying learning for {user_id} (DISABLED)")
        return {}