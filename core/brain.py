"""
Bot Brain - Orchestrator Principal com Sistema de Aprendizagem
Versão 3.0.0 - COMPLETA com Learning System integrado
WFinance Bot Framework - Mesh
"""
from typing import Dict, Any, Optional, List
import json
import time
from datetime import datetime

from config.settings import Settings
from core.llm import create_provider, LLMProvider
from memory.memory_manager import MemoryManager
from memory.learning import LearningSystem
from memory.retrieval import RetrievalSystem
from skills.skill_registry import SkillRegistry
from utils.logger import get_logger
from utils.metrics import record_metrics

# NOVO: Imports do Sistema de Aprendizagem
from learning.core.learning_engine import LearningEngine
from learning.models.user_profile import UserProfile

logger = get_logger(__name__)

class BotBrain:
    """
    Orchestrador central do bot - COM LEARNING SYSTEM COMPLETO
    Versão 3.0.0 - Fase 4 implementada
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
        
        # NOVO: Inicializar Learning Engine
        self.learning_engine = LearningEngine()
        logger.info("🧠 Learning Engine initialized")
        
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
        if primary_config:
            try:
                self.primary_provider = create_provider(primary_config["provider"], primary_config)
                if self.primary_provider and self.primary_provider.is_available():
                    logger.info(f"✅ Primary LLM Provider initialized: {primary_config['provider']}")
                else:
                    logger.warning(f"❌ Primary provider {primary_config['provider']} not available")
                    self.primary_provider = None
            except Exception as e:
                logger.error(f"Failed to initialize primary provider: {str(e)}")
                self.primary_provider = None
        
        # Initialize fallback provider
        fallback_config = self._get_llm_config("fallback")
        if fallback_config:
            try:
                self.fallback_provider = create_provider(fallback_config["provider"], fallback_config)
                if self.fallback_provider and self.fallback_provider.is_available():
                    logger.info(f"✅ Fallback LLM Provider initialized: {fallback_config['provider']}")
                else:
                    logger.warning(f"❌ Fallback provider {fallback_config['provider']} not available")
                    self.fallback_provider = None
            except Exception as e:
                logger.error(f"Failed to initialize fallback provider: {str(e)}")
                self.fallback_provider = None
        
        if not self.primary_provider and not self.fallback_provider:
            logger.error("⚠️ No LLM providers available! Bot will not function properly.")
        
        logger.info("=" * 60)
    
    def _get_llm_config(self, provider_type: str) -> Optional[Dict[str, Any]]:
        """Get LLM configuration for specified provider type"""
        if provider_type == "primary" and self.settings.llm and self.settings.llm.primary_model:
            return self.settings.llm.primary_model.model_dump()
        elif provider_type == "fallback" and self.settings.llm and self.settings.llm.fallback_model:
            return self.settings.llm.fallback_model.model_dump()
        return None
    
    async def think(
        self,
        user_id: str,
        message: str,
        channel: str = "unknown",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Main thinking process - NOW WITH LEARNING SYSTEM
        """
        start_time = time.time()
        
        try:
            # NOVO: 1. Recuperar ou criar perfil do usuário
            user_profile = await self.learning_engine.get_or_create_profile(user_id)
            logger.debug(f"👤 User profile loaded: {user_profile.communication_style}, expertise: {user_profile.expertise_level}")
            
            # NOVO: 2. Registrar interação para aprendizado
            await self.learning_engine.record_interaction(
                user_id=user_id,
                message=message,
                channel=channel,
                metadata=metadata or {}
            )
            
            # NOVO: 3. Detectar padrões do usuário
            patterns = await self.learning_engine.detect_patterns(user_id)
            if patterns:
                logger.info(f"🔍 Detected {len(patterns)} patterns for user {user_id}")
            
            # 4. Build context from memory (existente + aprimorado)
            context = await self._build_context(user_id, message)
            
            # NOVO: 5. Adicionar informações de aprendizado ao contexto
            context["user_profile"] = {
                "style": user_profile.communication_style,
                "expertise": user_profile.expertise_level,
                "preferences": user_profile.preferences,
                "satisfaction": user_profile.satisfaction_score
            }
            context["patterns"] = [
                {
                    "type": p.pattern_type,
                    "description": p.description,
                    "confidence": p.confidence
                }
                for p in patterns[:5]  # Top 5 padrões
            ]
            
            # 6. Build enhanced prompt WITH PERSONALIZATION
            enhanced_prompt = self._build_enhanced_prompt_with_learning(
                message=message,
                context=context,
                user_profile=user_profile,
                patterns=patterns
            )
            
            # 7. Generate response (com fallback)
            response = await self._generate_response(enhanced_prompt, user_id)
            
            # NOVO: 8. Registrar resposta para aprendizado
            response_time = time.time() - start_time
            await self.learning_engine.record_response(
                user_id=user_id,
                response=response,
                response_time=response_time
            )
            
            # 9. Calculate confidence
            confidence = self._calculate_confidence(response)
            
            # NOVO: 10. Atualizar satisfação baseado em sinais
            if "obrigado" in message.lower() or "perfeito" in message.lower():
                user_profile.satisfaction_score = min(1.0, user_profile.satisfaction_score + 0.1)
            elif "não entendi" in message.lower() or "errado" in message.lower():
                user_profile.satisfaction_score = max(0.0, user_profile.satisfaction_score - 0.1)
            
            # 11. Store interaction with learning metadata
            await self._store_interaction(
                user_id, 
                message, 
                response, 
                {
                    **context,
                    "confidence": confidence,
                    "processing_time": response_time,
                    "personalization_applied": True,
                    "patterns_used": len(patterns),
                    "user_expertise": user_profile.expertise_level
                }
            )
            
            # 12. Build final response with metadata
            return {
                "response": response,
                "metadata": {
                    "user_id": user_id,
                    "channel": channel,
                    "processing_time": response_time,
                    "confidence": confidence,
                    "provider": context.get("provider_used", "unknown"),
                    "memory_context": bool(context.get("conversation_history")),
                    # NOVO: Metadata de aprendizado
                    "personalization": {
                        "style": user_profile.communication_style,
                        "expertise": user_profile.expertise_level,
                        "patterns_detected": len(patterns),
                        "satisfaction_score": user_profile.satisfaction_score
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Error in thinking process: {str(e)}")
            logger.exception("Full traceback:")
            
            # Fallback response
            return {
                "response": "Desculpe, estou com dificuldades técnicas no momento. Por favor, tente novamente.",
                "metadata": {
                    "user_id": user_id,
                    "channel": channel,
                    "error": True,
                    "error_type": type(e).__name__
                }
            }
    
    def _build_enhanced_prompt_with_learning(
        self, 
        message: str, 
        context: Dict[str, Any],
        user_profile: UserProfile,
        patterns: List[Any]
    ) -> str:
        """
        Build enhanced prompt WITH PERSONALIZATION based on learning
        """
        prompt_parts = []
        
        # 1. System prompt base
        prompt_parts.append("### Contexto do Sistema ###")
        prompt_parts.append("Você é o Mesh, um analista financeiro especialista em BPO da WFinance.")
        prompt_parts.append("")
        
        # 2. NOVO: Personalização baseada no perfil
        prompt_parts.append("### Personalização ###")
        
        # Estilo de comunicação
        if user_profile.communication_style == "formal":
            prompt_parts.append("- Use linguagem formal e profissional")
            prompt_parts.append("- Seja respeitoso e use tratamento adequado")
        elif user_profile.communication_style == "casual":
            prompt_parts.append("- Use linguagem amigável e acessível")
            prompt_parts.append("- Seja informal mas profissional")
        else:
            prompt_parts.append("- Mantenha um tom neutro e profissional")
        
        # Tamanho de resposta
        if user_profile.preferred_response_length == "concise":
            prompt_parts.append("- Seja BREVE e direto ao ponto")
            prompt_parts.append("- Evite explicações desnecessárias")
        elif user_profile.preferred_response_length == "detailed":
            prompt_parts.append("- Forneça explicações DETALHADAS")
            prompt_parts.append("- Inclua exemplos quando relevante")
        
        # Nível de expertise
        if user_profile.expertise_level == "expert":
            prompt_parts.append("- O usuário é EXPERIENTE, use termos técnicos")
            prompt_parts.append("- Não explique conceitos básicos")
        elif user_profile.expertise_level == "beginner":
            prompt_parts.append("- O usuário é INICIANTE, evite jargões")
            prompt_parts.append("- Explique conceitos técnicos de forma simples")
        elif user_profile.expertise_level == "intermediate":
            prompt_parts.append("- O usuário tem conhecimento INTERMEDIÁRIO")
            prompt_parts.append("- Balance entre técnico e acessível")
        
        prompt_parts.append("")
        
        # 3. NOVO: Padrões detectados
        if patterns:
            prompt_parts.append("### Padrões e Preferências do Usuário ###")
            for pattern in patterns[:3]:  # Top 3 padrões mais relevantes
                if pattern.pattern_type == "recurring_question":
                    prompt_parts.append(f"- Frequentemente pergunta sobre: {pattern.description}")
                elif pattern.pattern_type == "daily_routine":
                    prompt_parts.append(f"- Rotina usual: {pattern.description}")
                elif pattern.pattern_type == "topic_sequence":
                    prompt_parts.append(f"- Costuma discutir: {pattern.description}")
                elif pattern.pattern_type == "preference":
                    prompt_parts.append(f"- Preferência: {pattern.description}")
            prompt_parts.append("")
        
        # 4. Contexto de memória (se houver)
        conversation_history = context.get("conversation_history", [])
        if conversation_history:
            prompt_parts.append("### Histórico Recente ###")
            for conv in conversation_history[-3:]:  # Últimas 3 interações
                prompt_parts.append(f"Usuário: {conv.get('user', 'N/A')[:100]}...")
                prompt_parts.append(f"Assistente: {conv.get('assistant', 'N/A')[:100]}...")
            prompt_parts.append("")
        
        # 5. NOVO: Informações específicas do usuário
        if user_profile.preferences:
            prompt_parts.append("### Preferências Específicas ###")
            for key, value in user_profile.preferences.items():
                if key == "topics_of_interest":
                    prompt_parts.append(f"- Interesses: {', '.join(value) if isinstance(value, list) else value}")
                elif key == "preferred_examples":
                    prompt_parts.append(f"- Tipos de exemplo preferidos: {value}")
            prompt_parts.append("")
        
        # 6. Mensagem atual
        prompt_parts.append("### Mensagem Atual ###")
        prompt_parts.append(message)
        prompt_parts.append("")
        
        # 7. Instruções finais personalizadas
        prompt_parts.append("### Instruções ###")
        prompt_parts.append("Responda de forma personalizada considerando todas as informações acima.")
        
        # Adicionar instruções específicas baseadas na satisfação
        if user_profile.satisfaction_score < 0.5:
            prompt_parts.append("IMPORTANTE: O usuário parece insatisfeito. Seja especialmente cuidadoso e solicito.")
        elif user_profile.satisfaction_score > 0.8:
            prompt_parts.append("O usuário está satisfeito com o serviço. Continue com o excelente trabalho!")
        
        return "\n".join(prompt_parts)
    
    async def _generate_response(self, prompt: str, user_id: str) -> str:
        """Generate response using available providers with fallback"""
        response = None
        provider_used = None
        
        # Try primary provider first
        if self.primary_provider and self.primary_provider.is_available():
            try:
                logger.debug(f"Using primary provider for user {user_id}")
                response = await self.primary_provider.generate_response(prompt, user_id)
                provider_used = "primary"
            except Exception as e:
                logger.warning(f"Primary provider failed: {str(e)}")
        
        # Fallback to secondary if needed
        if not response and self.fallback_provider and self.fallback_provider.is_available():
            try:
                logger.debug(f"Using fallback provider for user {user_id}")
                response = await self.fallback_provider.generate_response(prompt, user_id)
                provider_used = "fallback"
            except Exception as e:
                logger.error(f"Fallback provider also failed: {str(e)}")
        
        # Last resort - static response
        if not response:
            logger.error("All providers failed - using static response")
            response = "Desculpe, nossos serviços estão temporariamente indisponíveis. Por favor, tente novamente em alguns instantes."
            provider_used = "static"
        
        # Store provider info for metrics
        self._last_provider_used = provider_used
        
        return response
    
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
            
            # Learning context (sistema antigo - compatibilidade)
            if self.learning_system:
                try:
                    learning = await self.learning_system.apply_learning(user_id)
                    if learning:
                        context.update(learning)
                except Exception as e:
                    logger.debug(f"Legacy learning system not active: {str(e)}")
            
            # Retrieval context
            if self.retrieval_system:
                try:
                    relevant_docs = await self.retrieval_system.retrieve(message, user_id)
                    if relevant_docs:
                        context["relevant_documents"] = relevant_docs
                        logger.debug(f"📚 Retrieved {len(relevant_docs)} relevant documents")
                except Exception as e:
                    logger.debug(f"Retrieval system not active: {str(e)}")
            
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
        """Store interaction in memory and learning systems"""
        try:
            # Memory Manager storage
            if self.memory_manager:
                await self.memory_manager.store_conversation(
                    user_id=user_id,
                    user_message=message,
                    assistant_response=response,
                    metadata={
                        "channel": context.get("channel", "unknown"),
                        "confidence": context.get("confidence", 0.7),
                        "provider": self._last_provider_used if hasattr(self, '_last_provider_used') else "unknown",
                        "processing_time": context.get("processing_time", 0),
                        "personalization_applied": context.get("personalization_applied", False),
                        "patterns_used": context.get("patterns_used", 0),
                        "user_expertise": context.get("user_expertise", "unknown")
                    }
                )
                logger.debug(f"💾 Conversation saved with learning metadata")
            
            # Legacy learning system (compatibilidade)
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
                    logger.debug(f"Legacy learning system not active: {str(e)}")
            
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
        
        if "não sei" in response.lower() or "não tenho certeza" in response.lower():
            confidence -= 0.3
        
        if "?" in response:
            confidence -= 0.1
        
        # Ensure confidence is between 0 and 1
        return max(0.1, min(0.99, confidence))
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de memória"""
        stats = {}
        
        if self.memory_manager:
            stats["memory"] = self.memory_manager.get_storage_stats()
        
        # NOVO: Adicionar estatísticas de aprendizado
        if self.learning_engine:
            stats["learning"] = {
                "profiles_cached": len(self.learning_engine.profiles_cache),
                "patterns_detected": sum(len(p) for p in self.learning_engine.patterns_cache.values()),
                "store_available": self.learning_engine.store is not None
            }
        
        return stats
    
    async def get_user_history(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Recupera histórico do usuário via Memory Manager"""
        if self.memory_manager:
            return await self.memory_manager.get_conversation_history(user_id, limit)
        return []
    
    # NOVO: Método para obter insights do usuário
    async def get_user_insights(self, user_id: str) -> Dict[str, Any]:
        """Retorna insights detalhados sobre o usuário"""
        insights = {
            "user_id": user_id,
            "profile": None,
            "patterns": [],
            "history_summary": None
        }
        
        # Obter perfil
        if self.learning_engine:
            profile = await self.learning_engine.get_or_create_profile(user_id)
            insights["profile"] = {
                "style": profile.communication_style,
                "expertise": profile.expertise_level,
                "preferences": profile.preferences,
                "total_interactions": profile.total_interactions,
                "satisfaction_score": profile.satisfaction_score,
                "last_seen": profile.last_interaction.isoformat() if profile.last_interaction else None
            }
            
            # Obter padrões
            patterns = await self.learning_engine.detect_patterns(user_id)
            insights["patterns"] = [
                {
                    "type": p.pattern_type,
                    "description": p.description,
                    "confidence": p.confidence,
                    "occurrences": p.occurrences
                }
                for p in patterns
            ]
        
        # Resumo do histórico
        if self.memory_manager:
            history = await self.get_user_history(user_id, limit=5)
            if history:
                insights["history_summary"] = {
                    "total_conversations": len(history),
                    "recent_topics": self._extract_topics(history),
                    "average_response_time": self._calculate_avg_response_time(history)
                }
        
        return insights
    
    def _extract_topics(self, history: List[Dict]) -> List[str]:
        """Extrai tópicos principais do histórico"""
        # Implementação simplificada - pode ser melhorada com NLP
        topics = []
        keywords = ["imposto", "fluxo de caixa", "relatório", "análise", "BPO", "faturamento"]
        
        for conv in history:
            msg = conv.get("user", "").lower()
            for keyword in keywords:
                if keyword in msg and keyword not in topics:
                    topics.append(keyword)
        
        return topics[:5]  # Top 5 tópicos
    
    def _calculate_avg_response_time(self, history: List[Dict]) -> float:
        """Calcula tempo médio de resposta"""
        times = []
        for conv in history:
            if "metadata" in conv and "processing_time" in conv["metadata"]:
                times.append(conv["metadata"]["processing_time"])
        
        return sum(times) / len(times) if times else 0.0
    
    def is_available(self) -> bool:
        """Check if at least one provider is available"""
        primary_available = self.primary_provider and self.primary_provider.is_available()
        fallback_available = self.fallback_provider and self.fallback_provider.is_available()
        return primary_available or fallback_available