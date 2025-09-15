<<<<<<< HEAD
# core/brain.py
from typing import Dict, List, Optional
from abc import ABC, abstractmethod
from datetime import datetime
import asyncio
import os
import httpx

class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, context: Dict) -> str: ...
    async def get_embedding(self, text: str) -> List[float]:
        # mock simples, pode ser substituído por Azure Embeddings
        import hashlib, random
        h = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)
        rnd = random.Random(h)
        return [rnd.random() for _ in range(256)]

class AzureOpenAIProvider(LLMProvider):
    def __init__(self, config: Dict):
        self.endpoint = config.get("endpoint") or ""
        self.api_key = config.get("api_key") or ""
        self.deployment = config.get("deployment_name") or "gpt-4o"
        self.temperature = config.get("temperature", 0.7)
        self._mock = not (self.endpoint and self.api_key)

    async def generate(self, prompt: str, context: Dict) -> str:
        if self._mock:
            return f"[mock-azure] {prompt[:240]}"
        # Exemplo (ajuste ao seu endpoint real de Chat Completions):
        url = f"{self.endpoint}/openai/deployments/{self.deployment}/chat/completions?api-version=2024-02-15-preview"
        headers = {"api-key": self.api_key}
        payload = {
            "messages": [{"role": "system", "content": "You are a helpful assistant."},
                         {"role": "user", "content": prompt}],
            "temperature": self.temperature
        }
        timeout = httpx.Timeout(15.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
            # ajuste conforme o formato retornado pelo seu endpoint
            text = data["choices"][0]["message"]["content"]
            return text

class ClaudeProvider(LLMProvider):
    def __init__(self, config: Dict):
        self.api_key = config.get("api_key") or ""
        self.model = config.get("model", "claude-3-opus")
        self._mock = not self.api_key

    async def generate(self, prompt: str, context: Dict) -> str:
        if self._mock:
            return f"[mock-claude] {prompt[:240]}"
        # Chamada real omitida; implementar com o SDK/endpoint da Anthropic
        return f"[claude-not-implemented] {prompt[:240]}"

class BotBrain:
    def __init__(self, bot_config: Dict):
        self.config = bot_config
        # Suporta as duas formas: achatado e dentro de llm
        primary_cfg = self.config.get("primary_llm") or self.config.get("llm", {}).get("primary_llm", {})
        fallback_cfg = self.config.get("fallback_llm") or self.config.get("llm", {}).get("fallback_llm", {})
        self.primary_llm = AzureOpenAIProvider(primary_cfg) if primary_cfg.get("type") == "azure_openai" else None
        self.fallback_llm = ClaudeProvider(fallback_cfg) if fallback_cfg.get("type") == "claude" else None
        self.personality = self.config.get("bot", {})

    async def think(self, message: str, context: Dict) -> Dict:
        enhanced_prompt = self._build_prompt(message, context)
        try:
            resp = await self.primary_llm.generate(enhanced_prompt, context) if self.primary_llm else "[no-primary-llm]"
            return {
                "response": resp,
                "provider": "primary",
                "timestamp": datetime.utcnow().isoformat(),
                "confidence": self._confidence(resp)
            }
        except Exception as e:
            if self.fallback_llm:
                resp = await self.fallback_llm.generate(enhanced_prompt, context)
                return {
                    "response": resp,
                    "provider": "fallback",
                    "timestamp": datetime.utcnow().isoformat(),
                    "error": str(e)
                }
            raise

    def _build_prompt(self, message: str, context: Dict) -> str:
        parts = []
        bot = self.personality
        if bot:
            parts.append(f"You are {bot.get('name','Mesh')}.")
            parts.append(f"Role: {self.config.get('bot',{}).get('type','assistant')}")
        if context.get("conversation_history"):
            parts.append("\nRecent conversation:")
            for msg in context["conversation_history"][-5:]:
                parts.append(f"{msg['role']}: {msg['content']}")
        if context.get("relevant_memories"):
            parts.append("\nRelevant information from memory:")
            parts.extend([f"- {m}" for m in context["relevant_memories"]])
        if context.get("relevant_documents"):
            parts.append("\nRelevant documents:")
            parts.extend([f"- {d.get('title','doc')}: {d.get('snippet','...')}" for d in context["relevant_documents"]])
        parts.append(f"\nUser message: {message}\nYour response:")
        return "\n".join(parts)

    def _confidence(self, resp: str) -> float:
        if not resp: return 0.0
        bad = any(x in resp.lower() for x in ["não sei", "i don't know", "unknown"])
        return max(0.1, min(0.95, 0.5 if bad else 0.8))
=======
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from openai import AsyncAzureOpenAI, AsyncOpenAI
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
import numpy as np
import json

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
        
        # Validate required fields
        if not config.get("api_key") or not config.get("endpoint") or not config.get("deployment_name"):
            raise ValueError(f"Azure OpenAI requires api_key, endpoint, and deployment_name. Got: {config.keys()}")
        
        # Use AsyncAzureOpenAI for Azure endpoints
        self.client = AsyncAzureOpenAI(
            api_key=config["api_key"],
            api_version=config.get("api_version", "2024-02-01"),
            azure_endpoint=config['endpoint'].rstrip('/'),  # Remove trailing slash
            azure_deployment=config['deployment_name']
        )
        
        logger.info(f"AzureOpenAIProvider initialized successfully with endpoint={config['endpoint']}, "
                   f"deployment={config['deployment_name']}, "
                   f"api_version={config.get('api_version', '2024-02-01')}")
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def generate(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        try:
            logger.debug(f"Calling Azure OpenAI with deployment={self.config['deployment_name']}")
            logger.debug(f"Prompt: {prompt[:100]}...")  # Log first 100 chars of prompt
            
            response = await self.client.chat.completions.create(
                model=self.config["deployment_name"],  # Azure uses deployment name as model
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt},
                ],
                temperature=self.config.get("temperature", 0.7),
                max_tokens=self.config.get("max_tokens", 2000)
            )
            
            logger.debug(f"Azure OpenAI response received successfully")
            
            return {
                "text": response.choices[0].message.content,
                "usage": response.usage.model_dump() if response.usage else {},
                "provider": "azure_openai",
            }
            
        except Exception as e:
            import traceback
            logger.error(f"Azure OpenAI error: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
    
    async def get_embedding(self, text: str) -> list:
        try:
            embedding_model = self.config.get("embedding_deployment", "text-embedding-3-large")
            logger.debug(f"Calling Azure OpenAI Embeddings with model={embedding_model}")
            
            response = await self.client.embeddings.create(
                model=embedding_model,
                input=text
            )
            
            logger.debug(f"Azure Embeddings response received successfully")
            return response.data[0].embedding
            
        except Exception as e:
            import traceback
            logger.error(f"Azure OpenAI embedding error: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

class ClaudeProvider(LLMProvider):
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client = httpx.AsyncClient(timeout=60.0)  # Increase timeout
        
        # Validate API key
        if not config.get("api_key"):
            raise ValueError("Claude requires api_key")
        
        logger.info(f"ClaudeProvider initialized with model={config.get('model', 'claude-3-sonnet-20240229')}")
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def generate(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        try:
            headers = {
                "Content-Type": "application/json",
                "x-api-key": self.config["api_key"],
                "anthropic-version": "2023-06-01"  # Use stable version
            }
            
            payload = {
                "model": self.config.get("model", "claude-3-sonnet-20240229"),
                "max_tokens": self.config.get("max_tokens", 2000),
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
            
            logger.debug(f"Calling Claude API with model={payload['model']}")
            logger.debug(f"Request headers: {headers}")
            logger.debug(f"Request payload: {json.dumps(payload, indent=2)}")
            
            response = await self.client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload
            )
            
            # Log response details before checking status
            logger.debug(f"Claude response status: {response.status_code}")
            if response.status_code != 200:
                logger.error(f"Claude error response: {response.text}")
            
            response.raise_for_status()
            result = response.json()
            
            logger.debug(f"Claude response received successfully")
            
            return {
                "text": result["content"][0]["text"],
                "usage": result.get("usage", {}),
                "provider": "claude"
            }
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Claude HTTP error: {e.response.status_code}")
            logger.error(f"Claude error response: {e.response.text}")
            raise
        except Exception as e:
            import traceback
            logger.error(f"Claude error: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
    
    async def get_embedding(self, text: str) -> list:
        # Claude doesn't provide embedding API
        raise NotImplementedError("Claude provider doesn't support embeddings")
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

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
        
        # Log the structure of settings for debugging
        logger.debug(f"BotBrain init - type(settings): {type(settings)}")
        logger.debug(f"BotBrain init - hasattr(settings, 'llm'): {hasattr(settings, 'llm')}")
        
        # Initialize primary provider (Azure OpenAI)
        if hasattr(settings, 'llm') and settings.llm:
            llm_config = settings.llm
            logger.debug(f"BotBrain init - type(llm_config): {type(llm_config)}")
            
            # Try to get primary config
            primary_config = None
            
            # Handle ConfigNS or similar object
            if hasattr(llm_config, 'primary'):
                primary_config = llm_config.primary
                logger.debug(f"Found llm_config.primary")
            elif hasattr(llm_config, 'primary_llm'):
                primary_config = llm_config.primary_llm
                logger.debug(f"Found llm_config.primary_llm")
            elif isinstance(llm_config, dict):
                primary_config = llm_config.get('primary') or llm_config.get('primary_llm')
                logger.debug(f"Found primary config in dict")
            
            if primary_config:
                logger.debug(f"Primary config type: {type(primary_config)}")
                
                # Convert to dict if needed
                config_dict = None
                if hasattr(primary_config, '__dict__'):
                    config_dict = vars(primary_config)
                elif hasattr(primary_config, 'dict'):
                    config_dict = primary_config.dict()
                elif isinstance(primary_config, dict):
                    config_dict = primary_config
                else:
                    # Try to access attributes directly
                    config_dict = {
                        'type': getattr(primary_config, 'type', None),
                        'endpoint': getattr(primary_config, 'endpoint', None),
                        'api_key': getattr(primary_config, 'api_key', None),
                        'deployment_name': getattr(primary_config, 'deployment_name', None),
                        'temperature': getattr(primary_config, 'temperature', 0.7),
                        'max_tokens': getattr(primary_config, 'max_tokens', 2000),
                        'api_version': getattr(primary_config, 'api_version', '2024-02-01')
                    }
                
                logger.debug(f"Primary config dict: {config_dict}")
                
                if config_dict and config_dict.get('type') == 'azure_openai':
                    try:
                        self.primary_provider = AzureOpenAIProvider(config_dict)
                        logger.info("Primary provider (Azure OpenAI) initialized successfully")
                    except Exception as e:
                        logger.error(f"Failed to initialize Azure OpenAI: {str(e)}")
            
            # Try to get fallback config
            fallback_config = None
            
            if hasattr(llm_config, 'fallback'):
                fallback_config = llm_config.fallback
                logger.debug(f"Found llm_config.fallback")
            elif hasattr(llm_config, 'fallback_llm'):
                fallback_config = llm_config.fallback_llm
                logger.debug(f"Found llm_config.fallback_llm")
            elif isinstance(llm_config, dict):
                fallback_config = llm_config.get('fallback') or llm_config.get('fallback_llm')
                logger.debug(f"Found fallback config in dict")
            
            if fallback_config:
                logger.debug(f"Fallback config type: {type(fallback_config)}")
                
                # Convert to dict if needed
                config_dict = None
                if hasattr(fallback_config, '__dict__'):
                    config_dict = vars(fallback_config)
                elif hasattr(fallback_config, 'dict'):
                    config_dict = fallback_config.dict()
                elif isinstance(fallback_config, dict):
                    config_dict = fallback_config
                else:
                    # Try to access attributes directly
                    config_dict = {
                        'type': getattr(fallback_config, 'type', None),
                        'api_key': getattr(fallback_config, 'api_key', None),
                        'model': getattr(fallback_config, 'model', 'claude-3-sonnet-20240229'),
                        'temperature': getattr(fallback_config, 'temperature', 0.7),
                        'max_tokens': getattr(fallback_config, 'max_tokens', 2000)
                    }
                
                logger.debug(f"Fallback config dict: {config_dict}")
                
                if config_dict and config_dict.get('type') == 'claude':
                    try:
                        self.fallback_provider = ClaudeProvider(config_dict)
                        logger.info("Fallback provider (Claude) initialized successfully")
                    except Exception as e:
                        logger.error(f"Failed to initialize Claude: {str(e)}")
        
        if not self.primary_provider and not self.fallback_provider:
            logger.warning("No LLM providers configured! Check your configuration.")
    
    @record_metrics
    async def think(self, user_id: str, message: str, channel: str = "http") -> Dict[str, Any]:
        # Check for mock mode (for testing)
        if getattr(self.settings, "mock_mode", False):
            return await self._handle_mock_mode(user_id, message)
        
        # Build context
        context = await self._build_context(user_id, message)
        
        # Generate response with primary provider, fallback if needed
        response = None
        provider_used = "none"
        
        # Try primary provider
        if self.primary_provider:
            try:
                logger.info("Attempting to use primary provider (Azure OpenAI)")
                response = await self.primary_provider.generate(message, context)
                provider_used = "primary"
                logger.info(f"Primary provider responded successfully")
            except Exception as e:
                logger.error(f"Primary provider failed: {str(e)}")
                logger.exception("Primary provider exception details:")
        
        # Try fallback provider if primary failed
        if not response and self.fallback_provider:
            try:
                logger.info("Primary provider failed, attempting fallback provider (Claude)")
                response = await self.fallback_provider.generate(message, context)
                provider_used = "fallback"
                logger.info(f"Fallback provider responded successfully")
            except Exception as e:
                logger.error(f"Fallback provider also failed: {str(e)}")
                logger.exception("Fallback provider exception details:")
        
        # If all providers failed, raise error
        if not response:
            error_msg = "All LLM providers failed. Please check your configuration and API keys."
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        # Calculate confidence
        confidence = self._calculate_confidence(response["text"])
        
        # Store interaction
        await self._store_interaction(user_id, message, response["text"], context, confidence)
        
        logger.info(f"Response generated successfully using {provider_used} provider")
        
        return {
            "response": response["text"],
            "metadata": {
                "provider": response["provider"],
                "provider_used": provider_used,
                "confidence": confidence,
                "usage": response.get("usage", {}),
                "context_used": list(context.keys())
            }
        }
    
    async def _handle_mock_mode(self, user_id: str, message: str) -> Dict[str, Any]:
        """Handle mock mode for testing"""
        context = await self._build_context(user_id, message)
        
        # Simple name memory example
        if "qual é o meu nome" in message.lower():
            stored_name = context.get("user_name")
            if stored_name:
                return {
                    "response": f"Seu nome é {stored_name}",
                    "metadata": {
                        "provider": "memory",
                        "confidence": 0.95,
                        "usage": {},
                        "context_used": ["short_term"]
                    }
                }
        
        if "meu nome é" in message.lower():
            user_name = message.split("é")[-1].strip()
            await self.short_term_memory.store(user_id, {"user_name": user_name})
            return {
                "response": f"Prazer, {user_name}!",
                "metadata": {
                    "provider": "memory",
                    "confidence": 0.95,
                    "usage": {},
                    "context_used": ["short_term"]
                }
            }
        
        return {
            "response": "Olá, eu sou o bot em modo teste!",
            "metadata": {
                "provider": "mock",
                "confidence": 0.99,
                "usage": {},
                "context_used": []
            }
        }
    
    async def _build_context(self, user_id: str, message: str) -> Dict[str, Any]:
        """Build context from various memory systems"""
        context = {}
        
        try:
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
            
        except Exception as e:
            logger.error(f"Error building context: {str(e)}")
            # Return partial context if some systems fail
        
        return context
    
    def _calculate_confidence(self, response: str) -> float:
        """Calculate confidence score for the response"""
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
        """Store interaction in memory systems"""
        try:
            # Store in short-term memory
            await self.short_term_memory.store(
                user_id,
                {
                    "message": message,
                    "response": response,
                    "confidence": confidence
                }
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
        except Exception as e:
            logger.error(f"Error storing interaction: {str(e)}")
            # Continue even if storage fails
>>>>>>> resgate-eb512f
