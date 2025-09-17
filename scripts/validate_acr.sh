#!/bin/bash
# Script de Validação ACR - meshbrainregistry.azurecr.io/meshbrain:v1.2.8
# Execute: chmod +x scripts/validate_acr.sh && ./scripts/validate_acr.sh

set -e

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

# Configurações ACR
ACR_NAME="meshbrainregistry"
IMAGE_NAME="meshbrain"
FULL_IMAGE="meshbrainregistry.azurecr.io/meshbrain"
CURRENT_VERSION="v1.2.8"
RESOURCE_GROUP="rg-wf-ia-gpt41"
WEBAPP_NAME="meshbrain"

echo -e "${BLUE}🏗️ VALIDAÇÃO ACR - MESHBRAIN${NC}"
echo "======================================"
echo -e "ACR: ${PURPLE}$ACR_NAME${NC}"
echo -e "Image: ${PURPLE}$FULL_IMAGE${NC}"
echo -e "Current Version: ${PURPLE}$CURRENT_VERSION${NC}"
echo ""

# Função para log
log() {
    echo -e "${YELLOW}[$(date +'%H:%M:%S')] $1${NC}"
}

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

error() {
    echo -e "${RED}❌ $1${NC}"
}

warning() {
    echo -e "${YELLOW}⚠️ $1${NC}"
}

# 1. VERIFICAR AZURE CLI E LOGIN
echo -e "${BLUE}1️⃣ VERIFICAR AZURE CLI${NC}"
echo "========================="

if ! command -v az &> /dev/null; then
    error "Azure CLI não instalado!"
    echo "Instale: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
fi

success "Azure CLI encontrado"

if ! az account show &> /dev/null; then
    warning "Não logado no Azure"
    echo "Execute: az login"
    exit 1
fi

account=$(az account show --query name -o tsv)
success "Logado no Azure: $account"

# 2. VERIFICAR ACR
echo -e "\n${BLUE}2️⃣ VERIFICAR ACR${NC}"
echo "==================="

log "Verificando ACR $ACR_NAME..."

if az acr show --name $ACR_NAME --resource-group $RESOURCE_GROUP &> /dev/null; then
    success "ACR existe e está acessível"
    
    # Login no ACR
    log "Fazendo login no ACR..."
    if az acr login --name $ACR_NAME; then
        success "Login no ACR realizado"
    else
        error "Falha no login do ACR"
        exit 1
    fi
else
    error "ACR não encontrado ou sem acesso"
    echo "Verifique o nome e permissões"
    exit 1
fi

# 3. LISTAR IMAGENS NO ACR
echo -e "\n${BLUE}3️⃣ LISTAR IMAGENS${NC}"
echo "==================="

log "Listando repositórios no ACR..."

repositories=$(az acr repository list --name $ACR_NAME --output tsv 2>/dev/null || echo "")

if [ -z "$repositories" ]; then
    warning "Nenhum repositório encontrado no ACR"
else
    success "Repositórios encontrados:"
    echo "$repositories" | while read repo; do
        echo -e "   📦 $repo"
    done
fi

# Verificar se meshbrain existe
if echo "$repositories" | grep -q "^$IMAGE_NAME$"; then
    success "Repositório '$IMAGE_NAME' encontrado"
    
    log "Listando tags do repositório '$IMAGE_NAME'..."
    tags=$(az acr repository show-tags --name $ACR_NAME --repository $IMAGE_NAME --output table 2>/dev/null || echo "")
    
    if [ -n "$tags" ]; then
        success "Tags encontradas:"
        echo "$tags"
        
        # Verificar se a versão atual existe
        if az acr repository show-tags --name $ACR_NAME --repository $IMAGE_NAME --output tsv | grep -q "^$CURRENT_VERSION$"; then
            success "Versão atual ($CURRENT_VERSION) existe no ACR"
        else
            warning "Versão atual ($CURRENT_VERSION) NÃO existe no ACR"
            echo "Você precisa fazer push da versão atual"
        fi
    else
        warning "Nenhuma tag encontrada no repositório"
    fi
else
    warning "Repositório '$IMAGE_NAME' não encontrado"
    echo "Você precisa fazer o primeiro push"
fi

# 4. VERIFICAR WEBAPP
echo -e "\n${BLUE}4️⃣ VERIFICAR WEBAPP${NC}"
echo "==================="

log "Verificando Web App $WEBAPP_NAME..."

