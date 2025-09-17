"""
Sistema de Monitoramento Simplificado
MVP sem complexidade desnecessária
"""
import time
from typing import Dict, Any, Optional
from functools import wraps
from datetime import datetime

from utils.logger import get_logger

logger = get_logger(__name__)

class MetricsCollector:
    """Coletor simples de métricas"""
    
    def __init__(self):
        self.metrics = {
            "requests": 0,
            "errors": 0,
            "providers": {},
            "response_times": []
        }
    
    def record_request(self, provider: str, success: bool, duration: float):
        """Registra uma requisição"""
        self.metrics["requests"] += 1
        
        if not success:
            self.metrics["errors"] += 1
        
        if provider not in self.metrics["providers"]:
            self.metrics["providers"][provider] = {
                "success": 0,
                "failure": 0,
                "total_time": 0
            }
        
        if success:
            self.metrics["providers"][provider]["success"] += 1
        else:
            self.metrics["providers"][provider]["failure"] += 1
        
        self.metrics["providers"][provider]["total_time"] += duration
        self.metrics["response_times"].append(duration)
        
        # Manter apenas últimos 100 tempos
        if len(self.metrics["response_times"]) > 100:
            self.metrics["response_times"] = self.metrics["response_times"][-100:]
    
    def get_summary(self) -> Dict[str, Any]:
        """Retorna resumo das métricas"""
        avg_time = (
            sum(self.metrics["response_times"]) / len(self.metrics["response_times"])
            if self.metrics["response_times"] else 0
        )
        
        return {
            "total_requests": self.metrics["requests"],
            "total_errors": self.metrics["errors"],
            "error_rate": (
                self.metrics["errors"] / max(1, self.metrics["requests"]) * 100
            ),
            "avg_response_time": avg_time,
            "providers": self.metrics["providers"]
        }

# Instância global
metrics = MetricsCollector()

def track_performance(provider: str = "unknown"):
    """Decorator simples para tracking de performance"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            success = True
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise
            finally:
                duration = time.time() - start
                metrics.record_request(provider, success, duration)
                
                if duration > 2.0:  # Log se demorar muito
                    logger.warning(f"Slow operation: {func.__name__} took {duration:.2f}s")
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.time()
            success = True
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise
            finally:
                duration = time.time() - start
                metrics.record_request(provider, success, duration)
        
        # Retorna versão apropriada
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator