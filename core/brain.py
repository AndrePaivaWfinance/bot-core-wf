# core/brain.py
from typing import Dict, List, Optional
from abc import ABC, abstractmethod
from datetime import datetime
import asyncio
import os
import httpx

class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, context: Dict) -> str: ...
    async def get_embedding(self, text: str) -> List[float]:
        # mock simples, pode ser substituído por Azure Embeddings
        import hashlib, random
        h = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)
        rnd = random.Random(h)
        return [rnd.random() for _ in range(256)]

class AzureOpenAIProvider(LLMProvider):
    def __init__(self, config: Dict):
        self.endpoint = config.get("endpoint") or ""
        self.api_key = config.get("api_key") or ""
        self.deployment = config.get("deployment_name") or "gpt-4o"
        self.temperature = config.get("temperature", 0.7)
        self._mock = not (self.endpoint and self.api_key)

    async def generate(self, prompt: str, context: Dict) -> str:
        if self._mock:
            return f"[mock-azure] {prompt[:240]}"
        # Exemplo (ajuste ao seu endpoint real de Chat Completions):
        url = f"{self.endpoint}/openai/deployments/{self.deployment}/chat/completions?api-version=2024-02-15-preview"
        headers = {"api-key": self.api_key}
        payload = {
            "messages": [{"role": "system", "content": "You are a helpful assistant."},
                         {"role": "user", "content": prompt}],
            "temperature": self.temperature
        }
        timeout = httpx.Timeout(15.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
            # ajuste conforme o formato retornado pelo seu endpoint
            text = data["choices"][0]["message"]["content"]
            return text

class ClaudeProvider(LLMProvider):
    def __init__(self, config: Dict):
        self.api_key = config.get("api_key") or ""
        self.model = config.get("model", "claude-3-opus")
        self._mock = not self.api_key

    async def generate(self, prompt: str, context: Dict) -> str:
        if self._mock:
            return f"[mock-claude] {prompt[:240]}"
        # Chamada real omitida; implementar com o SDK/endpoint da Anthropic
        return f"[claude-not-implemented] {prompt[:240]}"

class BotBrain:
    def __init__(self, bot_config: Dict):
        self.config = bot_config
        # Suporta as duas formas: achatado e dentro de llm
        primary_cfg = self.config.get("primary_llm") or self.config.get("llm", {}).get("primary_llm", {})
        fallback_cfg = self.config.get("fallback_llm") or self.config.get("llm", {}).get("fallback_llm", {})
        self.primary_llm = AzureOpenAIProvider(primary_cfg) if primary_cfg.get("type") == "azure_openai" else None
        self.fallback_llm = ClaudeProvider(fallback_cfg) if fallback_cfg.get("type") == "claude" else None
        self.personality = self.config.get("bot", {})

    async def think(self, message: str, context: Dict) -> Dict:
        enhanced_prompt = self._build_prompt(message, context)
        try:
            resp = await self.primary_llm.generate(enhanced_prompt, context) if self.primary_llm else "[no-primary-llm]"
            return {
                "response": resp,
                "provider": "primary",
                "timestamp": datetime.utcnow().isoformat(),
                "confidence": self._confidence(resp)
            }
        except Exception as e:
            if self.fallback_llm:
                resp = await self.fallback_llm.generate(enhanced_prompt, context)
                return {
                    "response": resp,
                    "provider": "fallback",
                    "timestamp": datetime.utcnow().isoformat(),
                    "error": str(e)
                }
            raise

    def _build_prompt(self, message: str, context: Dict) -> str:
        parts = []
        bot = self.personality
        if bot:
            parts.append(f"You are {bot.get('name','Mesh')}.")
            parts.append(f"Role: {self.config.get('bot',{}).get('type','assistant')}")
        if context.get("conversation_history"):
            parts.append("\nRecent conversation:")
            for msg in context["conversation_history"][-5:]:
                parts.append(f"{msg['role']}: {msg['content']}")
        if context.get("relevant_memories"):
            parts.append("\nRelevant information from memory:")
            parts.extend([f"- {m}" for m in context["relevant_memories"]])
        if context.get("relevant_documents"):
            parts.append("\nRelevant documents:")
            parts.extend([f"- {d.get('title','doc')}: {d.get('snippet','...')}" for d in context["relevant_documents"]])
        parts.append(f"\nUser message: {message}\nYour response:")
        return "\n".join(parts)

    def _confidence(self, resp: str) -> float:
        if not resp: return 0.0
        bad = any(x in resp.lower() for x in ["não sei", "i don't know", "unknown"])
        return max(0.1, min(0.95, 0.5 if bad else 0.8))
