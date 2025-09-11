from prometheus_client import Counter, Histogram, generate_latest, REGISTRY
from fastapi import APIRouter, Response
from typing import Callable, Any
import time

# Create metrics router
metrics_router = APIRouter()

# Define metrics
LLM_CALLS = Counter(
    'llm_calls_total',
    'Total number of LLM calls',
    ['provider', 'status']
)

LLM_LATENCY = Histogram(
    'llm_call_latency_seconds',
    'Latency of LLM calls',
    ['provider']
)

SKILL_EXECUTIONS = Counter(
    'skill_executions_total',
    'Total number of skill executions',
    ['skill_name', 'status']
)

MESSAGES_PROCESSED = Counter(
    'messages_processed_total',
    'Total number of messages processed',
    ['channel', 'status']
)

@metrics_router.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(REGISTRY), media_type="text/plain")

def record_metrics(func: Callable) -> Callable:
    """Decorator to record metrics for LLM calls"""
    async def wrapper(*args, **kwargs) -> Any:
        start_time = time.time()
        provider = "unknown"
        status = "success"
        
        try:
            result = await func(*args, **kwargs)
            return result
        except Exception as e:
            status = "error"
            raise e
        finally:
            latency = time.time() - start_time
            LLM_CALLS.labels(provider=provider, status=status).inc()
            LLM_LATENCY.labels(provider=provider).observe(latency)
    
    return wrapper