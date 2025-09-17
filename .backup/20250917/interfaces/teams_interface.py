from fastapi import APIRouter, Request, Response
from fastapi.testclient import TestClient
from interfaces.teams_bot import TeamsBotInterface

# Router do FastAPI para integrar com o Teams
router = APIRouter()

@router.post("/api/messages")
async def messages(req: Request) -> Response:
    body_bytes = await req.body()
    body = body_bytes.decode("utf-8")
    auth_header = req.headers.get("Authorization", "")
    bot_interface: TeamsBotInterface = getattr(req.app.state, "teams_interface", None)
    if bot_interface is None:
        return Response(status_code=500, content="Teams interface not initialized")
    invoke_response = await bot_interface.adapter.process_activity(body, auth_header, bot_interface.on_turn)
    # Se o retorno for um objeto com status e body, converte para Response
    if hasattr(invoke_response, "status") and hasattr(invoke_response, "body"):
        return Response(status_code=invoke_response.status, content=invoke_response.body)
    else:
        return Response(status_code=200)

@router.post("/test/teams")
async def test_teams_message():
    """
    Endpoint de teste local para simular uma mensagem recebida do Teams e processada pelo BotBrain.
    """
    import os
    if os.getenv("ENV") == "production":
        return {"status_code": 403, "response": "Disabled in production"}
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