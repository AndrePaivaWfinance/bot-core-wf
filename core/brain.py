from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
import numpy as np

from config.settings import Settings
from memory.short_term import ShortTermMemory
from memory.long_term import LongTermMemory
from memory.learning import LearningSystem
from memory.retrieval import RetrievalSystem
from skills.skill_registry import SkillRegistry
from utils.logger import get_logger
from utils.metrics import record_metrics

logger = get_logger(__name__)

class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    async def get_embedding(self, text: str) -> list:
        pass

class AzureOpenAIProvider(LLMProvider):
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client = httpx.AsyncClient()
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def generate(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        try:
            headers = {
                "Content-Type": "application/json",
                "api-key": self.config["api_key"]
            }
            
            payload = {
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": self.config.get("temperature", 0.7),
                "max_tokens": self.config.get("max_tokens", 2000)
            }
            
            response = await self.client.post(
                f"{self.config['endpoint']}/openai/deployments/{self.config['deployment_name']}/chat/completions?api-version=2023-05-15",
                headers=headers,
                json=payload,
                timeout=30.0
            )
            
            response.raise_for_status()
            result = response.json()
            
            return {
                "text": result["choices"][0]["message"]["content"],
                "usage": result.get("usage", {}),
                "provider": "azure_openai"
            }
            
        except Exception as e:
            logger.error(f"Azure OpenAI error: {str(e)}")
            raise
    
    async def get_embedding(self, text: str) -> list:
        try:
            headers = {
                "Content-Type": "application/json",
                "api-key": self.config["api_key"]
            }
            
            payload = {
                "input": text
            }
            
            response = await self.client.post(
                f"{self.config['endpoint']}/openai/deployments/{self.config.get('embedding_deployment', 'text-embedding-ada-002')}/embeddings?api-version=2023-05-15",
                headers=headers,
                json=payload,
                timeout=30.0
            )
            
            response.raise_for_status()
            result = response.json()
            
            return result["data"][0]["embedding"]
            
        except Exception as e:
            logger.error(f"Azure OpenAI embedding error: {str(e)}")
            raise

class ClaudeProvider(LLMProvider):
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client = httpx.AsyncClient()
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def generate(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        try:
            headers = {
                "Content-Type": "application/json",
                "x-api-key": self.config["api_key"],
                "anthropic-version": "2023-06-01"
            }
            
            payload = {
                "model": self.config.get("model", "claude-3-opus-20240229"),
                "max_tokens": self.config.get("max_tokens", 2000),
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
            
            response = await self.client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
                timeout=30.0
            )
            
            response.raise_for_status()
            result = response.json()
            
            return {
                "text": result["content"][0]["text"],
                "usage": result.get("usage", {}),
                "provider": "claude"
            }
            
        except Exception as e:
            logger.error(f"Claude error: {str(e)}")
            raise
    
    async def get_embedding(self, text: str) -> list:
        # Claude doesn't provide embedding API, use Azure OpenAI as fallback
        raise NotImplementedError("Claude provider doesn't support embeddings")

class BotBrain:
    def __init__(
        self,
        settings: Settings,
        short_term_memory: ShortTermMemory,
        long_term_memory: LongTermMemory,
        learning_system: LearningSystem,
        retrieval_system: RetrievalSystem,
        skill_registry: SkillRegistry
    ):
        self.settings = settings
        self.short_term_memory = short_term_memory
        self.long_term_memory = long_term_memory
        self.learning_system = learning_system
        self.retrieval_system = retrieval_system
        self.skill_registry = skill_registry
        
        # Initialize LLM providers
        self.primary_provider = None
        self.fallback_provider = None

        if getattr(settings.llm, "primary_llm", None):
            if settings.llm.primary_llm.type == "azure_openai":
                self.primary_provider = AzureOpenAIProvider(settings.llm.primary_llm.dict())

        if getattr(settings.llm, "fallback_llm", None):
            if settings.llm.fallback_llm.type == "claude":
                self.fallback_provider = ClaudeProvider(settings.llm.fallback_llm.dict())
    
    @record_metrics
    async def think(self, user_id: str, message: str, channel: str = "http") -> Dict[str, Any]:
        # Build context
        context = await self._build_context(user_id, message)
        
        # Generate response with primary provider, fallback if needed
        response = None
        provider_used = "none"
        
        try:
            if self.primary_provider:
                response = await self.primary_provider.generate(message, context)
                provider_used = "primary"
        except Exception as e:
            logger.warning(f"Primary provider failed: {str(e)}")
            if self.fallback_provider:
                try:
                    response = await self.fallback_provider.generate(message, context)
                    provider_used = "fallback"
                except Exception as fallback_error:
                    logger.error(f"Fallback provider also failed: {str(fallback_error)}")
        
        # If all providers failed, use mock response
        if not response:
            response = {
                "text": "I'm experiencing technical difficulties. Please try again later.",
                "usage": {},
                "provider": "mock"
            }
            provider_used = "mock"
        
        # Calculate confidence
        confidence = self._calculate_confidence(response["text"])
        
        # Store interaction
        await self._store_interaction(user_id, message, response["text"], context, confidence)
        
        return {
            "response": response["text"],
            "metadata": {
                "provider": response["provider"],
                "confidence": confidence,
                "usage": response.get("usage", {}),
                "context_used": list(context.keys())
            }
        }
    
    async def _build_context(self, user_id: str, message: str) -> Dict[str, Any]:
        context = {}
        
        # Short-term memory
        short_term_context = await self.short_term_memory.get_context(user_id)
        context.update(short_term_context)
        
        # Long-term memory
        long_term_context = await self.long_term_memory.retrieve(user_id, limit=5)
        context.update({"long_term_memories": long_term_context})
        
        # Learning context
        learning_context = await self.learning_system.apply_learning(user_id)
        context.update(learning_context)
        
        # Retrieval context (RAG)
        retrieval_context = await self.retrieval_system.retrieve_relevant_documents(message)
        context.update({"retrieved_documents": retrieval_context})
        
        return context
    
    def _calculate_confidence(self, response: str) -> float:
        # Simple confidence heuristic
        confidence = 0.7  # Base confidence
        
        # Adjust based on response characteristics
        if len(response) < 10:
            confidence -= 0.2
        elif len(response) > 100:
            confidence += 0.1
            
        if "I don't know" in response or "I'm not sure" in response:
            confidence -= 0.3
            
        if "?" in response:
            confidence -= 0.1
            
        # Ensure confidence is between 0 and 1
        return max(0.1, min(0.99, confidence))
    
    async def _store_interaction(
        self,
        user_id: str,
        message: str,
        response: str,
        context: Dict[str, Any],
        confidence: float
    ):
        # Store in short-term memory
        await self.short_term_memory.store(
            user_id,
            {"message": message, "response": response, "confidence": confidence}
        )
        
        # Learn from interaction
        await self.learning_system.learn_from_interaction(
            user_id,
            {
                "input": message,
                "output": response,
                "context": context,
                "confidence": confidence
            }
        )