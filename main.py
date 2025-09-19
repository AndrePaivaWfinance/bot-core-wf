"""
Bot Framework - Main Application
Version: 3.0.0 with Learning System
WFinance - Mesh Financial Analyst
Porta padrão: 8000
"""
import asyncio
from contextlib import asynccontextmanager
from typing import Dict, Any
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os

# Setup logging first
from utils.logger import setup_logging, get_logger
setup_logging()

# Then import other modules
from config.settings import Settings, get_settings
from core.brain import BotBrain
from core.context_engine import ContextEngine
from core.response_builder import ResponseBuilder
from core.router import MessageRouter

# NOVA ARQUITETURA - Apenas os módulos que existem
from memory.memory_manager import MemoryManager
from memory.learning import LearningSystem
from memory.retrieval import RetrievalSystem

from personality.personality_loader import PersonalityLoader
from skills.skill_registry import SkillRegistry
from utils.metrics import metrics_router
from interfaces.bot_framework_handler import BotFrameworkHandler

logger = get_logger(__name__)

# Global para armazenar componentes
app_components = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia o ciclo de vida da aplicação com cleanup otimizado."""
    
    # ===== STARTUP =====
    logger.info("=" * 60)
    logger.info("🚀 Starting Bot Framework v3.0.0...")
    logger.info("=" * 60)
    
    try:
        # Carrega configurações
        logger.info("📋 Loading configuration...")
        settings = get_settings()
        app_components['settings'] = settings
        
        # Log configuração básica
        logger.info(f"   Bot Name: {settings.bot.name}")
        logger.info(f"   Bot Type: {settings.bot.type}")
        logger.info(f"   Environment: {os.getenv('BOT_ENV', 'production')}")
        
        # Inicializa componentes de memória - NOVA ARQUITETURA
        logger.info("💾 Initializing memory systems...")
        app_components['memory_manager'] = MemoryManager(settings)
        
        # Sistemas auxiliares
        app_components['learning_system'] = LearningSystem(settings, None)
        app_components['retrieval_system'] = RetrievalSystem(settings)
        
        # Inicializa personalidade
        logger.info("🎭 Loading personality...")
        app_components['personality_loader'] = PersonalityLoader(settings)
        
        # Inicializa registro de skills
        logger.info("🎯 Loading skills...")
        app_components['skill_registry'] = SkillRegistry(settings)
        await app_components['skill_registry'].load_skills()
        loaded_skills = app_components['skill_registry'].list_skills()
        if loaded_skills:
            logger.info(f"   Skills loaded: {', '.join(loaded_skills)}")
        
        # Inicializa roteador e construtor de resposta
        app_components['router'] = MessageRouter()
        app_components['response_builder'] = ResponseBuilder(
            settings,
            app_components['personality_loader']
        )
        
        # Context engine simplificado
        logger.info("🧩 Initializing context engine...")
        app_components['context_engine'] = ContextEngine(
            settings=settings,
            short_term_memory=None,  # Removido na nova arquitetura
            long_term_memory=None,   # Removido na nova arquitetura
            learning_system=app_components['learning_system'],
            retrieval_system=app_components['retrieval_system'],
            personality_loader=app_components['personality_loader']
        )
        
        # Inicializa o cérebro do bot
        logger.info("🧠 Initializing bot brain...")
        app_components['brain'] = BotBrain(
            settings=settings,
            memory_manager=app_components['memory_manager'],
            learning_system=app_components['learning_system'],
            retrieval_system=app_components['retrieval_system'],
            skill_registry=app_components['skill_registry']
        )
        
        # Verifica status dos providers
        _log_provider_status()
        
        # Inicializa Bot Framework Handler para Azure Bot Service/Teams
        if settings.teams and settings.teams.app_id:
            logger.info("🤖 Initializing Bot Framework handler for Teams...")
            app_components['bot_framework'] = BotFrameworkHandler(
                settings=settings,
                brain=app_components['brain']
            )
            # Registra as rotas do Bot Framework
            app.include_router(app_components['bot_framework'].router)
            logger.info("   ✅ Bot Framework endpoint ready at /api/messages")
        else:
            logger.warning("   ⚠️ Teams not configured - Bot Framework handler disabled")
        
        # Verifica Memory Manager
        memory_stats = app_components['memory_manager'].get_storage_stats()
        logger.info(f"💾 Memory Manager Status: {memory_stats['health']}")
        for provider, status in memory_stats['providers'].items():
            status_icon = '✅' if status['available'] else '❌'
            logger.info(f"   {provider}: {status_icon} ({status['type']})")
        
        logger.info("=" * 60)
        logger.info("✅ Bot Framework started successfully!")
        logger.info(f"   Version: 3.0.0")
        logger.info(f"   Architecture: Memory Manager + Learning System")
        logger.info(f"   Ready to receive messages on port 8000")
        logger.info("=" * 60)
        
        yield
        
    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"❌ Failed to start Bot Framework: {str(e)}")
        logger.error("=" * 60)
        raise
    
    # ===== SHUTDOWN =====
    logger.info("=" * 60)
    logger.info("🛑 Shutting down Bot Framework...")
    
    # Cleanup otimizado - sem chamar métodos que não existem
    try:
        # Log estatísticas finais se disponível
        if 'brain' in app_components and hasattr(app_components['brain'], 'get_memory_stats'):
            stats = app_components['brain'].get_memory_stats()
            logger.info(f"   Final memory stats: {stats.get('health', 'unknown')}")
        
        # Nota: Clientes HTTP (Azure OpenAI e Anthropic) fazem cleanup automático
        # Não é necessário fechar manualmente
        
        logger.info("✅ Shutdown completed gracefully")
        
    except Exception as e:
        logger.warning(f"⚠️ Cleanup warning (non-critical): {str(e)}")
    
    logger.info("=" * 60)

def _log_provider_status():
    """Helper para logar status dos LLM providers."""
    if 'brain' not in app_components:
        return
    
    brain = app_components['brain']
    
    logger.info("🤖 LLM Providers Status:")
    
    if brain.primary_provider and brain.primary_provider.is_available():
        logger.info("   ✅ Primary (Azure OpenAI): Available")
    else:
        logger.warning("   ❌ Primary (Azure OpenAI): Not configured")
    
    if brain.fallback_provider and brain.fallback_provider.is_available():
        logger.info("   ✅ Fallback (Claude): Available")
    else:
        logger.warning("   ⚠️ Fallback (Claude): Not configured")
    
    if not brain.primary_provider and not brain.fallback_provider:
        logger.error("   ⚠️ WARNING: No LLM providers available!")

# Cria a aplicação FastAPI
app = FastAPI(
    title="Bot Framework - Mesh",
    description="AI-powered BPO Financial Analyst Bot with Learning System",
    version="3.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware - configuração mais segura para produção
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://teams.microsoft.com",
        "https://*.teams.microsoft.com",
        "https://*.azurewebsites.net",
        "http://localhost:3000",  # Para desenvolvimento
        "http://localhost:8000"   # Para desenvolvimento
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Inclui rotas de métricas
app.include_router(metrics_router)

@app.get("/")
async def root():
    """Endpoint raiz com informações do sistema."""
    return {
        "service": "meshbrain",
        "version": "3.0.0",
        "status": "running",
        "description": "WFinance Bot Framework - Mesh Financial Analyst",
        "features": [
            "Multi-tier Memory System",
            "Learning System (Phase 4)",
            "Pattern Detection",
            "User Personalization"
        ],
        "endpoints": {
            "health": "/healthz",
            "docs": "/docs",
            "messages": "/v1/messages",
            "memory_stats": "/v1/memory/stats",
            "user_insights": "/v1/users/{user_id}/insights"
        }
    }

@app.get("/healthz")
async def health_check():
    """Health check endpoint detalhado."""
    
    health_status = {
        "status": "ok",
        "service": "meshbrain",
        "version": "3.0.0",
        "architecture": "memory_manager_learning",
        "timestamp": os.popen('date').read().strip()
    }
    
    # Verifica componentes
    checks = {}
    
    # Settings
    checks["settings"] = '✅' if 'settings' in app_components else '❌'
    
    # Brain
    if 'brain' in app_components:
        checks["brain"] = '✅'
        brain = app_components['brain']
        
        # Verifica providers
        if brain.primary_provider and brain.primary_provider.is_available():
            checks["azure_openai"] = '✅'
            health_status["provider_primary"] = "azure_openai"
        else:
            checks["azure_openai"] = '❌'
            health_status["provider_primary"] = "none"
        
        if brain.fallback_provider and brain.fallback_provider.is_available():
            checks["claude"] = '✅'
            health_status["provider_fallback"] = "claude"
        else:
            checks["claude"] = '⚠️'
            health_status["provider_fallback"] = "none"
    else:
        checks["brain"] = '❌'
    
    # Memory Manager
    if 'memory_manager' in app_components:
        checks["memory_manager"] = '✅'
        try:
            mem_stats = app_components['memory_manager'].get_storage_stats()
            health_status["memory_health"] = mem_stats.get("health", "unknown")
            health_status["memory_providers"] = {
                "hot": mem_stats["providers"]["hot"]["available"],
                "warm": mem_stats["providers"]["warm"]["available"],
                "cold": mem_stats["providers"]["cold"]["available"]
            }
        except:
            health_status["memory_health"] = "error"
    else:
        checks["memory_manager"] = '❌'
    
    # Bot Framework / Teams
    if 'bot_framework' in app_components:
        checks["bot_framework"] = '✅'
        health_status["teams_configured"] = True
    else:
        checks["bot_framework"] = '⚠️'
        health_status["teams_configured"] = False
    
    # Skills
    if 'skill_registry' in app_components:
        checks["skills"] = '✅'
    else:
        checks["skills"] = '❌'
    
    # Learning System
    if 'learning_system' in app_components:
        checks["learning"] = '✅'
    else:
        checks["learning"] = '❌'
    
    # Retrieval System
    if 'retrieval_system' in app_components:
        checks["retrieval"] = '✅'
    else:
        checks["retrieval"] = '❌'
    
    health_status["checks"] = checks
    
    # Environment info
    health_status["environment"] = {
        "bot_env": os.getenv("BOT_ENV", "production"),
        "port": "8000"
    }
    
    # Bot info
    if 'settings' in app_components:
        settings = app_components['settings']
        health_status["bot"] = settings.bot.name
        health_status["bot_type"] = settings.bot.type
    
    # Determina status geral
    critical_checks = ["brain", "memory_manager"]
    if any(checks.get(check) == '❌' for check in critical_checks):
        health_status["status"] = "unhealthy"
    elif checks.get("azure_openai") == '❌' and checks.get("claude") != '✅':
        health_status["status"] = "degraded"
        health_status["warning"] = "No LLM providers available"
    else:
        health_status["status"] = "healthy"
    
    return health_status

@app.get("/v1/memory/stats")
async def get_memory_stats():
    """Retorna estatísticas detalhadas de memória."""
    
    if 'memory_manager' not in app_components:
        raise HTTPException(status_code=503, detail="Memory Manager not initialized")
    
    stats = app_components['memory_manager'].get_storage_stats()
    
    # Adiciona informações extras se disponível
    if 'brain' in app_components:
        try:
            brain_stats = app_components['brain'].get_memory_stats()
            if 'learning' in brain_stats:
                stats['learning'] = brain_stats['learning']
        except:
            pass
    
    return stats

@app.post("/v1/messages")
async def handle_message(request: Dict[str, Any]):
    """
    Processa uma mensagem através do bot com Learning System.
    
    Payload esperado:
    {
        "user_id": "string",
        "message": "string",
        "channel": "string" (opcional, default: "http")
    }
    """
    
    # Validação de entrada
    user_id = request.get("user_id")
    message = request.get("message")
    channel = request.get("channel", "http")
    
    if not user_id or not message:
        raise HTTPException(
            status_code=400,
            detail="Both 'user_id' and 'message' are required"
        )
    
    # Verifica se o brain está disponível
    if 'brain' not in app_components:
        raise HTTPException(
            status_code=503,
            detail="Bot brain is not initialized. Please check the logs."
        )
    
    try:
        logger.info(f"📨 Processing message from user: {user_id} via {channel}")
        logger.debug(f"   Message: {message[:100]}...")
        
        # Processa a mensagem com Learning System
        response = await app_components['brain'].think(
            user_id=user_id,
            message=message,
            channel=channel
        )
        
        logger.info(f"✅ Response generated for user: {user_id}")
        
        # Log de personalização se disponível
        if 'personalization' in response.get('metadata', {}):
            pers = response['metadata']['personalization']
            logger.debug(f"   Personalization applied: style={pers.get('style')}, expertise={pers.get('expertise')}")
        
        return response
        
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        logger.exception("Full traceback:")
        
        # Retorna erro mais amigável
        return {
            "response": "Desculpe, ocorreu um erro ao processar sua mensagem. Por favor, tente novamente.",
            "metadata": {
                "error": True,
                "error_type": type(e).__name__,
                "channel": channel
            }
        }

@app.get("/v1/users/{user_id}/insights")
async def get_user_insights(user_id: str):
    """
    Retorna insights sobre o usuário do Learning System.
    """
    
    if 'brain' not in app_components:
        raise HTTPException(
            status_code=503,
            detail="Bot brain is not initialized"
        )
    
    try:
        insights = await app_components['brain'].get_user_insights(user_id)
        return insights
    except Exception as e:
        logger.error(f"Error getting user insights: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving user insights: {str(e)}"
        )

@app.post("/test/message")
async def test_message():
    """
    Endpoint de teste para verificar se o bot está funcionando.
    Desabilitado em produção.
    """
    
    if os.getenv("BOT_ENV", "production").lower() == "production":
        raise HTTPException(
            status_code=403,
            detail="Test endpoint disabled in production"
        )
    
    test_request = {
        "user_id": "test_user",
        "message": "Olá Mesh, como você está funcionando?",
        "channel": "test"
    }
    
    return await handle_message(test_request)

# IMPORTANTE: Usar porta padrão 8000
if __name__ == "__main__":
    # Define a porta padrão como 8000 (padrão FastAPI)
    port = int(os.getenv("PORT", "8000"))
    
    logger.info(f"🚀 Starting server on port {port}...")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info"
    )