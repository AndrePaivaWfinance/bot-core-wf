from typing import Dict, List, Any
import re
from config.settings import Settings
from memory.long_term import LongTermMemory
from utils.logger import get_logger

logger = get_logger(__name__)

class LearningSystem:
    """Sistema de aprendizado - DESABILITADO TEMPORARIAMENTE"""
    
    def __init__(self, settings: Settings, long_term_memory: LongTermMemory):
        self.settings = settings
        self.long_term_memory = long_term_memory
        logger.info("Learning system initialized but DISABLED for Phase 1")
    
    async def learn_from_interaction(self, user_id: str, interaction: Dict[str, Any]):
        """DESABILITADO - Será implementado na Fase 4"""
        return
    
    async def apply_learning(self, user_id: str) -> Dict[str, Any]:
        """DESABILITADO - Será implementado na Fase 4"""
        return {}