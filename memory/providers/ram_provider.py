"""
RAM Provider - Storage HOT em memória
Super rápido, temporário, grátis
"""
from typing import Dict, List, Any, Optional
from collections import deque
from datetime import datetime, timedelta
import time

from utils.logger import get_logger

logger = get_logger(__name__)

class RAMProvider:
    """Provider de storage em RAM - HOT tier"""
    
    def __init__(self, max_items: int = 100, ttl_minutes: int = 30):
        self.max_items = max_items
        self.ttl_seconds = ttl_minutes * 60
        self.storage = {}  # user_id -> deque of items
        self.timestamps = {}  # key -> timestamp
    
    async def save(self, key: str, data: Dict[str, Any], **kwargs) -> bool:
        """Salva em RAM com TTL"""
        try:
            user_id = data.get("user_id", "unknown")
            
            # Criar deque para o usuário se não existir
            if user_id not in self.storage:
                self.storage[user_id] = deque(maxlen=self.max_items)
            
            # Adicionar dados
            self.storage[user_id].append({
                "key": key,
                "data": data,
                "timestamp": time.time()
            })
            
            # Registrar timestamp para TTL
            self.timestamps[key] = time.time()
            
            # Limpar dados expirados periodicamente
            if len(self.timestamps) % 10 == 0:
                self._cleanup_expired()
            
            return True
            
        except Exception as e:
            logger.error(f"RAM save error: {str(e)}")
            return False
    
    async def load(self, key: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Carrega da RAM se ainda válido"""
        try:
            # Verificar TTL
            if key in self.timestamps:
                if time.time() - self.timestamps[key] > self.ttl_seconds:
                    # Expirado
                    del self.timestamps[key]
                    return None
            
            # Buscar nos dados
            for user_data in self.storage.values():
                for item in user_data:
                    if item["key"] == key:
                        return item["data"]
            
            return None
            
        except Exception as e:
            logger.error(f"RAM load error: {str(e)}")
            return None
    
    async def search(self, query: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        """Busca na RAM"""
        try:
            user_id = query.get("user_id")
            limit = query.get("limit", 10)
            
            if user_id not in self.storage:
                return []
            
            # Pegar itens mais recentes
            items = list(self.storage[user_id])
            items.reverse()  # Mais recente primeiro
            
            # Filtrar expirados
            current_time = time.time()
            valid_items = []
            
            for item in items[:limit]:
                if current_time - item["timestamp"] <= self.ttl_seconds:
                    valid_items.append(item["data"])
            
            return valid_items
            
        except Exception as e:
            logger.error(f"RAM search error: {str(e)}")
            return []
    
    async def delete(self, key: str, **kwargs) -> bool:
        """Remove da RAM"""
        try:
            # Remover timestamp
            if key in self.timestamps:
                del self.timestamps[key]
            
            # Remover dos dados
            for user_data in self.storage.values():
                for i, item in enumerate(user_data):
                    if item["key"] == key:
                        del user_data[i]
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"RAM delete error: {str(e)}")
            return False
    
    def is_available(self) -> bool:
        """RAM sempre disponível"""
        return True
    
    def _cleanup_expired(self):
        """Remove itens expirados"""
        current_time = time.time()
        expired_keys = [
            k for k, t in self.timestamps.items()
            if current_time - t > self.ttl_seconds
        ]
        
        for key in expired_keys:
            del self.timestamps[key]
        
        if expired_keys:
            logger.debug(f"Cleaned {len(expired_keys)} expired items from RAM")