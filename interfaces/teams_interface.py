import os
from fastapi import APIRouter, Request, Response
from botbuilder.core import BotFrameworkAdapterSettings, BotFrameworkAdapter, TurnContext, ActivityHandler

from core.brain import BotBrain
from config.settings import get_settings

# Variáveis de ambiente com credenciais do Azure Bot
MICROSOFT_APP_ID = os.getenv("MICROSOFT_APP_ID", "")
MICROSOFT_APP_PASSWORD = os.getenv("MICROSOFT_APP_PASSWORD", "")

if not MICROSOFT_APP_ID or not MICROSOFT_APP_PASSWORD:
    print("Warning: MICROSOFT_APP_ID or MICROSOFT_APP_PASSWORD environment variables are missing.")

# Configuração do adapter do Bot Framework
adapter_settings = BotFrameworkAdapterSettings(MICROSOFT_APP_ID, MICROSOFT_APP_PASSWORD)
adapter = BotFrameworkAdapter(adapter_settings)


# Implementação do bot integrado com BotBrain
class TeamsBot(ActivityHandler):
    def __init__(self, brain: BotBrain):
        self.brain = brain

    async def on_message_activity(self, turn_context: TurnContext) -> None:
        user_message = turn_context.activity.text.strip() if turn_context.activity.text else ""
        try:
            # Processa com o BotBrain
            response = await self.brain.process_message(user_message)
        except Exception as e:
            response = "Desculpe, ocorreu um erro ao processar sua mensagem."
        await turn_context.send_activity(response)

    async def on_turn(self, turn_context: TurnContext):
        if turn_context.activity.type == "message":
            await self.on_message_activity(turn_context)
        else:
            # Apenas loga ou envia resposta básica
            await turn_context.send_activity(f"[on_turn] Tipo de atividade recebido: {turn_context.activity.type}")


# Router do FastAPI para integrar com o Teams
router = APIRouter()

@router.post("/api/messages")
async def messages(req: Request) -> Response:
    body = await req.json()
    auth_header = req.headers.get("Authorization", "")
    bot = req.app.state.teams_interface
    return await adapter.process_activity(body, auth_header, bot.on_turn)


# Endpoint de teste local para simular uma mensagem recebida do Teams e processada pelo BotBrain.
from fastapi.testclient import TestClient

@router.post("/test/teams")
async def test_teams_message():
    """
    Endpoint de teste local para simular uma mensagem recebida do Teams e processada pelo BotBrain.
    """
    from main import app

    client = TestClient(app)

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

    response = client.post("/api/messages", json=fake_activity)
    return {
        "status_code": response.status_code,
        "response": response.text
    }

# Exemplo de teste com curl:
# curl -X POST http://localhost:8000/test/teams