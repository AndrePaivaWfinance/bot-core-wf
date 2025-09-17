"""
Bot Brain - Orchestrator Principal
Versão refatorada e modular
"""
from typing import Dict, Any, Optional, List
import json

from config.settings import Settings
from core.llm import create_provider, LLMProvider
from memory.memory_manager import MemoryManager
from memory.short_term import ShortTermMemory
from memory.long_term import LongTermMemory
from memory.learning import LearningSystem
from memory.retrieval import RetrievalSystem
from skills.skill_registry import SkillRegistry
from utils.logger import get_logger
from utils.metrics import record_metrics

logger = get_logger(__name__)

class BotBrain:
    """
    Orchestrador central do bot
    Coordena LLMs, memória, skills e contexto
    """
    
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
        
        # Memory Manager (NEW)
        self.memory_manager = MemoryManager(settings)
        
        # Initialize LLM providers
        self.primary_provider = None
        self.fallback_provider = None
        
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize LLM providers from configuration"""
        logger.info("=" * 60)
        logger.info("🧠 Initializing Bot Brain LLM Providers...")
        logger.info("=" * 60)
        
        # Initialize primary provider
        primary_config = self._get_llm_config("primary")
        if primary_config and primary_config.get('type'):
            try:
                self.primary_provider = create_provider(
                    primary_config['type'],
                    primary_config
                )
                logger.info(f"✅ Primary provider ({primary_config['type']}) initialized")
            except Exception as e:
                logger.error(f"❌ Failed to initialize primary provider: {str(e)}")
        
        # Initialize fallback provider
        fallback_config = self._get_llm_config("fallback")
        if fallback_config and fallback_config.get('type'):
            try:
                self.fallback_provider = create_provider(
                    fallback_config['type'],
                    fallback_config
                )
                logger.info(f"✅ Fallback provider ({fallback_config['type']}) initialized")
            except Exception as e:
                logger.error(f"❌ Failed to initialize fallback provider: {str(e)}")
        
        # Log final status
        self._log_provider_status()
    
    def _get_llm_config(self, provider_type: str) -> Optional[Dict]:
        """Extract LLM config from settings"""
        if not hasattr(self.settings, 'llm'):
            return None
        
        llm_config = self.settings.llm
        
        # Try different config names
        if provider_type == "primary":
            config = getattr(llm_config, 'primary', None) or \
                    getattr(llm_config, 'primary_llm', None)
        else:
            config = getattr(llm_config, 'fallback', None) or \
                    getattr(llm_config, 'fallback_llm', None)
        
        # Handle dict access
        if not config and isinstance(llm_config, dict):
            if provider_type == "primary":
                config = llm_config.get('primary') or llm_config.get('primary_llm')
            else:
                config = llm_config.get('fallback') or llm_config.get('fallback_llm')
        
        # Convert to dict if needed
        if config and not isinstance(config, dict):
            config = self._config_to_dict(config)
        
        return config
    
    def _config_to_dict(self, config) -> dict:
        """Convert config object to dictionary"""
        if hasattr(config, '__dict__'):
            return vars(config)
        elif hasattr(config, 'dict'):
            return config.dict()
        elif isinstance(config, dict):
            return config
        else:
            # Try to extract attributes directly
            return {
                'type': getattr(config, 'type', None),
                'endpoint': getattr(config, 'endpoint', None),
                'api_key': getattr(config, 'api_key', None),
                'deployment_name': getattr(config, 'deployment_name', None),
                'model': getattr(config, 'model', None),
                'temperature': getattr(config, 'temperature', 0.7),
                'max_tokens': getattr(config, 'max_tokens', 2000),
                'api_version': getattr(config, 'api_version', '2024-02-01')
            }
    
    def _log_provider_status(self):
        """Log the status of LLM providers"""
        logger.info("=" * 60)
        
        if not self.primary_provider and not self.fallback_provider:
            logger.error("⚠️ WARNING: No LLM providers configured!")
        elif not self.primary_provider:
            logger.warning("⚠️ Primary provider not configured, using only fallback")
        elif not self.fallback_provider:
            logger.warning("⚠️ Fallback provider not configured, no redundancy")
        else:
            logger.info("✅ Both primary and fallback providers are ready!")
        
        logger.info("=" * 60)
    
    @record_metrics
    async def think(self, user_id: str, message: str, channel: str = "http") -> Dict[str, Any]:
        """
        Process a message and generate response
        
        Args:
            user_id: User identifier
            message: User's message
            channel: Communication channel
            
        Returns:
            Response with metadata
        """
        logger.info(f"🤔 Processing message from {user_id}: {message[:50]}...")
        
        # Build context from memory
        context = await self._build_context(user_id, message)
        
        # Try to generate response
        response = await self._generate_response(message, context)
        
        # Calculate confidence
        confidence = self._calculate_confidence(response["text"])
        
        # Store interaction in memory
        await self._store_interaction(
            user_id, 
            message, 
            response["text"], 
            {
                **context,
                "provider": response["provider"],
                "channel": channel
            }, 
            confidence
        )
        
        logger.info(f"✨ Response generated using {response['provider']}")
        
        return {
            "response": response["text"],
            "metadata": {
                "provider": response["provider"],
                "provider_used": response.get("provider_used", "unknown"),
                "confidence": confidence,
                "usage": response.get("usage", {}),
                "context_used": list(context.keys()),
                "attempts": response.get("attempts", [])
            }
        }
    
    async def _generate_response(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate response using available LLM providers"""
        response = None
        provider_used = "none"
        attempts = []
        
        # Try primary provider
        if self.primary_provider:
            try:
                logger.info("📡 Attempting PRIMARY provider...")
                response = await self.primary_provider.generate(message, context)
                provider_used = "primary"
                attempts.append({"provider": response["provider"], "status": "success"})
            except Exception as e:
                logger.error(f"❌ Primary provider failed: {str(e)[:200]}")
                attempts.append({"provider": "primary", "status": "failed", "error": str(e)[:100]})
        
        # Try fallback if primary failed
        if not response and self.fallback_provider:
            try:
                logger.info("📡 Attempting FALLBACK provider...")
                response = await self.fallback_provider.generate(message, context)
                provider_used = "fallback"
                attempts.append({"provider": response["provider"], "status": "success"})
            except Exception as e:
                logger.error(f"❌ Fallback provider failed: {str(e)[:200]}")
                attempts.append({"provider": "fallback", "status": "failed", "error": str(e)[:100]})
        
        # If all failed, raise error
        if not response:
            error_msg = "All LLM providers failed"
            logger.error(f"💀 {error_msg}")
            raise RuntimeError(error_msg)
        
        response["provider_used"] = provider_used
        response["attempts"] = attempts
        return response
    
    async def _build_context(self, user_id: str, message: str) -> Dict[str, Any]:
        """Build context from memory systems"""
        context = {}
        
        try:
            # Get from Memory Manager (NEW)
            if self.memory_manager:
                history = await self.memory_manager.get_conversation_history(user_id, limit=5)
                context["conversation_history"] = history
                
                user_context = await self.memory_manager.get_user_context(user_id)
                if user_context:
                    context["user_preferences"] = user_context
            
            # Short-term memory (legacy support)
            short_term = await self.short_term_memory.get_context(user_id)
            context.update(short_term)
            
            # Learning context
            learning = await self.learning_system.apply_learning(user_id)
            context.update(learning)
            
            # Retrieval context (RAG)
            retrieval = await self.retrieval_system.retrieve_relevant_documents(message)
            context["retrieved_documents"] = retrieval
            
        except Exception as e:
            logger.error(f"Error building context: {str(e)}")
        
        return context
    
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
            # Store in Memory Manager (NEW)
            if self.memory_manager:
                await self.memory_manager.save_conversation(
                    user_id=user_id,
                    message=message,
                    response=response,
                    metadata={
                        "confidence": confidence,
                        "provider": context.get("provider", "unknown"),
                        "channel": context.get("channel", "http")
                    }
                )
                logger.info(f"💾 Conversation saved via Memory Manager")
            
            # Legacy storage (for compatibility)
            await self.short_term_memory.store(
                user_id,
                {
                    "message": message,
                    "response": response,
                    "confidence": confidence
                }
            )
            
            # Learning system (Phase 4)
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