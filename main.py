import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Setup logging first
from utils.logger import setup_logging
setup_logging()

# Then import other modules
from config.settings import Settings, get_settings
from core.brain import BotBrain
from memory.short_term import ShortTermMemory
from memory.long_term import LongTermMemory
from memory.learning import LearningSystem
from memory.retrieval import RetrievalSystem
from skills.skill_registry import SkillRegistry
from interfaces.teams_bot import TeamsBotInterface
from interfaces.email_handler import EmailHandlerInterface
from utils.logger import get_logger
from utils.metrics import metrics_router

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    settings = get_settings()
    
    # Initialize components
    app.state.settings = settings
    app.state.short_term_memory = ShortTermMemory(settings)
    app.state.long_term_memory = LongTermMemory(settings)
    app.state.learning_system = LearningSystem(settings, app.state.long_term_memory)
    app.state.retrieval_system = RetrievalSystem(settings)
    app.state.skill_registry = SkillRegistry(settings)
    
    # Load skills
    await app.state.skill_registry.load_skills()
    
    # Initialize brain
    app.state.brain = BotBrain(
        settings=settings,
        short_term_memory=app.state.short_term_memory,
        long_term_memory=app.state.long_term_memory,
        learning_system=app.state.learning_system,
        retrieval_system=app.state.retrieval_system,
        skill_registry=app.state.skill_registry
    )
    
    # Initialize interfaces
    app.state.teams_interface = TeamsBotInterface(settings, app.state.brain)
    app.state.email_interface = EmailHandlerInterface(settings, app.state.brain)
    
    logger.info("Bot framework started successfully")
    yield
    
    # Shutdown
    logger.info("Shutting down bot framework")

app = FastAPI(
    title="Bot Framework",
    description="Generic bot framework with memory and skills",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(metrics_router)

if hasattr(app.state, "teams_interface"):
    app.include_router(app.state.teams_interface.router)

if hasattr(app.state, "email_interface"):
    app.include_router(app.state.email_interface.router)

@app.get("/healthz")
async def health_check(settings: Settings = Depends(get_settings)):
    return {
        "status": "ok",
        "bot": settings.bot.name,
        "provider_primary": settings.llm.primary_llm.type if settings.llm.primary_llm else "none",
        "provider_fallback": settings.llm.fallback_llm.type if settings.llm.fallback_llm else "none",
        "version": "1.0.0"
    }

@app.post("/v1/messages")
async def handle_message(
    message: dict,
    settings: Settings = Depends(get_settings)
):
    try:
        user_id = message.get("user_id")
        user_message = message.get("message")
        channel = message.get("channel", "http")
        
        if not user_id or not user_message:
            raise HTTPException(status_code=400, detail="user_id and message are required")
        
        response = await app.state.brain.think(user_id, user_message, channel)
        return response
        
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/skills/{skill_name}")
async def invoke_skill(
    skill_name: str,
    parameters: dict,
    settings: Settings = Depends(get_settings)
):
    try:
        skill = app.state.skill_registry.get_skill(skill_name)
        if not skill:
            raise HTTPException(status_code=404, detail=f"Skill {skill_name} not found")
        
        result = await skill.execute(parameters, {})
        return {"skill": skill_name, "result": result}
        
    except Exception as e:
        logger.error(f"Error executing skill {skill_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )