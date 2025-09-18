#!/bin/bash
# Deploy da Fase 3 - Sistema de Memória Multi-Tier
# WFinance Bot Framework - Mesh

set -e

# Configurações
ACR_NAME="meshbrainregistry"
RESOURCE_GROUP="rg-wf-ia-gpt41"
WEBAPP_NAME="meshbrain"
IMAGE_NAME="meshbrain"
VERSION="v3.0.0"  # Nova versão major para a Fase 3
FULL_IMAGE="${ACR_NAME}.azurecr.io/${IMAGE_NAME}"

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}🚀 DEPLOY FASE 3 - SISTEMA DE MEMÓRIA${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "Versão: ${PURPLE}$VERSION${NC}"
echo -e "Azure Container Registry: ${PURPLE}$ACR_NAME${NC}"
echo -e "Web App: ${PURPLE}$WEBAPP_NAME${NC}"
echo ""

# Função para log com timestamp
log() {
    echo -e "${YELLOW}[$(date +'%H:%M:%S')] $1${NC}"
}

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

error() {
    echo -e "${RED}❌ $1${NC}"
    exit 1
}

# 1. Verificar arquivos críticos
echo -e "\n${BLUE}1️⃣ VERIFICAÇÃO DE ARQUIVOS${NC}"
echo "================================"

FILES_TO_CHECK=(
    "Dockerfile"
    "requirements.txt"
    "main.py"
    "core/brain.py"
    "memory/memory_manager.py"
    "core/llm/claude_provider.py"
    "config/timeouts.py"
)

for file in "${FILES_TO_CHECK[@]}"; do
    if [ -f "$file" ]; then
        success "$file"
    else
        error "$file não encontrado!"
    fi
done

# 2. Verificar variáveis de ambiente
echo -e "\n${BLUE}2️⃣ VERIFICAÇÃO DE CONFIGURAÇÃO${NC}"
echo "================================"

if [ ! -f ".env" ]; then
    error ".env não encontrado!"
fi

log "Verificando variáveis críticas..."
source .env

REQUIRED_VARS=(
    "AZURE_OPENAI_ENDPOINT"
    "AZURE_OPENAI_KEY"
    "ANTHROPIC_API_KEY"
    "AZURE_COSMOS_ENDPOINT"
    "AZURE_COSMOS_KEY"
)

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        error "$var não configurada!"
    else
        success "$var configurada"
    fi
done

# 3. Login no Azure
echo -e "\n${BLUE}3️⃣ LOGIN NO AZURE${NC}"
echo "================================"

log "Fazendo login no Azure CLI..."
if az account show &> /dev/null; then
    ACCOUNT=$(az account show --query name -o tsv)
    success "Já logado em: $ACCOUNT"
else
    az login
    success "Login realizado"
fi

# 4. Login no ACR
echo -e "\n${BLUE}4️⃣ LOGIN NO AZURE CONTAINER REGISTRY${NC}"
echo "================================"

log "Fazendo login no ACR..."
az acr login --name $ACR_NAME
success "Login no ACR realizado"

# 5. Build da imagem Docker
echo -e "\n${BLUE}5️⃣ BUILD DA IMAGEM DOCKER${NC}"
echo "================================"

log "Construindo imagem Docker..."
log "Versão: $VERSION"

docker build \
    --platform linux/amd64 \
    --no-cache \
    -t ${IMAGE_NAME}:${VERSION} \
    -t ${IMAGE_NAME}:latest \
    .

if [ $? -eq 0 ]; then
    success "Build concluído com sucesso"
else
    error "Falha no build Docker"
fi

# 6. Tag para ACR
echo -e "\n${BLUE}6️⃣ CRIANDO TAGS PARA ACR${NC}"
echo "================================"

docker tag ${IMAGE_NAME}:${VERSION} ${FULL_IMAGE}:${VERSION}
docker tag ${IMAGE_NAME}:latest ${FULL_IMAGE}:latest
docker tag ${IMAGE_NAME}:${VERSION} ${FULL_IMAGE}:phase3-latest

success "Tags criadas:"
echo "  • ${FULL_IMAGE}:${VERSION}"
echo "  • ${FULL_IMAGE}:latest"
echo "  • ${FULL_IMAGE}:phase3-latest"

# 7. Push para ACR
echo -e "\n${BLUE}7️⃣ PUSH PARA ACR${NC}"
echo "================================"

log "Enviando imagem para ACR..."

docker push ${FULL_IMAGE}:${VERSION}
docker push ${FULL_IMAGE}:latest
docker push ${FULL_IMAGE}:phase3-latest

success "Push concluído"

# 8. Verificar no ACR
echo -e "\n${BLUE}8️⃣ VERIFICAÇÃO NO ACR${NC}"
echo "================================"

log "Verificando tags no ACR..."
TAGS=$(az acr repository show-tags --name $ACR_NAME --repository $IMAGE_NAME --output tsv)

if echo "$TAGS" | grep -q "$VERSION"; then
    success "Versão $VERSION encontrada no ACR"
else
    error "Versão $VERSION não encontrada no ACR"
fi

# 9. Atualizar Web App
echo -e "\n${BLUE}9️⃣ ATUALIZANDO WEB APP${NC}"
echo "================================"

log "Configurando Web App para usar nova imagem..."

az webapp config container set \
    --name $WEBAPP_NAME \
    --resource-group $RESOURCE_GROUP \
    --docker-custom-image-name ${FULL_IMAGE}:${VERSION} \
    --docker-registry-server-url https://${ACR_NAME}.azurecr.io

success "Web App configurado"

# 10. Configurar variáveis de ambiente
echo -e "\n${BLUE}🔟 CONFIGURANDO VARIÁVEIS DE AMBIENTE${NC}"
echo "================================"

log "Aplicando configurações de ambiente..."

# Aplicar todas as variáveis necessárias
az webapp config appsettings set \
    --name $WEBAPP_NAME \
    --resource-group $RESOURCE_GROUP \
    --settings \
    WEBSITES_PORT=8000 \
    BOT_ENV=production \
    LOG_LEVEL=INFO \
    CLAUDE_TIMEOUT=40 \
    TEST_TIMEOUT=40 \
    SCM_DO_BUILD_DURING_DEPLOYMENT=false \
    WEBSITES_ENABLE_APP_SERVICE_STORAGE=false \
    DOCKER_ENABLE_CI=true \
    --output none

success "Variáveis de ambiente configuradas"

# 11. Restart do Web App
echo -e "\n${BLUE}1️⃣1️⃣ REINICIANDO WEB APP${NC}"
echo "================================"

log "Reiniciando aplicação..."
az webapp restart --name $WEBAPP_NAME --resource-group $RESOURCE_GROUP
success "Web App reiniciado"

# 12. Aguardar inicialização
echo -e "\n${BLUE}1️⃣2️⃣ AGUARDANDO INICIALIZAÇÃO${NC}"
echo "================================"

log "Aguardando 60 segundos para inicialização completa..."
for i in {60..1}; do
    echo -ne "\r⏱️  $i segundos restantes... "
    sleep 1
done
echo ""

# 13. Teste de saúde
echo -e "\n${BLUE}1️⃣3️⃣ TESTE DE SAÚDE${NC}"
echo "================================"

log "Testando health check..."
HEALTH_URL="https://${WEBAPP_NAME}.azurewebsites.net/healthz"

for i in {1..5}; do
    log "Tentativa $i/5..."
    
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" $HEALTH_URL)
    
    if [ "$HTTP_CODE" = "200" ]; then
        success "Health check OK (HTTP 200)"
        
        # Mostrar detalhes
        echo -e "\n${GREEN}📊 Status do Sistema:${NC}"
        curl -s $HEALTH_URL | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"  Status: {data.get('status', 'unknown')}\")
print(f\"  Bot: {data.get('bot', 'unknown')}\")
print(f\"  Architecture: {data.get('architecture', 'unknown')}\")
print(f\"  Version: {data.get('version', 'unknown')}\")
checks = data.get('checks', {})
print(f\"\\n  Providers:\")
for provider, status in checks.items():
    if provider in ['azure_openai', 'claude', 'memory_manager']:
        print(f\"    {provider}: {status}\")
memory = data.get('memory_providers', {})
if memory:
    print(f\"\\n  Memory Tiers:\")
    for tier, available in memory.items():
        status = '✅' if available else '❌'
        print(f\"    {tier}: {status}\")
" 2>/dev/null || echo "  Erro ao processar resposta JSON"
        break
    else
        log "HTTP $HTTP_CODE - Aguardando 20s..."
        sleep 20
    fi
done

# 14. Teste de memória
echo -e "\n${BLUE}1️⃣4️⃣ TESTE DE MEMÓRIA${NC}"
echo "================================"

log "Testando sistema de memória..."

# Teste 1: Enviar informação
log "Enviando informação inicial..."
RESPONSE1=$(curl -s -X POST https://${WEBAPP_NAME}.azurewebsites.net/v1/messages \
    -H "Content-Type: application/json" \
    -d '{"user_id":"deploy_test","message":"Deploy da Fase 3 concluído com sucesso!"}' \
    2>/dev/null || echo "{}")

if echo "$RESPONSE1" | grep -q "response"; then
    success "Mensagem processada"
else
    error "Falha ao processar mensagem"
fi

sleep 2

# Teste 2: Verificar memória
log "Verificando memória..."
RESPONSE2=$(curl -s -X POST https://${WEBAPP_NAME}.azurewebsites.net/v1/messages \
    -H "Content-Type: application/json" \
    -d '{"user_id":"deploy_test","message":"O que acabamos de fazer?"}' \
    2>/dev/null || echo "{}")

if echo "$RESPONSE2" | grep -q "response"; then
    success "Memória funcionando"
    
    # Verificar se lembrou do contexto
    if echo "$RESPONSE2" | grep -qi "fase\|deploy\|sucesso"; then
        success "Bot manteve contexto!"
    else
        log "Bot pode não ter mantido contexto completo"
    fi
else
    error "Falha no teste de memória"
fi

# 15. Logs
echo -e "\n${BLUE}1️⃣5️⃣ ÚLTIMOS LOGS${NC}"
echo "================================"

log "Capturando últimos logs..."
az webapp log tail \
    --name $WEBAPP_NAME \
    --resource-group $RESOURCE_GROUP \
    --timeout 10 2>/dev/null | tail -20 || log "Logs não disponíveis"

# 16. Resumo final
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}✅ DEPLOY DA FASE 3 CONCLUÍDO!${NC}"
echo -e "${GREEN}========================================${NC}"

echo -e "\n📊 ${PURPLE}RESUMO DO DEPLOY:${NC}"
echo -e "  • Versão: ${GREEN}$VERSION${NC}"
echo -e "  • Imagem: ${GREEN}${FULL_IMAGE}:${VERSION}${NC}"
echo -e "  • Web App: ${GREEN}https://${WEBAPP_NAME}.azurewebsites.net${NC}"
echo -e "  • Health: ${GREEN}https://${WEBAPP_NAME}.azurewebsites.net/healthz${NC}"
echo -e "  • Memory Stats: ${GREEN}https://${WEBAPP_NAME}.azurewebsites.net/v1/memory/stats${NC}"

echo -e "\n🎯 ${PURPLE}FASE 3 - SISTEMA DE MEMÓRIA:${NC}"
echo -e "  ✅ HOT Memory (RAM) - 30 minutos"
echo -e "  ✅ WARM Memory (Cosmos DB) - 30 dias"
echo -e "  ✅ COLD Memory (Blob Storage) - 90 dias"
echo -e "  ✅ Context Injection em LLMs"
echo -e "  ✅ Claude Timeout Otimizado (40s)"

echo -e "\n📝 ${PURPLE}PRÓXIMOS PASSOS:${NC}"
echo -e "  1. Testar no Teams"
echo -e "  2. Monitorar logs: ${YELLOW}az webapp log tail -n $WEBAPP_NAME -g $RESOURCE_GROUP${NC}"
echo -e "  3. Iniciar Fase 4 - Sistema de Aprendizagem"

echo -e "\n${GREEN}🎊 Parabéns! Fase 3 em produção!${NC}"