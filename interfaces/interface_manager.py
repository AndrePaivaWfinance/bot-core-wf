"""
Base Skill - Interface melhorada e padronizada
Todas as skills devem herdar desta classe
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from enum import Enum

class SkillPriority(Enum):
    """Prioridade de execução da skill"""
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4

class SkillCategory(Enum):
    """Categoria da skill para organização"""
    COMMUNICATION = "communication"
    ANALYSIS = "analysis"
    INTEGRATION = "integration"
    REPORTING = "reporting"
    UTILITY = "utility"

class BaseSkill(ABC):
    """
    Interface base para todas as skills
    Melhorada para ser mais modular e extensível
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = self.__class__.__name__
        self.enabled = config.get("enabled", True)
        self.priority = SkillPriority.NORMAL
        self.category = SkillCategory.UTILITY
        self.version = "1.0.0"
        
        # Metadados para tracking
        self.execution_count = 0
        self.success_count = 0
        self.error_count = 0
        
        # Validar configuração na inicialização
        self._validate_config()
    
    def _validate_config(self):
        """
        Valida se a configuração tem os campos necessários
        Sobrescrever nas subclasses se necessário
        """
        required_fields = self.get_required_config_fields()
        for field in required_fields:
            if field not in self.config:
                raise ValueError(f"Skill {self.name} requires config field: {field}")
    
    def get_required_config_fields(self) -> List[str]:
        """
        Retorna lista de campos obrigatórios na config
        Sobrescrever nas subclasses
        """
        return []
    
    @abstractmethod
    async def can_handle(self, intent: str, context: Dict[str, Any]) -> bool:
        """Verifica se a skill pode processar este intent"""
        pass
    
    @abstractmethod
    async def execute(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Executa a skill e retorna resultado padronizado"""
        pass
    
    async def pre_execute(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """
        Hook executado antes da execução principal
        Retorna False para cancelar execução
        """
        self.execution_count += 1
        return self.enabled
    
    async def post_execute(self, result: Dict[str, Any], context: Dict[str, Any]):
        """
        Hook executado após a execução principal
        Para logging, cleanup, etc
        """
        if result.get("success", False):
            self.success_count += 1
        else:
            self.error_count += 1
    
    def get_metadata(self) -> Dict[str, Any]:
        """Retorna metadados da skill"""
        return {
            "name": self.name,
            "version": self.version,
            "enabled": self.enabled,
            "priority": self.priority.value,
            "category": self.category.value,
            "stats": {
                "executions": self.execution_count,
                "successes": self.success_count,
                "errors": self.error_count,
                "success_rate": (
                    self.success_count / max(1, self.execution_count) * 100
                    if self.execution_count > 0 else 0
                )
            }
        }
    
    def _get_config_value(self, key: str, default: Any = None) -> Any:
        """Helper para pegar valores da config com fallback"""
        return self.config.get(key, default)
    
    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> 'BaseSkill':
        """Factory method para criar skill a partir de config"""
        return cls(config)