"""
Configuração centralizada de timeouts
"""
import os

class TimeoutConfig:
    """Configuração de timeouts para providers"""
    
    # Timeouts base
    AZURE_TIMEOUT = 10  # Azure é rápido
    CLAUDE_TIMEOUT = 40  # Claude precisa de mais tempo
    
    # Timeouts para testes
    TEST_TIMEOUT = 40  # Deve cobrir o pior caso (Claude)
    
    # Timeouts internos (margem de segurança +5s)
    AZURE_INTERNAL_TIMEOUT = 15
    CLAUDE_INTERNAL_TIMEOUT = 45
    
    # Timeout HTTP geral
    HTTP_TIMEOUT = 45
    
    @classmethod
    def get_provider_timeout(cls, provider_name: str) -> int:
        """Retorna timeout apropriado para o provider"""
        if "azure" in provider_name.lower():
            return cls.AZURE_TIMEOUT
        elif "claude" in provider_name.lower():
            return cls.CLAUDE_TIMEOUT
        else:
            return cls.HTTP_TIMEOUT
    
    @classmethod
    def from_env(cls):
        """Permite override via variáveis de ambiente"""
        cls.CLAUDE_TIMEOUT = int(os.getenv("CLAUDE_TIMEOUT", "40"))
        cls.AZURE_TIMEOUT = int(os.getenv("AZURE_TIMEOUT", "10"))
        cls.TEST_TIMEOUT = int(os.getenv("TEST_TIMEOUT", "40"))
        return cls
