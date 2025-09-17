"""
Sistema de Monitoramento Aprimorado com Application Insights e Métricas Customizadas
"""
import os
import json
from datetime import datetime
from typing import Dict, Any, Optional
from enum import Enum
import asyncio

from utils.logger import get_logger

logger = get_logger(__name__)

class ProviderType(Enum):
    AZURE_OPENAI = "azure_openai"
    CLAUDE = "claude"
    MOCK = "mock"

class MetricsTracker:
    """
    Rastreia métricas customizadas para monitoramento
    """
    def __init__(self):
        self.metrics = {
            "total_requests": 0,
            "provider_usage": {},
            "fallback_triggers": 0,
            "errors_by_provider": {},
            "response_times": [],
            "costs_estimate": {
                "azure_openai": 0.0,
                "claude": 0.0
            }
        }
        
        # Application Insights (se configurado)
        self.app_insights_client = None
        self._init_app_insights()
        
        # Arquivo local para métricas (backup)
        self.metrics_file = ".cache/metrics.json"
        os.makedirs(os.path.dirname(self.metrics_file), exist_ok=True)
        
        # Carrega métricas existentes
        self._load_metrics()
    
    def _init_app_insights(self):
        """Inicializa Application Insights se configurado"""
        connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
        
        if connection_string:
            try:
                from opencensus.ext.azure import metrics_exporter
                from opencensus.stats import aggregation, measure, stats, view
                
                # Configurar o exportador
                exporter = metrics_exporter.new_metrics_exporter(
                    connection_string=connection_string
                )
                
                # Definir métricas customizadas
                self.measure_fallback = measure.MeasureInt(
                    "fallback_triggered",
                    "Number of times fallback was triggered",
                    "1"
                )
                
                self.measure_response_time = measure.MeasureFloat(
                    "llm_response_time",
                    "Response time in seconds",
                    "s"
                )
                
                # Criar views para as métricas
                fallback_view = view.View(
                    "fallback_triggers_view",
                    "Tracks fallback triggers",
                    [],
                    self.measure_fallback,
                    aggregation.CountAggregation()
                )
                
                response_time_view = view.View(
                    "response_time_view",
                    "Tracks response times",
                    [],
                    self.measure_response_time,
                    aggregation.DistributionAggregation([0.1, 0.5, 1.0, 2.0, 5.0])
                )
                
                # Registrar views
                view_manager = stats.stats.view_manager
                view_manager.register_view(fallback_view)
                view_manager.register_view(response_time_view)
                
                # Registrar exportador
                view_manager.register_exporter(exporter)
                
                self.stats_recorder = stats.stats.stats_recorder
                logger.info("✅ Application Insights configurado com sucesso")
                
            except ImportError:
                logger.warning("⚠️ opencensus-ext-azure não instalado. Métricas locais apenas.")
            except Exception as e:
                logger.error(f"❌ Erro ao configurar Application Insights: {str(e)}")
    
    def _load_metrics(self):
        """Carrega métricas do arquivo local"""
        if os.path.exists(self.metrics_file):
            try:
                with open(self.metrics_file, 'r') as f:
                    saved_metrics = json.load(f)
                    self.metrics.update(saved_metrics)
                    logger.debug(f"Métricas carregadas: {self.metrics['total_requests']} requests")
            except Exception as e:
                logger.error(f"Erro ao carregar métricas: {str(e)}")
    
    def _save_metrics(self):
        """Salva métricas no arquivo local"""
        try:
            with open(self.metrics_file, 'w') as f:
                json.dump(self.metrics, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Erro ao salvar métricas: {str(e)}")
    
    async def track_request(
        self,
        provider: str,
        success: bool,
        response_time: float,
        tokens_used: Optional[int] = None,
        error: Optional[str] = None,
        is_fallback: bool = False
    ):
        """
        Rastreia uma requisição ao LLM
        """
        self.metrics["total_requests"] += 1
        
        # Track provider usage
        if provider not in self.metrics["provider_usage"]:
            self.metrics["provider_usage"][provider] = {"success": 0, "failure": 0}
        
        if success:
            self.metrics["provider_usage"][provider]["success"] += 1
        else:
            self.metrics["provider_usage"][provider]["failure"] += 1
            
            # Track errors
            if provider not in self.metrics["errors_by_provider"]:
                self.metrics["errors_by_provider"][provider] = []
            
            self.metrics["errors_by_provider"][provider].append({
                "timestamp": datetime.now().isoformat(),
                "error": error[:200] if error else "Unknown error"
            })
        
        # Track fallback triggers
        if is_fallback:
            self.metrics["fallback_triggers"] += 1
            logger.warning(f"⚠️ Fallback triggered! Total: {self.metrics['fallback_triggers']}")
            
            # Enviar alerta se muitos fallbacks
            if self.metrics["fallback_triggers"] % 5 == 0:
                await self._send_fallback_alert()
        
        # Track response times
        self.metrics["response_times"].append({
            "provider": provider,
            "time": response_time,
            "timestamp": datetime.now().isoformat()
        })
        
        # Estimate costs (valores aproximados)
        if tokens_used:
            if provider == "azure_openai":
                # GPT-4: ~$0.03 per 1K tokens (input) + $0.06 per 1K tokens (output)
                estimated_cost = (tokens_used / 1000) * 0.045  # média
                self.metrics["costs_estimate"]["azure_openai"] += estimated_cost
            elif provider == "claude":
                # Claude 3 Sonnet: ~$0.003 per 1K tokens (input) + $0.015 per 1K tokens (output)
                estimated_cost = (tokens_used / 1000) * 0.009  # média
                self.metrics["costs_estimate"]["claude"] += estimated_cost
        
        # Send to Application Insights
        if self.stats_recorder:
            try:
                measurement_map = self.stats_recorder.new_measurement_map()
                measurement_map.measure_float_put(self.measure_response_time, response_time)
                if is_fallback:
                    measurement_map.measure_int_put(self.measure_fallback, 1)
                measurement_map.record()
            except Exception as e:
                logger.error(f"Erro ao enviar para App Insights: {str(e)}")
        
        # Save metrics locally
        self._save_metrics()
        
        # Log summary periodicamente
        if self.metrics["total_requests"] % 10 == 0:
            await self._log_metrics_summary()
    
    async def _send_fallback_alert(self):
        """Envia alerta quando muitos fallbacks ocorrem"""
        alert_message = f"""
        🚨 ALERTA: Muitos fallbacks detectados!
        
        Total de fallbacks: {self.metrics['fallback_triggers']}
        Total de requests: {self.metrics['total_requests']}
        Taxa de fallback: {(self.metrics['fallback_triggers'] / max(1, self.metrics['total_requests'])) * 100:.1f}%
        
        Verifique:
        1. Azure OpenAI API Key
        2. Azure OpenAI Endpoint
        3. Limites de rate/quota
        """
        
        logger.error(alert_message)
        
        # Se tiver webhook configurado, envia alerta
        webhook_url = os.getenv("ALERT_WEBHOOK_URL")
        if webhook_url:
            try:
                import httpx
                async with httpx.AsyncClient() as client:
                    await client.post(webhook_url, json={
                        "text": alert_message,
                        "type": "fallback_alert",
                        "severity": "high"
                    })
            except Exception as e:
                logger.error(f"Erro ao enviar webhook: {str(e)}")
    
    async def _log_metrics_summary(self):
        """Log resumo das métricas"""
        summary = f"""
        📊 === RESUMO DE MÉTRICAS ===
        Total Requests: {self.metrics['total_requests']}
        Fallback Triggers: {self.metrics['fallback_triggers']}
        
        Provider Usage:
        """
        
        for provider, stats in self.metrics["provider_usage"].items():
            total = stats["success"] + stats["failure"]
            if total > 0:
                success_rate = (stats["success"] / total) * 100
                summary += f"\n  {provider}: {total} calls ({success_rate:.1f}% success)"
        
        summary += f"""
        
        Custos Estimados:
          Azure OpenAI: ${self.metrics['costs_estimate']['azure_openai']:.4f}
          Claude: ${self.metrics['costs_estimate']['claude']:.4f}
          Total: ${sum(self.metrics['costs_estimate'].values()):.4f}
        """
        
        logger.info(summary)
    
    def get_metrics_report(self) -> Dict[str, Any]:
        """Retorna relatório completo de métricas"""
        total_requests = max(1, self.metrics["total_requests"])
        
        report = {
            "summary": {
                "total_requests": self.metrics["total_requests"],
                "fallback_rate": (self.metrics["fallback_triggers"] / total_requests) * 100,
                "total_cost_estimate": sum(self.metrics["costs_estimate"].values())
            },
            "providers": self.metrics["provider_usage"],
            "costs": self.metrics["costs_estimate"],
            "recent_errors": {},
            "performance": {}
        }
        
        # Últimos erros por provider
        for provider, errors in self.metrics["errors_by_provider"].items():
            report["recent_errors"][provider] = errors[-5:]  # últimos 5 erros
        
        # Média de tempo de resposta
        if self.metrics["response_times"]:
            recent_times = self.metrics["response_times"][-100:]  # últimas 100
            by_provider = {}
            
            for entry in recent_times:
                provider = entry["provider"]
                if provider not in by_provider:
                    by_provider[provider] = []
                by_provider[provider].append(entry["time"])
            
            for provider, times in by_provider.items():
                report["performance"][provider] = {
                    "avg_response_time": sum(times) / len(times),
                    "min_response_time": min(times),
                    "max_response_time": max(times)
                }
        
        return report

# Instância global do tracker
metrics_tracker = MetricsTracker()

# Decorator para tracking automático
def track_llm_call(provider: str):
    """Decorator para rastrear chamadas LLM automaticamente"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            start_time = datetime.now()
            success = False
            error = None
            tokens = 0
            
            try:
                result = await func(*args, **kwargs)
                success = True
                
                # Extrai tokens do resultado se disponível
                if isinstance(result, dict) and "usage" in result:
                    usage = result["usage"]
                    if isinstance(usage, dict):
                        tokens = usage.get("total_tokens", 0)
                
                return result
                
            except Exception as e:
                error = str(e)
                raise
                
            finally:
                response_time = (datetime.now() - start_time).total_seconds()
                
                # Detecta se é fallback baseado no contexto
                is_fallback = provider == "claude" and "fallback" in str(args)
                
                # Track asynchronously to not block
                asyncio.create_task(
                    metrics_tracker.track_request(
                        provider=provider,
                        success=success,
                        response_time=response_time,
                        tokens_used=tokens,
                        error=error,
                        is_fallback=is_fallback
                    )
                )
        
        return wrapper
    return decorator