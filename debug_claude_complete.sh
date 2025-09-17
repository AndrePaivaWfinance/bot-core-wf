



 "🔍 DEBUG COMPLETO DO CLAUDE"
echo "============================"

# 1. Testar key localmente
echo -e "\n1️⃣ TESTANDO API KEY LOCALMENTE:"
KEY=$(grep ANTHROPIC_API_KEY .env | cut -d'=' -f2)
echo "Key: ${KEY:0:20}..."

response=$(curl -s -w "\nHTTP_CODE:%{http_code}" https://api.anthropic.com/v1/messages \
  -H "x-api-key: $KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{
    "model": "claude-opus-4-1-20250805",
    "max_tokens": 10,
    "messages": [{"role": "user", "content": "Say OK"}]
  }')

http_code=$(echo "$response" | grep "HTTP_CODE:" | cut -d: -f2)
content=$(echo "$response" | grep -v "HTTP_CODE:")

if [ "$http_code" == "200" ]; then
    echo "✅ API Key funciona!"
    echo "Response: $content" | head -n 3
else
    echo "❌ API Key problem! HTTP: $http_code"
    echo "$content"
fi

# 2. Ver o que está no Azure agora
echo -e "\n2️⃣ CONFIGURAÇÃO ATUAL NO AZURE:"
az webapp config appsettings list \
  -g rg-wf-ia-gpt41 \
  -n meshbrain \
  --query "[?contains(name, 'KEY')].{Name:name, Set:value!=null}" \
  -o table

# 3. Configurar TODAS as variáveis necessárias
echo -e "\n3️⃣ CONFIGURANDO VARIÁVEIS NO AZURE:"
source .env

az webapp config appsettings set \
  -g rg-wf-ia-gpt41 \
  -n meshbrain \
  --settings \
    ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
    AZURE_OPENAI_KEY="$AZURE_OPENAI_KEY" \
    AZURE_OPENAI_ENDPOINT="$AZURE_OPENAI_ENDPOINT" \
    AZURE_OPENAI_DEPLOYMENT="$AZURE_OPENAI_DEPLOYMENT" \
    AZURE_OPENAI_MODEL="$AZURE_OPENAI_MODEL" \
    AZURE_OPENAI_API_VERSION="$AZURE_OPENAI_API_VERSION" \
  --output none

echo "✅ Variáveis configuradas"
echo "⏳ Aguardando restart (50s)..."
sleep 50

# 4. Forçar reinicialização e ver logs
echo -e "\n4️⃣ REINICIANDO E VERIFICANDO LOGS:"
az webapp restart -g rg-wf-ia-gpt41 -n meshbrain

echo "Aguardando inicialização..."
sleep 20

# Fazer request para forçar inicialização
curl -s https://meshbrain.azurewebsites.net/healthz > /dev/null

# Capturar logs de inicialização
echo -e "\n📋 LOGS DE INICIALIZAÇÃO:"
az webapp log tail -g rg-wf-ia-gpt41 -n meshbrain --timeout 15 2>&1 | grep -E "(Brain|provider|Claude|initialized|error)" | tail -20

# 5. Testar com Azure funcionando
echo -e "\n5️⃣ TESTE COM AZURE NORMAL:"
response=$(curl -s -X POST https://meshbrain.azurewebsites.net/v1/messages \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test1", "message": "Hello"}')

provider=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('metadata',{}).get('provider','error'))" 2>/dev/null)
echo "Provider: $provider"

# 6. FORÇAR FALLBACK
echo -e "\n6️⃣ FORÇANDO FALLBACK (quebrando Azure):"
az webapp config appsettings set \
  -g rg-wf-ia-gpt41 \
  -n meshbrain \
  --settings AZURE_OPENAI_KEY="INVALID_KEY_FOR_TEST" \
  --output none

echo "Aguardando restart (50s)..."
sleep 50

# Testar com fallback
response=$(curl -s -X POST https://meshbrain.azurewebsites.net/v1/messages \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test2", "message": "Hello Claude"}')

echo -e "\n📋 RESPOSTA COMPLETA:"
echo "$response" | python3 -m json.tool || echo "$response"

provider=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('metadata',{}).get('provider','error'))" 2>/dev/null)

if [ "$provider" == "claude" ]; then
    echo -e "\n✅ FALLBACK FUNCIONANDO!"
else
    echo -e "\n❌ Fallback falhou. Provider: $provider"
    
    # Ver logs de erro
    echo -e "\n📋 LOGS DE ERRO:"
    az webapp log tail -g rg-wf-ia-gpt41 -n meshbrain --timeout 10 2>&1 | grep -E "(error|Error|ERROR|failed|Failed)" | tail -10
fi

# 7. Restaurar Azure
echo -e "\n7️⃣ RESTAURANDO AZURE:"
az webapp config appsettings set \
  -g rg-wf-ia-gpt41 \
  -n meshbrain \
  --settings AZURE_OPENAI_KEY="$AZURE_OPENAI_KEY" \
  --output none

echo "✅ Azure restaurado"
echo -e "\n============================"
echo "DEBUG COMPLETO FINALIZADO"
EOF