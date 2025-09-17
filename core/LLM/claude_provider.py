"""
Anthropic Claude Provider Implementation
"""
import os
import asyncio
from typing import Dict, Any, List
import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from core.llm.base_provider import LLMProvider
from utils.logger import get_logger

logger = get_logger(__name__)

class ClaudeProvider(LLMProvider):
    """Anthropic Claude implementation of LLM Provider"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client = None
        self.model = config.get('model', 'claude-opus-4-1-20250805')
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Claude client"""
        # Try multiple sources for API key
        api_key = (
            self.config.get("api_key") or 
            os.getenv("ANTHROPIC_API_KEY") or 
            os.getenv("CLAUDE_API_KEY")
        )
        
        if not api_key:
            raise ValueError("Claude requires api_key or ANTHROPIC_API_KEY env var")
        
        # Initialize client
        self.client = anthropic.Anthropic(api_key=api_key)
        
        logger.info(f"✅ ClaudeProvider initialized")
        logger.debug(f"   Model: {self.model}")
    
    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def generate(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate response using Claude"""
        try:
            logger.info(f"🟣 Claude: Generating response...")
            
            # Claude SDK doesn't have async yet, use run_in_executor
            loop = asyncio.get_event_loop()
            
            def create_message():
                return self.client.messages.create(
                    model=self.model,
                    max_tokens=self.config.get("max_tokens", 2000),
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
            
            # Execute in thread pool
            message = await loop.run_in_executor(None, create_message)
            
            logger.info(f"✅ Claude: Response received")
            
            # Extract text from response
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
            
            # Extract usage if available
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
            
            return {
                "text": response_text,
                "usage": usage,
                "provider": "claude"
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Claude error: {error_msg}")
            
            # Specific error handling
            if "api_key" in error_msg.lower():
                logger.error("🔐 API key issue - check ANTHROPIC_API_KEY")
            elif "model_not_found" in error_msg.lower():
                logger.error(f"🔍 Model not found: {self.model}")
            elif "rate" in error_msg.lower():
                logger.error("⚠️ Rate limit issue")
            
            raise
    
    async def get_embedding(self, text: str) -> List[float]:
        """Claude doesn't support embeddings"""
        raise NotImplementedError("Claude doesn't provide embedding API")
    
    def is_available(self) -> bool:
        """Check if Claude is available"""
        return self.client is not None