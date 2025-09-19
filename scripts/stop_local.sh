#!/bin/bash
# stop_local.sh - Parar Bot Framework Local
# WFinance Bot Framework

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}🛑 PARANDO BOT FRAMEWORK${NC}"
echo -e "${YELLOW}========================================${NC}"

# Funções
log() { echo -e "${YELLOW}[$(date +'%H:%M:%S')] $1${NC}"; }
success() { echo -e "${GREEN}✅ $1${NC}"; }

# 1. Parar containers Docker
if docker ps | grep -q mesh-bot; then
    log "Parando container Docker..."
    docker stop mesh-bot
    docker rm mesh-bot
    success "Container parado"
fi

# 2. Matar processos Python na porta 8000
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    log "Matando processo na porta 8000..."
    kill -9 $(lsof -Pi :8000 -sTCP:LISTEN -t) 2>/dev/null || true
    success "Processo parado"
fi

# 3. Matar processos Python do main.py
if pgrep -f "python.*main.py" > /dev/null; then
    log "Matando processos Python..."
    pkill -f "python.*main.py"
    success "Processos Python parados"
fi

echo -e "\n${GREEN}✅ Bot Framework parado com sucesso!${NC}"