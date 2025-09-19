#!/bin/bash
# deploy_phase4_fixed.sh - Deploy da Fase 4 - Sistema de Aprendizagem (CORRIGIDO)
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

# Funções melhoradas
log() { echo -e "${YELLOW}[$(date +'%H:%M:%S')] $1${NC}"; }
success() { echo -e "${GREEN}✅ $1${NC}"; }
error() { echo -e "${RED}❌ $1${NC}"; exit 1; }
warning() { echo -e "${YELLOW}⚠️ $1${NC}"; }

# Função para verificar se comando existe
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Função para retry de comandos
retry() {
    local retries=$1
    shift
    local command=("$@")
    
    for ((i=1; i<=retries; i++)); do
        if "${command[@]}"; then
            return 0
        else
            if [ $i -lt $retries ]; then
                warning "Tentativa $i/$retries falhou. Tentando novamente em 5s..."
                sleep 5
            fi
        fi
    done
    return 1
}

# 1. VERIFICAÇÃO PRÉ-DEPLOY
echo -e "\n${BLUE}1️⃣ VERIFICAÇÃO PRÉ-DEPLOY${NC}"
echo "================================"

# Verificar Azure CLI
if ! command_exists az; then
    error "Azure CLI não encontrado! Instale: https://aka.ms/InstallAzureCLI"
fi
success "Azure CLI encontrado"

# Verificar Docker
if ! command_exists docker; then
    error "Docker não encontrado! Instale: https://docs.docker.com/get-docker/"
fi
success "Docker encontrado"

# Verificar se Docker está rodando
if ! docker info >/dev/null 2>&1; then
    error "Docker não está rodando! Inicie o Docker Desktop"
fi
success "Docker rodando"

# Verificar arquivos críticos (mais flexível)
REQUIRED_FILES=("Dockerfile" "requirements.txt" "main.py" "core/brain.py")
OPTIONAL_FILES=("learning/core/learning_engine.py" "learning/models/user_profile.py")

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        success "$file ✓"
    else
        error "$file não encontrado! (obrigatório)"
    fi
done

for file in "${OPTIONAL_FILES[@]}"; do
    if [ -f "$file" ]; then
        success "$file ✓"
    else
        warning "$file não encontrado (opcional, mas recomendado)"
    fi
done

# Verificar .env
if [ ! -f ".env" ]; then
    error ".env não encontrado!"
fi
success "Arquivo .env presente"

# 2. VERIFICAÇÃO DE LOGIN AZURE
echo -e "\n${BLUE}2️⃣ VERIFICAÇÃO AZURE${NC}"
echo "================================"

log "Verificando login no Azure..."
if az account show &> /dev/null; then
    ACCOUNT=$(az account show --query name -o tsv)
    TENANT=$(az account show --query tenantId -o tsv)
    success "Logado em: $ACCOUNT"
    log "Tenant: $TENANT"
else
    log "Não logado no Azure. Fazendo login..."
    if az login --output table; then
        success "Login no Azure realizado"
    else
        error "Falha no login do Azure"
    fi
fi

# Verificar subscription ativa
SUBSCRIPTION=$(az account show --query name -o tsv)
log "Subscription ativa: $SUBSCRIPTION"

# 3. VERIFICAÇÃO DO ACR (MELHORADO)
echo -e "\n${BLUE}3️⃣ VERIFICAÇÃO DO ACR${NC}"
echo "================================"

# Verificar se ACR existe
log "Verificando ACR: $ACR_NAME"
if az acr show --name $ACR_NAME --resource-group $RESOURCE_GROUP &> /dev/null; then
    success "ACR encontrado"
else
    error "ACR '$ACR_NAME' não encontrado no resource group '$RESOURCE_GROUP'"
fi

# Verificar permissões no ACR
log "Verificando permissões no ACR..."
if az acr repository list --name $ACR_NAME &> /dev/null; then
    success "Permissões OK"
else
    warning "Problemas de permissão no ACR"
fi

# 4. LOGIN NO ACR (CORRIGIDO COM RETRY)
echo -e "\n${BLUE}4️⃣ LOGIN NO CONTAINER REGISTRY${NC}"
echo "================================"

log "Fazendo login no ACR: $ACR_NAME"

