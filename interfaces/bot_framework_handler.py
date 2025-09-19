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
                logger.error(f"Error processing Bot Framework message: {str(e)}", exc_info=True)
                return Response(status_code=500, content=str(e))
        
        @self.router.get("/api/health")
        async def health_check():
            """Health check endpoint para o Bot Framework"""
            return JSONResponse({
                "status": "healthy",
                "service": "Bot Framework Handler",
                "app_id_configured": bool(self.app_id),
                "tenant_id": self.tenant_id
            })
        
        @self.router.post("/api/messages/test")
        async def test_endpoint(request: Request):
            """Endpoint de teste para verificar integração"""
            if os.getenv("BOT_ENV", "production").lower() == "production":
                raise HTTPException(status_code=403, detail="Test endpoint disabled in production")
            
            test_activity = {
                "type": "message",
                "text": "Teste de mensagem",
                "from": {"id": "test_user"},
                "recipient": {"id": "bot"},
                "conversation": {"id": "test_conversation"},
                "channelId": "test",
                "id": "test_message_id",
                "serviceUrl": "http://localhost"
            }
            
            response = await self._process_activity(test_activity)
            return JSONResponse(response if response else {"status": "ok"})
    
    async def _process_activity(self, activity: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa uma activity do Bot Framework
        """
        activity_type = activity.get('type', '')
        
        # Trata diferentes tipos de activity
        if activity_type == 'message':
            return await self._handle_message(activity)
        elif activity_type == 'conversationUpdate':
            return await self._handle_conversation_update(activity)
        elif activity_type == 'invoke':
            return await self._handle_invoke(activity)
        else:
            logger.info(f"Received activity type '{activity_type}' - no action needed")
            return None
    
    async def _handle_message(self, activity: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa mensagens de texto
        """
        try:
            # Extrai informações da mensagem
            text = activity.get('text', '')
            user_id = activity.get('from', {}).get('id', 'unknown')
            user_name = activity.get('from', {}).get('name', 'User')
            conversation_id = activity.get('conversation', {}).get('id', 'unknown')
            channel_id = activity.get('channelId', 'unknown')
            service_url = activity.get('serviceUrl', '')
            
            logger.info(f"Processing message from {user_name} ({user_id}): {text[:50]}...")
            
            # Processa através do Brain
            response = await self.brain.think(
                user_id=user_id,
                message=text,
                channel=channel_id,
                metadata={
                    'user_name': user_name,
                    'conversation_id': conversation_id,
                    'service_url': service_url,
                    'channel_id': channel_id,
                    'activity_id': activity.get('id'),
                    'locale': activity.get('locale', 'pt-BR')
                }
            )
            
            # Formata resposta para o Bot Framework
            reply_activity = {
                'type': 'message',
                'from': activity.get('recipient'),
                'recipient': activity.get('from'),
                'conversation': activity.get('conversation'),
                'text': response.get('response', 'Desculpe, não consegui processar sua mensagem.'),
                'replyToId': activity.get('id'),
                'locale': activity.get('locale', 'pt-BR')
            }
            
            # Se precisar enviar a resposta proativamente
            if service_url:
                await self._send_proactive_message(service_url, conversation_id, reply_activity)
                return None  # Retorna None quando enviado proativamente
            else:
                return reply_activity
                
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}", exc_info=True)
            return {
                'type': 'message',
                'text': f'Erro ao processar mensagem: {str(e)}'
            }
    
    async def _handle_conversation_update(self, activity: Dict[str, Any]) -> Dict[str, Any]:
        """
        Trata atualizações de conversa (usuários entrando/saindo)
        """
        members_added = activity.get('membersAdded', [])
        members_removed = activity.get('membersRemoved', [])
        
        # Envia mensagem de boas-vindas para novos membros
        for member in members_added:
            if member.get('id') != activity.get('recipient', {}).get('id'):
                logger.info(f"New member joined: {member.get('name', 'Unknown')}")
                return {
                    'type': 'message',
                    'text': f"Olá! Sou o Mesh, seu assistente financeiro de BPO. Como posso ajudá-lo hoje?"
                }
        
        # Log quando membros saem
        for member in members_removed:
            logger.info(f"Member left: {member.get('name', 'Unknown')}")
        
        return None
    
    async def _handle_invoke(self, activity: Dict[str, Any]) -> Dict[str, Any]:
        """
        Trata invocações especiais (cards adaptativos, etc.)
        """
        invoke_name = activity.get('name', '')
        logger.info(f"Received invoke: {invoke_name}")
        
        # Retorna resposta padrão para invokes
        return {
            'status': 200,
            'body': {}
        }
    
    async def _send_proactive_message(self, service_url: str, conversation_id: str, activity: Dict[str, Any]):
        """
        Envia mensagem proativa para o Teams
        """
        try:
            # Obtém token de autenticação se configurado
            headers = {
                'Content-Type': 'application/json'
            }
            
            if self.app_id and self.app_password:
                token = await self._get_auth_token()
                if token:
                    headers['Authorization'] = f'Bearer {token}'
            
            # Constrói URL para enviar mensagem
            url = f"{service_url}v3/conversations/{conversation_id}/activities"
            
            # Envia mensagem
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=activity,
                    headers=headers,
                    timeout=30.0
                )
                
                if response.status_code >= 200 and response.status_code < 300:
                    logger.info(f"Proactive message sent successfully to conversation {conversation_id}")
                else:
                    logger.error(f"Failed to send proactive message: {response.status_code} - {response.text}")
                    
        except Exception as e:
            logger.error(f"Error sending proactive message: {str(e)}", exc_info=True)
    
    async def _get_auth_token(self) -> str:
        """
        Obtém token de autenticação do Azure AD para Bot Framework
        """
        if not self.app_id or not self.app_password:
            return ""
        
        try:
            # URL de autenticação para single-tenant
            auth_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
            
            data = {
                'grant_type': 'client_credentials',
                'client_id': self.app_id,
                'client_secret': self.app_password,
                'scope': 'https://api.botframework.com/.default'
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    auth_url,
                    data=data,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    token_data = response.json()
                    return token_data.get('access_token', '')
                else:
                    logger.error(f"Failed to get auth token: {response.status_code} - {response.text}")
                    return ""
                    
        except Exception as e:
            logger.error(f"Error getting auth token: {str(e)}", exc_info=True)
            return ""