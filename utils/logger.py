import structlog
import logging
import sys
import os
from datetime import datetime

def get_logger(name: str):
    """Get a structured logger instance"""
    if not structlog.get_config():
        setup_logging()
    return structlog.get_logger(name)

def setup_logging():
    """Setup structured logging with JSON format"""
    # Remove existing handlers
    logging.getLogger().handlers.clear()
    
    # Setup basic logging configuration
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    
    # Add correlation ID processor if application insights is enabled
    if os.getenv("APP_INSIGHTS_CONNECTION_STRING"):
        from opencensus.ext.azure.log_exporter import AzureLogHandler
        handler = AzureLogHandler(connection_string=os.getenv("APP_INSIGHTS_CONNECTION_STRING"))
        logging.getLogger().addHandler(handler)
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

# Setup logging when module is imported
setup_logging()