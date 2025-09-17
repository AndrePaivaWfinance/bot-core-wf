#!/bin/bash
# Script de Teste Completo - Local e Azure (Aprimorado)
# Execute: chmod +x scripts/test_complete.sh && ./scripts/test_complete.sh

set -e

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

# URLs
LOCAL_URL="http://localhost:8001"
AZURE_URL="https://meshbrain.azurewebsites.net"

echo -e "${BLUE}🧪 TESTE COMPLETO DO BOT FRAMEWORK${NC}"
echo "========================================="
echo -e "Local: ${PURPLE}$LOCAL_URL${NC}"
echo -e "Azure: ${PURPLE}$AZURE_URL${NC}"
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
}

warning() {
    echo -e "${YELLOW}⚠️ $1${NC}"
}

# Função para testar endpoint
test_endpoint() {
    local url=$1
    local name=$2
    local detailed=${3:-false}
    
    echo -e "\n${BLUE}🔍 Testing $name${NC}"
    echo "================================="
    
    # Health check
    log "Health check..."
    response=$(curl -s -m 10 "$url/healthz" 2>/dev/null || echo "{}")
    
    if echo "$response" | python3 -c "import sys, json; json.load(sys.stdin)" 2>/dev/null; then
        status=$(echo $response | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'error'))" 2>/dev/null || echo "error")
        architecture=$(echo $response | python3 -c "import sys, json; print(json.load(sys.stdin).get('architecture', 'unknown'))" 2>/dev/null || echo "unknown")
        
        if [ "$status" == "ok" ]; then
            success "Health check OK - Architecture: $architecture"
            
            # Mostrar detalhes se solicitado
            if [ "$detailed" == "true" ]; then
                echo -e "\n${PURPLE}📊 Health Details:${NC}"
                echo "$response" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    checks = data.get('checks', {})
    providers = data.get('memory_providers', {})
    
    print('  System Checks:')
    for check, status in checks.items():
        emoji = '✅' if status == '✅' else '❌' if status == '❌' else '⚠️'
        print(f'    {check}: {emoji}')
    
    if providers:
        print('  Memory Providers:')
        for provider, available in providers.items():
            emoji = '✅' if available else '❌'
            print(f'    {provider}: {emoji}')
except Exception as e:
    print(f'  Error parsing details: {e}')
