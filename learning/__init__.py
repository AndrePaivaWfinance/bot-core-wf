"""
Sistema de Aprendizagem - Fase 4
Módulo principal que exporta todos os componentes
"""

from .core.learning_engine import LearningEngine
from .models.user_profile import UserProfile, CommunicationStyle, ResponsePreference
from .analyzers.pattern_detector import PatternDetector, PatternType
from .storage.learning_store import LearningStore

__all__ = [
    # Core
    'LearningEngine',
    
    # Models
    'UserProfile',
    'CommunicationStyle',
    'ResponsePreference',
    
    # Analyzers
    'PatternDetector',
    'PatternType',
    
    # Storage
    'LearningStore'
]

# Versão do sistema de aprendizagem
__version__ = "1.0.0"