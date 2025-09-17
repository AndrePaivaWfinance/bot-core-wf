"""
Memory Manager - Gerenciador Central de Memória
Arquitetura modular e extensível para múltiplas camadas de storage
"""
from typing import Dict, List, Any, Optional, Protocol
from datetime import datetime, timedelta, timezone
from enum import Enum
import json

from config.settings import Settings
from utils.logger import get_logger

logger = get_logger(__name__)

class StorageTier(Enum):
    """Níveis de storage disponíveis"""
    HOT = "hot"      # RAM - microsegundos
    WARM = "warm"    # Cosmos - milisegundos  
    COLD = "cold"    # Blob - segundos
    ARCHIVE = "archive"  # Futuro: Glacier/Archive

class IStorageProvider(Protocol):
    """Interface que todo provider de storage deve implementar"""
    
    async def save(self, key: str, data: Dict[str, Any], **kwargs) -> bool:
        """Salva dados"""
        ...
    
    async def load(self, key: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Carrega dados"""
        ...
    
    async def search(self, query: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        """Busca dados"""
        ...
    
    async def delete(self, key: str, **kwargs) -> bool:
        """Deleta dados"""
        ...
    
    def is_available(self) -> bool:
        """Verifica se o storage está disponível"""
        ...

class MemoryManager:
    """
    Gerenciador central de memória com múltiplas camadas
    Coordena entre diferentes tipos de storage de forma inteligente
    """
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.providers: Dict[StorageTier, IStorageProvider] = {}
        
        # Políticas de storage (configurável)
        self.policies = {
            "hot_duration": timedelta(minutes=30),    # Quanto tempo em RAM
            "warm_duration": timedelta(days=7),       # Quanto tempo em Cosmos
            "cold_duration": timedelta(days=90),      # Quanto tempo em Blob
            "archive_after": timedelta(days=365),     # Quando arquivar
        }
        
        # Inicializar providers disponíveis
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Inicializa os providers de storage disponíveis"""
        
        # 1. HOT Storage (RAM) - Sempre disponível
        from memory.providers.ram_provider import RAMProvider
        self.providers[StorageTier.HOT] = RAMProvider(
            max_items=self.settings.memory.short_term.get("max_messages", 20),
            ttl_minutes=self.settings.memory.short_term.get("ttl_minutes", 30)
        )
        logger.info("✅ HOT storage (RAM) inicializado")
        
        # 2. WARM Storage (Cosmos) - Se configurado
        if self.settings.cosmos.endpoint and self.settings.cosmos.key:
            try:
                from memory.providers.cosmos_provider import CosmosProvider
                self.providers[StorageTier.WARM] = CosmosProvider(self.settings)
                logger.info("✅ WARM storage (Cosmos) inicializado")
            except Exception as e:
                logger.warning(f"⚠️ Cosmos não disponível: {str(e)}")
        
        # 3. COLD Storage (Blob) - Se configurado
        if self.settings.blob_storage.connection_string:
            try:
                from memory.providers.blob_provider import BlobProvider
                self.providers[StorageTier.COLD] = BlobProvider(self.settings)
                logger.info("✅ COLD storage (Blob) inicializado")
            except Exception as e:
                logger.warning(f"⚠️ Blob storage não disponível: {str(e)}")
    
    async def save_conversation(
        self, 
        user_id: str,
        message: str,
        response: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Salva uma conversa usando a estratégia apropriada
        MVP: Salva em HOT + WARM simultaneamente
        Futuro: Implementar políticas de tiering
        """
        
        # Preparar dados
        conversation_data = {
            "user_id": user_id,
            "message": message,
            "response": response,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata
        }
        
        # Gerar chave única
        key = f"{user_id}:{datetime.now().timestamp()}"
        
        saved = False
        
        # 1. SEMPRE salvar em HOT (RAM) para acesso imediato
        if StorageTier.HOT in self.providers:
            try:
                await self.providers[StorageTier.HOT].save(key, conversation_data)
                saved = True
                logger.debug(f"💾 Saved to HOT storage: {user_id}")
            except Exception as e:
                logger.error(f"Failed to save to HOT: {str(e)}")
        
        # 2. Salvar em WARM (Cosmos) se disponível
        if StorageTier.WARM in self.providers:
            try:
                await self.providers[StorageTier.WARM].save(key, conversation_data)
                saved = True
                logger.debug(f"💾 Saved to WARM storage: {user_id}")
            except Exception as e:
                logger.error(f"Failed to save to WARM: {str(e)}")
        
        # 3. Para dados importantes, salvar também em COLD
        importance = metadata.get("confidence", 0.5)
        if importance > 0.8 and StorageTier.COLD in self.providers:
            try:
                await self.providers[StorageTier.COLD].save(key, conversation_data)
                logger.debug(f"💾 Important conversation saved to COLD storage")
            except Exception as e:
                logger.error(f"Failed to save to COLD: {str(e)}")
        
        return saved
    
    async def get_conversation_history(
        self, 
        user_id: str,
        limit: int = 10,
        time_range: Optional[tuple] = None
    ) -> List[Dict[str, Any]]:
        """
        Busca histórico de conversas
        Estratégia: HOT → WARM → COLD (para de buscar quando encontrar suficiente)
        """
        results = []
        needed = limit
        
        # 1. Buscar em HOT primeiro (mais rápido)
        if StorageTier.HOT in self.providers and needed > 0:
            try:
                hot_results = await self.providers[StorageTier.HOT].search(
                    {"user_id": user_id, "limit": needed}
                )
                results.extend(hot_results)
                needed -= len(hot_results)
                logger.debug(f"Found {len(hot_results)} in HOT storage")
            except Exception as e:
                logger.error(f"HOT search failed: {str(e)}")
        
        # 2. Se precisar mais, buscar em WARM
        if StorageTier.WARM in self.providers and needed > 0:
            try:
                warm_results = await self.providers[StorageTier.WARM].search(
                    {"user_id": user_id, "limit": needed}
                )
                results.extend(warm_results)
                needed -= len(warm_results)
                logger.debug(f"Found {len(warm_results)} in WARM storage")
            except Exception as e:
                logger.error(f"WARM search failed: {str(e)}")
        
        # 3. Se ainda precisar mais, buscar em COLD
        if StorageTier.COLD in self.providers and needed > 0 and time_range:
            try:
                cold_results = await self.providers[StorageTier.COLD].search(
                    {
                        "user_id": user_id, 
                        "limit": needed,
                        "time_range": time_range
                    }
                )
                results.extend(cold_results)
                logger.debug(f"Found {len(cold_results)} in COLD storage")
            except Exception as e:
                logger.error(f"COLD search failed: {str(e)}")
        
        # Ordenar por timestamp (mais recente primeiro)
        results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        return results[:limit]
    
    async def get_user_context(self, user_id: str) -> Dict[str, Any]:
        """
        Recupera contexto do usuário (preferências, padrões, etc)
        Busca primeiro em WARM (Cosmos) por ser estruturado
        """
        context = {}
        
        # Buscar contexto em WARM storage
        if StorageTier.WARM in self.providers:
            try:
                user_data = await self.providers[StorageTier.WARM].load(f"context:{user_id}")
                if user_data:
                    context = user_data.get("preferences", {})
            except Exception as e:
                logger.debug(f"No context found for {user_id}: {str(e)}")
        
        return context
    
    async def archive_old_data(self) -> int:
        """
        Move dados antigos para storage mais barato
        HOT → WARM → COLD → ARCHIVE
        Retorna número de itens movidos
        """
        moved_count = 0
        
        # Por enquanto, apenas log
        # TODO: Implementar lógica de archiving
        logger.info("📦 Archive job would run here (not implemented in MVP)")
        
        return moved_count
    
    async def optimize_storage(self) -> Dict[str, Any]:
        """
        Otimiza uso de storage baseado em padrões de acesso
        Retorna estatísticas de otimização
        """
        stats = {
            "hot_items": 0,
            "warm_items": 0, 
            "cold_items": 0,
            "optimizations": []
        }
        
        # TODO: Implementar análise e otimização
        logger.debug("Storage optimization would run here")
        
        return stats
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """
        Retorna estatísticas de uso de storage
        """
        stats = {
            "providers": {},
            "health": "healthy"
        }
        
        for tier, provider in self.providers.items():
            stats["providers"][tier.value] = {
                "available": provider.is_available(),
                "type": provider.__class__.__name__
            }
        
        # Se não tiver WARM ou COLD, marcar como degraded
        if StorageTier.WARM not in self.providers:
            stats["health"] = "degraded"
            stats["warning"] = "No WARM storage available"
        
        return stats

# Factory function para facilitar criação
def create_memory_manager(settings: Settings) -> MemoryManager:
    """Factory function para criar o memory manager"""
    return MemoryManager(settings)