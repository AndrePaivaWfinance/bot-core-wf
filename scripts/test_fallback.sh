#!/bin/bash
# Script de Teste de Fallback - Bot Framework
# Testa cenários de falha e recuperação

set -e

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

echo -e "${BLUE}🔀 TESTE DE FALLBACK - MESH BOT${NC}"
echo "========================================="
echo ""

# URLs
URL="http://localhost:8001"

# Função de log
log() { echo -e "${YELLOW}[$(date +'%H:%M:%S')] $1${NC}"; }
success() { echo -e "${GREEN}✅ $1${NC}"; }
error() { echo -e "${RED}❌ $1${NC}"; }
warning() { echo -e "${YELLOW}⚠️ $1${NC}"; }

# Verificar se container está rodando
if ! docker ps | grep -q "mesh-bot"; then
    error "Container mesh-bot não está rodando!"
    echo "Execute: ./scripts/test_docker.sh"
    exit 1
fi

# Menu de testes
echo -e "${YELLOW}📋 CENÁRIOS DE TESTE:${NC}"
echo ""
echo "1️⃣  Teste com Azure funcionando (ambas keys válidas)"
echo "2️⃣  Teste com Azure inválido (fallback para Claude)"
echo "3️⃣  Teste com ambos inválidos (resposta estática)"
echo "4️⃣  Teste de recuperação (corrigir keys)"
echo "5️⃣  Verificar histórico no Cosmos"
echo ""

read -p "Escolha o cenário (1-5): " scenario

