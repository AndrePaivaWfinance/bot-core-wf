<<<<<<< HEAD
# memory/long_term.py
from typing import Dict, List, Optional
from datetime import datetime
import asyncio

try:
    from azure.cosmos import CosmosClient
except Exception:
    CosmosClient = None  # permite rodar sem SDK instalado em dev

class LongTermMemory:
    def __init__(self, config: Dict):
        self.cfg = config
        self.client = None
        self.database = None
        self.container = None
        self.ttl_days = config.get("ttl_days", 90)
        if CosmosClient and self.cfg.get("endpoint") and self.cfg.get("key"):
            self.client = CosmosClient(self.cfg["endpoint"], self.cfg["key"])
            self.database = self.client.get_database_client(self.cfg.get("database","bot_memory"))
            self.container = self.database.get_container_client("memories")

    async def _run(self, fn, *args, **kwargs):
        return await asyncio.to_thread(fn, *args, **kwargs)

    async def store(self, user_id: str, memory_type: str, content: Dict) -> str:
        mem = {
            "id": f"{user_id}_{datetime.utcnow().timestamp()}",
            "user_id": user_id,
            "type": memory_type,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "ttl": self.ttl_days * 24 * 3600,
            "importance": 0.5,
            "access_count": 0,
        }
        if not self.container:
            return mem["id"]  # mock local sem persistência real
        await self._run(self.container.create_item, body=mem)
        return mem["id"]

    async def retrieve(self, user_id: str, memory_type: Optional[str]=None, limit: int=10) -> List[Dict]:
        if not self.container:
            return []
        query = "SELECT * FROM c WHERE c.user_id = @uid"
        params = [{"name":"@uid","value":user_id}]
        if memory_type:
            query += " AND c.type = @t"
            params.append({"name":"@t","value":memory_type})
        query += " ORDER BY c.importance DESC, c.timestamp DESC"
        it = self.container.query_items(query=query, parameters=params, max_item_count=limit)
        items = list(await self._run(list, it))
        # atualiza access_count de forma best-effort
        for item in items:
            item["access_count"] = item.get("access_count",0) + 1
            try:
                await self._run(self.container.upsert_item, item)
            except Exception:
                pass
        return items
=======
from typing import Dict, List, Any, Optional
import uuid
from datetime import datetime, timezone
from azure.cosmos import CosmosClient, PartitionKey
from azure.cosmos.exceptions import CosmosHttpResponseError

from config.settings import Settings
from utils.logger import get_logger

logger = get_logger(__name__)

class LongTermMemory:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = None
        self.database = None
        self.container = None
        
        if settings.cosmos.endpoint and settings.cosmos.key:
            self._initialize_cosmos_client()
        else:
            logger.warning("Cosmos DB not configured, using in-memory storage")
            self.in_memory_store = {}
    
    def _initialize_cosmos_client(self):
        try:
            self.client = CosmosClient(
                self.settings.cosmos.endpoint,
                credential=self.settings.cosmos.key
            )
            
            # Create database if it doesn't exist
            self.database = self.client.create_database_if_not_exists(
                self.settings.cosmos.database
            )
            
            # Create container if it doesn't exist
            self.container = self.database.create_container_if_not_exists(
                id="memories",
                partition_key=PartitionKey(path="/user_id"),
                default_ttl=self.settings.cosmos.ttl_days * 86400  # Convert days to seconds
            )
            
            logger.info("Cosmos DB client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Cosmos DB: {str(e)}")
            self.in_memory_store = {}
    
    async def store(
        self,
        user_id: str,
        memory_type: str,
        content: Dict[str, Any],
        importance: float = 0.5
    ) -> str:
        """Store a memory with automatic TTL"""
        memory_id = str(uuid.uuid4())
        memory_item = {
            "id": memory_id,
            "user_id": user_id,
            "type": memory_type,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "importance": importance,
            "access_count": 0
        }
        
        if self.container:
            try:
                self.container.create_item(memory_item)
                logger.debug(f"Stored memory in Cosmos DB for user {user_id}", memory_type=memory_type)
            except CosmosHttpResponseError as e:
                logger.error(f"Failed to store memory in Cosmos DB: {str(e)}")
                # Fallback to in-memory storage
                if user_id not in self.in_memory_store:
                    self.in_memory_store[user_id] = []
                self.in_memory_store[user_id].append(memory_item)
        else:
            # Use in-memory storage
            if user_id not in self.in_memory_store:
                self.in_memory_store[user_id] = []
            self.in_memory_store[user_id].append(memory_item)
            logger.debug(f"Stored memory in-memory for user {user_id}", memory_type=memory_type)
        
        return memory_id
    
    async def retrieve(
        self,
        user_id: str,
        memory_type: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Retrieve memories for a user, optionally filtered by type"""
        if self.container:
            try:
                query = "SELECT * FROM c WHERE c.user_id = @user_id"
                parameters = [{"name": "@user_id", "value": user_id}]
                
                if memory_type:
                    query += " AND c.type = @memory_type"
                    parameters.append({"name": "@memory_type", "value": memory_type})
                
                query += " ORDER BY c.timestamp DESC"
                
                items = list(self.container.query_items(
                    query=query,
                    parameters=parameters,
                    enable_cross_partition_query=True,
                    max_item_count=limit
                ))
                
                # Update access count
                for item in items:
                    item["access_count"] = item.get("access_count", 0) + 1
                    self.container.replace_item(item, item)
                
                logger.debug(f"Retrieved {len(items)} memories from Cosmos DB for user {user_id}")
                return items
            except CosmosHttpResponseError as e:
                logger.error(f"Failed to retrieve memories from Cosmos DB: {str(e)}")
                return await self._retrieve_from_memory(user_id, memory_type, limit)
        else:
            return await self._retrieve_from_memory(user_id, memory_type, limit)
    
    async def _retrieve_from_memory(
        self,
        user_id: str,
        memory_type: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Retrieve memories from in-memory storage"""
        if user_id not in self.in_memory_store:
            return []
        
        memories = self.in_memory_store[user_id]
        if memory_type:
            memories = [m for m in memories if m.get("type") == memory_type]
        
        # Sort by timestamp (newest first) and limit results
        memories.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return memories[:limit]
    
    async def retrieve_relevant_memories(self, user_id: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Retrieve memories relevant to the current query (simplified)"""
        # For now, just return recent memories
        # In a real implementation, you would use semantic search with embeddings
        return await self.retrieve(user_id, limit=limit)
>>>>>>> resgate-eb512f
