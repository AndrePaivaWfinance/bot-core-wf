import os
from fastapi import APIRouter, Request, Response
from fastapi.testclient import TestClient
from interfaces.teams_bot import TeamsBotInterface

# Router do FastAPI para integrar com o Teams
router = APIRouter()

@router.post("/api/messages")
async def messages(req: Request) -> Response:
    body = await req.json()
    auth_header = req.headers.get("Authorization", "")
    bot_interface: TeamsBotInterface = req.app.state.teams_interface
    return await bot_interface.adapter.process_activity(body, auth_header, bot_interface.on_turn)

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