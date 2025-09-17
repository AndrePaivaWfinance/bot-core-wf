"""
Memory management components - Updated Architecture
Versão corrigida para nova estrutura modular
"""

from .memory_manager import MemoryManager
from .learning import LearningSystem
from .retrieval import RetrievalSystem

# Providers (se disponíveis)
try:
    from .providers.ram_provider import RAMProvider
    from .providers.cosmos_provider import CosmosProvider
    from .providers.blob_provider import BlobProvider
except ImportError:
    # Fallback se providers não estiverem implementados ainda
    RAMProvider = None
    CosmosProvider = None
    BlobProvider = None

__all__ = [
    'MemoryManager',
    'LearningSystem',
    'RetrievalSystem'
]

# Adicionar providers se disponíveis
if RAMProvider:
    __all__.extend(['RAMProvider', 'CosmosProvider', 'BlobProvider'])