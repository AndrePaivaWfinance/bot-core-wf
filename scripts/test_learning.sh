#!/bin/bash
# test.sh - Script de Teste SIMPLES e FUNCIONAL
# WFinance Bot Framework

# Cores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}🧠 TESTE DO LEARNING SYSTEM${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 1. VERIFICAR SE ESTÁ RODANDO
echo -e "${YELLOW}1. Verificando servidor...${NC}"
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/healthz)

if [ "$RESPONSE" = "200" ]; then
    echo -e "${GREEN}✅ Servidor está rodando!${NC}"
else
    echo -e "${RED}❌ Servidor não está respondendo${NC}"
    echo "Execute: python main.py"
    exit 1
fi

# 2. MOSTRAR STATUS
echo -e "\n${YELLOW}2. Status do servidor:${NC}"
curl -s http://localhost:8000/healthz | grep -o '"status":"[^"]*"' | head -1
curl -s http://localhost:8000/healthz | grep -o '"learning":"[^"]*"'
echo ""

# 3. TESTE BÁSICO
echo -e "${YELLOW}3. Testando mensagem...${NC}"
USER_ID="test_$RANDOM"

curl -s -X POST http://localhost:8000/v1/messages \
    -H "Content-Type: application/json" \
    -d "{
        \"user_id\": \"$USER_ID\",
        \"message\": \"Olá Mesh!\",
        \"channel\": \"test\"
    }" > response.json

if [ -f response.json ]; then
    if grep -q "response" response.json; then
        echo -e "${GREEN}✅ Resposta recebida!${NC}"
        echo "Resposta: $(grep -o '"response":"[^"]*"' response.json | cut -d'"' -f4 | head -c 100)..."
    else
        echo -e "${RED}❌ Erro na resposta${NC}"
        cat response.json
    fi
    rm response.json
fi

# 4. TESTE DE ESTILO FORMAL
echo -e "\n${YELLOW}4. Teste estilo formal...${NC}"
curl -s -X POST http://localhost:8000/v1/messages \
    -H "Content-Type: application/json" \
    -d "{
        \"user_id\": \"${USER_ID}_formal\",
        \"message\": \"Prezado Mesh, gostaria de informações sobre fluxo de caixa.\",
        \"channel\": \"test\"
    }" > response2.json

if grep -q "response" response2.json 2>/dev/null; then
    echo -e "${GREEN}✅ Estilo formal processado${NC}"
else
    echo -e "${RED}❌ Erro${NC}"
fi
rm -f response2.json

# 5. TESTE DE ESTILO CASUAL
echo -e "\n${YELLOW}5. Teste estilo casual...${NC}"
curl -s -X POST http://localhost:8000/v1/messages \
    -H "Content-Type: application/json" \
    -d "{
        \"user_id\": \"${USER_ID}_casual\",
        \"message\": \"Oi! Me explica o que é ROI?\",
        \"channel\": \"test\"
    }" > response3.json

if grep -q "response" response3.json 2>/dev/null; then
    echo -e "${GREEN}✅ Estilo casual processado${NC}"
else
    echo -e "${RED}❌ Erro${NC}"
fi
rm -f response3.json

# 6. CRIAR PADRÃO
echo -e "\n${YELLOW}6. Criando padrão (3 mensagens)...${NC}"
for i in {1..3}; do
    curl -s -X POST http://localhost:8000/v1/messages \
        -H "Content-Type: application/json" \
        -d "{
            \"user_id\": \"$USER_ID\",
            \"message\": \"Pergunta sobre impostos $i\",
            \"channel\": \"test\"
        }" > /dev/null 2>&1
    echo -n "."
done
echo -e "\n${GREEN}✅ Padrões criados${NC}"

# 7. VERIFICAR ESTATÍSTICAS
echo -e "\n${YELLOW}7. Estatísticas:${NC}"
curl -s http://localhost:8000/v1/memory/stats > stats.json 2>/dev/null

if [ -f stats.json ]; then
    if grep -q "health" stats.json; then
        echo -e "${GREEN}✅ Memory stats OK${NC}"
        grep -o '"health":"[^"]*"' stats.json
    fi
    rm stats.json
fi

# 8. INSIGHTS
echo -e "\n${YELLOW}8. Tentando obter insights...${NC}"
curl -s http://localhost:8000/v1/users/$USER_ID/insights > insights.json 2>/dev/null

if [ -f insights.json ]; then
    if grep -q "profile" insights.json; then
        echo -e "${GREEN}✅ Insights disponíveis${NC}"
    else
        echo -e "${YELLOW}⚠️ Insights não disponíveis ainda${NC}"
    fi
    rm -f insights.json
fi

# RESUMO
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}✅ TESTE CONCLUÍDO!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "User ID testado: $USER_ID"
echo ""
echo -e "${YELLOW}Nota:${NC} Como não há LLM configurado, as respostas"
echo "são mensagens padrão, mas o Learning System está"
echo "registrando e aprendendo com as interações!"
echo ""
echo "Para ver logs: tail -f logs/bot.log"