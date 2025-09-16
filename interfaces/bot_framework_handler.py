"""
Bot Framework Handler para integração com Azure Bot Service e Teams
"""
import json
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
        
        # Configurações do Bot Framework
        self.app_id = settings.teams.app_id if hasattr(settings, 'teams') else None
        self.app_password = settings.teams.app_password if hasattr(settings, 'teams') else None
        
        logger.info(f"BotFrameworkHandler initialized. App ID configured: {bool(self.app_id)}")
    
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
            
            # Envia resposta de volta ao Bot Framework
            if service_url and activity.get('id'):
                await self._send_reply(activity, response['response'])
            
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
            return ""
        
        try:
            # Endpoint de autenticação da Microsoft
            auth_url = "https://login.microsoftonline.com/botframework.com/oauth2/v2.0/token"
            
            data = {
                "grant_type": "client_credentials",
                "client_id": self.app_id,
                "client_secret": self.app_password,
                "scope": "https://api.botframework.com/.default"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    auth_url,
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                
                if response.status_code == 200:
                    token_data = response.json()
                    return token_data.get("access_token", "")
                else:
                    logger.error(f"Failed to get auth token: {response.status_code}")
                    return ""
                    
        except Exception as e:
            logger.error(f"Error getting auth token: {str(e)}")
            return ""