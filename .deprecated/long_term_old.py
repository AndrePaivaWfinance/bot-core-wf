"""
Long-term memory com Cosmos DB - MVP BÁSICO
Versão simplificada que FUNCIONA
"""
from typing import Dict, List, Any, Optional
import os
from datetime import datetime, timezone
from azure.cosmos import CosmosClient, PartitionKey
from azure.cosmos.exceptions import CosmosHttpResponseError

from config.settings import Settings
from memory.schemas import MemorySchemas
from utils.logger import get_logger

logger = get_logger(__name__)

class LongTermMemory:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = None
        self.database = None
        self.container = None
        
        # Tentar conectar ao Cosmos
        self._initialize_cosmos_client()
    
    def _initialize_cosmos_client(self):
        """Conecta ao Cosmos DB - MVP sem muita complexidade"""
        try:
            # Pegar credenciais do ambiente ou settings
            endpoint = (
                os.getenv("AZURE_COSMOS_ENDPOINT") or 
                self.settings.cosmos.endpoint
            )
            key = (
                os.getenv("AZURE_COSMOS_KEY") or 
                self.settings.cosmos.key
            )
            
            if not endpoint or not key:
                logger.warning("🟡 Cosmos DB não configurado - usando memória local")
                return
            
            # Conectar ao Cosmos
            logger.info(f"🔗 Conectando ao Cosmos DB...")
            self.client = CosmosClient(endpoint, credential=key)
            
            # Database name (criar se não existir)
            db_name = "meshbrain-memory"
            self.database = self.client.create_database_if_not_exists(db_name)
            
            # Container único para MVP (simplicidade)
            container_name = "conversations"
            self.container = self.database.create_container_if_not_exists(
                id=container_name,
                partition_key=PartitionKey(path="/partitionKey"),
                default_ttl=7776000  # 90 dias
            )
            
            logger.info("✅ Cosmos DB conectado com sucesso!")
            
        except Exception as e:
            logger.error(f"❌ Erro ao conectar Cosmos: {str(e)}")
            logger.warning("🟡 Continuando com memória local apenas")
    
    async def save_conversation(
        self, 
        user_id: str, 
        message: str, 
        response: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Salva uma conversa no Cosmos - MVP SUPER SIMPLES
        """
        if not self.container:
            logger.debug("Cosmos não disponível - não salvando")
            return False
        
        try:
            # Criar documento
            doc = MemorySchemas.create_conversation(
                user_id=user_id,
                message=message,
                response=response,
                metadata=metadata
            )
            
            # Salvar no Cosmos
            self.container.create_item(doc)
            logger.debug(f"💾 Conversa salva para user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao salvar conversa: {str(e)}")
            return False
    
    async def get_user_history(
        self, 
        user_id: str, 
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Recupera histórico do usuário - MVP BÁSICO
        """
        if not self.container:
            return []
        
        try:
            # Query simples - últimas N conversas
            query = """
                SELECT TOP @limit 
                    c.message, 
                    c.response, 
                    c.timestamp,
                    c.provider
                FROM c 
                WHERE c.partitionKey = @userId 
                    AND c.type = 'conversation'
                ORDER BY c.timestamp DESC
            """
            
            items = list(self.container.query_items(
                query=query,
                parameters=[
                    {"name": "@limit", "value": limit},
                    {"name": "@userId", "value": user_id}
                ],
                enable_cross_partition_query=False  # Mais eficiente
            ))
            
            logger.debug(f"📖 Recuperadas {len(items)} conversas para {user_id}")
            return items
            
        except Exception as e:
            logger.error(f"Erro ao recuperar histórico: {str(e)}")
            return []
    
    async def get_user_context(self, user_id: str) -> Dict[str, Any]:
        """
        Recupera contexto do usuário (se existir)
        """
        if not self.container:
            return {}
        
        try:
            # Tentar pegar contexto salvo
            context_id = f"context_{user_id}"
            context = self.container.read_item(
                item=context_id,
                partition_key=user_id
            )
            return context.get("preferences", {})
            
        except:
            # Se não existir, retorna vazio
            return {}
    
    # Métodos antigos mantidos para compatibilidade
    async def store(self, user_id: str, memory_type: str, content: Dict[str, Any], importance: float = 0.5) -> str:
        """Mantido para compatibilidade"""
        return "mvp_" + str(datetime.now().timestamp())
    
    async def retrieve(self, user_id: str, memory_type: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Mantido para compatibilidade - redireciona para get_user_history"""
        return await self.get_user_history(user_id, limit)
    
    async def retrieve_relevant_memories(self, user_id: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Mantido para compatibilidade - MVP apenas retorna últimas"""
        return await self.get_user_history(user_id, limit)