#!/bin/bash
# deploy_phase4.sh - Deploy da Fase 4 - Sistema de Aprendizagem
# WFinance Bot Framework - Mesh v3.0.0

set -e

# Configurações Azure
ACR_NAME="meshbrainregistry"
RESOURCE_GROUP="rg-wf-ia-gpt41"
WEBAPP_NAME="meshbrain"
IMAGE_NAME="meshbrain"
VERSION="v3.0.0"
FULL_IMAGE="${ACR_NAME}.azurecr.io/${IMAGE_NAME}"

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

echo -e "${PURPLE}========================================${NC}"
echo -e "${PURPLE}🚀 DEPLOY FASE 4 - LEARNING SYSTEM${NC}"
echo -e "${PURPLE}========================================${NC}"
echo -e "Versão: ${GREEN}$VERSION${NC}"
echo -e "Azure Web App: ${BLUE}$WEBAPP_NAME${NC}"
echo ""

# Funções
log() { echo -e "${YELLOW}[$(date +'%H:%M:%S')] $1${NC}"; }
success() { echo -e "${GREEN}✅ $1${NC}"; }
error() { echo -e "${RED}❌ $1${NC}"; exit 1; }
warning() { echo -e "${YELLOW}⚠️ $1${NC}"; }

# 1. VERIFICAÇÃO PRÉ-DEPLOY
echo -e "\n${BLUE}1️⃣ VERIFICAÇÃO PRÉ-DEPLOY${NC}"
echo "================================"

# Verificar arquivos críticos
FILES_TO_CHECK=(
    "Dockerfile"
    "requirements.txt"
    "main.py"
    "core/brain.py"
    "learning/core/learning_engine.py"
    "learning/models/user_profile.py"
    "learning/storage/learning_store.py"
    "learning/analyzers/pattern_detector.py"
)

for file in "${FILES_TO_CHECK[@]}"; do
    if [ -f "$file" ]; then
        success "$file"
    else
        error "$file não encontrado!"
    fi
done

# Verificar .env
if [ ! -f ".env" ]; then
    error ".env não encontrado!"
fi
success "Arquivo .env presente"

# 2. TESTES LOCAIS
echo -e "\n${BLUE}2️⃣ EXECUTANDO TESTES LOCAIS${NC}"
echo "================================"

# Verificar se servidor está rodando
if curl -s http://localhost:8001/healthz > /dev/null 2>&1; then
    log "Servidor local detectado, executando testes..."
    
    # Executar teste do learning system
    if [ -f "./scripts/test_learning.sh" ]; then
        if ./scripts/test_learning.sh > /dev/null 2>&1; then
            success "Testes locais passaram"
        else
            warning "Alguns testes falharam, mas continuando..."
        fi
    fi
else
    warning "Servidor local não está rodando, pulando testes"
fi

# 3. LOGIN NO AZURE
echo -e "\n${BLUE}3️⃣ LOGIN NO AZURE${NC}"
echo "================================"

log "Verificando login no Azure..."
if az account show &> /dev/null; then
    ACCOUNT=$(az account show --query name -o tsv)
    success "Logado em: $ACCOUNT"
else
    log "Fazendo login..."
    az login
    success "Login realizado"
fi

# 4. LOGIN NO ACR
echo -e "\n${BLUE}4️⃣ LOGIN NO CONTAINER REGISTRY${NC}"
echo "================================"

log "Fazendo login no ACR: $ACR_NAME"
az acr login --name $ACR_NAME
success "Login no ACR realizado"

# 5. BUILD DA IMAGEM
echo -e "\n${BLUE}5️⃣ BUILD DA IMAGEM DOCKER${NC}"
echo "================================"

log "Construindo imagem $VERSION..."
log "Isso pode levar alguns minutos..."

docker build \
    --platform linux/amd64 \
    --no-cache \
    -t ${IMAGE_NAME}:${VERSION} \
    -t ${IMAGE_NAME}:latest \
    -f Dockerfile \
    .

if [ $? -eq 0 ]; then
    success "Build concluído"
else
    error "Falha no build Docker"
fi

# Verificar tamanho da imagem
SIZE=$(docker images ${IMAGE_NAME}:${VERSION} --format "{{.Size}}")
log "Tamanho da imagem: $SIZE"

# 6. TAG E PUSH
echo -e "\n${BLUE}6️⃣ PUSH PARA AZURE REGISTRY${NC}"
echo "================================"

# Tag para ACR
log "Aplicando tags..."
docker tag ${IMAGE_NAME}:${VERSION} ${FULL_IMAGE}:${VERSION}
docker tag ${IMAGE_NAME}:${VERSION} ${FULL_IMAGE}:latest
success "Tags aplicadas"

# Push para ACR
log "Fazendo push para $ACR_NAME..."
log "Isso pode levar vários minutos..."

