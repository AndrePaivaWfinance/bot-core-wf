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
    """Gerencia o ciclo de vida da aplicação."""
    
    # ===== STARTUP =====
    logger.info("Starting Bot Framework...")
    
    try:
        # Carrega configurações
        settings = get_settings()
        app_components['settings'] = settings
        
        # Inicializa componentes de memória - NOVA ARQUITETURA APENAS
        logger.info("Initializing memory systems...")
        app_components['memory_manager'] = MemoryManager(settings)
        
        # Sistemas auxiliares
        app_components['learning_system'] = LearningSystem(settings, None)  # Sem dependência de LongTermMemory
        app_components['retrieval_system'] = RetrievalSystem(settings)
        
        # Inicializa personalidade
        logger.info("Loading personality...")
        app_components['personality_loader'] = PersonalityLoader(settings)
        
        # Inicializa registro de skills
        logger.info("Loading skills...")
        app_components['skill_registry'] = SkillRegistry(settings)
        await app_components['skill_registry'].load_skills()
        
        # Inicializa roteador e construtor de resposta
        app_components['router'] = MessageRouter()
        app_components['response_builder'] = ResponseBuilder(
            settings,
            app_components['personality_loader']
        )
        
        # Context engine simplificado (sem dependências antigas)
        logger.info("Initializing context engine...")
        app_components['context_engine'] = ContextEngine(
            settings=settings,
            short_term_memory=None,  # Removido
            long_term_memory=None,   # Removido  
            learning_system=app_components['learning_system'],
            retrieval_system=app_components['retrieval_system'],
            personality_loader=app_components['personality_loader']
        )
        
        # Inicializa o cérebro do bot - NOVA ARQUITETURA
        logger.info("Initializing bot brain...")
        app_components['brain'] = BotBrain(
            settings=settings,
            memory_manager=app_components['memory_manager'],  # NOVO
            learning_system=app_components['learning_system'],
            retrieval_system=app_components['retrieval_system'],
            skill_registry=app_components['skill_registry']
        )
        
        logger.info("✅ Bot Framework started successfully!")
        
        # Inicializa Bot Framework Handler para Azure Bot Service
        if settings.teams and settings.teams.app_id:
            logger.info("Initializing Bot Framework handler for Azure Bot Service...")
            app_components['bot_framework'] = BotFrameworkHandler(
                settings=settings,
                brain=app_components['brain']
            )
            # Registra as rotas do Bot Framework
            app.include_router(app_components['bot_framework'].router)
            logger.info("✅ Bot Framework handler initialized - /api/messages endpoint ready")
        else:
            logger.warning("⚠️ Teams App ID not configured - Bot Framework handler not initialized")
        
        # Verificação de saúde do LLM
        if app_components['brain'].primary_provider:
            logger.info("✅ Primary LLM provider (Azure OpenAI) is configured")
        else:
            logger.warning("⚠️ Primary LLM provider is not configured")
            
        if app_components['brain'].fallback_provider:
            logger.info("✅ Fallback LLM provider (Claude) is configured")
        else:
            logger.warning("⚠️ Fallback LLM provider is not configured")
        
        # Verificar Memory Manager
        memory_stats = app_components['memory_manager'].get_storage_stats()
        logger.info(f"💾 Memory Manager Status: {memory_stats['health']}")
        for provider, status in memory_stats['providers'].items():
            logger.info(f"   {provider}: {'✅' if status['available'] else '❌'}")
        
        yield
        
    except Exception as e:
        logger.error(f"❌ Failed to start Bot Framework: {str(e)}")
        raise
    
    # ===== SHUTDOWN =====
    logger.info("Shutting down Bot Framework...")
    
    # Cleanup de recursos se necessário
    if 'brain' in app_components:
        # Fecha conexões do Claude se existir
        if hasattr(app_components['brain'], 'fallback_provider') and app_components['brain'].fallback_provider:
            if hasattr(app_components['brain'].fallback_provider, 'client'):
                try:
                    await app_components['brain'].fallback_provider.client.aclose()
                except:
                    pass  # Ignore cleanup errors

