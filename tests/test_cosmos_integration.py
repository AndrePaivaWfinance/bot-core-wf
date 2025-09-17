#!/bin/bash
# Script de Teste Rápido - Cosmos DB Integration

echo "🧪 TESTANDO INTEGRAÇÃO COM COSMOS DB"
echo "====================================="

# Cores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# URL do bot
URL="https://meshbrain.azurewebsites.net"
# URL="http://localhost:8000"  # Descomente para teste local

echo -e "\n${YELLOW}1. Enviando mensagem de teste...${NC}"

# Enviar mensagem (isso deve salvar no Cosmos)
response=$(curl -s -X POST "$URL/v1/messages" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "cosmos_test_user",
    "message": "Olá Mesh, esta mensagem deve ser salva no Cosmos DB!"
  }')

echo "Resposta recebida:"
echo "$response" | python3 -m json.tool | head -20

echo -e "\n${YELLOW}2. Enviando segunda mensagem...${NC}"

# Segunda mensagem
response2=$(curl -s -X POST "$URL/v1/messages" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "cosmos_test_user",
    "message": "Esta é a segunda mensagem para testar o histórico"
  }')

echo "Segunda resposta recebida"

echo -e "\n${YELLOW}3. Verificando se foi salvo no Cosmos...${NC}"
echo "Para verificar manualmente:"
echo "1. Acesse o Azure Portal"
echo "2. Vá para o Cosmos DB"
echo "3. Data Explorer > conversations > Items"
echo "4. Procure por 'cosmos_test_user'"

echo -e "\n${GREEN}✅ Teste enviado! Verifique:${NC}"
echo "- Os logs do Azure para ver se salvou"
echo "- O Cosmos DB no portal"
echo "- Se não houver erros, está funcionando!"

# Verificar health
echo -e "\n${YELLOW}4. Health Check...${NC}"
curl -s "$URL/healthz" | python3 -m json.tool | grep -E "(cosmos|memory|status)"

echo -e "\n${GREEN}====================================${NC}"
echo -e "${GREEN}Teste concluído!${NC}"