"
            fi
        else
            error "Health check failed - Status: $status"
            return 1
        fi
    else
        error "Health check returned invalid JSON or timed out"
        if [ ${#response} -lt 200 ]; then
            echo "  Response: $response"
        fi
        return 1
    fi
    
    # Test message processing
    log "Testing message processing..."
    test_message='{"user_id":"test_'$(date +%s)'","message":"Hello! Testing the refactored architecture."}'
    
    response=$(curl -s -m 15 -X POST "$url/v1/messages" \
        -H "Content-Type: application/json" \
        -d "$test_message" 2>/dev/null || echo "{}")
    
    if echo "$response" | python3 -c "import sys, json; json.load(sys.stdin)" 2>/dev/null; then
        provider=$(echo $response | python3 -c "import sys, json; print(json.load(sys.stdin).get('metadata', {}).get('provider', 'none'))" 2>/dev/null || echo "none")
        architecture=$(echo $response | python3 -c "import sys, json; print(json.load(sys.stdin).get('metadata', {}).get('architecture', 'unknown'))" 2>/dev/null || echo "unknown")
        confidence=$(echo $response | python3 -c "import sys, json; print(json.load(sys.stdin).get('metadata', {}).get('confidence', 0))" 2>/dev/null || echo "0")
        
        if [ "$provider" != "none" ]; then
            success "Message processed - Provider: $provider, Architecture: $architecture, Confidence: $confidence"
            
            if [ "$detailed" == "true" ]; then
                response_text=$(echo $response | python3 -c "import sys, json; print(json.load(sys.stdin).get('response', 'No response')[:150])" 2>/dev/null || echo "No response")
                echo -e "\n${PURPLE}💬 Response Sample:${NC}"
                echo "  $response_text..."
            fi
        else
            warning "Message processed but no provider responded"
        fi
    else
        error "Message processing failed or timed out"
        if [ ${#response} -lt 200 ]; then
            echo "  Response: $response"
        fi
        return 1
    fi
    
    # Test memory stats (se disponível)
    if [ "$detailed" == "true" ]; then
        log "Testing memory stats..."
        response=$(curl -s -m 10 "$url/v1/memory/stats" 2>/dev/null || echo "{}")
        
        if echo "$response" | python3 -c "import sys, json; json.load(sys.stdin)" 2>/dev/null; then
            success "Memory stats available"
            echo -e "\n${PURPLE}💾 Memory Providers:${NC}"
            echo "$response" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    providers = data.get('providers', {})
    for provider, status in providers.items():
        available = '✅' if status.get('available', False) else '❌'
        provider_type = status.get('type', 'unknown')
        print(f'  {provider}: {available} ({provider_type})')
    
    health = data.get('health', 'unknown')
    print(f'  Overall Health: {health}')
except Exception as e:
    print(f'  Error parsing memory stats: {e}')
"
        else
            warning "Memory stats not available"
        fi
    fi
    
    return 0
}

# Menu principal
show_menu() {
    echo -e "\n${YELLOW}📋 MENU DE TESTES:${NC}"
    echo ""
    echo "  1️⃣  Teste Local (rápido)"
    echo "  2️⃣  Teste Local (detalhado)"
    echo "  3️⃣  Teste Azure (rápido)"  
    echo "  4️⃣  Teste Azure (detalhado)"
    echo "  5️⃣  Teste Completo (Local + Azure)"
    echo "  6️⃣  Teste de Fallback"
    echo "  7️⃣  Preparar Ambiente Local"
    echo "  8️⃣  Verificar Configurações"
    echo "  0️⃣  Sair"
    echo ""
}

# Loop principal
while true; do
    show_menu
    read -p "Escolha uma opção: " choice
    
    case $choice in
        1)
            echo -e "\n${BLUE}🏠 TESTE LOCAL - RÁPIDO${NC}"
            echo "================================="
            
            # Verificar se container está rodando
            if ! docker ps | grep -q "mesh-bot"; then
                warning "Container mesh-bot não está rodando"
                echo "Execute: ./scripts/test_docker.sh e inicie o container (opção 2)"
                continue
            fi
            
            test_endpoint "$LOCAL_URL" "Local Environment" false
            ;;
            
        2)
            echo -e "\n${BLUE}🏠 TESTE LOCAL - DETALHADO${NC}"
            echo "================================="
            
            if ! docker ps | grep -q "mesh-bot"; then
                warning "Container mesh-bot não está rodando"
                echo "Execute: ./scripts/test_docker.sh e inicie o container (opção 2)"
                continue
            fi
            
            test_endpoint "$LOCAL_URL" "Local Environment" true
            ;;
            
        3)
            echo -e "\n${BLUE}☁️ TESTE AZURE - RÁPIDO${NC}"
            echo "================================="
            
            test_endpoint "$AZURE_URL" "Azure Environment" false
            ;;
            
        4)
            echo -e "\n${BLUE}☁️ TESTE AZURE - DETALHADO${NC}"
            echo "================================="
            
            test_endpoint "$AZURE_URL" "Azure Environment" true
            ;;
            
        5)
            echo -e "\n${BLUE}🔄 TESTE COMPLETO${NC}"
            echo "================================="
            
            echo -e "${PURPLE}Testando Local...${NC}"
            if docker ps | grep -q "mesh-bot"; then
                test_endpoint "$LOCAL_URL" "Local" true
            else
                warning "Local container não disponível - pulando"
            fi
            
            echo -e "\n${PURPLE}Testando Azure...${NC}"
            test_endpoint "$AZURE_URL" "Azure" true
            ;;
            
        6)
            echo -e "\n${BLUE}🔀 TESTE DE FALLBACK${NC}"
            echo "================================="
            
            warning "Este teste temporariamente quebra o Azure OpenAI para testar o fallback"
            read -p "Continuar? (y/N) " confirm
            
            if [[ $confirm =~ ^[Yy]$ ]]; then
                log "Salvando chave atual do Azure OpenAI..."
                current_key=$(az webapp config appsettings list -g rg-wf-ia-gpt41 -n meshbrain --query "[?name=='AZURE_OPENAI_KEY'].value" -o tsv 2>/dev/null || echo "")
                
                if [ -z "$current_key" ]; then
                    error "Não foi possível obter a chave atual do Azure"
                    continue
                fi
                
                log "Quebrando Azure OpenAI temporariamente..."
                az webapp config appsettings set \
                    -g rg-wf-ia-gpt41 \
                    -n meshbrain \
                    --settings AZURE_OPENAI_KEY="INVALID_KEY_FOR_FALLBACK_TEST" \
                    --output none
                
                log "Aguardando restart (60s)..."
                sleep 60
                
                log "Testando fallback..."
                response=$(curl -s -X POST "$AZURE_URL/v1/messages" \
                    -H "Content-Type: application/json" \
                    -d '{"user_id":"fallback_test","message":"Hello Claude fallback!"}' \
                    2>/dev/null || echo "{}")
                
                if echo "$response" | python3 -c "import sys, json; json.load(sys.stdin)" 2>/dev/null; then
                    provider=$(echo $response | python3 -c "import sys, json; print(json.load(sys.stdin).get('metadata', {}).get('provider', 'none'))" 2>/dev/null)
                    
                    if [ "$provider" == "claude" ]; then
                        success "FALLBACK FUNCIONANDO! Provider: $provider"
                    else
                        warning "Fallback pode não ter funcionado. Provider: $provider"
                    fi
                    
                    echo -e "\n${PURPLE}Response Details:${NC}"
                    echo "$response" | python3 -m json.tool | head -20
                else
                    error "Fallback test failed"
                    echo "Response: $response"
                fi
                
                log "Restaurando Azure OpenAI..."
                az webapp config appsettings set \
                    -g rg-wf-ia-gpt41 \
                    -n meshbrain \
                    --settings AZURE_OPENAI_KEY="$current_key" \
                    --output none
                
                success "Azure OpenAI restaurado"
            fi
            ;;
            
        7)
            echo -e "\n${BLUE}🔧 PREPARAR AMBIENTE LOCAL${NC}"
            echo "================================="
            
            log "Verificando Docker..."
            if command -v docker &> /dev/null; then
                success "Docker instalado"
            else
                error "Docker não encontrado!"
                continue
            fi
            
            log "Verificando .env..."
            if [ -f ".env" ]; then
                success ".env encontrado"
            else
                warning ".env não encontrado"
                if [ -f ".env.example" ]; then
                    read -p "Copiar de .env.example? (y/N) " copy_env
                    if [[ $copy_env =~ ^[Yy]$ ]]; then
                        cp .env.example .env
                        success ".env criado a partir do exemplo"
                        echo "Edite o .env com suas chaves antes de continuar"
                    fi
                fi
            fi
            
            log "Verificando imagem Docker..."
            if docker images | grep -q "bot-framework"; then
                success "Imagem bot-framework encontrada"
            else
                warning "Imagem não encontrada"
                read -p "Fazer build agora? (y/N) " build_now
                if [[ $build_now =~ ^[Yy]$ ]]; then
                    docker build -t bot-framework:local .
                    success "Build concluído"
                fi
            fi
            
            success "Ambiente local verificado!"
            echo -e "Execute ${PURPLE}./scripts/test_docker.sh${NC} para gerenciar containers"
            ;;
            
        8)
            echo -e "\n${BLUE}🔍 VERIFICAR CONFIGURAÇÕES${NC}"
            echo "================================="
            
            echo -e "\n${PURPLE}Arquivo .env:${NC}"
            if [ -f ".env" ]; then
                success ".env exists"
                
                vars=("AZURE_OPENAI_ENDPOINT" "AZURE_OPENAI_KEY" "ANTHROPIC_API_KEY" "AZURE_COSMOS_ENDPOINT" "AZURE_STORAGE_CONNECTION_STRING")
                
                for var in "${vars[@]}"; do
                    if grep -q "^$var=" .env && [ -n "$(grep "^$var=" .env | cut -d'=' -f2-)" ]; then
                        success "$var configurado"
                    else
                        warning "$var não configurado ou vazio"
                    fi
                done
            else
                error ".env não encontrado!"
            fi
            
            echo -e "\n${PURPLE}Azure CLI:${NC}"
            if command -v az &> /dev/null; then
                success "Azure CLI instalado"
                
                if az account show &> /dev/null; then
                    account=$(az account show --query name -o tsv)
                    success "Logado no Azure: $account"
                else
                    warning "Não logado no Azure (execute: az login)"
                fi
            else
                error "Azure CLI não instalado"
            fi
            
            echo -e "\n${PURPLE}Docker:${NC}"
            if command -v docker &> /dev/null; then
                success "Docker instalado"
                
                if docker ps &> /dev/null; then
                    success "Docker daemon rodando"
                else
                    error "Docker daemon não está rodando"
                fi
            else
                error "Docker não instalado"
            fi
            ;;
            
        0)
            echo -e "\n${GREEN}👋 Até mais!${NC}"
            exit 0
            ;;
            
        *)
            error "Opção inválida!"
            ;;
    esac
    
    echo -e "\n${YELLOW}Pressione Enter para continuar...${NC}"
    read
done