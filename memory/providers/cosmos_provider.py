"""
Cosmos Provider - Storage WARM
Rápido, indexado, mais caro
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from azure.cosmos import CosmosClient, PartitionKey
from azure.cosmos.exceptions import CosmosHttpResponseError
import uuid

from config.settings import Settings
from utils.logger import get_logger

logger = get_logger(__name__)

class CosmosProvider:
    """Provider de storage em Cosmos DB - WARM tier"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = None
        self.database = None
        self.container = None
        self.available = False
        
        self._initialize_cosmos()
    
    def _initialize_cosmos(self):
        """Inicializa conexão com Cosmos"""
        try:
            endpoint = self.settings.cosmos.endpoint
            key = self.settings.cosmos.key
            
            if not endpoint or not key:
                logger.warning("Cosmos credentials not provided")
                return
            
            # Conectar
            self.client = CosmosClient(endpoint, credential=key)
            
            # Database
            db_name = self.settings.cosmos.database or "bot-memory"
            self.database = self.client.create_database_if_not_exists(db_name)
            
            # Container com TTL
            self.container = self.database.create_container_if_not_exists(
                id="conversations",
                partition_key=PartitionKey(path="/userId"),
                default_ttl=self.settings.cosmos.ttl_days * 86400  # dias para segundos
            )
            
            self.available = True
            logger.info("✅ Cosmos DB provider initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize Cosmos: {str(e)}")
            self.available = False
    
    async def save(self, key: str, data: Dict[str, Any], **kwargs) -> bool:
        """Salva no Cosmos"""
        if not self.available:
            return False
        
        try:
            # Preparar documento
            document = {
                "id": str(uuid.uuid4()),
                "key": key,
                "userId": data.get("user_id", "unknown"),
                "type": "conversation",
                "timestamp": data.get("timestamp", datetime.now(timezone.utc).isoformat()),
                "message": data.get("message"),
                "response": data.get("response"),
                "metadata": data.get("metadata", {}),
                "ttl": kwargs.get("ttl", self.settings.cosmos.ttl_days * 86400)
            }
            
            # Salvar
            self.container.create_item(document)
            logger.debug(f"Saved to Cosmos: {key}")
            return True
            
        except CosmosHttpResponseError as e:
            logger.error(f"Cosmos save error: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected Cosmos error: {str(e)}")
            return False
    
    async def load(self, key: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Carrega do Cosmos"""
        if not self.available:
            return None
        
        try:
            # Buscar por key
            query = "SELECT * FROM c WHERE c.key = @key"
            items = list(self.container.query_items(
                query=query,
                parameters=[{"name": "@key", "value": key}],
                enable_cross_partition_query=True
            ))
            
            if items:
                return items[0]
            return None
            
        except Exception as e:
            logger.error(f"Cosmos load error: {str(e)}")
            return None
    
    async def search(self, query: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        """Busca no Cosmos"""
        if not self.available:
            return []
        
        try:
            user_id = query.get("user_id")
            limit = query.get("limit", 10)
            
            # Query otimizada (sem cross-partition)
            cosmos_query = """
                SELECT TOP @limit 
                    c.message, 
                    c.response, 
                    c.timestamp,
                    c.metadata
                FROM c 
                WHERE c.userId = @userId 
                    AND c.type = 'conversation'
                ORDER BY c.timestamp DESC
            """
            
            items = list(self.container.query_items(
                query=cosmos_query,
                parameters=[
                    {"name": "@limit", "value": limit},
                    {"name": "@userId", "value": user_id}
                ],
                partition_key=user_id  # Evita cross-partition query
            ))
            
            logger.debug(f"Found {len(items)} items in Cosmos for {user_id}")
            return items
            
        except Exception as e:
            logger.error(f"Cosmos search error: {str(e)}")
            return []
    
    async def delete(self, key: str, **kwargs) -> bool:
        """Deleta do Cosmos"""
        if not self.available:
            return False
        
        try:
            # Buscar documento
            item = await self.load(key)
            if item:
                self.container.delete_item(
                    item=item["id"],
                    partition_key=item["userId"]
                )
                return True
            return False
            
        except Exception as e:
            logger.error(f"Cosmos delete error: {str(e)}")
            return False
    
    def is_available(self) -> bool:
        """Verifica se Cosmos está disponível"""
        return self.available