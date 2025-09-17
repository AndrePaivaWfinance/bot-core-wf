#!/bin/bash

echo "🔧 Configurando variáveis no Azure App Service..."

# Ler do .env local
source .env

# Configurar todas as variáveis importantes
az webapp config appsettings set \
  -g rg-wf-ia-gpt41 \
  -n meshbrain \
  --settings \
    AZURE_OPENAI_ENDPOINT="$AZURE_OPENAI_ENDPOINT" \
    AZURE_OPENAI_KEY="$AZURE_OPENAI_KEY" \
    AZURE_OPENAI_DEPLOYMENT="$AZURE_OPENAI_DEPLOYMENT" \
    AZURE_OPENAI_MODEL="$AZURE_OPENAI_MODEL" \
    AZURE_OPENAI_API_VERSION="$AZURE_OPENAI_API_VERSION" \
    CLAUDE_API_KEY="$CLAUDE_API_KEY" \
    BOT_ID="$BOT_ID" \
    BOT_NAME="$BOT_NAME" \
    LOG_LEVEL="INFO"

echo "✅ Configurações aplicadas!"
echo "⏳ Aguardando restart (40 segundos)..."
sleep 40

echo "🧪 Testando health..."
curl https://meshbrain.azurewebsites.net/healthz | python3 -m json.tool
