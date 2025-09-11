# utils/logger.py
import logging
import sys
import structlog

def setup_logging(level: int = logging.INFO) -> None:
    """
    Configura logging de forma compatível com structlog + stdlib.
    """
    # Config do logging básico (stdout)
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    # Processors do structlog
    processors = [
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),  # se preferir texto, troque por KeyValueRenderer()
    ]

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

def get_logger(name: str = None):
    """
    Retorna um logger structlog já configurado.
    """
    if not structlog.is_configured():
        setup_logging()
    return structlog.get_logger(name) if name else structlog.get_logger()

# Configura ao importar o módulo (como você já fazia)
setup_logging()
