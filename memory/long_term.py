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
