import asyncio
from contextlib import asynccontextmanager
from typing import Dict, Any
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Setup logging first
from utils.logger import setup_logging, get_logger
setup_logging()

# Then import other modules
from config.settings import Settings, get_settings
from core.brain import BotBrain
from core.context_engine import ContextEngine
from core.response_builder import ResponseBuilder
from core.router import MessageRouter
from memory.short_term import ShortTermMemory
from memory.long_term import LongTermMemory
from memory.learning import LearningSystem
from memory.retrieval import RetrievalSystem
from personality.personality_loader import PersonalityLoader
from skills.skill_registry import SkillRegistry
from utils.metrics import metrics_router

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
        
        # Inicializa componentes de memória
        logger.info("Initializing memory systems...")
        app_components['short_term_memory'] = ShortTermMemory(settings)
        app_components['long_term_memory'] = LongTermMemory(settings)
        app_components['learning_system'] = LearningSystem(
            settings, 
            app_components['long_term_memory']
        )
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
        
        # Inicializa context engine
        app_components['context_engine'] = ContextEngine(
            settings=settings,
            short_term_memory=app_components['short_term_memory'],
            long_term_memory=app_components['long_term_memory'],
            learning_system=app_components['learning_system'],
            retrieval_system=app_components['retrieval_system'],
            personality_loader=app_components['personality_loader']
        )
        
        # Inicializa o cérebro do bot
        logger.info("Initializing bot brain...")
        app_components['brain'] = BotBrain(
            settings=settings,
            short_term_memory=app_components['short_term_memory'],
            long_term_memory=app_components['long_term_memory'],
            learning_system=app_components['learning_system'],
            retrieval_system=app_components['retrieval_system'],
            skill_registry=app_components['skill_registry']
        )
        
        logger.info("✅ Bot Framework started successfully!")
        
        # Verificação de saúde do LLM
        if app_components['brain'].primary_provider:
            logger.info("✅ Primary LLM provider (Azure OpenAI) is configured")
        else:
            logger.warning("⚠️ Primary LLM provider is not configured")
            
        if app_components['brain'].fallback_provider:
            logger.info("✅ Fallback LLM provider (Claude) is configured")
        else:
            logger.warning("⚠️ Fallback LLM provider is not configured")
        
        yield
        
    except Exception as e:
        logger.error(f"❌ Failed to start Bot Framework: {str(e)}")
        raise
    
    # ===== SHUTDOWN =====
    logger.info("Shutting down Bot Framework...")
    
    # Cleanup de recursos se necessário
    if 'brain' in app_components:
        # Fecha conexões do Claude se existir
        if hasattr(app_components['brain'].fallback_provider, 'client'):
            await app_components['brain'].fallback_provider.client.aclose()

# Cria a aplicação FastAPI
app = FastAPI(
    title="Bot Framework - Mesh",
    description="Bot Framework with Azure OpenAI integration",
    version="1.0.0",
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
        "endpoints": {
            "health": "/healthz",
            "metrics": "/metrics",
            "messages": "/v1/messages",
            "test": "/test/message"
        }
    }

@app.get("/healthz")
async def health_check():
    """Verifica a saúde da aplicação."""
    
    health_status = {
        "status": "ok",
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
    
    # Verifica memória
    health_status["checks"]["memory"] = "✅" if 'short_term_memory' in app_components else "❌"
    health_status["checks"]["skills"] = "✅" if 'skill_registry' in app_components else "❌"
    
    # Determina status geral
    if "❌" in health_status["checks"].values():
        health_status["status"] = "unhealthy"
        return health_status
    
    health_status["version"] = "1.0.0"
    return health_status

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
    Envia uma mensagem simples e retorna a resposta.
    """
    
    test_request = {
        "user_id": "test_user",
        "message": "Olá, qual é seu nome?",
        "channel": "test"
    }
    
    try:
        response = await handle_message(test_request)
        return {
            "test": "success",
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