case $scenario in
    1)
        echo -e "\n${BLUE}1️⃣ TESTE COM AMBOS FUNCIONANDO${NC}"
        echo "================================="
        
        log "Verificando keys atuais..."
        docker exec mesh-bot sh -c 'echo "Azure: ${AZURE_OPENAI_KEY:0:10}... | Claude: ${ANTHROPIC_API_KEY:0:10}..."'
        
        log "Enviando mensagem de teste..."
        response=$(curl -s -X POST $URL/v1/messages \
            -H "Content-Type: application/json" \
            -d '{"user_id":"test_both","message":"Olá! Os dois providers estão funcionando?"}')
        
        provider=$(echo $response | python3 -c "import sys, json; print(json.load(sys.stdin).get('metadata', {}).get('provider', 'unknown'))" 2>/dev/null || echo "error")
        
        if [ "$provider" == "azure_openai" ]; then
            success "Azure OpenAI respondeu (primary)"
        elif [ "$provider" == "claude" ]; then
            warning "Claude respondeu (Azure pode estar com problema)"
        else
            error "Nenhum provider respondeu: $provider"
        fi
        
        echo -e "\n${PURPLE}Resposta:${NC}"
        echo $response | python3 -m json.tool | head -20
        ;;
        
    2)
        echo -e "\n${BLUE}2️⃣ TESTE DE FALLBACK (Azure → Claude)${NC}"
        echo "================================="
        
        warning "Este teste vai quebrar temporariamente o Azure OpenAI"
        read -p "Continuar? (y/N) " confirm
        
        if [[ $confirm =~ ^[Yy]$ ]]; then
            # Salvar key atual
            current_key=$(docker exec mesh-bot sh -c 'echo $AZURE_OPENAI_KEY')
            
            log "Quebrando Azure OpenAI..."
            docker exec mesh-bot sh -c 'export AZURE_OPENAI_KEY="INVALID_KEY_FOR_TEST"'
            
            # Reiniciar para aplicar
            log "Reiniciando container..."
            docker restart mesh-bot
            sleep 30
            
            log "Testando fallback..."
            response=$(curl -s -X POST $URL/v1/messages \
                -H "Content-Type: application/json" \
                -d '{"user_id":"test_fallback","message":"Teste de fallback - Azure deve falhar"}')
            
            provider=$(echo $response | python3 -c "import sys, json; print(json.load(sys.stdin).get('metadata', {}).get('provider', 'unknown'))" 2>/dev/null || echo "error")
            
            if [ "$provider" == "claude" ]; then
                success "FALLBACK FUNCIONOU! Claude respondeu"
            elif [ "$provider" == "static" ]; then
                warning "Resposta estática (Claude também falhou)"
            else
                error "Fallback falhou: $provider"
            fi
            
            echo -e "\n${PURPLE}Resposta:${NC}"
            echo $response | python3 -m json.tool | head -20
            
            # Restaurar key
            log "Restaurando Azure OpenAI..."
            docker exec mesh-bot sh -c "export AZURE_OPENAI_KEY='$current_key'"
            docker restart mesh-bot
            success "Azure restaurado"
        fi
        ;;
        
    3)
        echo -e "\n${BLUE}3️⃣ TESTE COM AMBOS INVÁLIDOS${NC}"
        echo "================================="
        
        warning "Este teste vai quebrar AMBOS os providers"
        read -p "Continuar? (y/N) " confirm
        
        if [[ $confirm =~ ^[Yy]$ ]]; then
            # Salvar keys atuais
            azure_key=$(docker exec mesh-bot sh -c 'echo $AZURE_OPENAI_KEY')
            claude_key=$(docker exec mesh-bot sh -c 'echo $ANTHROPIC_API_KEY')
            
            log "Quebrando ambos providers..."
            docker exec mesh-bot sh -c 'export AZURE_OPENAI_KEY="INVALID" && export ANTHROPIC_API_KEY="INVALID"'
            docker restart mesh-bot
            sleep 30
            
            log "Testando resposta estática..."
            
            # Teste 1: Saudação
            response=$(curl -s -X POST $URL/v1/messages \
                -H "Content-Type: application/json" \
                -d '{"user_id":"test_static","message":"Olá!"}')
            
            text=$(echo $response | python3 -c "import sys, json; print(json.load(sys.stdin).get('response', 'no response')[:100])" 2>/dev/null)
            
            if [[ "$text" == *"Mesh"* ]]; then
                success "Resposta estática para saudação funcionou"
            else
                warning "Resposta: $text"
            fi
            
            # Teste 2: Status
            response=$(curl -s -X POST $URL/v1/messages \
                -H "Content-Type: application/json" \
                -d '{"user_id":"test_static","message":"Você está funcionando?"}')
            
            text=$(echo $response | python3 -c "import sys, json; print(json.load(sys.stdin).get('response', 'no response')[:100])" 2>/dev/null)
            
            if [[ "$text" == *"operacional"* ]] || [[ "$text" == *"limitado"* ]]; then
                success "Resposta estática para status funcionou"
            else
                warning "Resposta: $text"
            fi
            
            # Restaurar keys
            log "Restaurando providers..."
            docker exec mesh-bot sh -c "export AZURE_OPENAI_KEY='$azure_key' && export ANTHROPIC_API_KEY='$claude_key'"
            docker restart mesh-bot
            success "Providers restaurados"
        fi
        ;;
        
    4)
        echo -e "\n${BLUE}4️⃣ TESTE DE RECUPERAÇÃO${NC}"
        echo "================================="
        
        log "Verificando estado atual..."
        
        # Health check
        health=$(curl -s $URL/healthz)
        azure_ok=$(echo $health | python3 -c "import sys, json; print('azure_openai' in str(json.load(sys.stdin).get('checks', {})))" 2>/dev/null)
        claude_ok=$(echo $health | python3 -c "import sys, json; print('claude' in str(json.load(sys.stdin).get('checks', {})))" 2>/dev/null)
        
        if [ "$azure_ok" == "True" ]; then
            success "Azure OpenAI: OK"
        else
            error "Azure OpenAI: Falhou"
        fi
        
        if [ "$claude_ok" == "True" ]; then
            success "Claude: OK"
        else
            error "Claude: Falhou"
        fi
        
        log "Testando recuperação após falha..."
        
        # Enviar 3 mensagens seguidas
        for i in {1..3}; do
            response=$(curl -s -X POST $URL/v1/messages \
                -H "Content-Type: application/json" \
                -d "{\"user_id\":\"test_recovery\",\"message\":\"Mensagem $i - teste de recuperação\"}")
            
            provider=$(echo $response | python3 -c "import sys, json; print(json.load(sys.stdin).get('metadata', {}).get('provider', 'unknown'))" 2>/dev/null)
            echo "  Mensagem $i: Provider = $provider"
            sleep 2
        done
        ;;
        
    5)
        echo -e "\n${BLUE}5️⃣ VERIFICAR HISTÓRICO NO COSMOS${NC}"
        echo "================================="
        
        log "Verificando conversas salvas no Cosmos..."
        
        # Query direto no container
        docker exec mesh-bot python3 -c "
from memory.memory_manager import MemoryManager
from config.settings import Settings
import asyncio

async def check():
    settings = Settings.from_yaml()
    mm = MemoryManager(settings)
    
    # Buscar últimas conversas
    history = await mm.get_conversation_history('test_fallback', limit=5)
    
    print(f'Encontradas {len(history)} conversas')
    for conv in history:
        provider = conv.get('metadata', {}).get('provider', 'unknown')
        had_error = conv.get('metadata', {}).get('had_error', False)
        msg = conv.get('message', '')[:50]
        print(f'  - Provider: {provider}, Error: {had_error}, Message: {msg}...')

asyncio.run(check())
"
        ;;
        
    *)
        error "Opção inválida"
        ;;
esac

echo -e "\n${GREEN}✅ Teste concluído!${NC}"
echo ""
echo -e "${BLUE}📊 Resumo:${NC}"
echo "• Fallback Azure → Claude: Configure cenário 2"
echo "• Resposta estática: Configure cenário 3"
echo "• Histórico persiste mesmo com erros"
echo ""
echo -e "${YELLOW}💡 Dica:${NC} Use 'docker logs mesh-bot -f' para ver logs em tempo real"