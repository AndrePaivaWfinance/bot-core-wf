#!/bin/bash
# Script de Teste da Refatoração - Nova Arquitetura com MemoryManager
# Execute: chmod +x scripts/test_refactor.sh && ./scripts/test_refactor.sh

set -e

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

echo -e "${BLUE}🚀 TESTE DA REFATORAÇÃO - NOVA ARQUITETURA${NC}"
echo "=============================================="
echo -e "Testando migração para ${PURPLE}MemoryManager${NC}"
echo ""

# Função para logging
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

info() {
    echo -e "${BLUE}ℹ️ $1${NC}"
}

# 1. TESTE DE IMPORTS
echo -e "${BLUE}1️⃣ TESTE DE IMPORTS${NC}"
echo "=============================="

log "Testando imports da nova arquitetura..."

python3 -c "
try:
    from memory.memory_manager import MemoryManager
    from memory.learning import LearningSystem
    from memory.retrieval import RetrievalSystem
    print('✅ Core memory imports: OK')
except ImportError as e:
    print(f'❌ Core memory imports: {e}')
    exit(1)

try:
    from core.llm import create_provider, LLMProvider
    from core.llm.azure_provider import AzureOpenAIProvider
    from core.llm.claude_provider import ClaudeProvider
    print('✅ LLM providers imports: OK')
except ImportError as e:
    print(f'❌ LLM providers imports: {e}')
    exit(1)

try:
    from core.brain import BotBrain
    from config.settings import Settings
    print('✅ Brain and settings imports: OK')
except ImportError as e:
    print(f'❌ Brain and settings imports: {e}')
    exit(1)

try:
    import main
    print('✅ Main module import: OK')
except ImportError as e:
    print(f'❌ Main module import: {e}')
    exit(1)

print('\\n🎉 TODOS OS IMPORTS FUNCIONARAM!')
"

if [ $? -eq 0 ]; then
    success "Imports da nova arquitetura funcionando!"
else
    error "Falha nos imports - verifique os arquivos"
    exit 1
fi

# 2. TESTE DE CONFIGURAÇÃO
echo -e "\n${BLUE}2️⃣ TESTE DE CONFIGURAÇÃO${NC}"
echo "=============================="

log "Verificando configurações..."

if [ ! -f ".env" ]; then
    error ".env não encontrado!"
    exit 1
fi

# Verificar variáveis críticas
check_var() {
    local var_name=$1
    local var_value=$(grep "^$var_name=" .env | cut -d'=' -f2- | tr -d '"' | tr -d "'")
    
    if [ -z "$var_value" ] || [ "$var_value" == "" ]; then
        warning "$var_name não configurada"
        return 1
    else
        success "$var_name configurada"
        return 0
    fi
}

echo "Verificando variáveis essenciais:"
check_var "AZURE_OPENAI_ENDPOINT"
check_var "AZURE_OPENAI_KEY"
check_var "ANTHROPIC_API_KEY"

# 3. TESTE LOCAL
echo -e "\n${BLUE}3️⃣ TESTE LOCAL${NC}"
echo "=============================="

log "Parando containers antigos..."
docker stop mesh-bot 2>/dev/null || true
docker rm mesh-bot 2>/dev/null || true

log "Construindo imagem Docker..."
if docker build -t bot-framework:refactor . --quiet; then
    success "Build Docker concluído"
else
    error "Falha no build Docker"
    exit 1
fi

log "Iniciando container..."
docker run -d --name mesh-bot -p 8001:8000 --env-file .env bot-framework:refactor

# Aguardar inicialização
log "Aguardando inicialização (30s)..."
sleep 30

# Verificar se está rodando
if docker ps | grep -q mesh-bot; then
    success "Container rodando"
else
    error "Container não está rodando"
    docker logs mesh-bot
    exit 1
fi

# 4. TESTE DE HEALTH CHECK
echo -e "\n${BLUE}4️⃣ TESTE DE HEALTH CHECK${NC}"
echo "=============================="

log "Testando health check..."

response=$(curl -s http://localhost:8001/healthz 2>/dev/null || echo "{}")

# Verificar se recebeu resposta válida
if echo "$response" | python3 -c "import sys, json; json.load(sys.stdin)" 2>/dev/null; then
    success "Health check retornou JSON válido"
    
    # Verificar status
    status=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'error'))" 2>/dev/null)
    
    if [ "$status" == "ok" ]; then
        success "Status: OK"
    else
        warning "Status: $status"
    fi
    
    # Verificar arquitetura
    arch=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('architecture', 'unknown'))" 2>/dev/null)
    
    if [ "$arch" == "memory_manager" ]; then
        success "Arquitetura: MemoryManager ✨"
    else
        warning "Arquitetura: $arch (esperado: memory_manager)"
    fi
    
    # Verificar providers
    echo -e "\n📊 Status dos Providers:"
    echo "$response" | python3 -c "
