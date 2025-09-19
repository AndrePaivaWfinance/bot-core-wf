#!/bin/bash
# test_docker.sh - Teste Completo com Docker
# WFinance Bot Framework

set -e

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}🐳 TESTE COM DOCKER${NC}"
echo -e "${BLUE}========================================${NC}"

# Funções
log() { echo -e "${YELLOW}[$(date +'%H:%M:%S')] $1${NC}"; }
success() { echo -e "${GREEN}✅ $1${NC}"; }
error() { echo -e "${RED}❌ $1${NC}"; exit 1; }

# 1. Limpar containers antigos
log "Limpando containers antigos..."
docker stop mesh-bot-test 2>/dev/null || true
docker rm mesh-bot-test 2>/dev/null || true

# 2. Build
log "Construindo imagem..."
docker build -t mesh-bot:test . --quiet

# 3. Run
log "Iniciando container de teste..."
docker run -d \
    --name mesh-bot-test \
    -p 8002:8000 \
    --env-file .env \
    mesh-bot:test

# 4. Aguardar
log "Aguardando inicialização (30s)..."
sleep 30

# 5. Testar
log "Testando health check..."
if curl -s http://localhost:8002/healthz | grep -q '"status":"ok"'; then
    success "Container funcionando!"
    
    # Executar testes
    TEST_URL=http://localhost:8002 ./scripts/test_learning.sh
else
    error "Container não respondeu"
fi

# 6. Cleanup
docker stop mesh-bot-test
docker rm mesh-bot-test

success "Teste Docker concluído!"