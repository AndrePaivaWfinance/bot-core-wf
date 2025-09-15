import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from typing import Dict, Any

from skills.base_skill import BaseSkill
from utils.logger import get_logger

logger = get_logger(__name__)

class APICallerSkill(BaseSkill):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.timeout = self._get_config_value("timeout", 30)
        self.retry_count = self._get_config_value("retry_count", 3)
    
    async def can_handle(self, intent: str, context: Dict[str, Any]) -> bool:
        return intent.lower() in ["api_call", "http_request", "call_api"]
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def execute(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        try:
            url = parameters.get("url")
            method = parameters.get("method", "GET").upper()
            headers = parameters.get("headers", {})
            body = parameters.get("body", {})
            
            if not url:
                return {"error": "URL parameter is required"}
            
            async with httpx.AsyncClient() as client:
                if method == "GET":
                    response = await client.get(
                        url,
                        headers=headers,
                        timeout=self.timeout
                    )
                elif method == "POST":
                    response = await client.post(
                        url,
                        headers=headers,
                        json=body,
                        timeout=self.timeout
                    )
                elif method == "PUT":
                    response = await client.put(
                        url,
                        headers=headers,
                        json=body,
                        timeout=self.timeout
                    )
                elif method == "DELETE":
                    response = await client.delete(
                        url,
                        headers=headers,
                        timeout=self.timeout
                    )
                else:
                    return {"error": f"Unsupported HTTP method: {method}"}
                
                response.raise_for_status()
                
                return {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": response.json() if response.content else {}
                }
                
        except httpx.RequestError as e:
            logger.error(f"HTTP request error: {str(e)}")
            return {"error": f"Request failed: {str(e)}"}
        except Exception as e:
            logger.error(f"API call error: {str(e)}")
            return {"error": str(e)}
