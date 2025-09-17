"""
Memory Providers Registry
Centraliza todos os providers de memória
"""

from .ram_provider import RAMProvider
from .cosmos_provider import CosmosProvider
from .blob_provider import BlobProvider

# Registry de providers disponíveis
AVAILABLE_PROVIDERS = {
    "ram": RAMProvider,
    "cosmos": CosmosProvider,
    "blob": BlobProvider,
}

__all__ = [
    'RAMProvider',
    'CosmosProvider', 
    'BlobProvider',
    'AVAILABLE_PROVIDERS'
]