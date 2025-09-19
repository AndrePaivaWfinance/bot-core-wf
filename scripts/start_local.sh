#!/bin/bash
# start_local.sh - Iniciar Bot Framework Localmente
# WFinance Bot Framework - Mesh v3.0.0

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

echo -e "${PURPLE}========================================${NC}"
echo -e "${PURPLE}🚀 INICIANDO BOT FRAMEWORK LOCAL${NC}"
echo -e "${PURPLE}========================================${NC}"
echo -e "Versão: ${GREEN}3.0.0${NC} - Com Learning System"
echo ""

# Funções auxiliares
log() { echo -e "${YELLOW}[$(date +'%H:%M:%S')] $1${NC}"; }
success() { echo -e "${GREEN}✅ $1${NC}"; }
error() { echo -e "${RED}❌ $1${NC}"; exit 1; }

# 1. Verificar Python
echo -e "\n${BLUE}1️⃣ VERIFICANDO AMBIENTE${NC}"
echo "================================"

if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    success "Python instalado: $PYTHON_VERSION"
else
    error "Python 3 não encontrado!"
fi

# 2. Verificar .env
if [ ! -f ".env" ]; then
    error "Arquivo .env não encontrado! Copie .env.example e configure."
fi
success "Arquivo .env encontrado"

# 3. Verificar Docker (opcional)
USE_DOCKER=false
if command -v docker &> /dev/null; then
    echo -e "\n${BLUE}Docker disponível. Usar Docker? (y/N)${NC}"
    read -r USE_DOCKER_RESPONSE
    if [[ "$USE_DOCKER_RESPONSE" =~ ^[Yy]$ ]]; then
        USE_DOCKER=true
    fi
fi

# 4. Parar processos anteriores
echo -e "\n${BLUE}2️⃣ LIMPANDO PROCESSOS ANTERIORES${NC}"
echo "================================"

if [ "$USE_DOCKER" = true ]; then
    log "Parando containers antigos..."
    docker stop mesh-bot 2>/dev/null || true
    docker rm mesh-bot 2>/dev/null || true
    success "Containers limpos"
else
    # Matar processo Python na porta 8001
    if lsof -Pi :8001 -sTCP:LISTEN -t >/dev/null 2>&1; then
        log "Matando processo na porta 8001..."
        kill -9 $(lsof -Pi :8001 -sTCP:LISTEN -t) 2>/dev/null || true
        sleep 2
    fi
    success "Portas liberadas"
fi

# 5. Instalar dependências (se não usar Docker)
if [ "$USE_DOCKER" = false ]; then
    echo -e "\n${BLUE}3️⃣ INSTALANDO DEPENDÊNCIAS${NC}"
    echo "================================"
    
    # Criar ambiente virtual se não existir
    if [ ! -d "venv" ]; then
        log "Criando ambiente virtual..."
        python3 -m venv venv
        success "Ambiente virtual criado"
    fi
    
    # Ativar ambiente virtual
    source venv/bin/activate
    
    # Instalar/atualizar dependências
    log "Instalando dependências..."
    pip install -q --upgrade pip
    pip install -q -r requirements.txt
    success "Dependências instaladas"
fi

# 6. Verificar estrutura de diretórios
echo -e "\n${BLUE}4️⃣ VERIFICANDO ESTRUTURA${NC}"
echo "================================"

REQUIRED_DIRS=("learning/core" "learning/models" "learning/storage" "learning/analyzers" "logs" "data")
for dir in "${REQUIRED_DIRS[@]}"; do
    if [ ! -d "$dir" ]; then
        log "Criando diretório: $dir"
        mkdir -p "$dir"
    fi
done
success "Estrutura de diretórios OK"

# 7. Iniciar servidor
echo -e "\n${BLUE}5️⃣ INICIANDO SERVIDOR${NC}"
echo "================================"

if [ "$USE_DOCKER" = true ]; then
    # Usar Docker
    log "Construindo imagem Docker..."
    docker build -t mesh-bot:v3 . --quiet
    
    log "Iniciando container..."
    docker run -d \
        --name mesh-bot \
        -p 8000:8000 \
        --env-file .env \
        -v $(pwd)/logs:/app/logs \
        mesh-bot:v3
    
    success "Container iniciado"
    
    # Mostrar logs
    echo -e "\n${BLUE}📋 LOGS DO CONTAINER:${NC}"
    echo "================================"
    docker logs -f mesh-bot &
    LOGS_PID=$!
    
else
    # Usar Python direto
    log "Iniciando servidor Python..."
    
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
    fi
    
    # Exportar variáveis de ambiente
    export $(grep -v '^#' .env | xargs)
    
    # Iniciar servidor em background
    python3 main.py &
    SERVER_PID=$!
    
    success "Servidor iniciado (PID: $SERVER_PID)"
    
    # Mostrar logs
    if [ -f "logs/bot.log" ]; then
        echo -e "\n${BLUE}📋 LOGS DO SERVIDOR:${NC}"
        echo "================================"
        tail -f logs/bot.log &
        LOGS_PID=$!
    fi
fi

# 8. Aguardar inicialização
echo -e "\n${BLUE}6️⃣ AGUARDANDO INICIALIZAÇÃO${NC}"
echo "================================"

RETRIES=30
while [ $RETRIES -gt 0 ]; do
    if curl -s http://localhost:8000/healthz > /dev/null 2>&1; then
        success "Servidor respondendo!"
        break
    fi
    echo -n "."
    sleep 1
    RETRIES=$((RETRIES - 1))
done

if [ $RETRIES -eq 0 ]; then
    error "Servidor não iniciou após 30 segundos"
fi

# 9. Verificar health check
echo -e "\n${BLUE}7️⃣ HEALTH CHECK${NC}"
echo "================================"

HEALTH=$(curl -s http://localhost:8000/healthz)
echo "$HEALTH" | python3 -m json.tool

# 10. Mostrar informações de acesso
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}✅ BOT FRAMEWORK RODANDO!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "🌐 URLs disponíveis:"
echo -e "   ${BLUE}Health:${NC} http://localhost:8000/healthz"
echo -e "   ${BLUE}Docs:${NC}   http://localhost:8000/docs"
echo -e "   ${BLUE}Chat:${NC}   http://localhost:8000/v1/messages"
echo ""
echo -e "📝 Comandos úteis:"
echo -e "   ${YELLOW}Testar:${NC}  ./scripts/test_learning.sh"
echo -e "   ${YELLOW}Parar:${NC}   ./scripts/stop_local.sh"
echo -e "   ${YELLOW}Logs:${NC}    tail -f logs/bot.log"
echo ""
echo -e "${PURPLE}Pressione Ctrl+C para parar o servidor${NC}"

# Manter script rodando
trap cleanup INT

cleanup() {
    echo -e "\n${YELLOW}Parando servidor...${NC}"
    
    if [ "$USE_DOCKER" = true ]; then
        docker stop mesh-bot
        docker rm mesh-bot
    else
        if [ ! -z "$SERVER_PID" ]; then
            kill $SERVER_PID 2>/dev/null || true
        fi
    fi
    
    if [ ! -z "$LOGS_PID" ]; then
        kill $LOGS_PID 2>/dev/null || true
    fi
    
    success "Servidor parado"
    exit 0
}

# Aguardar
wait