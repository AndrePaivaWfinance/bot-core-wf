# main.py
import os, asyncio
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from config.settings import BotConfig
from core.brain import BotBrain

REQUESTS = Counter("wf_requests_total","Total de requisições",["route"])
LATENCY = Histogram("wf_request_seconds","Latência por rota",["route"])

app = FastAPI(title="WF Bot Core", version="1.0.1")
cfg = BotConfig().config
brain = BotBrain(cfg)

@app.get("/healthz")
async def healthz():
    primary = cfg.get("primary_llm", {})
    fallback = cfg.get("fallback_llm", {})
    cosmos_ok = bool(cfg.get("cosmos",{}).get("endpoint") and cfg.get("cosmos",{}).get("key"))
    blob_ok = bool(cfg.get("blob_storage",{}).get("connection_string"))
    return {
        "status":"ok",
        "bot": cfg.get("bot",{}).get("name","Mesh"),
        "provider_primary": primary.get("type","none") if primary.get("api_key") else f"{primary.get('type','none')}|mock",
        "provider_fallback": fallback.get("type","none") if fallback.get("api_key") else (f"{fallback.get('type','none')}|mock" if fallback else "none"),
        "cosmos_connected": cosmos_ok,
        "blob_connected": blob_ok,
        "version": app.version
    }

@app.get("/metrics")
async def metrics():
    data = generate_latest()
    return PlainTextResponse(data.decode("utf-8"), media_type=CONTENT_TYPE_LATEST)

@app.post("/v1/messages")
async def post_message(payload: dict):
    REQUESTS.labels("/v1/messages").inc()
    message = payload.get("message","")
    user_id = payload.get("user_id","anonymous")
    context = {"conversation_history": payload.get("history",[])}
    with LATENCY.labels("/v1/messages").time():
        result = await brain.think(message, context)
    return result
