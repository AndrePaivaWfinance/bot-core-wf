#!/bin/bash
# Script de Teste Completo - Local e Azure

set -e

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# URLs
LOCAL_URL="http://localhost:8000"
AZURE_URL="https://meshbrain.azurewebsites.net"

echo -e "${BLUE}🧪 TESTE COMPLETO DO BOT FRAMEWORK${NC}"
echo "========================================="

# Função para testar endpoint
test_endpoint() {
    local url=$1
    local name=$2
    
    echo -e "\n${YELLOW}Testing $name...${NC}"
    
    # Health check
    echo -e "  📋 Health check..."
    response=$(curl -s "$url/healthz")
    status=$(echo $response | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'error'))" 2>/dev/null || echo "error")
    
    if [ "$status" == "ok" ]; then
        echo -e "  ${GREEN}✅ Health check OK${NC}"
    else
        echo -e "  ${RED}❌ Health check failed${NC}"
        return 1
    fi
    
    # Test with Azure OpenAI
    echo -e "  📋 Testing Azure OpenAI..."
    response=$(curl -s -X POST "$url/v1/messages" \
        -H "Content-Type: application/json" \
        -d '{"user_id":"test1","message":"Hello"}' || echo "{}")
    
    provider=$(echo $response | python3 -c "import sys, json; print(json.load(sys.stdin).get('metadata', {}).get('provider', 'none'))" 2>/dev/null || echo "error")
    
    if [ "$provider" == "azure_openai" ]; then
        echo -e "  ${GREEN}✅ Azure OpenAI working${NC}"
    elif [ "$provider" == "claude" ]; then
        echo -e "  ${YELLOW}⚠️ Using fallback (Claude)${NC}"
    else
        echo -e "  ${RED}❌ No provider responded${NC}"
    fi
    
    return 0
}

# Menu
echo -e "\n${YELLOW}Escolha o teste:${NC}"
echo "1) Teste Local apenas"
echo "2) Teste Azure apenas"
echo "3) Teste Completo (Local + Azure)"
echo "4) Teste de Fallback"
echo "5) Verificar Configurações"
read -p "Opção: " choice

case $choice in
    1)
        # Teste Local
        echo -e "\n${BLUE}🏠 TESTE LOCAL${NC}"
        
        # Verificar se container está rodando
        if ! docker ps | grep -q mesh-bot; then
            echo -e "${YELLOW}Starting local container...${NC}"
            docker run -d --name mesh-bot -p 8000:8000 --env-file .env bot-framework:local
            sleep 10
        fi
        
        test_endpoint "$LOCAL_URL" "Local"
        ;;
    
    2)
        # Teste Azure
        echo -e "\n${BLUE}☁️ TESTE AZURE${NC}"
        test_endpoint "$AZURE_URL" "Azure"
        ;;
    
    3)
        # Teste Completo
        echo -e "\n${BLUE}🔄 TESTE COMPLETO${NC}"
        
        # Local
        if docker ps | grep -q mesh-bot; then
            test_endpoint "$LOCAL_URL" "Local"
        else
            echo -e "${YELLOW}Container local não está rodando${NC}"
        fi
        
        # Azure
        test_endpoint "$AZURE_URL" "Azure"
        ;;
    
    4)
        # Teste de Fallback
        echo -e "\n${BLUE}🔄 TESTE DE FALLBACK${NC}"
        
        echo -e "${YELLOW}Este teste irá:${NC}"
        echo "1. Quebrar a Azure key temporariamente"
        echo "2. Verificar se Claude assume"
        echo "3. Restaurar a key original"
        echo ""
        read -p "Continuar? (y/n) " -n 1 -r
        echo
        
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            # Salvar key atual
            ORIGINAL_KEY=$(az webapp config appsettings list -g rg-wf-ia-gpt41 -n meshbrain --query "[?name=='AZURE_OPENAI_KEY'].value" -o tsv)
            
            # Quebrar key
            echo -e "\n${YELLOW}Breaking Azure key...${NC}"
            az webapp config appsettings set -g rg-wf-ia-gpt41 -n meshbrain --settings AZURE_OPENAI_KEY="BROKEN_FOR_TEST" --output none
            
            echo -e "${YELLOW}Waiting for restart (40s)...${NC}"
            sleep 40
            
            # Testar
            echo -e "${YELLOW}Testing with broken key...${NC}"
            response=$(curl -s -X POST "$AZURE_URL/v1/messages" \
                -H "Content-Type: application/json" \
                -d '{"user_id":"fallback_test","message":"Testing fallback"}')
            
            provider=$(echo $response | python3 -c "import sys, json; print(json.load(sys.stdin).get('metadata', {}).get('provider', 'none'))" 2>/dev/null)
            
            if [ "$provider" == "claude" ]; then
                echo -e "${GREEN}✅ Fallback working! Claude responded${NC}"
            else
                echo -e "${RED}❌ Fallback failed. Provider: $provider${NC}"
            fi
            
            # Restaurar
            echo -e "\n${YELLOW}Restoring original key...${NC}"
            az webapp config appsettings set -g rg-wf-ia-gpt41 -n meshbrain --settings AZURE_OPENAI_KEY="$ORIGINAL_KEY" --output none
            echo -e "${GREEN}✅ Key restored${NC}"
        fi
        ;;
    
    5)
        # Verificar Configurações
        echo -e "\n${BLUE}⚙️ VERIFICANDO CONFIGURAÇÕES${NC}"
        
        echo -e "\n${YELLOW}Local (.env):${NC}"
        if [ -f .env ]; then
            echo -e "  AZURE_OPENAI_KEY: $(grep AZURE_OPENAI_KEY .env | cut -c1-30)..."
            echo -e "  ANTHROPIC_API_KEY: $(grep ANTHROPIC_API_KEY .env | cut -c1-30)..."
        else
            echo -e "  ${RED}❌ .env not found${NC}"
        fi
        
        echo -e "\n${YELLOW}Azure (App Settings):${NC}"
        az webapp config appsettings list -g rg-wf-ia-gpt41 -n meshbrain \
            --query "[?contains(name, 'KEY')].{Name:name, Set:value!=null}" -o table
        ;;
    
    *)
        echo -e "${RED}Invalid option${NC}"
        exit 1
        ;;
esac

echo -e "\n${GREEN}=========================================${NC}"
echo -e "${GREEN}✅ Teste concluído!${NC}"