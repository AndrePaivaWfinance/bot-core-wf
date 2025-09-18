#!/bin/bash
# test_all_memory_tiers.sh

echo "🧪 TESTE COMPLETO DO SISTEMA DE MEMÓRIA"
echo "========================================"

BASE_URL="https://meshbrain.azurewebsites.net"
USER_ID="memory_test_$(date +%s)"

# Função para enviar mensagem
send_message() {
    local msg="$1"
    echo "📤 Enviando: $msg"
    curl -s -X POST "$BASE_URL/v1/messages" \
        -H "Content-Type: application/json" \
        -d "{\"user_id\":\"$USER_ID\",\"message\":\"$msg\"}" | \
        python3 -c "import sys,json; d=json.load(sys.stdin); print('📥 Resposta:', d.get('response','')[:100]+'...')"
    echo ""
}

# 1. Status
echo "1️⃣ STATUS DA MEMÓRIA:"
curl -s "$BASE_URL/v1/memory/stats" | python3 -m json.tool | grep -E "(providers|available|health)"

# 2. Teste HOT
echo -e "\n2️⃣ TESTE HOT MEMORY (RAM):"
send_message "Meu nome é André Paiva e sou o criador deste bot"
sleep 2
send_message "Qual é meu nome completo?"

# 3. Teste WARM
echo -e "\n3️⃣ TESTE WARM MEMORY (COSMOS):"
for i in {1..3}; do
    send_message "Informação $i para Cosmos: Projeto WFinance Bot Framework"
    sleep 1
done
sleep 3
send_message "Resuma todas as informações sobre o projeto que mencionei"

# 4. Teste Context
echo -e "\n4️⃣ TESTE USER CONTEXT:"
send_message "Eu prefiro respostas diretas e objetivas"
send_message "Trabalho com Python e Azure"
sleep 2
send_message "Quais são minhas preferências e com o que trabalho?"

echo -e "\n✅ Testes concluídos! Verifique se o bot manteve o contexto."