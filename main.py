import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os

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

from utils.logger import get_logger
from interfaces import teams_interface

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    settings = get_settings()
    app.state.settings = settings

    # Inicializa componentes com fallback mock
    try:
        long_term = LongTermMemory(settings=settings)
    except Exception as e:
        logger.warning(f"LongTermMemory fallback: {e}")
        class MockLongTerm:
            async def save(self, *a, **kw): pass
            async def query(self, *a, **kw): return []
        long_term = MockLongTerm()

    try:
        retrieval = RetrievalSystem(settings=settings)
    except Exception as e:
        logger.warning(f"RetrievalSystem fallback: {e}")
        class MockRetrieval:
            async def search(self, *a, **kw): return []
        retrieval = MockRetrieval()

    try:
        skill_registry = SkillRegistry(settings=settings)
    except Exception as e:
        logger.warning(f"SkillRegistry fallback: {e}")
        class MockSkills:
            def get(self, *a, **kw): return None
        skill_registry = MockSkills()

    app.state.brain = BotBrain(
        settings=settings,
        short_term_memory=ShortTermMemory(settings=settings),
        long_term_memory=long_term,
        learning_system=LearningSystem(settings=settings, long_term_memory=long_term),
        retrieval_system=retrieval,
        skill_registry=skill_registry
    )

    if os.getenv("ENABLE_TEAMS", "false").lower() == "true":
        from interfaces.teams_bot import TeamsBotInterface
        app.state.teams_interface = TeamsBotInterface(
            settings=settings,
            brain=app.state.brain
        )

    logger.info("Bot framework started successfully")
    yield
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
if os.getenv("ENABLE_TEAMS", "false").lower() == "true":
    app.include_router(teams_interface.router)

@app.get("/healthz")
async def health_check(settings: Settings = Depends(get_settings)):
    primary_llm = getattr(settings.llm, "primary_llm", None)
    primary_type = getattr(primary_llm, "type", "none") if primary_llm else "none"
    fallback_llm = getattr(settings.llm, "fallback_llm", None)
    fallback_type = getattr(fallback_llm, "type", "none") if fallback_llm else "none"

    return {
        "status": "ok",
        "bot": settings.bot.get("name", "unknown") if isinstance(settings.bot, dict) else getattr(settings.bot, "name", "unknown"),
        "provider_primary": primary_type,
        "provider_fallback": fallback_type,
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


# Endpoint de teste local para simular uma mensagem recebida do Teams

@app.post("/test/teams")
async def test_teams_message():
    """
    Endpoint de teste local para simular uma mensagem recebida do Teams.
    """
    fake_activity = {
        "type": "message",
        "text": "Olá bot",
        "from": {"id": "user1"},
        "recipient": {"id": "bot"},
        "conversation": {"id": "conv1"},
        "channelId": "msteams",
        "id": "msg1",
        "serviceUrl": "http://localhost"
    }

    bot_interface = app.state.teams_interface
    adapter = bot_interface.adapter

    async def process():
        async def logic(turn_context):
            await bot_interface.on_turn(turn_context)

        await adapter.process_activity(fake_activity, "", logic)

    await process()

    return {
        "status_code": 200,
        "message": fake_activity.get("text", "")
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )