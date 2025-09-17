"""
Anthropic Claude Provider Implementation
Com suporte completo a variáveis de ambiente configuráveis
"""
import os
import asyncio
from typing import Dict, Any, List, Optional
import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential
from dotenv import load_dotenv

from core.llm.base_provider import LLMProvider
from utils.logger import get_logger

# Garantir que .env seja carregado
load_dotenv()

logger = get_logger(__name__)

class ClaudeProvider(LLMProvider):
    """Anthropic Claude implementation of LLM Provider"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client = None
        self.model = None
        self.api_version = None
        self._initialize_client()
    
    def _get_config_value(self, key: str, env_vars: List[str], default: Optional[str] = None) -> Optional[str]:
        """
        Helper para pegar valor da config com fallback para variáveis de ambiente
        Similar ao Azure provider para consistência
        """
        # 1. Tentar do config dict
        value = self.config.get(key)
        if value and not str(value).startswith("${"):
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
        """Initialize Claude client com configuração completa"""
        logger.info("🟣 Initializing Claude Provider...")
        
        # Obter configurações com fallback para variáveis de ambiente
        api_key = self._get_config_value(
            "api_key",
            ["ANTHROPIC_API_KEY", "CLAUDE_API_KEY"]
        )
        
        # API Version (similar ao Azure)
        self.api_version = self._get_config_value(
            "api_version",
            ["CLAUDE_API_VERSION"],
            "2023-06-01"  # Default
        )
        
        # Model (configurável via ambiente)
        self.model = self._get_config_value(
            "model",
            ["CLAUDE_MODEL"],
            "claude-3-5-sonnet-20241022"  # Default para o modelo mais recente
        )
        
        # Log configuração
        logger.debug(f"   Model: {self.model}")
        logger.debug(f"   API Version: {self.api_version}")
        logger.debug(f"   API Key: {'✅ Configured' if api_key else '❌ Missing'}")
        
        if api_key:
            # Detectar de onde veio a key
            if os.getenv("ANTHROPIC_API_KEY") == api_key:
                logger.debug(f"   Key source: ANTHROPIC_API_KEY")
            elif os.getenv("CLAUDE_API_KEY") == api_key:
                logger.debug(f"   Key source: CLAUDE_API_KEY")
            else:
                logger.debug(f"   Key source: config dict")
            
            # Validar formato da key
            if not api_key.startswith('sk-ant-'):
                logger.warning(f"   ⚠️ API key doesn't start with 'sk-ant-' - might be invalid")
                logger.warning(f"   Key starts with: {api_key[:10]}...")
        
        # Validar API key
        if not api_key:
            error_msg = (
                "Claude requires API key. Please set ANTHROPIC_API_KEY in .env"
            )
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)
        
        # Validar modelo conhecido
        known_models = [
            "claude-3-5-sonnet-20241022",  # Mais recente
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229", 
            "claude-3-haiku-20240307",
            # Adicionar modelos customizados/futuros se necessário
            "claude-opus-4-1-20250805"  # Seu modelo específico
        ]
        
        if self.model not in known_models:
            logger.warning(f"   ⚠️ Model '{self.model}' not in known list, may fail")
            logger.info(f"   Known models: {', '.join(known_models[:4])}")
        
        try:
            # Inicializar cliente com a API key
            self.client = anthropic.Anthropic(
                api_key=api_key,
                # Nota: Anthropic SDK atualmente não usa api_version no construtor
                # mas guardamos para referência/logging
            )
            
            logger.info(f"✅ ClaudeProvider initialized successfully")
            logger.info(f"   Ready to use model: {self.model}")
            logger.info(f"   API Version: {self.api_version}")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Claude client: {str(e)}")
            raise
    
    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def generate(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate response using Claude"""
        try:
            logger.info(f"🟣 Claude: Generating response...")
            logger.debug(f"   Model: {self.model}")
            logger.debug(f"   Prompt length: {len(prompt)} chars")
            
            # Claude SDK não tem async ainda, usar run_in_executor
            loop = asyncio.get_event_loop()
            
            def create_message():
                try:
                    # Tentar com o modelo configurado
                    return self.client.messages.create(
                        model=self.model,
                        max_tokens=self.config.get("max_tokens", 2000),
                        temperature=self.config.get("temperature", 0.7),
                        messages=[
                            {"role": "user", "content": prompt}
                        ]
                    )
                except anthropic.NotFoundError as e:
                    # Se o modelo não for encontrado, tentar com um modelo padrão
                    logger.warning(f"Model {self.model} not found, trying claude-3-opus-20240229")
                    return self.client.messages.create(
                        model="claude-3-opus-20240229",
                        max_tokens=self.config.get("max_tokens", 2000),
                        temperature=self.config.get("temperature", 0.7),
                        messages=[
                            {"role": "user", "content": prompt}
                        ]
                    )
            
            # Execute em thread pool
            logger.debug("   Calling Claude API...")
            message = await loop.run_in_executor(None, create_message)
            
            # Extrair texto da resposta
            response_text = ""
            if hasattr(message, 'content'):
                if isinstance(message.content, list) and len(message.content) > 0:
                    content_block = message.content[0]
                    if hasattr(content_block, 'text'):
                        response_text = content_block.text
                    else:
                        response_text = str(content_block)
                elif isinstance(message.content, str):
                    response_text = message.content
                else:
                    response_text = str(message.content)
            
            if not response_text:
                logger.warning("   ⚠️ Empty response from Claude")
                response_text = "I apologize, but I couldn't generate a response."
            
            logger.info(f"✅ Claude: Response received ({len(response_text)} chars)")
            
            # Extrair usage se disponível
            usage = {}
            if hasattr(message, 'usage'):
                usage = {
                    "input_tokens": getattr(message.usage, 'input_tokens', 0),
                    "output_tokens": getattr(message.usage, 'output_tokens', 0),
                    "total_tokens": (
                        getattr(message.usage, 'input_tokens', 0) + 
                        getattr(message.usage, 'output_tokens', 0)
                    )
                }
                logger.debug(f"   Tokens used: {usage.get('total_tokens', 0)}")
            
            # Incluir modelo usado na resposta
            return {
                "text": response_text,
                "usage": usage,
                "provider": "claude",
                "model": self.model,
                "api_version": self.api_version
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Claude error: {error_msg[:200]}")
            
            # Diagnóstico específico de erros
            if "401" in error_msg or "authentication" in error_msg.lower():
                logger.error("🔐 API key issue - Authentication failed")
                logger.error("   1. Check if ANTHROPIC_API_KEY is correct")
                logger.error("   2. Verify key at console.anthropic.com")
                logger.error("   3. Ensure key starts with 'sk-ant-api03-'")
                logger.error(f"   4. Current key starts with: {os.getenv('ANTHROPIC_API_KEY', 'NOT SET')[:15]}...")
            elif "model_not_found" in error_msg.lower() or "404" in error_msg:
                logger.error(f"🔍 Model not found: {self.model}")
                logger.error("   Valid models: claude-3-5-sonnet-20241022, claude-3-opus-20240229")
            elif "rate" in error_msg.lower():
                logger.error("⚠️ Rate limit issue")
                logger.error("   Wait a moment and retry")
            elif "invalid_request" in error_msg.lower():
                logger.error("📝 Invalid request format")
                logger.error("   Check prompt format and length")
            else:
                logger.error("   Unknown error - check Anthropic status page")
            
            raise
    
    async def get_embedding(self, text: str) -> List[float]:
        """Claude doesn't support embeddings"""
        logger.warning("⚠️ Claude doesn't provide embedding API")
        logger.warning("   Use Azure OpenAI for embeddings")
        raise NotImplementedError("Claude doesn't provide embedding API")
    
    def is_available(self) -> bool:
        """Check if Claude is available"""
        return self.client is not None