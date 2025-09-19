"""
Bot Framework Handler para integração com Azure Bot Service e Teams
"""
import json
import os
from typing import Dict, Any
from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import JSONResponse
import httpx

from config.settings import Settings
from core.brain import BotBrain
from utils.logger import get_logger

logger = get_logger(__name__)

class BotFrameworkHandler:
    def __init__(self, settings: Settings, brain: BotBrain):
        self.settings = settings
        self.brain = brain
        self.router = APIRouter()
        self._setup_routes()
        
        # Configurações do Bot Framework - tenta múltiplas variáveis
        self.app_id = (
            os.getenv('MICROSOFT_APP_ID') or 
            os.getenv('TEAMS_APP_ID') or
            (settings.teams.app_id if hasattr(settings, 'teams') else None)
        )
        self.app_password = (
            os.getenv('MICROSOFT_APP_PASSWORD') or 
            os.getenv('TEAMS_APP_PASSWORD') or
            (settings.teams.app_password if hasattr(settings, 'teams') else None)
        )
        # IMPORTANTE: Pegar o tenant correto para single-tenant
        self.tenant_id = (
            os.getenv('MICROSOFT_APP_TENANT_ID') or
            os.getenv('MicrosoftAppTenantId') or
            '9ad45470-e5c8-45d9-a335-b5f311990261'  # Seu tenant específico
        )
        
        logger.info(f"BotFrameworkHandler initialized. App ID configured: {bool(self.app_id)}")
        logger.info(f"Using tenant: {self.tenant_id}")
        if self.app_id:
            logger.info(f"App ID starts with: {self.app_id[:8]}...")
        else:
            logger.warning("No App ID found in environment variables!")
    
    def _setup_routes(self):
        """Configura as rotas do Bot Framework"""
        
        @self.router.post("/api/messages")
        async def messages_handler(request: Request) -> Response:
            """
            Endpoint principal do Bot Framework
            Recebe activities do Azure Bot Service
            """
            try:
                # Lê o body da requisição
                body = await request.body()
                body_str = body.decode('utf-8')
                
                # Parse do JSON
                try:
                    activity = json.loads(body_str)
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON received: {body_str[:200]}")
                    return Response(status_code=400, content="Invalid JSON")
                
                logger.info(f"Received activity type: {activity.get('type')}")
                logger.debug(f"Activity: {json.dumps(activity, indent=2)}")
                
                # Processa a activity
                response = await self._process_activity(activity)
                
                # Bot Framework espera status 200 para sucesso
                if response:
                    return JSONResponse(content=response, status_code=200)
                else:
                    return Response(status_code=200)
                    
            except Exception as e:
                logger.error(f"Error in messages_handler: {str(e)}")
                return Response(status_code=500)
        
        @self.router.options("/api/messages")
        async def messages_options() -> Response:
            """Handle OPTIONS requests for CORS"""
            return Response(status_code=200)
    
    async def _process_activity(self, activity: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa uma activity do Bot Framework
        """
        activity_type = activity.get('type', '')
        
        if activity_type == 'message':
            # Extrai informações da mensagem
            user_id = activity.get('from', {}).get('id', 'unknown')
            user_name = activity.get('from', {}).get('name', '')
            text = activity.get('text', '')
            channel_id = activity.get('channelId', 'emulator')
            conversation_id = activity.get('conversation', {}).get('id', '')
            
            logger.info(f"Processing message from {user_name} ({user_id}): {text}")
            
            # Processa a mensagem com o Brain
            try:
                response = await self.brain.process_message(
                    user_id=user_id,
                    message=text,
                    channel="teams"
                )
                
                response_text = response.get('response', 'Desculpe, ocorreu um erro ao processar sua mensagem.')
                
                # IMPORTANTE: Enviar resposta pelo Bot Framework
                await self._send_reply(activity, response_text)
                
                # Retorna resposta para o endpoint (para compatibilidade)
                return {
                    "type": "message",
                    "from": {"id": self.app_id or "bot", "name": "Mesh"},
                    "recipient": activity.get('from'),
                    "conversation": activity.get('conversation'),
                    "text": response_text,
                    "replyToId": activity.get('id'),
                    "locale": "pt-BR"
                }
                
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")
                error_msg = "Desculpe, ocorreu um erro ao processar sua mensagem. Por favor, tente novamente."
                await self._send_reply(activity, error_msg)
                return {
                    "type": "message",
                    "text": error_msg
                }
        
        elif activity_type == 'conversationUpdate':
            # Mensagem de boas-vindas quando bot é adicionado
            members_added = activity.get('membersAdded', [])
            bot_id = activity.get('recipient', {}).get('id', '')
            
            for member in members_added:
                if member.get('id') != bot_id:
                    welcome_msg = (
                        "👋 Olá! Eu sou o Mesh, seu assistente virtual.\n\n"
                        "Estou aqui para ajudar com suas dúvidas e tarefas. "
                        "Como posso ajudá-lo hoje?"
                    )
                    await self._send_reply(activity, welcome_msg)
                    
            return None
        
        elif activity_type == 'typing':
            # Ignora eventos de digitação
            logger.info("Received activity type 'typing' - no action needed")
            return None
        
        else:
            logger.info(f"Received unsupported activity type: {activity_type}")
            return None
    
    async def _send_reply(self, activity: Dict[str, Any], response_text: str):
        """
        Envia resposta de volta pelo Bot Framework
        """
        service_url = activity.get('serviceUrl', '')
        conversation_id = activity.get('conversation', {}).get('id', '')
        activity_id = activity.get('id', '')
        
        if not service_url or not conversation_id:
            logger.error("Missing serviceUrl or conversation.id")
            return
        
        # URL para enviar resposta
        reply_url = f"{service_url}v3/conversations/{conversation_id}/activities/{activity_id}"
        
        # Activity de resposta
        reply_activity = {
            "type": "message",
            "from": {
                "id": self.app_id or "bot",
                "name": "Mesh"
            },
            "recipient": activity.get('from'),
            "conversation": activity.get('conversation'),
            "text": response_text,
            "replyToId": activity_id,
            "locale": "pt-BR",
            "channelData": {}
        }
        
        # Obter token de autenticação
        headers = {
            "Content-Type": "application/json"
        }
        
        if self.app_id and self.app_password:
            token = await self._get_auth_token()
            if token:
                headers["Authorization"] = f"Bearer {token}"
                logger.info("Using authenticated request")
            else:
                logger.warning("Failed to get auth token, sending without authentication")
        
        # Enviar resposta
        try:
            logger.info(f"Sending reply to: {reply_url}")
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    reply_url,
                    json=reply_activity,
                    headers=headers,
                    timeout=10.0
                )
                
                if response.status_code in [200, 201, 202]:
                    logger.info("✅ Reply sent successfully to Bot Framework")
                else:
                    logger.error(f"❌ Failed to send reply: {response.status_code}")
                    logger.error(f"Response: {response.text}")
                    
        except Exception as e:
            logger.error(f"❌ Error sending reply: {str(e)}")
    
    async def _get_auth_token(self) -> str:
        """
        Obtém token de autenticação do Bot Framework
        """
        if not self.app_id or not self.app_password:
            logger.warning("No app_id or app_password configured")
            return ""
        
        try:
            # Usa o tenant específico configurado
            tenant = self.tenant_id if hasattr(self, 'tenant_id') else '9ad45470-e5c8-45d9-a335-b5f311990261'
            logger.info(f"Attempting auth with tenant: {tenant}, app_id: {self.app_id[:8]}...")
            
            # URL de autenticação com tenant específico
            auth_url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
            
            # Formato correto para Bot Framework single-tenant
            data = {
                "grant_type": "client_credentials",
                "client_id": self.app_id.strip(),
                "client_secret": self.app_password.strip(),
                "scope": "https://api.botframework.com/.default"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    auth_url,
                    data=data,  # Use data, not json
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                
                if response.status_code == 200:
                    token_data = response.json()
                    logger.info("Successfully obtained auth token")
                    return token_data.get("access_token", "")
                else:
                    logger.error(f"Failed to get auth token: {response.status_code}")
                    logger.error(f"Response: {response.text}")
                    return ""
                    
        except Exception as e:
            logger.error(f"Error getting auth token: {str(e)}")
            return ""
    
    async def test_connection(self) -> bool:
        """
        Testa a conexão com o Bot Framework
        """
        try:
            token = await self._get_auth_token()
            if token:
                logger.info("✅ Bot Framework authentication successful")
                return True
            else:
                logger.error("❌ Bot Framework authentication failed")
                return False
        except Exception as e:
            logger.error(f"❌ Bot Framework test failed: {str(e)}")
            return False