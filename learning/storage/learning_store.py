"""
Learning Store - Armazenamento para Sistema de Aprendizagem
Gerencia persistência de perfis, padrões e conhecimento
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json
import uuid

from config.settings import Settings
from utils.logger import get_logger

logger = get_logger(__name__)

class LearningStore:
    """
    Storage para dados de aprendizagem
    Usa Cosmos DB para persistência
    """
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = None
        self.database = None
        self.profiles_container = None
        self.patterns_container = None
        self.knowledge_container = None
        self.available = False
        
        self._initialize_storage()
    
    def _initialize_storage(self):
        """Inicializa conexão com Cosmos DB"""
        try:
            # Verificar se Cosmos está configurado
            if not self.settings.cosmos.endpoint or not self.settings.cosmos.key:
                logger.warning("Cosmos DB not configured for Learning Store")
                logger.info("Using in-memory storage only")
                self._init_memory_storage()
                return
            
            from azure.cosmos import CosmosClient, PartitionKey
            
            # Conectar ao Cosmos
            self.client = CosmosClient(
                self.settings.cosmos.endpoint,
                credential=self.settings.cosmos.key
            )
            
            # Database
            db_name = self.settings.cosmos.database or "bot-memory"
            self.database = self.client.get_database_client(db_name)
            
            # Container para perfis de usuário
            try:
                self.profiles_container = self.database.create_container_if_not_exists(
                    id="user_profiles_enhanced",
                    partition_key=PartitionKey(path="/userId"),
                    default_ttl=None  # Perfis não expiram
                )
                logger.info("✅ User profiles container ready")
            except Exception as e:
                logger.error(f"Error creating profiles container: {str(e)}")
            
            # Container para padrões detectados
            try:
                self.patterns_container = self.database.create_container_if_not_exists(
                    id="learning_patterns",
                    partition_key=PartitionKey(path="/userId"),
                    default_ttl=2592000  # 30 dias
                )
                logger.info("✅ Patterns container ready")
            except Exception as e:
                logger.error(f"Error creating patterns container: {str(e)}")
            
            # Container para base de conhecimento
            try:
                self.knowledge_container = self.database.create_container_if_not_exists(
                    id="knowledge_base",
                    partition_key=PartitionKey(path="/domain"),
                    default_ttl=None  # Conhecimento não expira
                )
                logger.info("✅ Knowledge base container ready")
            except Exception as e:
                logger.error(f"Error creating knowledge container: {str(e)}")
            
            self.available = True
            logger.info("✅ Learning Store initialized with Cosmos DB")
            
        except Exception as e:
            logger.error(f"Failed to initialize Cosmos DB: {str(e)}")
            logger.info("Falling back to in-memory storage")
            self._init_memory_storage()
    
    def _init_memory_storage(self):
        """Inicializa storage em memória como fallback"""
        self.memory_profiles = {}
        self.memory_patterns = {}
        self.memory_knowledge = {}
        self.available = True
        logger.info("✅ Learning Store using in-memory storage")
    
    async def save_profile(self, profile) -> bool:
        """
        Salva perfil de usuário
        """
        try:
            profile_dict = profile.to_dict()
            profile_dict["id"] = f"profile_{profile.user_id}"
            profile_dict["userId"] = profile.user_id  # Para partição
            profile_dict["type"] = "user_profile"
            profile_dict["last_saved"] = datetime.now().isoformat()
            
            if self.profiles_container:
                # Salvar no Cosmos
                self.profiles_container.upsert_item(profile_dict)
                logger.debug(f"Profile saved to Cosmos for user {profile.user_id}")
            else:
                # Salvar em memória
                self.memory_profiles[profile.user_id] = profile_dict
                logger.debug(f"Profile saved to memory for user {profile.user_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error saving profile: {str(e)}")
            return False
    
    async def get_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Recupera perfil de usuário
        """
        try:
            if self.profiles_container:
                # Buscar no Cosmos
                query = "SELECT * FROM c WHERE c.userId = @userId AND c.type = 'user_profile'"
                items = list(self.profiles_container.query_items(
                    query=query,
                    parameters=[{"name": "@userId", "value": user_id}],
                    partition_key=user_id
                ))
                
                if items:
                    logger.debug(f"Profile found in Cosmos for user {user_id}")
                    return items[0]
            else:
                # Buscar em memória
                if user_id in self.memory_profiles:
                    logger.debug(f"Profile found in memory for user {user_id}")
                    return self.memory_profiles[user_id]
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting profile: {str(e)}")
            return None
    
    async def save_pattern(self, pattern: Dict[str, Any]) -> bool:
        """
        Salva padrão detectado
        """
        try:
            pattern["id"] = str(uuid.uuid4())
            pattern["type"] = "pattern"
            pattern["timestamp"] = datetime.now().isoformat()
            
            if self.patterns_container:
                # Salvar no Cosmos
                self.patterns_container.create_item(pattern)
                logger.debug(f"Pattern saved to Cosmos: {pattern.get('pattern_type')}")
            else:
                # Salvar em memória
                user_id = pattern.get("userId", "unknown")
                if user_id not in self.memory_patterns:
                    self.memory_patterns[user_id] = []
                self.memory_patterns[user_id].append(pattern)
                logger.debug(f"Pattern saved to memory: {pattern.get('pattern_type')}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error saving pattern: {str(e)}")
            return False
    
    async def get_patterns(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Recupera padrões do usuário
        """
        try:
            if self.patterns_container:
                # Buscar no Cosmos
                query = """
                    SELECT TOP @limit * FROM c 
                    WHERE c.userId = @userId AND c.type = 'pattern'
                    ORDER BY c.timestamp DESC
                """
                items = list(self.patterns_container.query_items(
                    query=query,
                    parameters=[
                        {"name": "@userId", "value": user_id},
                        {"name": "@limit", "value": limit}
                    ],
                    partition_key=user_id
                ))
                return items
            else:
                # Buscar em memória
                patterns = self.memory_patterns.get(user_id, [])
                return sorted(patterns, key=lambda x: x.get("timestamp", ""), reverse=True)[:limit]
            
        except Exception as e:
            logger.error(f"Error getting patterns: {str(e)}")
            return []
    
    async def save_knowledge(self, knowledge_item: Dict[str, Any]) -> bool:
        """
        Salva item na base de conhecimento
        """
        try:
            knowledge_item["id"] = str(uuid.uuid4())
            knowledge_item["type"] = "knowledge"
            knowledge_item["created_at"] = datetime.now().isoformat()
            knowledge_item["domain"] = knowledge_item.get("domain", "general")
            
            if self.knowledge_container:
                # Salvar no Cosmos
                self.knowledge_container.create_item(knowledge_item)
                logger.debug(f"Knowledge saved to Cosmos: {knowledge_item.get('topic')}")
            else:
                # Salvar em memória
                domain = knowledge_item["domain"]
                if domain not in self.memory_knowledge:
                    self.memory_knowledge[domain] = []
                self.memory_knowledge[domain].append(knowledge_item)
                logger.debug(f"Knowledge saved to memory: {knowledge_item.get('topic')}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error saving knowledge: {str(e)}")
            return False
    
    async def search_knowledge(self, query: str, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Busca na base de conhecimento
        """
        try:
            if self.knowledge_container:
                # Buscar no Cosmos
                if domain:
                    cosmos_query = """
                        SELECT * FROM c 
                        WHERE c.type = 'knowledge' 
                        AND c.domain = @domain
                        AND (CONTAINS(LOWER(c.content), LOWER(@query))
                             OR CONTAINS(LOWER(c.topic), LOWER(@query)))
                    """
                    params = [
                        {"name": "@domain", "value": domain},
                        {"name": "@query", "value": query}
                    ]
                else:
                    cosmos_query = """
                        SELECT * FROM c 
                        WHERE c.type = 'knowledge'
                        AND (CONTAINS(LOWER(c.content), LOWER(@query))
                             OR CONTAINS(LOWER(c.topic), LOWER(@query)))
                    """
                    params = [{"name": "@query", "value": query}]
                
                items = list(self.knowledge_container.query_items(
                    query=cosmos_query,
                    parameters=params,
                    enable_cross_partition_query=True
                ))
                return items
            else:
                # Buscar em memória
                results = []
                search_domains = [domain] if domain else self.memory_knowledge.keys()
                
                for d in search_domains:
                    if d in self.memory_knowledge:
                        for item in self.memory_knowledge[d]:
                            content = item.get("content", "").lower()
                            topic = item.get("topic", "").lower()
                            if query.lower() in content or query.lower() in topic:
                                results.append(item)
                
                return results
            
        except Exception as e:
            logger.error(f"Error searching knowledge: {str(e)}")
            return []
    
    async def update_knowledge_confidence(self, knowledge_id: str, delta: float) -> bool:
        """
        Atualiza confiança de um item de conhecimento
        """
        try:
            if self.knowledge_container:
                # Buscar item
                query = "SELECT * FROM c WHERE c.id = @id"
                items = list(self.knowledge_container.query_items(
                    query=query,
                    parameters=[{"name": "@id", "value": knowledge_id}],
                    enable_cross_partition_query=True
                ))
                
                if items:
                    item = items[0]
                    current_confidence = item.get("confidence", 0.5)
                    new_confidence = max(0.0, min(1.0, current_confidence + delta))
                    item["confidence"] = new_confidence
                    item["last_updated"] = datetime.now().isoformat()
                    
                    self.knowledge_container.upsert_item(item)
                    logger.debug(f"Knowledge confidence updated: {knowledge_id} -> {new_confidence:.2f}")
                    return True
            else:
                # Atualizar em memória
                for domain in self.memory_knowledge.values():
                    for item in domain:
                        if item.get("id") == knowledge_id:
                            current = item.get("confidence", 0.5)
                            item["confidence"] = max(0.0, min(1.0, current + delta))
                            item["last_updated"] = datetime.now().isoformat()
                            return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error updating knowledge confidence: {str(e)}")
            return False
    
    async def get_learning_stats(self) -> Dict[str, Any]:
        """
        Retorna estatísticas do storage de aprendizagem
        """
        stats = {
            "storage_type": "cosmos" if self.client else "memory",
            "available": self.available
        }
        
        try:
            if self.profiles_container:
                # Contar no Cosmos
                count_query = "SELECT VALUE COUNT(1) FROM c WHERE c.type = 'user_profile'"
                profile_count = list(self.profiles_container.query_items(
                    query=count_query,
                    enable_cross_partition_query=True
                ))[0]
                stats["total_profiles"] = profile_count
                
                pattern_count_query = "SELECT VALUE COUNT(1) FROM c WHERE c.type = 'pattern'"
                pattern_count = list(self.patterns_container.query_items(
                    query=pattern_count_query,
                    enable_cross_partition_query=True
                ))[0] if self.patterns_container else 0
                stats["total_patterns"] = pattern_count
                
                knowledge_count_query = "SELECT VALUE COUNT(1) FROM c WHERE c.type = 'knowledge'"
                knowledge_count = list(self.knowledge_container.query_items(
                    query=knowledge_count_query,
                    enable_cross_partition_query=True
                ))[0] if self.knowledge_container else 0
                stats["total_knowledge_items"] = knowledge_count
            else:
                # Contar em memória
                stats["total_profiles"] = len(self.memory_profiles)
                stats["total_patterns"] = sum(len(p) for p in self.memory_patterns.values())
                stats["total_knowledge_items"] = sum(len(k) for k in self.memory_knowledge.values())
            
        except Exception as e:
            logger.error(f"Error getting learning stats: {str(e)}")
            stats["error"] = str(e)
        
        return stats
    
    def is_available(self) -> bool:
        """Verifica se o storage está disponível"""
        return self.available