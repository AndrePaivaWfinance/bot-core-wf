"""
Bot Brain - Versão Corrigida
Baseado no backup funcional com Learning System
"""
from typing import Dict, Any, Optional, List
import time
import os

from config.settings import Settings
from core.llm import create_provider, LLMProvider
from memory.memory_manager import MemoryManager
from memory.learning import LearningSystem
from memory.retrieval import RetrievalSystem
from skills.skill_registry import SkillRegistry
from utils.logger import get_logger
from utils.metrics import record_metrics

# Learning imports (opcional)
try:
    from learning.core.learning_engine import LearningEngine
    LEARNING_ENABLED = True
except ImportError:
    LEARNING_ENABLED = False

logger = get_logger(__name__)

class BotBrain:
    """Orchestrador central do bot - VERSÃO CORRIGIDA"""
    
    def __init__(
        self,
        settings: Settings,
        memory_manager: MemoryManager,
        learning_system: LearningSystem,
        retrieval_system: RetrievalSystem,
        skill_registry: SkillRegistry
    ):
        self.settings = settings
        self.memory_manager = memory_manager
        self.learning_system = learning_system
        self.retrieval_system = retrieval_system
        self.skill_registry = skill_registry
        
        # Learning Engine opcional
        self.learning_engine = None
        if LEARNING_ENABLED:
            try:
                self.learning_engine = LearningEngine(settings, memory_manager)
                logger.info("✅ Learning Engine initialized")
            except Exception as e:
                logger.warning(f"⚠️ Learning Engine disabled: {e}")
        
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
        """Extract LLM config from settings - CORRIGIDO"""
        if not hasattr(self.settings, 'llm'):
            return None
        
        llm_config = self.settings.llm
        
        # Handle dict access (nosso caso)
        if isinstance(llm_config, dict):
            if provider_type == "primary":
                config = llm_config.get('primary')
            else:
                config = llm_config.get('fallback_llm')
        else:
            # Try object attributes
            if provider_type == "primary":
                config = getattr(llm_config, 'primary', None)
            else:
                config = getattr(llm_config, 'fallback_llm', None)
        
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
        elif hasattr(config, 'model_dump'):
            return config.model_dump()
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
        """Process a message and generate response - COM FALLBACK"""
        logger.info(f"🤔 Processing message from {user_id}: {message[:50]}...")
        
        start_time = time.time()
        
        # Build context from memory
        context = await self._build_context(user_id, message)
        
        # Apply learning if available
        if self.learning_engine:
            try:
                profile = await self.learning_engine.get_or_create_profile(user_id)
                await self.learning_engine.record_interaction(
                    user_id, message, channel, {}
                )
                context["user_style"] = profile.communication_style
                context["user_expertise"] = profile.expertise_level
            except Exception as e:
                logger.debug(f"Learning not applied: {e}")
        
        # Try to generate response
        try:
            response = await self._generate_response(message, context)
        except Exception as e:
            logger.error(f"Failed to generate response: {str(e)}")
            response = {
                "text": "Desculpe, estou com dificuldades técnicas no momento. Por favor, tente novamente.",
                "provider": "error",
                "provider_used": "none",
                "error": str(e)
            }
        
        processing_time = time.time() - start_time
        
        # Calculate confidence
        confidence = self._calculate_confidence(response["text"])
        
        # Store interaction in memory
        await self._store_interaction(
            user_id, 
            message, 
            response["text"], 
            {
                **context,
                "provider": response.get("provider", "unknown"),
                "channel": channel,
                "confidence": confidence,
                "processing_time": processing_time
            }
        )
        
        logger.info(f"✨ Response generated using {response.get('provider', 'unknown')}")
        
        return {
            "response": response["text"],
            "metadata": {
                "user_id": user_id,
                "channel": channel,
                "processing_time": processing_time,
                "confidence": confidence,
                "provider": response.get("provider", "unknown"),
                "provider_used": response.get("provider_used", "unknown"),
                "has_context": bool(context.get("conversation_history")),
                "architecture": "memory_manager"
            }
        }
    
    async def _generate_response(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate response using available LLM providers - USANDO generate()"""
        response = None
        provider_used = "none"
        attempts = []
        last_error = None
        
        # Build enhanced prompt with context
        enhanced_prompt = self._build_enhanced_prompt(message, context)
        
        # Log if using context
        if context.get("conversation_history"):
            logger.info("📝 Using memory context in prompt")
        
        # Try primary provider
        if self.primary_provider and self.primary_provider.is_available():
            try:
                logger.info("📡 Attempting PRIMARY provider (Azure OpenAI)...")
                # USANDO generate() como no backup
                response = await self.primary_provider.generate(enhanced_prompt, context)
                provider_used = "primary"
                attempts.append({"provider": "azure_openai", "status": "success"})
                logger.info("✅ Primary provider succeeded")
            except Exception as e:
                logger.warning(f"⚠️ Primary provider failed: {str(e)[:200]}")
                last_error = str(e)
                attempts.append({"provider": "azure_openai", "status": "failed", "error": str(e)[:100]})
        
        # Try fallback if primary failed
        if not response and self.fallback_provider and self.fallback_provider.is_available():
            try:
                logger.info("📡 Attempting FALLBACK provider (Claude)...")
                # USANDO generate() como no backup
                response = await self.fallback_provider.generate(enhanced_prompt, context)
                provider_used = "fallback"
                attempts.append({"provider": "claude", "status": "success"})
                logger.info("✅ Fallback provider succeeded")
            except Exception as e:
                logger.warning(f"⚠️ Fallback provider failed: {str(e)[:200]}")
                last_error = str(e)
                attempts.append({"provider": "claude", "status": "failed", "error": str(e)[:100]})
        
        # If both failed, use static response
        if not response:
            logger.warning("⚠️ All LLM providers failed - using static response")
            
            # Check for simple greetings
            greetings = ["olá", "oi", "hello", "hi", "bom dia", "boa tarde", "boa noite"]
            if any(greeting in message.lower() for greeting in greetings):
                response = {
                    "text": "Olá! Sou o Mesh, seu assistente financeiro. Como posso ajudá-lo hoje?",
                    "provider": "static",
                    "provider_used": "static"
                }
            else:
                response = {
                    "text": "Desculpe, estou com dificuldades técnicas para processar sua mensagem no momento.",
                    "provider": "error",
                    "provider_used": "none",
                    "error": last_error or "All providers unavailable"
                }
        
        response["provider_used"] = provider_used
        response["attempts"] = attempts
        
        return response
    
    def _build_enhanced_prompt(self, message: str, context: Dict[str, Any]) -> str:
        """Build prompt including context from memory - SIMPLIFICADO"""
        prompt_parts = []
        
        # Add conversation history if available
        conversation_history = context.get("conversation_history", [])
        if conversation_history:
            prompt_parts.append("### Contexto da Conversa Anterior ###")
            for conv in conversation_history[-3:]:  # Last 3 messages
                user_msg = conv.get('message', '')[:200]
                bot_response = conv.get('response', '')[:200]
                if user_msg and bot_response:
                    prompt_parts.append(f"Usuário: {user_msg}")
                    prompt_parts.append(f"Assistente: {bot_response}")
            prompt_parts.append("")
        
        # Add user style if available
        if context.get("user_style"):
            prompt_parts.append("### Estilo de Comunicação ###")
            style = context["user_style"]
            if style == "formal":
                prompt_parts.append("Use linguagem formal e profissional.")
            elif style == "casual":
                prompt_parts.append("Use linguagem amigável e acessível.")
            prompt_parts.append("")
        
        # Add instruction
        if conversation_history:
            prompt_parts.append("### Instrução ###")
            prompt_parts.append("Considere o contexto acima ao responder.")
            prompt_parts.append("")
        
        # Add current message
        prompt_parts.append("### Mensagem Atual ###")
        prompt_parts.append(message)
        
        return "\n".join(prompt_parts)
    
    async def _build_context(self, user_id: str, message: str) -> Dict[str, Any]:
        """Build context from memory systems"""
        context = {}
        
        try:
            # Memory Manager context
            if self.memory_manager:
                # Get conversation history
                history = await self.memory_manager.get_conversation_history(user_id, limit=5)
                if history:
                    context["conversation_history"] = history
                    logger.debug(f"💾 Loaded {len(history)} conversations")
                
                # Get user context
                user_context = await self.memory_manager.get_user_context(user_id)
                if user_context:
                    context["user_preferences"] = user_context
                    logger.debug(f"💾 Loaded user preferences")
            
            # Learning context
            if self.learning_system:
                try:
                    learning = await self.learning_system.apply_learning(user_id)
                    if learning:
                        context.update(learning)
                except Exception as e:
                    logger.debug(f"Learning system not available: {e}")
            
            # Retrieval context (RAG)
            if self.retrieval_system:
                try:
                    retrieval = await self.retrieval_system.retrieve_relevant_documents(message)
                    if retrieval:
                        context["retrieved_documents"] = retrieval
                        logger.debug(f"📚 Retrieved {len(retrieval)} documents")
                except Exception as e:
                    logger.debug(f"Retrieval system error: {e}")
            
            logger.info(f"📋 Context built: {list(context.keys())}")
            
        except Exception as e:
            logger.error(f"Error building context: {str(e)}")
        
        return context
    
    async def _store_interaction(self, user_id: str, message: str, response: str, context: Dict[str, Any]):
        """Store interaction in memory - USANDO save_conversation()"""
        try:
            if self.memory_manager:
                # USANDO save_conversation como no backup
                await self.memory_manager.save_conversation(
                    user_id=user_id,
                    message=message,
                    response=response,
                    metadata={
                        "confidence": context.get("confidence", 0.7),
                        "provider": context.get("provider", "unknown"),
                        "channel": context.get("channel", "http"),
                        "processing_time": context.get("processing_time", 0)
                    }
                )
                logger.debug(f"💾 Conversation saved")
            
            # Learning system
            if self.learning_system:
                try:
                    await self.learning_system.learn_from_interaction(
                        user_id,
                        {
                            "input": message,
                            "output": response,
                            "context": context,
                            "confidence": context.get("confidence", 0.7)
                        }
                    )
                except Exception as e:
                    logger.debug(f"Learning system not active: {e}")
            
        except Exception as e:
            logger.error(f"Error storing interaction: {str(e)}")
    
    def _calculate_confidence(self, response: str) -> float:
        """Calculate confidence score for the response"""
        confidence = 0.7
        
        # Lower confidence for error responses
        if "dificuldades técnicas" in response or "temporariamente" in response:
            confidence = 0.2
        elif len(response) < 10:
            confidence -= 0.2
        elif len(response) > 100:
            confidence += 0.1
        
        # Boost if contextual
        if any(word in response.lower() for word in ["você mencionou", "anteriormente"]):
            confidence += 0.1
        
        return max(0.1, min(0.99, confidence))
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory statistics"""
        if self.memory_manager:
            return self.memory_manager.get_storage_stats()
        return {"status": "no_memory_manager"}
    
    async def get_user_history(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get user conversation history"""
        if self.memory_manager:
            return await self.memory_manager.get_conversation_history(user_id, limit)
        return []
    
    async def get_user_insights(self, user_id: str) -> Dict[str, Any]:
        """Get user insights from learning system"""
        insights = {"user_id": user_id}
        
        if self.learning_engine:
            try:
                profile = await self.learning_engine.get_or_create_profile(user_id)
                insights["profile"] = {
                    "style": profile.communication_style,
                    "expertise": profile.expertise_level,
                    "interactions": profile.total_interactions
                }
            except:
                pass
        
        if self.memory_manager:
            history = await self.get_user_history(user_id, 5)
            insights["history_count"] = len(history)
        
        return insights
    
    def is_available(self) -> bool:
        """Check if at least one provider is available"""
        return bool(
            (self.primary_provider and self.primary_provider.is_available()) or
            (self.fallback_provider and self.fallback_provider.is_available())
        )