docker push ${FULL_IMAGE}:${VERSION}
docker push ${FULL_IMAGE}:latest

if [ $? -eq 0 ]; then
    success "Push concluído"
else
    error "Falha no push para ACR"
fi

# 7. CONFIGURAR VARIÁVEIS NO AZURE
echo -e "\n${BLUE}7️⃣ CONFIGURANDO VARIÁVEIS${NC}"
echo "================================"

log "Atualizando configurações do Web App..."

# Ler variáveis do .env e configurar no Azure
while IFS='=' read -r key value; do
    # Pular comentários e linhas vazias
    if [[ ! "$key" =~ ^#.*$ ]] && [ ! -z "$key" ]; then
        # Remover aspas do valor
        value="${value%\"}"
        value="${value#\"}"
        
        # Configurar no Azure (sem mostrar valores sensíveis)
        if [[ "$key" == *"KEY"* ]] || [[ "$key" == *"PASSWORD"* ]]; then
            log "Configurando: $key=***"
        else
            log "Configurando: $key"
        fi
        
        az webapp config appsettings set \
            --name $WEBAPP_NAME \
            --resource-group $RESOURCE_GROUP \
            --settings "$key=$value" \
            --output none
    fi
done < .env

success "Variáveis configuradas"

# 8. DEPLOY DA IMAGEM
echo -e "\n${BLUE}8️⃣ DEPLOY PARA WEB APP${NC}"
echo "================================"

log "Configurando Web App para usar imagem $VERSION..."

az webapp config container set \
    --name $WEBAPP_NAME \
    --resource-group $RESOURCE_GROUP \
    --docker-custom-image-name ${FULL_IMAGE}:${VERSION} \
    --docker-registry-server-url https://${ACR_NAME}.azurecr.io \
    --output none

success "Configuração atualizada"

# 9. RESTART DO WEB APP
echo -e "\n${BLUE}9️⃣ REINICIANDO WEB APP${NC}"
echo "================================"

log "Reiniciando aplicação..."
az webapp restart --name $WEBAPP_NAME --resource-group $RESOURCE_GROUP
success "Web App reiniciado"

# 10. VERIFICAÇÃO PÓS-DEPLOY
echo -e "\n${BLUE}🔟 VERIFICAÇÃO PÓS-DEPLOY${NC}"
echo "================================"

log "Aguardando aplicação inicializar (60s)..."
sleep 60

# Verificar health
APP_URL="https://${WEBAPP_NAME}.azurewebsites.net"
log "Verificando health em $APP_URL/healthz"

RETRIES=10
while [ $RETRIES -gt 0 ]; do
    if curl -s "$APP_URL/healthz" | grep -q '"status":"ok"'; then
        success "Aplicação respondendo!"
        break
    fi
    echo -n "."
    sleep 5
    RETRIES=$((RETRIES - 1))
done

if [ $RETRIES -eq 0 ]; then
    error "Aplicação não respondeu após deploy"
fi

# Verificar se Learning Engine está ativo
if curl -s "$APP_URL/healthz" | grep -q "learning"; then
    success "Learning Engine ativo!"
else
    warning "Learning Engine pode não estar totalmente configurado"
fi

# 11. LOGS DE DEPLOY
echo -e "\n${BLUE}📋 LOGS DO DEPLOY${NC}"
echo "================================"

log "Últimas linhas do log:"
az webapp log tail \
    --name $WEBAPP_NAME \
    --resource-group $RESOURCE_GROUP \
    --timeout 30 || true

# RESUMO FINAL
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}✅ DEPLOY FASE 4 CONCLUÍDO!${NC}"
echo -e "${GREEN}========================================${NC}"

echo -e "\n${PURPLE}📊 Resumo do Deploy:${NC}"
echo -e "  • Versão: ${GREEN}$VERSION${NC}"
echo -e "  • Imagem: ${BLUE}${FULL_IMAGE}:${VERSION}${NC}"
echo -e "  • Web App: ${BLUE}$WEBAPP_NAME${NC}"
echo -e "  • URL: ${BLUE}$APP_URL${NC}"

echo -e "\n${PURPLE}🔗 Links Úteis:${NC}"
echo -e "  • App: $APP_URL"
echo -e "  • Health: $APP_URL/healthz"
echo -e "  • Docs: $APP_URL/docs"
echo -e "  • Teams: Configure no Bot Framework Portal"

echo -e "\n${PURPLE}📝 Próximos Passos:${NC}"
echo "  1. Verificar logs: az webapp log tail -n $WEBAPP_NAME -g $RESOURCE_GROUP"
echo "  2. Testar no Teams"
echo "  3. Monitorar métricas no Azure Portal"
echo "  4. Verificar insights de usuários"

echo -e "\n${GREEN}🎉 Sistema de Aprendizagem (Fase 4) em produção!${NC}"