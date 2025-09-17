"""
LLM Providers Module
Centralizes all LLM provider implementations
"""

from .base_provider import LLMProvider
from .azure_provider import AzureOpenAIProvider
from .claude_provider import ClaudeProvider

# Registry of available providers
AVAILABLE_PROVIDERS = {
    "azure_openai": AzureOpenAIProvider,
    "claude": ClaudeProvider,
}

def create_provider(provider_type: str, config: dict) -> LLMProvider:
    """
    Factory function to create LLM providers
    
    Args:
        provider_type: Type of provider ('azure_openai', 'claude')
        config: Configuration dictionary for the provider
        
    Returns:
        Instance of the requested provider
        
    Raises:
        ValueError: If provider type is not supported
    """
    if provider_type not in AVAILABLE_PROVIDERS:
        raise ValueError(f"Unknown provider type: {provider_type}")
    
    provider_class = AVAILABLE_PROVIDERS[provider_type]
    return provider_class(config)

__all__ = [
    'LLMProvider',
    'AzureOpenAIProvider',
    'ClaudeProvider',
    'create_provider',
    'AVAILABLE_PROVIDERS'
]