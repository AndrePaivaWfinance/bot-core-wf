#!/bin/bash
# Script de Deploy Automatizado para Azure

set -e  # Para em caso de erro

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configurações
ACR_NAME="meshbrainregistry"
IMAGE_NAME="meshbrain"
WEBAPP_NAME="meshbrain"
RESOURCE_GROUP="rg-wf-ia-gpt41"

# Versão
VERSION=1.2.8
FULL_IMAGE="$ACR_NAME.azurecr.io/$IMAGE_NAME:$VERSION"

echo -e "${GREEN}🚀 Deploy do Bot Framework - v$VERSION${NC}"
echo "========================================="

# 1. Verificar pré-requisitos
echo -e "\n${YELLOW}📋 Verificando pré-requisitos...${NC}"

if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker não está instalado${NC}"
    exit 1
fi

if ! command -v az &> /dev/null; then
    echo -e "${RED}❌ Azure CLI não está instalado${NC}"
    exit 1
fi

# 2. Login no Azure
echo -e "\n${YELLOW}🔐 Fazendo login no Azure...${NC}"
az account show &> /dev/null || az login

# 3. Login no ACR
echo -e "\n${YELLOW}🔐 Login no Container Registry...${NC}"
az acr login --name $ACR_NAME

# 4. Build da imagem
echo -e "\n${YELLOW}🔨 Building Docker image...${NC}"
docker build -t $IMAGE_NAME:latest .
docker tag $IMAGE_NAME:latest $FULL_IMAGE

# 5. Push para ACR
echo -e "\n${YELLOW}📤 Pushing to ACR...${NC}"
docker push $FULL_IMAGE

# 6. Atualizar Web App
echo -e "\n${YELLOW}🔄 Atualizando Web App...${NC}"
az webapp config container set \
  -n $WEBAPP_NAME \
  -g $RESOURCE_GROUP \
  -i $FULL_IMAGE

# 7. Configurar variáveis de ambiente
echo -e "\n${YELLOW}⚙️ Verificando variáveis de ambiente...${NC}"

# Verificar se ANTHROPIC_API_KEY está configurada
if ! az webapp config appsettings list -n $WEBAPP_NAME -g $RESOURCE_GROUP --query "[?name=='ANTHROPIC_API_KEY'].name" -o tsv | grep -q "ANTHROPIC_API_KEY"; then
    echo -e "${YELLOW}Configurando ANTHROPIC_API_KEY...${NC}"
    if [ -f .env ]; then
        source .env
        if [ ! -z "$ANTHROPIC_API_KEY" ]; then
            az webapp config appsettings set -n $WEBAPP_NAME -g $RESOURCE_GROUP --settings ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY"
        fi
    fi
fi

# 8. Restart do Web App
echo -e "\n${YELLOW}🔄 Reiniciando Web App...${NC}"
az webapp restart -n $WEBAPP_NAME -g $RESOURCE_GROUP

# 9. Aguardar inicialização
echo -e "\n${YELLOW}⏳ Aguardando inicialização (30s)...${NC}"
sleep 30

# 10. Testar health check
echo -e "\n${YELLOW}🧪 Testando health check...${NC}"
HEALTH_URL="https://$WEBAPP_NAME.azurewebsites.net/healthz"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" $HEALTH_URL)

if [ "$HTTP_CODE" == "200" ]; then
    echo -e "${GREEN}✅ Deploy concluído com sucesso!${NC}"
    echo -e "${GREEN}✅ Health check OK${NC}"
    curl -s $HEALTH_URL | python3 -m json.tool
else
    echo -e "${RED}❌ Health check falhou (HTTP $HTTP_CODE)${NC}"
    echo -e "${YELLOW}Verificando logs...${NC}"
    az webapp log tail -n $WEBAPP_NAME -g $RESOURCE_GROUP --timeout 30
fi

echo -e "\n${GREEN}=========================================${NC}"
echo -e "${GREEN}Deploy Information:${NC}"
echo -e "  Image: $FULL_IMAGE"
echo -e "  WebApp: https://$WEBAPP_NAME.azurewebsites.net"
echo -e "  Version: $VERSION"
echo -e "${GREEN}=========================================${NC}"