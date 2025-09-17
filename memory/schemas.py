"""
Schemas básicos para o Cosmos DB - MVP
Manteremos SUPER SIMPLES para funcionar rápido
"""
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import uuid

class MemorySchemas:
    """Schemas simplificados para MVP"""
    
    @staticmethod
    def create_conversation(user_id: str, message: str, response: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Cria um documento de conversa para salvar no Cosmos
        MVP: Salvamos TUDO em um único container para simplicidade
        """
        return {
            "id": str(uuid.uuid4()),
            "partitionKey": user_id,  # Particionar por usuário
            "type": "conversation",
            "userId": user_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": message,
            "response": response,
            "provider": metadata.get("provider", "unknown"),
            "confidence": metadata.get("confidence", 0.0),
            # TTL de 90 dias (em segundos)
            "ttl": 7776000
        }
    
    @staticmethod
    def create_user_context(user_id: str, context_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Cria/atualiza contexto do usuário
        MVP: Apenas informações básicas
        """
        return {
            "id": f"context_{user_id}",
            "partitionKey": user_id,
            "type": "user_context",
            "userId": user_id,
            "lastActive": datetime.now(timezone.utc).isoformat(),
            "messageCount": context_data.get("message_count", 0),
            "preferences": context_data.get("preferences", {}),
            # Sem TTL - contexto do usuário permanece
        }
    
    @staticmethod
    def create_daily_summary(user_id: str, date: str, summary: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resumo diário de interações (opcional para MVP)
        """
        return {
            "id": f"summary_{user_id}_{date}",
            "partitionKey": user_id,
            "type": "daily_summary",
            "userId": user_id,
            "date": date,
            "totalMessages": summary.get("total", 0),
            "topics": summary.get("topics", []),
            "ttl": 2592000  # 30 dias
        }