# Tentar login no ACR com retry
if retry 3 az acr login --name $ACR_NAME; then
    success "Login no ACR realizado"
else
    # Método alternativo usando Docker login
    warning "Login direto falhou. Tentando método alternativo..."
    
    log "Obtendo credenciais do ACR..."
    ACR_USERNAME=$(az acr credential show --name $ACR_NAME --query username -o tsv)
    ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query passwords[0].value -o tsv)
    
    if [ ! -z "$ACR_USERNAME" ] && [ ! -z "$ACR_PASSWORD" ]; then
        log "Fazendo login via Docker..."
        if echo "$ACR_PASSWORD" | docker login ${ACR_NAME}.azurecr.io --username "$ACR_USERNAME" --password-stdin; then
            success "Login alternativo no ACR realizado"
        else
            error "Falha no login do ACR por ambos os métodos"
        fi
    else
        error "Não foi possível obter credenciais do ACR"
    fi
fi

# 5. TESTES LOCAIS (OPCIONAL)
echo -e "\n${BLUE}5️⃣ TESTES LOCAIS${NC}"
echo "================================"

# Verificar se servidor local está rodando
if curl -s http://localhost:8000/healthz > /dev/null 2>&1; then
    log "Servidor local na porta 8000 detectado"
    
    # Executar teste básico
    HEALTH_STATUS=$(curl -s http://localhost:8000/healthz | grep -o '"status":"[^"]*"' | cut -d'"' -f4 || echo "unknown")
    if [ "$HEALTH_STATUS" = "healthy" ]; then
        success "Testes locais OK"
    else
        warning "Health check retornou: $HEALTH_STATUS"
    fi
else
    warning "Servidor local não detectado (normal para deploy direto)"
fi

# 6. BUILD DA IMAGEM (MELHORADO)
echo -e "\n${BLUE}6️⃣ BUILD DA IMAGEM DOCKER${NC}"
echo "================================"

log "Iniciando build da imagem $VERSION..."
log "Isso pode levar alguns minutos dependendo da conexão..."

# Build com informações de progresso
BUILD_START=$(date +%s)

if docker build \
    --platform linux/amd64 \
    --progress=plain \
    --no-cache \
    -t ${IMAGE_NAME}:${VERSION} \
    -t ${IMAGE_NAME}:latest \
    -f Dockerfile \
    . ; then
    
    BUILD_END=$(date +%s)
    BUILD_TIME=$((BUILD_END - BUILD_START))
    success "Build concluído em ${BUILD_TIME}s"
    
    # Verificar tamanho da imagem
    SIZE=$(docker images ${IMAGE_NAME}:${VERSION} --format "{{.Size}}")
    log "Tamanho da imagem: $SIZE"
else
    error "Falha no build Docker"
fi

# 7. TAG E PUSH (MELHORADO)
echo -e "\n${BLUE}7️⃣ PUSH PARA AZURE REGISTRY${NC}"
echo "================================"

# Tag para ACR
log "Aplicando tags..."
docker tag ${IMAGE_NAME}:${VERSION} ${FULL_IMAGE}:${VERSION}
docker tag ${IMAGE_NAME}:${VERSION} ${FULL_IMAGE}:latest
success "Tags aplicadas"

# Push para ACR com retry
log "Fazendo push para $ACR_NAME..."
log "Versão: ${VERSION}"
log "Isso pode levar vários minutos..."

PUSH_START=$(date +%s)

if retry 2 docker push ${FULL_IMAGE}:${VERSION} && retry 2 docker push ${FULL_IMAGE}:latest; then
    PUSH_END=$(date +%s)
    PUSH_TIME=$((PUSH_END - PUSH_START))
    success "Push concluído em ${PUSH_TIME}s"
else
    error "Falha no push para ACR após múltiplas tentativas"
fi

# 8. CONFIGURAR VARIÁVEIS NO AZURE (MELHORADO)
echo -e "\n${BLUE}8️⃣ CONFIGURANDO VARIÁVEIS${NC}"
echo "================================"

log "Atualizando configurações do Web App..."

# Configurações básicas primeiro
az webapp config appsettings set \
    --name $WEBAPP_NAME \
    --resource-group $RESOURCE_GROUP \
    --settings "WEBSITES_PORT=8000" \
    --output none

# Ler e configurar variáveis do .env
if [ -f ".env" ]; then
    ENV_VARS=""
    while IFS='=' read -r key value; do
        # Pular comentários e linhas vazias
        if [[ ! "$key" =~ ^#.*$ ]] && [ ! -z "$key" ] && [ ! -z "$value" ]; then
            # Remover aspas do valor
            value="${value%\"}"
            value="${value#\"}"
            
            # Adicionar à lista
            ENV_VARS="$ENV_VARS $key=$value"
        fi
    done < .env
    
    if [ ! -z "$ENV_VARS" ]; then
        log "Configurando variáveis de ambiente..."
        az webapp config appsettings set \
            --name $WEBAPP_NAME \
            --resource-group $RESOURCE_GROUP \
            --settings $ENV_VARS \
            --output none
        success "Variáveis configuradas"
    fi
else
    warning "Arquivo .env não encontrado para configurar variáveis"
fi

# 9. DEPLOY DA IMAGEM (MELHORADO)
echo -e "\n${BLUE}9️⃣ DEPLOY PARA WEB APP${NC}"
echo "================================"

log "Configurando Web App para usar imagem $VERSION..."

# Obter credenciais do ACR
ACR_SERVER="https://${ACR_NAME}.azurecr.io"
ACR_USERNAME=$(az acr credential show --name $ACR_NAME --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query passwords[0].value -o tsv)

# Configurar container
if az webapp config container set \
    --name $WEBAPP_NAME \
    --resource-group $RESOURCE_GROUP \
    --docker-custom-image-name ${FULL_IMAGE}:${VERSION} \
    --docker-registry-server-url $ACR_SERVER \
    --docker-registry-server-user $ACR_USERNAME \
    --docker-registry-server-password $ACR_PASSWORD \
    --output none; then
    success "Configuração de container atualizada"
else
    error "Falha na configuração do container"
fi

# 10. RESTART E VERIFICAÇÃO
echo -e "\n${BLUE}🔟 RESTART E VERIFICAÇÃO${NC}"
echo "================================"

log "Reiniciando Web App..."
az webapp restart --name $WEBAPP_NAME --resource-group $RESOURCE_GROUP --output none
success "Web App reiniciado"

# Aguardar e verificar
APP_URL="https://${WEBAPP_NAME}.azurewebsites.net"
log "Aguardando aplicação inicializar..."
log "URL: $APP_URL"

# Verificação com timeout maior e melhor feedback
RETRIES=20
WAIT_TIME=10

for i in $(seq 1 $RETRIES); do
    log "Tentativa $i/$RETRIES..."
    
    if curl -s -m 30 "$APP_URL/healthz" | grep -q '"status":"healthy"'; then
        success "Aplicação respondendo corretamente!"
        
        # Mostrar informações da versão
        HEALTH_INFO=$(curl -s "$APP_URL/healthz")
        VERSION_DEPLOYED=$(echo "$HEALTH_INFO" | grep -o '"version":"[^"]*"' | cut -d'"' -f4 || echo "unknown")
        ARCHITECTURE=$(echo "$HEALTH_INFO" | grep -o '"architecture":"[^"]*"' | cut -d'"' -f4 || echo "unknown")
        
        log "Versão deployada: $VERSION_DEPLOYED"
        log "Arquitetura: $ARCHITECTURE"
        break
    fi
    
    if [ $i -lt $RETRIES ]; then
        sleep $WAIT_TIME
    else
        warning "Aplicação não respondeu após $(($RETRIES * $WAIT_TIME))s"
        log "Verificar logs: az webapp log tail -n $WEBAPP_NAME -g $RESOURCE_GROUP"
    fi
done

# 11. RESUMO FINAL
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
echo -e "  • Logs: az webapp log tail -n $WEBAPP_NAME -g $RESOURCE_GROUP"

echo -e "\n${PURPLE}📝 Próximos Passos:${NC}"
echo "  1. Verificar funcionamento: curl $APP_URL/healthz"
echo "  2. Testar no Teams"
echo "  3. Monitorar logs por alguns minutos"
echo "  4. Configurar alertas no Azure Monitor"

echo -e "\n${GREEN}🎉 Sistema de Aprendizagem (Fase 4) em produção!${NC}"