"""
Azure OpenAI Provider Implementation - VERSÃO CORRIGIDA
Com fallback robusto para variáveis de ambiente
"""
import os
from typing import Dict, Any, List, Optional
from openai import AsyncAzureOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
from dotenv import load_dotenv

from core.llm.base_provider import LLMProvider
from utils.logger import get_logger

# Garantir que .env seja carregado
load_dotenv()

logger = get_logger(__name__)

class AzureOpenAIProvider(LLMProvider):
    """Azure OpenAI implementation of LLM Provider"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client = None
        self._initialize_client()
    
    def _get_config_value(self, key: str, env_vars: List[str], default: Optional[str] = None) -> Optional[str]:
        """
        Helper para pegar valor da config com fallback para variáveis de ambiente
        
        Args:
            key: Chave no config dict
            env_vars: Lista de variáveis de ambiente para tentar
            default: Valor padrão se nada for encontrado
        """
        # 1. Tentar do config dict
        value = self.config.get(key)
        if value and value != f"${{{env_vars[0]}}}":  # Não é placeholder
            return value
        
        # 2. Tentar variáveis de ambiente em ordem
        for env_var in env_vars:
            value = os.getenv(env_var)
            if value:
                logger.debug(f"   {key} obtido de {env_var}")
                return value
        
        # 3. Retornar default
        return default
    
    def _initialize_client(self):
        """Initialize Azure OpenAI client com fallback robusto"""
        logger.info("🔷 Initializing Azure OpenAI Provider...")
        
        # Obter configurações com fallback para múltiplas variáveis de ambiente
        api_key = self._get_config_value(
            "api_key",
            ["AZURE_OPENAI_KEY", "AZURE_OPENAI_API_KEY", "OPENAI_API_KEY"]
        )
        
        endpoint = self._get_config_value(
            "endpoint",
            ["AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_BASE"]
        )
        
        deployment_name = self._get_config_value(
            "deployment_name",
            ["AZURE_OPENAI_DEPLOYMENT", "AZURE_OPENAI_DEPLOYMENT_NAME", "AZURE_OPENAI_MODEL"]
        )
        
        api_version = self._get_config_value(
            "api_version",
            ["AZURE_OPENAI_API_VERSION"],
            "2024-02-01"  # Default para versão estável
        )
        
        # Log das configurações (sem expor a chave completa)
        logger.debug(f"   Endpoint: {endpoint[:40] if endpoint else 'NOT SET'}...")
        logger.debug(f"   Deployment: {deployment_name or 'NOT SET'}")
        logger.debug(f"   API Version: {api_version}")
        logger.debug(f"   API Key: {'✅ Configured' if api_key else '❌ Missing'} ({len(api_key) if api_key else 0} chars)")
        
        # Validar configurações obrigatórias
        missing = []
        if not api_key:
            missing.append("API Key (AZURE_OPENAI_KEY or AZURE_OPENAI_API_KEY)")
        if not endpoint:
            missing.append("Endpoint (AZURE_OPENAI_ENDPOINT)")
        if not deployment_name:
            missing.append("Deployment (AZURE_OPENAI_DEPLOYMENT)")
        
        if missing:
            error_msg = f"Azure OpenAI missing required configurations: {', '.join(missing)}"
            logger.error(f"❌ {error_msg}")
            logger.error("   Please check your .env file has these variables set")
            raise ValueError(error_msg)
        
        # Limpar endpoint
        endpoint = endpoint.rstrip('/')
        
        # Verificar se API version é reconhecida (incluindo 2025-01-01-preview)
        known_versions = [
            "2024-02-01", "2024-06-01", "2024-08-01-preview", 
            "2024-12-01-preview", "2025-01-01-preview"
        ]
        if api_version not in known_versions:
            logger.warning(f"   ⚠️ API version '{api_version}' may not be recognized")
        
        try:
            # Inicializar cliente - passando api_key explicitamente
            self.client = AsyncAzureOpenAI(
                api_key=api_key,  # Explicitamente passar a key
                api_version=api_version,
                azure_endpoint=endpoint,
                azure_deployment=deployment_name,
                # Desabilitar variáveis de ambiente padrão para evitar conflitos
                azure_ad_token=None,
                azure_ad_token_provider=None
            )
            
            # Guardar configurações para uso posterior
            self.deployment_name = deployment_name
            self.api_version = api_version
            self.endpoint = endpoint
            
            logger.info(f"✅ AzureOpenAIProvider initialized successfully")
            logger.info(f"   Ready to use deployment: {self.deployment_name}")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Azure OpenAI client: {str(e)}")
            if "api_key" in str(e).lower():
                logger.error("   Tip: Check if AZURE_OPENAI_KEY is set in .env")
            raise
    
    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def generate(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate response using Azure OpenAI"""
        try:
            logger.info(f"🔷 Azure OpenAI: Generating response...")
            logger.debug(f"   Using deployment: {self.deployment_name}")
            logger.debug(f"   Prompt length: {len(prompt)} chars")
            
            # Criar mensagens
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ]
            
            # Adicionar contexto se disponível
            if context.get("conversation_history"):
                logger.debug(f"   Including {len(context['conversation_history'])} history items")
            
            # Fazer chamada para API
            response = await self.client.chat.completions.create(
                model=self.deployment_name,
                messages=messages,
                temperature=self.config.get("temperature", 0.7),
                max_tokens=self.config.get("max_tokens", 2000),
                top_p=0.95,
                frequency_penalty=0,
                presence_penalty=0
            )
            
            # Processar resposta
            response_text = response.choices[0].message.content
            logger.info(f"✅ Azure OpenAI: Response received ({len(response_text)} chars)")
            
            # Preparar retorno
            result = {
                "text": response_text,
                "usage": {},
                "provider": "azure_openai",
                "model": self.deployment_name,
                "api_version": self.api_version
            }
            
            # Adicionar usage se disponível
            if response.usage:
                result["usage"] = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
                logger.debug(f"   Tokens used: {response.usage.total_tokens}")
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Azure OpenAI error: {error_msg[:200]}")
            
            # Diagnóstico detalhado de erros
            if "401" in error_msg or "unauthorized" in error_msg.lower():
                logger.error("🔐 Authentication failed")
                logger.error("   1. Check if AZURE_OPENAI_KEY is correct")
                logger.error("   2. Verify key in Azure Portal -> Keys and Endpoint")
                logger.error("   3. Ensure key hasn't been regenerated")
            elif "404" in error_msg or "not found" in error_msg.lower():
                logger.error(f"🔍 Resource not found")
                logger.error(f"   1. Deployment '{self.deployment_name}' may not exist")
                logger.error(f"   2. Endpoint may be wrong: {self.endpoint}")
                logger.error(f"   3. Check in Azure Portal -> Deployments")
            elif "429" in error_msg:
                logger.error("⚠️ Rate limit exceeded")
                logger.error("   Wait a moment and retry")
            elif "missing credentials" in error_msg.lower():
                logger.error("🔑 Credentials not being passed correctly")
                logger.error("   This shouldn't happen with the fix applied")
                logger.error("   Check if .env is loaded properly")
            else:
                logger.error(f"   Unknown error type - check Azure Portal for service status")
            
            raise
    
    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding using Azure OpenAI"""
        try:
            # Usar modelo de embedding configurado ou padrão
            embedding_model = self.config.get("embedding_deployment", "text-embedding-3-large")
            
            response = await self.client.embeddings.create(
                model=embedding_model,
                input=text
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            logger.error(f"Azure OpenAI embedding error: {str(e)}")
            raise
    
    def is_available(self) -> bool:
        """Check if Azure OpenAI is available"""
        return self.client is not None