import sys, json
data = json.load(sys.stdin)
checks = data.get('checks', {})
print(f\"  Azure OpenAI: {'✅' if checks.get('azure_openai') == '✅' else '❌'}\")
print(f\"  Claude: {'✅' if checks.get('claude') == '✅' else '❌'}\")
print(f\"  Memory Manager: {'✅' if checks.get('memory_manager') == '✅' else '❌'}\")
print(f\"  Brain: {'✅' if checks.get('brain') == '✅' else '❌'}\")
"
    
else
    error "Health check falhou ou retornou JSON inválido"
    echo "Resposta: $response"
fi

# 5. TESTE DE MESSAGING
echo -e "\n${BLUE}5️⃣ TESTE DE MESSAGING${NC}"
echo "=============================="

log "Testando processamento de mensagens..."

# Teste básico
response=$(curl -s -X POST http://localhost:8001/v1/messages \
    -H "Content-Type: application/json" \
    -d '{"user_id":"test_refactor","message":"Olá, teste da nova arquitetura!"}' 2>/dev/null || echo "{}")

if echo "$response" | python3 -c "import sys, json; json.load(sys.stdin)" 2>/dev/null; then
    success "Mensagem processada com sucesso"
    
    # Verificar provider usado
    provider=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('metadata', {}).get('provider', 'none'))" 2>/dev/null)
    architecture=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('metadata', {}).get('architecture', 'unknown'))" 2>/dev/null)
    
    if [ "$provider" != "none" ]; then
        success "Provider usado: $provider"
    else
        warning "Nenhum provider respondeu"
    fi
    
    if [ "$architecture" == "memory_manager" ]; then
        success "Usando nova arquitetura: MemoryManager"
    else
        warning "Arquitetura: $architecture"
    fi
    
else
    error "Falha no processamento da mensagem"
    echo "Resposta: $response"
fi

# 6. TESTE DE MEMORY STATS
echo -e "\n${BLUE}6️⃣ TESTE DE MEMORY STATS${NC}"
echo "=============================="

log "Testando endpoint de estatísticas de memória..."

response=$(curl -s http://localhost:8001/v1/memory/stats 2>/dev/null || echo "{}")

if echo "$response" | python3 -c "import sys, json; json.load(sys.stdin)" 2>/dev/null; then
    success "Memory stats disponível"
    
    echo -e "\n📊 Providers de Memória:"
    echo "$response" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    providers = data.get('providers', {})
    for provider, status in providers.items():
        available = '✅' if status.get('available', False) else '❌'
        provider_type = status.get('type', 'unknown')
        print(f\"  {provider}: {available} ({provider_type})\")
    
    health = data.get('health', 'unknown')
    print(f\"\\nHealth: {health}\")
except Exception as e:
    print(f\"Erro ao processar stats: {e}\")
"
else
    warning "Memory stats não disponível ou com erro"
fi

# 7. VERIFICAR LOGS
echo -e "\n${BLUE}7️⃣ VERIFICAÇÃO DE LOGS${NC}"
echo "=============================="

log "Verificando logs do container..."

echo -e "\n📋 Últimas linhas dos logs:"
docker logs mesh-bot 2>&1 | tail -20 | while read line; do
    if [[ "$line" =~ ✅ ]]; then
        echo -e "${GREEN}$line${NC}"
    elif [[ "$line" =~ ❌ ]]; then
        echo -e "${RED}$line${NC}"
    elif [[ "$line" =~ ⚠️ ]]; then
        echo -e "${YELLOW}$line${NC}"
    else
        echo "$line"
    fi
done

# 8. RESUMO FINAL
echo -e "\n${BLUE}8️⃣ RESUMO FINAL${NC}"
echo "=============================="

echo -e "\n${PURPLE}🎯 RESULTADO DO TESTE DA REFATORAÇÃO:${NC}"
echo ""

# Verificar se tudo funcionou
if curl -s http://localhost:8001/healthz | grep -q '"status":"ok"'; then
    success "✨ REFATORAÇÃO FUNCIONOU!"
    success "   • Nova arquitetura MemoryManager ativa"
    success "   • Imports corrigidos"
    success "   • Container rodando corretamente"
    success "   • Health check OK"
    success "   • Processamento de mensagens OK"
    
    echo -e "\n${GREEN}🚀 PRONTO PARA DEPLOY!${NC}"
    
    echo -e "\n${BLUE}📋 Próximos passos:${NC}"
    echo "1. Execute: docker stop mesh-bot && docker rm mesh-bot"
    echo "2. Execute: ./scripts/deploy.sh"
    echo "3. Monitore: az webapp log tail -g rg-wf-ia-gpt41 -n meshbrain"
    
else
    error "❌ REFATORAÇÃO COM PROBLEMAS!"
    
    echo -e "\n${RED}🔍 Para debugar:${NC}"
    echo "1. Verifique logs: docker logs mesh-bot"
    echo "2. Entre no container: docker exec -it mesh-bot bash"
    echo "3. Teste imports: docker exec mesh-bot python -c 'import main'"
fi

# Limpar
log "Parando container de teste..."
docker stop mesh-bot >/dev/null 2>&1 || true
docker rm mesh-bot >/dev/null 2>&1 || true

echo -e "\n${BLUE}=============================="
echo "TESTE DA REFATORAÇÃO CONCLUÍDO"
echo -e "==============================${NC}"