if az webapp show --name $WEBAPP_NAME --resource-group $RESOURCE_GROUP &> /dev/null; then
    success "Web App encontrado"
    
    # Verificar configuração do container
    log "Verificando configuração do container..."
    container_settings=$(az webapp config container show --name $WEBAPP_NAME --resource-group $RESOURCE_GROUP 2>/dev/null || echo "{}")
    
    if echo "$container_settings" | python3 -c "import sys, json; json.load(sys.stdin)" 2>/dev/null; then
        current_image=$(echo "$container_settings" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    for config in data:
        if 'value' in config and 'azurecr.io' in str(config.get('value', '')):
            print(config['value'])
            break
    else:
        print('none')
except:
    print('error')
" 2>/dev/null || echo "error")
        
        if [ "$current_image" != "none" ] && [ "$current_image" != "error" ]; then
            success "Container configurado: $current_image"
            
            if [[ "$current_image" == *"$CURRENT_VERSION"* ]]; then
                success "Web App usando versão atual ($CURRENT_VERSION)"
            else
                warning "Web App usando versão diferente: $current_image"
                echo "Versão esperada: $FULL_IMAGE:$CURRENT_VERSION"
            fi
        else
            warning "Configuração do container não encontrada"
        fi
    else
        warning "Não foi possível obter configuração do container"
    fi
    
    # Verificar status
    state=$(az webapp show --name $WEBAPP_NAME --resource-group $RESOURCE_GROUP --query state -o tsv 2>/dev/null || echo "unknown")
    if [ "$state" == "Running" ]; then
        success "Web App está rodando"
    else
        warning "Web App status: $state"
    fi
    
else
    error "Web App não encontrado"
    echo "Verifique o nome e resource group"
fi

# 5. TESTE DE CONECTIVIDADE
echo -e "\n${BLUE}5️⃣ TESTE DE CONECTIVIDADE${NC}"
echo "========================="

log "Testando health check do Web App..."

response=$(curl -s -m 10 "https://$WEBAPP_NAME.azurewebsites.net/healthz" 2>/dev/null || echo "{}")

if echo "$response" | python3 -c "import sys, json; json.load(sys.stdin)" 2>/dev/null; then
    status=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'unknown'))" 2>/dev/null || echo "unknown")
    
    if [ "$status" == "ok" ]; then
        success "Web App respondendo corretamente"
        
        # Mostrar detalhes da versão
        version=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('version', 'unknown'))" 2>/dev/null || echo "unknown")
        architecture=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('architecture', 'unknown'))" 2>/dev/null || echo "unknown")
        
        echo -e "   Version: $version"
        echo -e "   Architecture: $architecture"
    else
        warning "Web App respondeu mas status: $status"
    fi
else
    warning "Web App não responde ou erro de conectividade"
    echo "   URL: https://$WEBAPP_NAME.azurewebsites.net/healthz"
    echo "   Response: ${response:0:100}..."
fi

# 6. RESUMO E RECOMENDAÇÕES
echo -e "\n${BLUE}6️⃣ RESUMO E RECOMENDAÇÕES${NC}"
echo "========================="

echo -e "\n${PURPLE}📊 Status Atual:${NC}"
echo "   ACR: $ACR_NAME ✅"
echo "   Repository: $IMAGE_NAME"
echo "   Current Version: $CURRENT_VERSION"
echo "   Web App: $WEBAPP_NAME"
echo ""

echo -e "${PURPLE}🔧 Comandos Úteis:${NC}"
echo ""

echo -e "${YELLOW}Para fazer build e push da versão atual:${NC}"
echo "   docker build -t $IMAGE_NAME:local ."
echo "   docker tag $IMAGE_NAME:local $FULL_IMAGE:$CURRENT_VERSION"
echo "   docker tag $IMAGE_NAME:local $FULL_IMAGE:latest"
echo "   docker push $FULL_IMAGE:$CURRENT_VERSION"
echo "   docker push $FULL_IMAGE:latest"
echo ""

echo -e "${YELLOW}Para atualizar Web App com nova versão:${NC}"
echo "   az webapp config container set \\"
echo "     --name $WEBAPP_NAME \\"
echo "     --resource-group $RESOURCE_GROUP \\"
echo "     --docker-custom-image-name $FULL_IMAGE:$CURRENT_VERSION"
echo ""

echo -e "${YELLOW}Para criar nova versão:${NC}"
NEW_VERSION="v$(echo $CURRENT_VERSION | sed 's/v//' | awk -F. '{print $1"."$2"."$3+1}')"
echo "   # Atualizar versão para $NEW_VERSION"
echo "   docker build -t $IMAGE_NAME:local ."
echo "   docker tag $IMAGE_NAME:local $FULL_IMAGE:$NEW_VERSION"
echo "   docker push $FULL_IMAGE:$NEW_VERSION"
echo ""

echo -e "${YELLOW}Para usar script interativo:${NC}"
echo "   ./scripts/test_docker.sh"
echo ""

success "Validação ACR concluída!"