# Cria a aplicação FastAPI
app = FastAPI(
    title="Bot Framework - Mesh",
    description="Bot Framework with Memory Manager Architecture",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, especifique os domínios permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclui rotas de métricas
app.include_router(metrics_router)

@app.get("/")
async def root():
    """Endpoint raiz."""
    return {
        "message": "Bot Framework is running",
        "status": "online",
        "architecture": "memory_manager",
        "version": "2.0.0",
        "memory": "multi-tier",
        "endpoints": {
            "health": "/healthz",
            "metrics": "/metrics", 
            "messages": "/v1/messages",
            "bot_framework": "/api/messages",
            "test": "/test/message",
            "memory_stats": "/v1/memory/stats"
        }
    }

@app.get("/healthz")
async def health_check():
    """Verifica a saúde da aplicação."""
    
    health_status = {
        "status": "ok",
        "architecture": "memory_manager",
        "version": "2.0.0",
        "checks": {}
    }
    
    # Verifica configurações
    if 'settings' in app_components:
        settings = app_components['settings']
        health_status["bot"] = settings.bot.name
        health_status["bot_type"] = settings.bot.type
        health_status["checks"]["settings"] = "✅"
    else:
        health_status["checks"]["settings"] = "❌"
    
    # Verifica brain
    if 'brain' in app_components:
        brain = app_components['brain']
        health_status["checks"]["brain"] = "✅"
        
        # Verifica providers
        if brain.primary_provider:
            health_status["provider_primary"] = "azure_openai"
            health_status["checks"]["azure_openai"] = "✅"
        else:
            health_status["provider_primary"] = "none"
            health_status["checks"]["azure_openai"] = "❌"
            
        if brain.fallback_provider:
            health_status["provider_fallback"] = "claude"
            health_status["checks"]["claude"] = "✅"
        else:
            health_status["provider_fallback"] = "none"
            health_status["checks"]["claude"] = "⚠️"
    else:
        health_status["checks"]["brain"] = "❌"
    
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
    
    # Verifica Bot Framework
    if 'bot_framework' in app_components:
        health_status["checks"]["bot_framework"] = "✅"
        health_status["bot_framework_endpoint"] = "/api/messages"
    else:
        health_status["checks"]["bot_framework"] = "❌"
    
    # Verifica skills
    health_status["checks"]["skills"] = "✅" if 'skill_registry' in app_components else "❌"
    health_status["checks"]["learning"] = "✅" if 'learning_system' in app_components else "❌"
    health_status["checks"]["retrieval"] = "✅" if 'retrieval_system' in app_components else "❌"
    
    # Determina status geral
    critical_checks = ["brain", "memory_manager", "settings"]
    if any(health_status["checks"].get(check) == "❌" for check in critical_checks):
        health_status["status"] = "unhealthy"
        return health_status
    
    return health_status

@app.get("/v1/memory/stats")
async def memory_stats():
    """Retorna estatísticas detalhadas de memória."""
    if 'memory_manager' not in app_components:
        raise HTTPException(status_code=503, detail="Memory Manager not initialized")
    
    return app_components['memory_manager'].get_storage_stats()

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
        logger.info(f"Processing message from user: {user_id}")
        
        # Processa a mensagem
        response = await app_components['brain'].think(
            user_id=user_id,
            message=message,
            channel=channel
        )
        
        logger.info(f"Response generated successfully for user: {user_id}")
        return response
        
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/test/message")
async def test_message():
    """
    Endpoint de teste para verificar se o bot está funcionando.
    """
    
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
        
        result = await skill.execute(parameters, {})
        return {"skill": skill_name, "result": result}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing skill {skill_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # Configurações de desenvolvimento
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=True,
        log_level=os.getenv("LOG_LEVEL", "info").lower()
    )