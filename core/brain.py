"""
Bot Brain - Orchestrator Principal
Versão com fallback melhorado e tratamento de erros
CORRIGIDO: Agora inclui contexto de memória nas chamadas LLM
"""
from typing import Dict, Any, Optional, List
import json

from config.settings import Settings
from core.llm import create_provider, LLMProvider
from memory.memory_manager import MemoryManager
from memory.learning import LearningSystem
from memory.retrieval import RetrievalSystem
from skills.skill_registry import SkillRegistry
from utils.logger import get_logger
from utils.metrics import record_metrics

logger = get_logger(__name__)

class BotBrain:
    """
    Orchestrador central do bot - COM FALLBACK MELHORADO E CONTEXTO DE MEMÓRIA
    """
    
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
        Process a message and generate response - COM FALLBACK MELHORADO
        """
        logger.info(f"🤔 Processing message from {user_id}: {message[:50]}...")
        
        # Build context from memory
        context = await self._build_context(user_id, message)
        
        # Try to generate response with better error handling
        try:
            response = await self._generate_response(message, context)
        except Exception as e:
            logger.error(f"Failed to generate response: {str(e)}")
            # Return a safe error response instead of throwing 500
            response = {
                "text": "Desculpe, estou com dificuldades técnicas no momento. Por favor, tente novamente em alguns instantes.",
                "provider": "error",
                "provider_used": "none",
                "error": str(e)
            }
        
        # Calculate confidence
        confidence = self._calculate_confidence(response["text"])
        
        # Store interaction in memory (even if it failed)
        await self._store_interaction(
            user_id, 
            message, 
            response["text"], 
            {
                **context,
                "provider": response.get("provider", "unknown"),
                "channel": channel,
                "confidence": confidence,
                "had_error": "error" in response
            }
        )
        
        logger.info(f"✨ Response generated using {response.get('provider', 'unknown')}")
        
        return {
            "response": response["text"],
            "metadata": {
                "provider": response.get("provider", "unknown"),
                "provider_used": response.get("provider_used", "unknown"),
                "confidence": confidence,
                "usage": response.get("usage", {}),
                "context_used": list(context.keys()),
                "attempts": response.get("attempts", []),
                "architecture": "memory_manager",
                "had_error": "error" in response
            }
        }
    
    async def _generate_response(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate response using available LLM providers WITH CONTEXT"""
        response = None
        provider_used = "none"
        attempts = []
        last_error = None
        
        # NOVO: Construir prompt com contexto de memória
        enhanced_prompt = self._build_enhanced_prompt(message, context)
        
        # Log se está usando contexto
        if context.get("conversation_history") or context.get("user_preferences"):
            logger.info("📝 Using memory context in prompt")
            logger.debug(f"   History items: {len(context.get('conversation_history', []))}")
            logger.debug(f"   Has preferences: {bool(context.get('user_preferences'))}")
        
        # Try primary provider
        if self.primary_provider and self.primary_provider.is_available():
            try:
                logger.info("📡 Attempting PRIMARY provider (Azure OpenAI)...")
                # MUDANÇA: Usar enhanced_prompt ao invés de message simples
                response = await self.primary_provider.generate(enhanced_prompt, context)
                provider_used = "primary"
                attempts.append({
                    "provider": response.get("provider", "azure_openai"),
                    "status": "success"
                })
                logger.info("✅ Primary provider succeeded")
            except Exception as e:
                error_msg = str(e)
                logger.warning(f"⚠️ Primary provider failed: {error_msg[:200]}")
                last_error = error_msg
                attempts.append({
                    "provider": "azure_openai",
                    "status": "failed",
                    "error": error_msg[:100]
                })
                # Continue to try fallback
        
        # Try fallback if primary failed or not available
        if not response and self.fallback_provider and self.fallback_provider.is_available():
            try:
                logger.info("📡 Attempting FALLBACK provider (Claude)...")
                # MUDANÇA: Usar enhanced_prompt ao invés de message simples
                response = await self.fallback_provider.generate(enhanced_prompt, context)
                provider_used = "fallback"
                attempts.append({
                    "provider": response.get("provider", "claude"),
                    "status": "success"
                })
                logger.info("✅ Fallback provider succeeded")
            except Exception as e:
                error_msg = str(e)
                logger.warning(f"⚠️ Fallback provider failed: {error_msg[:200]}")
                last_error = error_msg
                attempts.append({
                    "provider": "claude",
                    "status": "failed",
                    "error": error_msg[:100]
                })
        
        # If both failed, try a simple response without LLM
        if not response:
            logger.warning("⚠️ All LLM providers failed - using static response")
            
            # Check if it's a simple greeting
            greetings = ["olá", "oi", "hello", "hi", "bom dia", "boa tarde", "boa noite"]
            if any(greeting in message.lower() for greeting in greetings):
                response = {
                    "text": "Olá! Sou o Mesh, seu assistente financeiro. Como posso ajudá-lo hoje?",
                    "provider": "static",
                    "provider_used": "static"
                }
            # Check if it's asking about status
            elif any(word in message.lower() for word in ["status", "funcionando", "working", "ok"]):
                response = {
                    "text": "Estou operacional, mas com recursos limitados no momento. Os serviços de IA estão temporariamente indisponíveis.",
                    "provider": "static",
                    "provider_used": "static"
                }
            else:
                # Generic fallback
                response = {
                    "text": "Desculpe, estou com dificuldades técnicas para processar sua mensagem no momento. Por favor, tente novamente mais tarde ou entre em contato com o suporte.",
                    "provider": "error",
                    "provider_used": "none",
                    "error": last_error or "All providers unavailable"
                }
        
        response["provider_used"] = provider_used
        response["attempts"] = attempts
        
        return response
    
    def _build_enhanced_prompt(self, message: str, context: Dict[str, Any]) -> str:
        """
        NOVO MÉTODO: Constrói prompt incluindo contexto de memória
        Formata o prompt para incluir histórico e informações relevantes
        """
        prompt_parts = []
        
        # 1. Adicionar histórico de conversas se disponível
        conversation_history = context.get("conversation_history", [])
        if conversation_history:
            prompt_parts.append("### Contexto da Conversa Anterior ###")
            # Pegar últimas 5 conversas, mas limitar tamanho
            for conv in conversation_history[-5:]:
                user_msg = conv.get('message', '')[:200]  # Limitar tamanho
                bot_response = conv.get('response', '')[:200]
                if user_msg and bot_response:
                    prompt_parts.append(f"Usuário: {user_msg}")
                    prompt_parts.append(f"Assistente: {bot_response}")
            prompt_parts.append("")  # Linha em branco
        
        # 2. Adicionar preferências do usuário se disponível
        user_preferences = context.get("user_preferences", {})
        if user_preferences:
            prompt_parts.append("### Informações sobre o Usuário ###")
            for key, value in user_preferences.items():
                if value:  # Apenas se tiver valor
                    prompt_parts.append(f"- {key}: {value}")
            prompt_parts.append("")  # Linha em branco
        
        # 3. Adicionar documentos recuperados (RAG) se disponível
        retrieved_docs = context.get("retrieved_documents", [])
        if retrieved_docs:
            prompt_parts.append("### Documentos Relevantes ###")
            for doc in retrieved_docs[:3]:  # Top 3 documentos
                content = doc.get('content', '')[:300]  # Limitar tamanho
                if content:
                    prompt_parts.append(f"- {content}")
            prompt_parts.append("")  # Linha em branco
        
        # 4. Adicionar instrução se há contexto
        if conversation_history or user_preferences:
            prompt_parts.append("### Instrução ###")
            prompt_parts.append("Por favor, considere o contexto e histórico acima ao responder. Mantenha consistência com as informações já discutidas.")
            prompt_parts.append("")
        
        # 5. Adicionar a mensagem atual
        prompt_parts.append("### Mensagem Atual do Usuário ###")
        prompt_parts.append(message)
        
        # Juntar tudo
        enhanced_prompt = "\n".join(prompt_parts)
        
        # Log do tamanho do prompt para debug
        logger.debug(f"Enhanced prompt size: {len(enhanced_prompt)} chars")
        
        return enhanced_prompt
    
    async def _build_context(self, user_id: str, message: str) -> Dict[str, Any]:
        """Build context from memory systems"""
        context = {}
        
        try:
            # Memory Manager context
            if self.memory_manager:
                # Histórico de conversas
                history = await self.memory_manager.get_conversation_history(user_id, limit=5)
                if history:
                    context["conversation_history"] = history
                    logger.debug(f"💾 Loaded {len(history)} conversations from MemoryManager")
                
                # Contexto do usuário
                user_context = await self.memory_manager.get_user_context(user_id)
                if user_context:
                    context["user_preferences"] = user_context
                    logger.debug(f"💾 Loaded user preferences from MemoryManager")
            
            # Learning context (se aplicável)
            if self.learning_system:
                try:
                    learning = await self.learning_system.apply_learning(user_id)
                    if learning:
                        context.update(learning)
                        logger.debug(f"🎓 Applied learning context")
                except Exception as e:
                    logger.debug(f"Learning system not available: {str(e)}")
            
            # Retrieval context (RAG)
            if self.retrieval_system:
                try:
                    retrieval = await self.retrieval_system.retrieve_relevant_documents(message)
                    if retrieval:
                        context["retrieved_documents"] = retrieval
                        logger.debug(f"📚 Retrieved {len(retrieval)} documents")
                except Exception as e:
                    logger.debug(f"Retrieval system error: {str(e)}")
            
            # Log resumo do contexto construído
            logger.info(f"📋 Context built: {list(context.keys())}")
            
        except Exception as e:
            logger.error(f"Error building context: {str(e)}")
        
        return context
    
    async def _store_interaction(
        self,
        user_id: str,
        message: str,
        response: str,
        context: Dict[str, Any]
    ):
        """Store interaction in memory"""
        try:
            # Armazenar via Memory Manager
            if self.memory_manager:
                await self.memory_manager.save_conversation(
                    user_id=user_id,
                    message=message,
                    response=response,
                    metadata={
                        "confidence": context.get("confidence", 0.7),
                        "provider": context.get("provider", "unknown"),
                        "channel": context.get("channel", "http"),
                        "had_error": context.get("had_error", False)
                    }
                )
                logger.debug(f"💾 Conversation saved via Memory Manager")
            
            # Learning system (Fase 4 - futuro)
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
                    logger.debug(f"Learning system not active: {str(e)}")
            
        except Exception as e:
            logger.error(f"Error storing interaction: {str(e)}")
    
    def _calculate_confidence(self, response: str) -> float:
        """Calculate confidence score for the response"""
        confidence = 0.7  # Base confidence
        
        # Lower confidence for error/static responses
        if "dificuldades técnicas" in response or "temporariamente indisponíveis" in response:
            confidence = 0.2
        elif len(response) < 10:
            confidence -= 0.2
        elif len(response) > 100:
            confidence += 0.1
        
        # Boost confidence if response seems contextual
        if any(word in response.lower() for word in ["você mencionou", "anteriormente", "como disse", "conforme"]):
            confidence += 0.1
        
        if "I don't know" in response or "I'm not sure" in response or "não tenho acesso" in response:
            confidence -= 0.3
        
        if "?" in response:
            confidence -= 0.1
        
        # Ensure confidence is between 0 and 1
        return max(0.1, min(0.99, confidence))
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de memória"""
        if self.memory_manager:
            return self.memory_manager.get_storage_stats()
        return {"status": "no_memory_manager"}
    
    async def get_user_history(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Recupera histórico do usuário via Memory Manager"""
        if self.memory_manager:
            return await self.memory_manager.get_conversation_history(user_id, limit)
        return []