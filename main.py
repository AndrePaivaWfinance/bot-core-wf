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
    logger.info("🚀 Starting Bot Framework v2.0.0...")
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
        logger.info(f"   Version: 2.0.0")
        logger.info(f"   Architecture: Memory Manager")
        logger.info(f"   Ready to receive messages")
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
    description="AI-powered BPO Financial Analyst Bot",
    version="2.0.0",
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
        "service": "Bot Framework - Mesh",
        "status": "online",
        "version": "2.0.0",
        "architecture": "memory_manager",
        "bot": {
            "name": app_components.get('settings', {}).bot.name if 'settings' in app_components else "Mesh",
            "type": app_components.get('settings', {}).bot.type if 'settings' in app_components else "financial_analyst"
        },
        "endpoints": {
            "health": "/healthz",
            "metrics": "/metrics",
            "messages": "/v1/messages",
            "bot_framework": "/api/messages",
            "memory_stats": "/v1/memory/stats",
            "docs": "/docs"
        },
        "timestamp": os.popen('date').read().strip()
    }

@app.get("/healthz")
async def health_check():
    """Health check endpoint com informações detalhadas."""
    
    health_status = {
        "status": "ok",
        "service": "meshbrain",
        "version": "2.0.0",
        "architecture": "memory_manager",
        "timestamp": os.popen('date').read().strip(),
        "checks": {},
        "environment": {
            "bot_env": os.getenv("BOT_ENV", "production"),
            "port": os.getenv("PORT", "8000")
        }
    }
    
    # Verifica configurações
    if 'settings' in app_components:
        settings = app_components['settings']
        health_status["bot"] = settings.bot.name
        health_status["bot_type"] = settings.bot.type
        health_status["checks"]["settings"] = "✅"
    else:
        health_status["checks"]["settings"] = "❌"
        health_status["status"] = "degraded"
    
    # Verifica brain e providers
    if 'brain' in app_components:
        brain = app_components['brain']
        health_status["checks"]["brain"] = "✅"
        
        # Verifica providers
        if brain.primary_provider and brain.primary_provider.is_available():
            health_status["provider_primary"] = "azure_openai"
            health_status["checks"]["azure_openai"] = "✅"
        else:
            health_status["provider_primary"] = "none"
            health_status["checks"]["azure_openai"] = "❌"
            
        if brain.fallback_provider and brain.fallback_provider.is_available():
            health_status["provider_fallback"] = "claude"
            health_status["checks"]["claude"] = "✅"
        else:
            health_status["provider_fallback"] = "none"
            health_status["checks"]["claude"] = "⚠️"
    else:
        health_status["checks"]["brain"] = "❌"
        health_status["status"] = "unhealthy"
    
    # Verifica Memory Manager
    if 'memory_manager' in app_components:
        memory_stats = app_components['memory_manager'].get_storage_stats()
        health_status["checks"]["memory_manager"] = "✅"
        health_status["memory_health"] = memory_stats["health"]
        health_status["memory_providers"] = {
            provider: status["available"]
            for provider, status in memory_stats["providers"].items()
        }
    else:
        health_status["checks"]["memory_manager"] = "❌"
        health_status["status"] = "unhealthy"
    
    # Verifica Bot Framework
    if 'bot_framework' in app_components:
        health_status["checks"]["bot_framework"] = "✅"
        health_status["bot_framework_endpoint"] = "/api/messages"
        health_status["teams_configured"] = True
    else:
        health_status["checks"]["bot_framework"] = "⚠️"
        health_status["teams_configured"] = False
    
    # Verifica outros componentes
    health_status["checks"]["skills"] = "✅" if 'skill_registry' in app_components else "❌"
    health_status["checks"]["learning"] = "✅" if 'learning_system' in app_components else "❌"
    health_status["checks"]["retrieval"] = "✅" if 'retrieval_system' in app_components else "❌"
    
    # Determina status geral
    critical_checks = ["brain", "memory_manager", "settings"]
    failed_critical = [check for check in critical_checks if health_status["checks"].get(check) == "❌"]
    
    if failed_critical:
        health_status["status"] = "unhealthy"
        health_status["failed_components"] = failed_critical
    elif health_status["checks"].get("azure_openai") == "❌" and health_status["checks"].get("claude") == "⚠️":
        health_status["status"] = "degraded"
        health_status["warning"] = "No LLM providers available"
    
    # Retorna com status HTTP apropriado
    status_code = 200 if health_status["status"] == "ok" else 503 if health_status["status"] == "unhealthy" else 200
    
    return health_status

@app.get("/v1/memory/stats")
async def memory_stats():
    """Retorna estatísticas detalhadas de memória."""
    if 'memory_manager' not in app_components:
        raise HTTPException(status_code=503, detail="Memory Manager not initialized")
    
    stats = app_components['memory_manager'].get_storage_stats()
    
    # Adiciona informações extras se disponível
    if 'brain' in app_components:
        try:
            # Pode adicionar estatísticas do brain se necessário
            pass
        except:
            pass
    
    return stats

@app.post("/v1/messages")
async def handle_message(request: Dict[str, Any]):
    """
    Processa uma mensagem através do bot.
    
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
        
        # Processa a mensagem
        response = await app_components['brain'].think(
            user_id=user_id,
            message=message,
            channel=channel
        )
        
        logger.info(f"✅ Response generated for user: {user_id}")
        logger.debug(f"   Provider used: {response.get('metadata', {}).get('provider', 'unknown')}")
        
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
    
    try:
        response = await handle_message(test_request)
        return {
            "test": "success",
            "architecture": "memory_manager",
            "request": test_request,
            "response": response
        }
    except Exception as e:
        return {
            "test": "failed",
            "error": str(e)
        }

@app.post("/v1/skills/{skill_name}")
async def invoke_skill(skill_name: str, parameters: Dict[str, Any]):
    """
    Invoca uma skill específica diretamente.
    """
    
    if 'skill_registry' not in app_components:
        raise HTTPException(
            status_code=503,
            detail="Skill registry is not initialized"
        )
    
    try:
        skill = app_components['skill_registry'].get_skill(skill_name)
        if not skill:
            raise HTTPException(
                status_code=404,
                detail=f"Skill '{skill_name}' not found"
            )
        
        # Verifica se skill está habilitada
        if not skill.enabled:
            raise HTTPException(
                status_code=403,
                detail=f"Skill '{skill_name}' is disabled"
            )
        
        result = await skill.execute(parameters, {})
        
        return {
            "skill": skill_name,
            "result": result,
            "metadata": skill.get_metadata()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing skill {skill_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v1/skills")
async def list_skills():
    """Lista todas as skills disponíveis."""
    if 'skill_registry' not in app_components:
        return {"skills": [], "error": "Skill registry not initialized"}
    
    skills = []
    for skill_name in app_components['skill_registry'].list_skills():
        skill = app_components['skill_registry'].get_skill(skill_name)
        if skill:
            skills.append({
                "name": skill_name,
                "enabled": skill.enabled,
                "metadata": skill.get_metadata()
            })
    
    return {"skills": skills}

if __name__ == "__main__":
    # Configurações de desenvolvimento
    port = int(os.getenv("PORT", 8000))
    
    logger.info(f"Starting server on port {port}...")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv("BOT_ENV", "production").lower() == "development",
        log_level=os.getenv("LOG_LEVEL", "info").lower()
    )