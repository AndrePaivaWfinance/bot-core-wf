"""
Base Provider Interface for LLM implementations
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List

class LLMProvider(ABC):
    """Base interface that all LLM providers must implement"""
    
    @abstractmethod
    async def generate(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a response from the LLM
        
        Args:
            prompt: The prompt to send to the LLM
            context: Additional context for the generation
            
        Returns:
            Dict with 'text', 'usage', and 'provider' keys
        """
        pass
    
    @abstractmethod
    async def get_embedding(self, text: str) -> List[float]:
        """
        Get embedding vector for text
        
        Args:
            text: Text to get embedding for
            
        Returns:
            List of floats representing the embedding
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is available and configured"""
        pass