import logging
import sys
import os
import structlog
from typing import Optional

def setup_logging(level: Optional[str] = None) -> None:
    """
    Configura logging estruturado para a aplicação.
    """
    # Pega o nível de log do ambiente ou usa INFO como padrão
    log_level = level or os.getenv("LOG_LEVEL", "INFO").upper()
    
    # Configura o logging básico do Python
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    
    # Determina o formato baseado no ambiente
    is_production = os.getenv("BOT_ENV", "development").lower() == "production"
    
    # Configuração dos processors do structlog
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    
    # Em produção usa JSON, em dev usa formato legível
    if is_production:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    
    # Configura o structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

def get_logger(name: Optional[str] = None):
    """
    Retorna um logger estruturado.
    
    Args:
        name: Nome do módulo/componente
    
    Returns:
        Logger estruturado configurado
    """
    if not structlog.is_configured():
        setup_logging()
    
    return structlog.get_logger(name) if name else structlog.get_logger()

# Configura logging ao importar o módulo
setup_logging()