from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BaseSkill(ABC):
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = self.__class__.__name__
    
    @abstractmethod
    async def can_handle(self, intent: str, context: Dict[str, Any]) -> bool:
        pass
    
    @abstractmethod
    async def execute(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        pass
    
    def _get_config_value(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)