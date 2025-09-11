from typing import Dict, List, Any, Optional
import asyncio
from collections import deque
import time

from config.settings import Settings
from utils.logger import get_logger

logger = get_logger(__name__)

class ShortTermMemory:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.memory_store = {}
        self.max_messages = settings.memory.short_term.get("max_messages", 20)
        self.ttl_minutes = settings.memory.short_term.get("ttl_minutes", 30)
    
    async def store(self, user_id: str, message: Dict[str, Any]):
        if user_id not in self.memory_store:
            self.memory_store[user_id] = {
                "messages": deque(maxlen=self.max_messages),
                "last_updated": time.time()
            }
        
        self.memory_store[user_id]["messages"].append({
            "timestamp": time.time(),
            "data": message
        })
        self.memory_store[user_id]["last_updated"] = time.time()
        
        logger.debug(f"Stored message in short-term memory for user {user_id}")
    
    async def get_context(self, user_id: str) -> Dict[str, Any]:
        if user_id not in self.memory_store:
            return {"short_term_memory": []}
        
        # Clean up old messages
        self._cleanup_old_messages(user_id)
        
        messages = list(self.memory_store[user_id]["messages"])
        return {
            "short_term_memory": messages,
            "recent_message_count": len(messages)
        }
    
    def _cleanup_old_messages(self, user_id: str):
        if user_id not in self.memory_store:
            return
        
        current_time = time.time()
        ttl_seconds = self.ttl_minutes * 60
        
        # Remove messages older than TTL
        self.memory_store[user_id]["messages"] = deque(
            [msg for msg in self.memory_store[user_id]["messages"] 
             if current_time - msg["timestamp"] < ttl_seconds],
            maxlen=self.max_messages
        )
        
        # Remove user entry if no messages left
        if not self.memory_store[user_id]["messages"]:
            del self.memory_store[user_id]