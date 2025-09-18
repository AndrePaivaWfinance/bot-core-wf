#!/bin/bash
# deploy_with_fixed_dockerfile.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

VERSION="v1.4.0"  # Nova versão

echo -e "${BLUE}🚀 DEPLOY COM DOCKERFILE CORRIGIDO${NC}"
echo "======================================"

# 1. Verificar arquivos
echo -e "\n${YELLOW}1. Verificando arquivos...${NC}"
if [ ! -f "Dockerfile" ]; then
    echo -e "${RED}❌ Dockerfile não encontrado${NC}"
    exit 1
fi

if [ ! -f "requirements.txt" ]; then
    echo -e "${RED}❌ requirements.txt não encontrado${NC}"
    exit 1
fi

# 2. Login no ACR
echo -e "\n${YELLOW}2. Login no ACR...${NC}"
az acr login -n meshbrainregistry

# 3. Build com Docker Buildx para AMD64
echo -e "\n${YELLOW}3. Building para AMD64...${NC}"
docker buildx build \
  --platform linux/amd64 \
  -t meshbrainregistry.azurecr.io/meshbrain:$VERSION \
  --push \
  .

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Build falhou${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Build e push concluídos${NC}"

# 4. Verificar no ACR
echo -e "\n${YELLOW}4. Verificando no ACR...${NC}"
if az acr repository show-tags -n meshbrainregistry --repository meshbrain | grep -q "$VERSION"; then
    echo -e "${GREEN}✅ $VERSION no ACR${NC}"
else
    echo -e "${RED}❌ $VERSION não encontrada${NC}"
    exit 1
fi

# 5. Deploy no Web App
echo -e "\n${YELLOW}5. Configurando Web App...${NC}"
az webapp config container set \
  -n meshbrain \
  -g rg-wf-ia-gpt41 \
  -i meshbrainregistry.azurecr.io/meshbrain:$VERSION

# 6. Garantir configurações críticas
echo -e "\n${YELLOW}6. Configurando variáveis críticas...${NC}"
az webapp config appsettings set -n meshbrain -g rg-wf-ia-gpt41 --settings \
  WEBSITES_PORT=8000 \
  SCM_DO_BUILD_DURING_DEPLOYMENT=false \
  WEBSITES_ENABLE_APP_SERVICE_STORAGE=false \
  DOCKER_ENABLE_CI=true \
  --output none

# 7. Restart
echo -e "\n${YELLOW}7. Reiniciando...${NC}"
az webapp restart -n meshbrain -g rg-wf-ia-gpt41

# 8. Monitorar
echo -e "\n${YELLOW}8. Aguardando inicialização...${NC}"
sleep 60

# 9. Testar
echo -e "\n${YELLOW}9. Testando...${NC}"
for i in {1..3}; do
    response=$(curl -s -o /dev/null -w "%{http_code}" https://meshbrain.azurewebsites.net/healthz)
    if [ "$response" == "200" ]; then
        echo -e "${GREEN}✅ SUCESSO! App rodando!${NC}"
        curl -s https://meshbrain.azurewebsites.net/healthz | python3 -m json.tool
        exit 0
    fi
    echo "Tentativa $i/3... HTTP $response"
    sleep 30
done

echo -e "${RED}❌ App não respondeu${NC}"
az webapp log tail -n meshbrain -g rg-wf-ia-gpt41 --timeout 30