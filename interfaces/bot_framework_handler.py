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
        import os
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
                logger.error(f"Error processing Bot Framework message: {str(e)}")
                logger.exception("Full traceback:")
                # Bot Framework espera 200 mesmo em erro para evitar retry
                return Response(status_code=200)
    
    async def _process_activity(self, activity: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa uma activity do Bot Framework
        """
        activity_type = activity.get('type', '')
        
        # Trata diferentes tipos de activity
        if activity_type == 'message':
            return await self._handle_message_activity(activity)
        elif activity_type == 'conversationUpdate':
            return await self._handle_conversation_update(activity)
        elif activity_type == 'invoke':
            return await self._handle_invoke_activity(activity)
        else:
            logger.info(f"Unhandled activity type: {activity_type}")
            return None
    
    async def _handle_message_activity(self, activity: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa mensagens de texto
        """
        try:
            # Extrai informações da activity
            text = activity.get('text', '')
            user_id = activity.get('from', {}).get('id', 'unknown')
            user_name = activity.get('from', {}).get('name', 'User')
            conversation_id = activity.get('conversation', {}).get('id', 'unknown')
            service_url = activity.get('serviceUrl', '')
            
            logger.info(f"Processing message from {user_name} ({user_id}): {text}")
            
            # Processa com o Brain
            response = await self.brain.think(
                user_id=user_id,
                message=text,
                channel='teams'
            )
            
            logger.info(f"Bot brain response: {response.get('response', 'No response')[:100]}")
            
            # Envia resposta de volta ao Bot Framework
            if service_url and activity.get('id'):
                logger.info(f"Sending reply to service_url: {service_url}")
                await self._send_reply(activity, response['response'])
            else:
                logger.warning(f"Cannot send reply - missing service_url or activity.id")
            
            # Retorna vazio - já enviamos a resposta diretamente
            return None
            
        except Exception as e:
            logger.error(f"Error handling message activity: {str(e)}")
            # Envia mensagem de erro
            if activity.get('serviceUrl') and activity.get('id'):
                await self._send_reply(
                    activity, 
                    "Desculpe, ocorreu um erro ao processar sua mensagem. Por favor, tente novamente."
                )
            return None
    
    async def _handle_conversation_update(self, activity: Dict[str, Any]) -> Dict[str, Any]:
        """
        Trata quando o bot é adicionado/removido de uma conversa
        """
        members_added = activity.get('membersAdded', [])
        
        for member in members_added:
            # Se o bot foi adicionado
            if member.get('id') == activity.get('recipient', {}).get('id'):
                # Envia mensagem de boas-vindas
                welcome_message = (
                    f"Olá! Sou {self.settings.bot.name}, "
                    f"seu assistente de {self.settings.bot.type}. "
                    "Como posso ajudar você hoje?"
                )
                await self._send_reply(activity, welcome_message)
        
        return None
    
    async def _handle_invoke_activity(self, activity: Dict[str, Any]) -> Dict[str, Any]:
        """
        Trata invocações especiais (ex: cards adaptativos)
        """
        invoke_name = activity.get('name', '')
        logger.info(f"Handling invoke: {invoke_name}")
        
        # Por enquanto, retorna sucesso
        return {
            "status": 200,
            "body": {}
        }
    
    async def _send_reply(self, activity: Dict[str, Any], text: str):
        """
        Envia uma resposta de volta ao Bot Framework
        """
        try:
            service_url = activity.get('serviceUrl', '').rstrip('/')
            conversation_id = activity.get('conversation', {}).get('id')
            
            # Se não tiver serviceUrl real, apenas loga
            if not service_url or service_url == "https://test.com":
                logger.info(f"Test mode - would send reply: {text[:100]}")
                return
            
            activity_id = activity.get('id')
            
            if not all([service_url, conversation_id, activity_id]):
                logger.warning("Missing required fields to send reply")
                return
            
            # URL para enviar a resposta
            reply_url = f"{service_url}/v3/conversations/{conversation_id}/activities/{activity_id}"
            
            # Cria a mensagem de resposta
            reply_activity = {
                "type": "message",
                "text": text,
                "from": activity.get('recipient'),
                "recipient": activity.get('from'),
                "conversation": activity.get('conversation'),
                "replyToId": activity_id
            }
            
            # Obtém token de autenticação se configurado
            headers = {
                "Content-Type": "application/json"
            }
            
            if self.app_id and self.app_password:
                token = await self._get_auth_token()
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                else:
                    logger.warning("Failed to get auth token, sending without authentication")
            
            # Envia a resposta
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    reply_url,
                    json=reply_activity,
                    headers=headers,
                    timeout=10.0
                )
                
                if response.status_code not in [200, 201, 202]:
                    logger.error(f"Failed to send reply: {response.status_code} - {response.text}")
                else:
                    logger.info("Reply sent successfully")
                    
        except Exception as e:
            logger.error(f"Error sending reply: {str(e)}")
    
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