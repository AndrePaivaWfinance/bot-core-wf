"""
Cosmos Provider - Storage WARM
Versão corrigida com partition key e queries otimizadas
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from azure.cosmos import CosmosClient, PartitionKey
from azure.cosmos.exceptions import CosmosHttpResponseError, CosmosResourceNotFoundError
import uuid
import json

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
        
        # Configurações do container
        self.database_name = "meshbrain-memory"
        self.container_name = "conversations"
        self.partition_key_path = "/userId"  # Define o campo usado como partition key
        
        self._initialize_cosmos()
    
    def _initialize_cosmos(self):
        """Inicializa conexão com Cosmos com criação automática de recursos"""
        try:
            endpoint = self.settings.cosmos.endpoint
            key = self.settings.cosmos.key
            
            if not endpoint or not key:
                logger.warning("⚠️ Cosmos credentials not provided")
                return
            
            logger.info("🔷 Initializing Cosmos DB Provider...")
            logger.debug(f"   Endpoint: {endpoint[:40]}...")
            logger.debug(f"   Database: {self.database_name}")
            logger.debug(f"   Container: {self.container_name}")
            
            # Conectar ao Cosmos
            self.client = CosmosClient(endpoint, credential=key)
            
            # Criar database se não existir
            self.database = self.client.create_database_if_not_exists(
                id=self.database_name
            )
            logger.info(f"   ✅ Database '{self.database_name}' ready")
            
            # Criar container com TTL e partition key corretos
            ttl_seconds = self.settings.cosmos.ttl_days * 86400  # dias para segundos
            
            # Detectar se é serverless (não suporta offer_throughput)
            try:
                # Tentar criar com throughput primeiro (para contas provisionadas)
                self.container = self.database.create_container_if_not_exists(
                    id=self.container_name,
                    partition_key=PartitionKey(path=self.partition_key_path),
                    default_ttl=ttl_seconds,
                    offer_throughput=400  # RU/s mínimo
                )
                logger.info("   📊 Using provisioned throughput mode (400 RU/s)")
            except Exception as e:
                if "serverless" in str(e).lower() or "offer throughput" in str(e).lower():
                    # É serverless, criar sem throughput
                    logger.info("   🌐 Detected serverless account, creating without throughput")
                    self.container = self.database.create_container_if_not_exists(
                        id=self.container_name,
                        partition_key=PartitionKey(path=self.partition_key_path),
                        default_ttl=ttl_seconds
                        # SEM offer_throughput para serverless!
                    )
                    logger.info("   ✅ Using serverless mode (pay-per-request)")
                else:
                    raise e
            
            self.available = True
            logger.info(f"✅ Cosmos DB provider initialized successfully")
            logger.info(f"   Container: {self.container_name}")
            logger.info(f"   Partition Key: {self.partition_key_path}")
            logger.info(f"   TTL: {self.settings.cosmos.ttl_days} days")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Cosmos: {str(e)}")
            logger.error(f"   Check your connection string and permissions")
            self.available = False
    
    async def save(self, key: str, data: Dict[str, Any], **kwargs) -> bool:
        """
        Salva no Cosmos com estrutura otimizada
        
        Args:
            key: Chave única do documento
            data: Dados para salvar
            **kwargs: Parametros adicionais (ttl customizado, etc)
        """
        if not self.available:
            logger.debug("Cosmos not available, skipping save")
            return False
        
        try:
            # Extrair userId (CRÍTICO para partition key)
            user_id = data.get("user_id") or data.get("userId") or "unknown"
            
            # Preparar documento com estrutura correta
            document = {
                "id": str(uuid.uuid4()),  # ID único do documento
                "key": key,  # Chave de referência
                "userId": user_id,  # PARTITION KEY - CRÍTICO!
                "type": data.get("type", "conversation"),
                "timestamp": data.get("timestamp", datetime.now(timezone.utc).isoformat()),
                "message": data.get("message"),
                "response": data.get("response"),
                "metadata": data.get("metadata", {}),
                "channel": data.get("metadata", {}).get("channel", "unknown"),
                "provider": data.get("metadata", {}).get("provider", "unknown"),
                "confidence": data.get("metadata", {}).get("confidence", 0.0),
                # TTL em segundos (sobrescreve o padrão se fornecido)
                "ttl": kwargs.get("ttl", self.settings.cosmos.ttl_days * 86400)
            }
            
            # Salvar no Cosmos
            created_item = self.container.create_item(document)
            
            logger.debug(f"💾 Saved to Cosmos: {key}")
            logger.debug(f"   userId (partition): {user_id}")
            logger.debug(f"   Document ID: {document['id']}")
            
            return True
            
        except CosmosHttpResponseError as e:
            if e.status_code == 409:
                logger.debug(f"Document already exists: {key}")
            else:
                logger.error(f"❌ Cosmos save error: {e.status_code} - {e.message}")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected Cosmos error: {str(e)}")
            return False
    
    async def load(self, key: str, user_id: Optional[str] = None, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Carrega do Cosmos por key
        
        Args:
            key: Chave do documento
            user_id: ID do usuário (para otimizar busca com partition key)
        """
        if not self.available:
            return None
        
        try:
            # Se temos o user_id, usar busca otimizada com partition key
            if user_id:
                query = "SELECT * FROM c WHERE c.key = @key AND c.userId = @userId"
                items = list(self.container.query_items(
                    query=query,
                    parameters=[
                        {"name": "@key", "value": key},
                        {"name": "@userId", "value": user_id}
                    ],
                    partition_key=user_id  # Busca otimizada!
                ))
            else:
                # Busca cross-partition (mais lenta)
                query = "SELECT * FROM c WHERE c.key = @key"
                items = list(self.container.query_items(
                    query=query,
                    parameters=[{"name": "@key", "value": key}],
                    enable_cross_partition_query=True  # Necessário sem partition key
                ))
            
            if items:
                logger.debug(f"📖 Loaded from Cosmos: {key}")
                return items[0]
            
            logger.debug(f"Document not found: {key}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Cosmos load error: {str(e)}")
            return None
    
    async def search(self, query: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        """
        Busca no Cosmos com queries otimizadas
        
        Args:
            query: Dict com parametros de busca
                - user_id: ID do usuário (usa partition key)
                - limit: Número máximo de resultados
                - type: Tipo de documento
                - since: Buscar após esta data
        """
        if not self.available:
            return []
        
        try:
            user_id = query.get("user_id")
            limit = query.get("limit", 10)
            doc_type = query.get("type", "conversation")
            since_date = query.get("since")
            
            # Construir query SQL
            conditions = ["c.type = @type"]
            parameters = [{"name": "@type", "value": doc_type}]
            
            # Se temos user_id, adicionar à query
            if user_id:
                conditions.append("c.userId = @userId")
                parameters.append({"name": "@userId", "value": user_id})
            
            # Se temos data mínima
            if since_date:
                conditions.append("c.timestamp >= @since")
                parameters.append({"name": "@since", "value": since_date})
            
            # Montar query final
            where_clause = " AND ".join(conditions)
            cosmos_query = f"""
                SELECT TOP {limit}
                    c.id,
                    c.key,
                    c.userId,
                    c.message,
                    c.response,
                    c.timestamp,
                    c.metadata,
                    c.channel,
                    c.provider,
                    c.confidence
                FROM c
                WHERE {where_clause}
                ORDER BY c.timestamp DESC
            """
            
            # Executar query com otimização
            if user_id:
                # Query otimizada com partition key
                items = list(self.container.query_items(
                    query=cosmos_query,
                    parameters=parameters,
                    partition_key=user_id  # ← OTIMIZAÇÃO CRÍTICA!
                ))
                logger.debug(f"🔍 Cosmos query with partition key for user: {user_id}")
            else:
                # Query cross-partition (mais lenta, use com moderação)
                items = list(self.container.query_items(
                    query=cosmos_query,
                    parameters=parameters,
                    enable_cross_partition_query=True  # ← NECESSÁRIO!
                ))
                logger.debug(f"🔍 Cosmos cross-partition query")
            
            logger.info(f"📊 Found {len(items)} items in Cosmos")
            
            # Log sample para debug
            if items and logger.isEnabledFor(10):  # DEBUG level
                sample = items[0]
                logger.debug(f"   Sample: userId={sample.get('userId')}, "
                           f"timestamp={sample.get('timestamp', 'N/A')[:19]}, "
                           f"message={sample.get('message', '')[:30]}...")
            
            return items
            
        except Exception as e:
            logger.error(f"❌ Cosmos search error: {str(e)}")
            logger.error(f"   Query params: {query}")
            return []
    
    async def delete(self, key: str, user_id: Optional[str] = None, **kwargs) -> bool:
        """
        Deleta do Cosmos
        
        Args:
            key: Chave do documento
            user_id: ID do usuário (necessário para deletar com partition key)
        """
        if not self.available:
            return False
        
        try:
            # Primeiro, tentar encontrar o documento
            item = await self.load(key, user_id)
            
            if item:
                # Deletar usando ID e partition key
                self.container.delete_item(
                    item=item["id"],
                    partition_key=item["userId"]
                )
                logger.debug(f"🗑️ Deleted from Cosmos: {key}")
                return True
            
            logger.debug(f"Document not found for deletion: {key}")
            return False
            
        except CosmosResourceNotFoundError:
            logger.debug(f"Document already deleted or not found: {key}")
            return False
        except Exception as e:
            logger.error(f"❌ Cosmos delete error: {str(e)}")
            return False
    
    async def get_user_context(self, user_id: str) -> Dict[str, Any]:
        """
        Busca contexto específico do usuário
        Otimizado para buscar preferências e padrões
        """
        if not self.available:
            return {}
        
        try:
            # Buscar documento de contexto/perfil do usuário
            query = """
                SELECT TOP 1 *
                FROM c
                WHERE c.userId = @userId 
                AND c.type = 'user_context'
                ORDER BY c.timestamp DESC
            """
            
            items = list(self.container.query_items(
                query=query,
                parameters=[{"name": "@userId", "value": user_id}],
                partition_key=user_id  # Busca otimizada
            ))
            
            if items:
                context = items[0]
                logger.debug(f"📋 Found user context for: {user_id}")
                return context.get("preferences", {})
            
            return {}
            
        except Exception as e:
            logger.error(f"Error getting user context: {str(e)}")
            return {}
    
    async def save_user_context(self, user_id: str, context: Dict[str, Any]) -> bool:
        """
        Salva contexto/preferências do usuário
        """
        if not self.available:
            return False
        
        try:
            document = {
                "id": f"context_{user_id}",
                "userId": user_id,  # Partition key
                "type": "user_context",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "preferences": context,
                # Contexto não expira (sem TTL)
            }
            
            # Upsert (atualiza se existir, cria se não)
            self.container.upsert_item(document)
            
            logger.debug(f"💾 Saved user context for: {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving user context: {str(e)}")
            return False
    
    def is_available(self) -> bool:
        """Verifica se Cosmos está disponível"""
        return self.available
    
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Retorna estatísticas do container
        Útil para monitoramento e debug
        """
        if not self.available:
            return {"available": False}
        
        try:
            # Query para estatísticas
            stats_query = """
                SELECT 
                    COUNT(1) as total,
                    c.type,
                    c.provider
                FROM c
                GROUP BY c.type, c.provider
            """
            
            stats = list(self.container.query_items(
                query=stats_query,
                enable_cross_partition_query=True
            ))
            
            # Query para usuários únicos
            users_query = """
                SELECT DISTINCT VALUE c.userId
                FROM c
            """
            
            users = list(self.container.query_items(
                query=users_query,
                enable_cross_partition_query=True
            ))
            
            return {
                "available": True,
                "database": self.database_name,
                "container": self.container_name,
                "statistics": stats,
                "unique_users": len(users),
                "partition_key": self.partition_key_path
            }
            
        except Exception as e:
            logger.error(f"Error getting statistics: {str(e)}")
            return {"available": True, "error": str(e)}