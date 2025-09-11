# skills/api_caller.py
from typing import Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_fixed
import httpx

class APICallerSkill:
    name = "api_caller"
    description = "Chama APIs HTTP externas."

    async def can_handle(self, intent: str, context: Dict) -> bool:
        intent = (intent or "").lower()
        return any(x in intent for x in ["fetch_data","call_api","get_information","consultar"])

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(0.5))
    async def execute(self, parameters: Dict, context: Dict) -> Dict:
        url = parameters.get("url")
        method = (parameters.get("method") or "GET").upper()
        headers = parameters.get("headers") or {}
        data = parameters.get("data")
        params = parameters.get("params")

        timeout = httpx.Timeout(15.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request(method, url, headers=headers, json=data, params=params)
            ok = 200 <= resp.status_code < 300
            content = None
            try:
                content = resp.json()
            except Exception:
                content = resp.text
            return {"success": ok, "status_code": resp.status_code, "data": content, "skill": self.name}
