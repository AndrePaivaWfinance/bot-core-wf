


import os
from fastapi import APIRouter, Request, Response
from botbuilder.core import BotFrameworkAdapterSettings, BotFrameworkAdapter, TurnContext, ActivityHandler

# Variáveis de ambiente com credenciais do Azure Bot
MICROSOFT_APP_ID = os.getenv("MICROSOFT_APP_ID", "")
MICROSOFT_APP_PASSWORD = os.getenv("MICROSOFT_APP_PASSWORD", "")

# Configuração do adapter do Bot Framework
adapter_settings = BotFrameworkAdapterSettings(MICROSOFT_APP_ID, MICROSOFT_APP_PASSWORD)
adapter = BotFrameworkAdapter(adapter_settings)

# Implementação básica do bot
class TeamsBot(ActivityHandler):
    async def on_message_activity(self, turn_context: TurnContext):
        text = turn_context.activity.text.strip() if turn_context.activity.text else ""
        await turn_context.send_activity(f"Você disse: {text}")

bot = TeamsBot()

# Router do FastAPI para integrar com o Teams
router = APIRouter()

@router.post("/api/messages")
async def messages(req: Request) -> Response:
    body = await req.body()
    auth_header = req.headers.get("Authorization", "")
    return await adapter.process_activity(body.decode("utf-8"), auth_header, bot.on_turn)