import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from types import SimpleNamespace
from pydantic import BaseModel

from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings, TurnContext
from botbuilder.schema import Activity

class ConfigNS(SimpleNamespace):
    def get(self, key, default=None):
        return getattr(self, key, default)

    def __getitem__(self, key):
        return getattr(self, key)

    def __contains__(self, key):
        return hasattr(self, key)

    def __iter__(self):
        return iter(self.__dict__)

    def items(self):
        return self.__dict__.items()

    def values(self):
        return self.__dict__.values()

    def keys(self):
        return self.__dict__.keys()

    def __repr__(self):
        return f"ConfigNS({self.__dict__})"

    def dict(self):
        result = {}
        for k, v in self.__dict__.items():
            if isinstance(v, ConfigNS):
                result[k] = v.dict()
            else:
                result[k] = v
        return result

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

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    settings = get_settings()
    # Normalize nested dict configs to attribute-style objects
    def _to_ns(x):
        if isinstance(x, BaseModel):
            return _to_ns(x.dict())
        if isinstance(x, dict):
            return ConfigNS(**{k: _to_ns(v) for k, v in x.items()})
        if isinstance(x, list):
            return [_to_ns(v) for v in x]
        return x

    try:
        settings = ConfigNS(**{k: _to_ns(v) for k, v in settings.__dict__.items()})
        llm_section = getattr(settings, "llm", None)
        if isinstance(llm_section, dict):
            settings.llm = ConfigNS(**{k: _to_ns(v) for k, v in llm_section.items()})
        elif llm_section is None:
            settings.llm = ConfigNS(enabled=False)

        bot_section = getattr(settings, "bot", None)
        if isinstance(bot_section, dict):
            settings.bot = ConfigNS(**{k: _to_ns(v) for k, v in bot_section.items()})
        elif bot_section is None:
            settings.bot = ConfigNS(name="unknown")

        features_section = getattr(settings, "features", None)
        if isinstance(features_section, dict):
            settings.features = ConfigNS(**{k: _to_ns(v) for k, v in features_section.items()})
        elif features_section is None:
            settings.features = ConfigNS()
    except Exception:
        pass
    app.state.settings = settings

    # Inicializa componentes com fallback mock, controlados por flags de ambiente
    if os.getenv("ENABLE_LONG_TERM", "false").lower() == "true":
        try:
            long_term = LongTermMemory(settings=settings)
        except Exception as e:
            logger.warning(f"LongTermMemory fallback: {e}")
            class MockLongTerm:
                async def save(self, *a, **kw):
                    return None
                async def query(self, *a, **kw):
                    return []
                async def retrieve(self, *a, **kw):
                    # alias to query for compatibility with brain.think
                    return []
                async def upsert(self, *a, **kw):
                    return None
                async def add(self, *a, **kw):
                    return None
            long_term = MockLongTerm()
    else:
        logger.info("LongTermMemory disabled by ENABLE_LONG_TERM=false; using mock store")
        class MockLongTerm:
            async def save(self, *a, **kw):
                return None
            async def query(self, *a, **kw):
                return []
            async def retrieve(self, *a, **kw):
                # alias to query for compatibility with brain.think
                return []
            async def upsert(self, *a, **kw):
                return None
            async def add(self, *a, **kw):
                return None
        long_term = MockLongTerm()

    if os.getenv("ENABLE_RETRIEVAL", "false").lower() == "true":
        try:
            retrieval = RetrievalSystem(settings=settings)
        except Exception as e:
            logger.warning(f"RetrievalSystem fallback: {e}")
            class MockRetrieval:
                async def search(self, *a, **kw): return []
                async def retrieve_relevant_documents(self, *a, **kw):
                    return []
            retrieval = MockRetrieval()
    else:
        logger.info("RetrievalSystem disabled by ENABLE_RETRIEVAL=false; using mock search")
        class MockRetrieval:
            async def search(self, *a, **kw): return []
            async def retrieve_relevant_documents(self, *a, **kw):
                return []
        retrieval = MockRetrieval()

    try:
        skill_registry = SkillRegistry(settings=settings)
    except Exception as e:
        logger.warning(f"SkillRegistry fallback: {e}")
        class MockSkills:
            def get(self, *a, **kw): return None
        skill_registry = MockSkills()

    logger.info(f"[DEBUG main] type(settings.llm)={type(settings.llm)}, content={settings.llm}")
    logger.info(f"[DEBUG main] type(settings.bot)={type(settings.bot)}, content={settings.bot}")
    logger.info(f"[DEBUG main] type(settings.features)={type(settings.features)}, content={settings.features}")

    app.state.brain = BotBrain(
        settings=app.state.settings,
        short_term_memory=ShortTermMemory(settings=app.state.settings),
        long_term_memory=long_term,
        learning_system=LearningSystem(settings=app.state.settings, long_term_memory=long_term),
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

APP_ID = os.getenv("MICROSOFT_APP_ID", "")
APP_PASSWORD = os.getenv("MICROSOFT_APP_PASSWORD", "")
adapter_settings = BotFrameworkAdapterSettings(APP_ID, APP_PASSWORD)
adapter = BotFrameworkAdapter(adapter_settings)

class EchoBot:
    async def on_turn(self, turn_context: TurnContext):
        if turn_context.activity.type == "message":
            await turn_context.send_activity(f"Você disse: {turn_context.activity.text}")

bot = EchoBot()

@app.post("/api/messages")
async def messages(request: Request):
    body = await request.json()
    activity = Activity().deserialize(body)
    auth_header = request.headers.get("Authorization", "")

    async def aux(turn_context: TurnContext):
        await bot.on_turn(turn_context)

    response = await adapter.process_activity(activity, auth_header, aux)
    if response:
        return response.body
    return {"status": "ok"}

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
    try:
        from interfaces import teams_interface as _teams_interface
        app.include_router(_teams_interface.router)
    except Exception as e:
        logger.warning(f"Teams interface not loaded: {e}")

@app.get("/healthz")
async def health_check(request: Request):
    settings = getattr(request.app.state, "settings", None)
    if settings is None:
        settings = get_settings()
    primary_llm = getattr(settings.llm, "primary_llm", None)
    primary_type = getattr(primary_llm, "type", "none") if primary_llm else "none"
    fallback_llm = getattr(settings.llm, "fallback_llm", None)
    fallback_type = getattr(fallback_llm, "type", "none") if fallback_llm else "none"

    bot_name = getattr(settings.bot, "name", "unknown")
    return {
        "status": "ok",
        "bot": bot_name,
        "provider_primary": primary_type,
        "provider_fallback": fallback_type,
        "long_term_enabled": os.getenv("ENABLE_LONG_TERM", "false").lower() == "true",
        "retrieval_enabled": os.getenv("ENABLE_RETRIEVAL", "false").lower() == "true",
        "version": "1.0.0"
    }

@app.post("/v1/messages")
async def handle_message(
    message: dict,
    request: Request
):
    settings = getattr(request.app.state, "settings", None)
    user_id = message.get("user_id")
    user_message = message.get("message")
    channel = message.get("channel", "http")

    if not user_id or not user_message:
        raise HTTPException(status_code=400, detail="user_id and message are required")

    try:
        response = await app.state.brain.think(user_id, user_message, channel)
        return response
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        # Fallback path to keep the primary HTTP flow alive without hard failing
        if os.getenv("SAFE_ECHO", "false").lower() == "true":
            return {
                "status": "ok",
                "mode": "safe-echo",
                "reply": f"[echo] {user_message}",
                "detail": "Brain unavailable; returning echo because SAFE_ECHO=true"
            }
        raise HTTPException(status_code=500, detail=str(e))


# Endpoint de teste local para simular uma mensagem recebida do Teams

@app.post("/test/teams")
async def test_teams_message():
    """
    Endpoint de teste local para simular uma mensagem recebida do Teams.
    """
    bot_interface = getattr(app.state, "teams_interface", None)
    if not bot_interface:
        return {"status_code": 400, "error": "Teams interface disabled. Set ENABLE_TEAMS=true to enable."}

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
        port=int(os.getenv("PORT", 80)),  # Usa PORT definida pelo Azure ou cai no 80
        reload=os.getenv("UVICORN_RELOAD", "true").lower() == "true"
    )