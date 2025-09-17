"""
Azure OpenAI Provider Implementation
"""
from typing import Dict, Any, List
from openai import AsyncAzureOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from core.llm.base_provider import LLMProvider
from utils.logger import get_logger

logger = get_logger(__name__)

class AzureOpenAIProvider(LLMProvider):
    """Azure OpenAI implementation of LLM Provider"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Azure OpenAI client"""
        # Validate required fields
        required_fields = ["api_key", "endpoint", "deployment_name"]
        missing = [f for f in required_fields if not self.config.get(f)]
        
        if missing:
            raise ValueError(f"Azure OpenAI requires: {', '.join(missing)}")
        
        # Check API key length
        api_key = self.config["api_key"]
        if len(api_key) < 10:
            logger.warning(f"⚠️ API key seems too short: {len(api_key)} chars")
        
        # Initialize client
        self.client = AsyncAzureOpenAI(
            api_key=api_key,
            api_version=self.config.get("api_version", "2024-02-01"),
            azure_endpoint=self.config['endpoint'].rstrip('/'),
            azure_deployment=self.config['deployment_name']
        )
        
        logger.info(f"✅ AzureOpenAIProvider initialized")
        logger.debug(f"   Endpoint: {self.config['endpoint']}")
        logger.debug(f"   Deployment: {self.config['deployment_name']}")
    
    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def generate(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate response using Azure OpenAI"""
        try:
            logger.info(f"🔷 Azure OpenAI: Generating response...")
            
            response = await self.client.chat.completions.create(
                model=self.config["deployment_name"],
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt},
                ],
                temperature=self.config.get("temperature", 0.7),
                max_tokens=self.config.get("max_tokens", 2000)
            )
            
            logger.info(f"✅ Azure OpenAI: Response received")
            
            return {
                "text": response.choices[0].message.content,
                "usage": response.usage.model_dump() if response.usage else {},
                "provider": "azure_openai",
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Azure OpenAI error: {error_msg}")
            
            # Specific error handling
            if "401" in error_msg or "authentication" in error_msg.lower():
                logger.error(f"🔐 Authentication failed - check API key")
            elif "404" in error_msg:
                logger.error(f"🔍 Deployment not found: {self.config['deployment_name']}")
            elif "429" in error_msg:
                logger.error(f"⚠️ Rate limit exceeded")
            
            raise
    
    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding using Azure OpenAI"""
        try:
            model = self.config.get("embedding_deployment", "text-embedding-3-large")
            
            response = await self.client.embeddings.create(
                model=model,
                input=text
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            logger.error(f"Azure OpenAI embedding error: {str(e)}")
            raise
    
    def is_available(self) -> bool:
        """Check if Azure OpenAI is available"""
        return self.client is not None