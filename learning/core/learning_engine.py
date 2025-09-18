"""
Learning Engine - Motor Principal do Sistema de Aprendizagem
Coordena todos os componentes de aprendizagem
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
import asyncio

from config.settings import Settings
from learning.models.user_profile import UserProfile
from learning.storage.learning_store import LearningStore
from memory.memory_manager import MemoryManager
from utils.logger import get_logger

logger = get_logger(__name__)

class LearningEngine:
    """
    Motor central do sistema de aprendizagem
    Coordena perfis, padrões e otimizações
    """
    
    def __init__(self, 
                 settings: Settings,
                 memory_manager: MemoryManager):
        self.settings = settings
        self.memory_manager = memory_manager
        self.learning_store = LearningStore(settings)
        
        # Cache de perfis em memória
        self.profile_cache: Dict[str, UserProfile] = {}
        
        # Configurações
        self.learning_enabled = settings.memory.learning.get("enabled", True)
        self.min_confidence = settings.memory.learning.get("min_confidence", 0.7)
        self.auto_learn = settings.memory.learning.get("auto_learn", True)
        
        logger.info("🧠 Learning Engine initialized")
        logger.info(f"   Learning: {'Enabled' if self.learning_enabled else 'Disabled'}")
        logger.info(f"   Auto-learn: {'Yes' if self.auto_learn else 'No'}")
        logger.info(f"   Min confidence: {self.min_confidence}")
    
    async def get_user_profile(self, user_id: str) -> UserProfile:
        """
        Obtém perfil do usuário (cache ou storage)
        """
        # Verificar cache
        if user_id in self.profile_cache:
            logger.debug(f"Profile found in cache for {user_id}")
            return self.profile_cache[user_id]
        
        # Buscar no storage
        profile_data = await self.learning_store.get_profile(user_id)
        
        if profile_data:
            profile = UserProfile.from_dict(profile_data)
            logger.debug(f"Profile loaded from storage for {user_id}")
        else:
            # Criar novo perfil
            profile = UserProfile(user_id=user_id)
            logger.info(f"Created new profile for {user_id}")
        
        # Adicionar ao cache
        self.profile_cache[user_id] = profile
        
        return profile
    
    async def analyze_interaction(self,
                                 user_id: str,
                                 message: str,
                                 response: str,
                                 metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analisa uma interação e extrai insights de aprendizagem
        """
        if not self.learning_enabled:
            return {}
        
        logger.debug(f"Analyzing interaction for {user_id}")
        
        # Obter perfil
        profile = await self.get_user_profile(user_id)
        
        # Análises
        insights = {
            "user_id": user_id,
            "timestamp": datetime.now().isoformat(),
            "profile_confidence": profile.profile_confidence,
            "communication_style": profile.communication_style.value,
            "should_personalize": profile.profile_confidence >= self.min_confidence,
            "personalization_params": {},
            "patterns_detected": [],
            "suggestions": []
        }
        
        # Se confiança suficiente, adicionar personalização
        if insights["should_personalize"]:
            insights["personalization_params"] = profile.get_personalization_params()
            logger.debug(f"Personalization enabled for {user_id} (confidence: {profile.profile_confidence:.2f})")
        
        # Detectar padrões (simplificado por enquanto)
        patterns = await self._detect_patterns(user_id, message)
        if patterns:
            insights["patterns_detected"] = patterns
        
        # Sugestões de melhoria
        if profile.should_request_feedback():
            insights["suggestions"].append({
                "type": "request_feedback",
                "message": "Você está satisfeito com minhas respostas? Seu feedback é importante!"
            })
        
        return insights
    
    async def learn_from_interaction(self,
                                    user_id: str,
                                    message: str,
                                    response: str,
                                    metadata: Dict[str, Any]) -> None:
        """
        Aprende com a interação e atualiza perfil
        """
        if not self.learning_enabled or not self.auto_learn:
            return
        
        try:
            logger.debug(f"Learning from interaction for {user_id}")
            
            # Obter perfil
            profile = await self.get_user_profile(user_id)
            
            # Atualizar perfil
            profile.update_from_interaction(message, response, metadata)
            
            # Salvar perfil atualizado
            await self.learning_store.save_profile(profile)
            
            # Analisar satisfação implícita
            satisfaction = await self._analyze_implicit_satisfaction(message, response, metadata)
            if satisfaction is not None:
                profile.add_feedback(satisfaction)
            
            logger.info(f"✅ Learned from interaction - User: {user_id}, Confidence: {profile.profile_confidence:.2f}")
            
        except Exception as e:
            logger.error(f"Error learning from interaction: {str(e)}")
    
    async def personalize_response(self,
                                  response: str,
                                  user_id: str,
                                  context: Dict[str, Any]) -> str:
        """
        Personaliza resposta baseado no perfil do usuário
        """
        if not self.learning_enabled:
            return response
        
        try:
            profile = await self.get_user_profile(user_id)
            
            # Só personalizar se tiver confiança suficiente
            if profile.profile_confidence < self.min_confidence:
                return response
            
            # Aplicar personalização baseada no estilo
            if profile.communication_style.value == "formal":
                # Tornar resposta mais formal
                response = self._make_formal(response)
            elif profile.communication_style.value == "casual":
                # Tornar resposta mais casual
                response = self._make_casual(response)
            
            # Ajustar tamanho baseado na preferência
            if profile.response_preference.value == "concise":
                response = self._make_concise(response)
            elif profile.response_preference.value == "detailed":
                response = self._make_detailed(response)
            
            logger.debug(f"Response personalized for {user_id}")
            
        except Exception as e:
            logger.error(f"Error personalizing response: {str(e)}")
        
        return response
    
    async def _detect_patterns(self, user_id: str, message: str) -> List[Dict[str, Any]]:
        """
        Detecta padrões na mensagem (simplificado)
        """
        patterns = []
        
        # Padrão: Pergunta recorrente
        history = await self.memory_manager.get_conversation_history(user_id, limit=10)
        
        if history:
            similar_messages = [h for h in history if self._similarity(message, h.get("message", "")) > 0.7]
            if len(similar_messages) >= 2:
                patterns.append({
                    "type": "recurring_question",
                    "count": len(similar_messages),
                    "confidence": 0.8
                })
        
        # Padrão: Horário típico
        current_hour = datetime.now().hour
        if 9 <= current_hour <= 10:
            patterns.append({
                "type": "morning_routine",
                "confidence": 0.6
            })
        
        return patterns
    
    async def _analyze_implicit_satisfaction(self,
                                            message: str,
                                            response: str,
                                            metadata: Dict[str, Any]) -> Optional[float]:
        """
        Analisa satisfação implícita baseada em sinais
        """
        # Sinais positivos
        positive_signals = ["obrigado", "valeu", "perfeito", "ótimo", "excelente", "ajudou"]
        negative_signals = ["não entendi", "errado", "incorreto", "não é isso", "péssimo"]
        
        message_lower = message.lower()
        
        positive_count = sum(1 for signal in positive_signals if signal in message_lower)
        negative_count = sum(1 for signal in negative_signals if signal in message_lower)
        
        if positive_count > negative_count:
            return 4.5  # Satisfação alta
        elif negative_count > positive_count:
            return 2.0  # Satisfação baixa
        
        return None  # Neutro/indefinido
    
    def _similarity(self, text1: str, text2: str) -> float:
        """
        Calcula similaridade simples entre textos (0-1)
        """
        if not text1 or not text2:
            return 0.0
        
        # Implementação simples baseada em palavras em comum
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def _make_formal(self, response: str) -> str:
        """Torna resposta mais formal"""
        # Substituições simples
        replacements = {
            "oi": "olá",
            "vc": "você",
            "tb": "também",
            "pra": "para"
        }
        
        for informal, formal in replacements.items():
            response = response.replace(informal, formal)
        
        return response
    
    def _make_casual(self, response: str) -> str:
        """Torna resposta mais casual"""
        # Adicionar elementos casuais se não existirem
        if not response.startswith(("Olá", "Oi", "E aí")):
            if response[0].isupper():
                response = "Oi! " + response
        
        return response
    
    def _make_concise(self, response: str) -> str:
        """Torna resposta mais concisa"""
        # Se muito longa, pegar primeiras frases
        sentences = response.split(". ")
        if len(sentences) > 3:
            return ". ".join(sentences[:2]) + "."
        return response
    
    def _make_detailed(self, response: str) -> str:
        """Torna resposta mais detalhada"""
        # Adicionar contexto se muito curta
        if len(response) < 100:
            response += "\n\nPosso fornecer mais detalhes se necessário."
        return response
    
    async def get_learning_stats(self) -> Dict[str, Any]:
        """
        Retorna estatísticas do sistema de aprendizagem
        """
        total_profiles = len(self.profile_cache)
        avg_confidence = 0.0
        
        if self.profile_cache:
            avg_confidence = sum(p.profile_confidence for p in self.profile_cache.values()) / total_profiles
        
        return {
            "learning_enabled": self.learning_enabled,
            "total_profiles_cached": total_profiles,
            "average_confidence": avg_confidence,
            "auto_learn": self.auto_learn,
            "min_confidence_threshold": self.min_confidence
        }
    
    async def cleanup_cache(self, max_age_hours: int = 24) -> int:
        """
        Limpa cache de perfis antigos
        """
        from datetime import timedelta
        
        now = datetime.now()
        profiles_removed = 0
        
        for user_id in list(self.profile_cache.keys()):
            profile = self.profile_cache[user_id]
            age = now - profile.last_updated
            
            if age > timedelta(hours=max_age_hours):
                del self.profile_cache[user_id]
                profiles_removed += 1
        
        if profiles_removed > 0:
            logger.info(f"Cleaned {profiles_removed} profiles from cache")
        
        return profiles_removed