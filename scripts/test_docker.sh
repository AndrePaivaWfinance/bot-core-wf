#!/bin/bash
# Script de Teste Docker - Versão Interativa Melhorada
# Execute: chmod +x scripts/test_docker.sh && ./scripts/test_docker.sh

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

# Configurações
CONTAINER_NAME="meshbrain"
IMAGE_NAME="meshbrain"
ACR_NAME="meshbrainregistry"
FULL_IMAGE="meshbrainregistry.azurecr.io/meshbrain"
VERSION="v1.2.10"
PORT="8001"  # Usar porta diferente para evitar conflitos

clear
echo -e "${BLUE}🐳 TESTE DOCKER - BOT FRAMEWORK${NC}"
echo "=================================="
echo -e "Container: ${PURPLE}$CONTAINER_NAME${NC}"
echo -e "Image: ${PURPLE}$FULL_IMAGE:$VERSION${NC}"
echo -e "Port: ${PURPLE}$PORT${NC}"
echo ""

show_menu() {
    echo -e "${YELLOW}📋 MENU DE OPÇÕES:${NC}"
    echo ""
    echo "  1️⃣  Build da imagem"
    echo "  2️⃣  Iniciar container"
    echo "  3️⃣  Ver logs (follow)"
    echo "  4️⃣  Health check"
    echo "  5️⃣  Teste de mensagem"
    echo "  6️⃣  Memory stats"
    echo "  7️⃣  Shell no container"
    echo "  8️⃣  Parar container"
    echo "  9️⃣  Limpar tudo"
    echo "  🔄  Rebuild completo"
    echo "  📤  Push para ACR"
    echo "  📥  Pull do ACR"
    echo "  0️⃣  Sair"
    echo ""
}

# Função para verificar se container está rodando
check_container() {
    if docker ps | grep -q "$CONTAINER_NAME"; then
        return 0  # Rodando
    else
        return 1  # Não rodando
    fi
}

# Função para mostrar status
show_status() {
    if check_container; then
        echo -e "${GREEN}🟢 Container $CONTAINER_NAME está rodando${NC}"
        echo -e "   URL: ${BLUE}http://localhost:$PORT${NC}"
    else
        echo -e "${RED}🔴 Container $CONTAINER_NAME não está rodando${NC}"
    fi
}

# Loop principal
while true; do
    echo -e "\n${BLUE}===============================================${NC}"
    show_status
    echo -e "${BLUE}===============================================${NC}"
    show_menu
    
    read -p "Escolha uma opção: " choice
    
    case $choice in
        1)
            echo -e "\n${YELLOW}🔨 Building imagem Docker...${NC}"
            
            # Build local
            echo -e "Building imagem local: ${PURPLE}$IMAGE_NAME:local${NC}"
            docker build -t $IMAGE_NAME:local . --no-cache
            
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}✅ Build local concluído!${NC}"
                
                # Perguntar se quer fazer tag para ACR
                read -p "Fazer tag para ACR? (y/N) " tag_choice
                if [[ $tag_choice =~ ^[Yy]$ ]]; then
                    docker tag $IMAGE_NAME:local $FULL_IMAGE:$VERSION
                    docker tag $IMAGE_NAME:local $FULL_IMAGE:latest
                    echo -e "${GREEN}✅ Tags criadas:${NC}"
                    echo -e "   $FULL_IMAGE:$VERSION"
                    echo -e "   $FULL_IMAGE:latest"
                fi
            else
                echo -e "${RED}❌ Build falhou!${NC}"
            fi
            ;;
            
        2)
            echo -e "\n${YELLOW}🚀 Iniciando container...${NC}"
            
            # Parar container antigo se existir
            docker stop $CONTAINER_NAME 2>/dev/null || true
            docker rm $CONTAINER_NAME 2>/dev/null || true
            
            # Verificar se .env existe
            if [ ! -f ".env" ]; then
                echo -e "${RED}❌ Arquivo .env não encontrado!${NC}"
                echo -e "   Copie .env.example para .env e configure"
                continue
            fi
            
            # Iniciar novo container
            docker run -d \
                --name $CONTAINER_NAME \
                -p $PORT:8000 \
                --env-file .env \
                $IMAGE_NAME:local
            
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}✅ Container iniciado!${NC}"
                echo -e "   Aguardando inicialização..."
                sleep 5
                
                # Verificar se iniciou corretamente
                if check_container; then
                    echo -e "${GREEN}✅ Container rodando em http://localhost:$PORT${NC}"
                else
                    echo -e "${RED}❌ Container falhou ao iniciar${NC}"
                    echo -e "   Verifique os logs (opção 3)"
                fi
            else
                echo -e "${RED}❌ Falha ao iniciar container!${NC}"
            fi
            ;;
            
        3)
            echo -e "\n${YELLOW}📋 Logs do container (Ctrl+C para sair):${NC}"
            echo -e "${BLUE}===========================================${NC}"
            
            if check_container; then
                docker logs -f $CONTAINER_NAME
            else
                echo -e "${RED}❌ Container não está rodando!${NC}"
                echo -e "\n${YELLOW}Logs da última execução:${NC}"
                docker logs $CONTAINER_NAME 2>/dev/null || echo "Nenhum log encontrado"
            fi
            ;;
            
        4)
            echo -e "\n${YELLOW}🏥 Health Check...${NC}"
            
            if ! check_container; then
                echo -e "${RED}❌ Container não está rodando!${NC}"
                continue
            fi
            
            response=$(curl -s http://localhost:$PORT/healthz 2>/dev/null || echo "{}")
            
            if echo "$response" | python3 -c "import sys, json; json.load(sys.stdin)" 2>/dev/null; then
                echo -e "${GREEN}✅ Health check OK!${NC}"
                echo ""
                echo "$response" | python3 -m json.tool | head -30
                
                # Mostrar resumo
                status=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'unknown'))" 2>/dev/null)
                architecture=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('architecture', 'unknown'))" 2>/dev/null)
                
                echo -e "\n${BLUE}📊 Resumo:${NC}"
                echo -e "   Status: ${GREEN}$status${NC}"
                echo -e "   Architecture: ${PURPLE}$architecture${NC}"
                
            else
                echo -e "${RED}❌ Health check falhou!${NC}"
                echo -e "   Resposta: $response"
            fi
            ;;
            
        5)
            echo -e "\n${YELLOW}💬 Teste de Mensagem...${NC}"
            
            if ! check_container; then
                echo -e "${RED}❌ Container não está rodando!${NC}"
                continue
            fi
            
            echo -e "Enviando mensagem de teste..."
            
            response=$(curl -s -X POST http://localhost:$PORT/v1/messages \
                -H "Content-Type: application/json" \
                -d '{"user_id":"docker_test","message":"Olá! Teste do Docker container."}' \
                2>/dev/null || echo "{}")
            
            if echo "$response" | python3 -c "import sys, json; json.load(sys.stdin)" 2>/dev/null; then
                echo -e "${GREEN}✅ Mensagem processada!${NC}"
                
                # Extrair informações
                provider=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('metadata', {}).get('provider', 'unknown'))" 2>/dev/null)
                architecture=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('metadata', {}).get('architecture', 'unknown'))" 2>/dev/null)
                response_text=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('response', 'No response')[:100])" 2>/dev/null)
                
                echo -e "\n${BLUE}📊 Detalhes:${NC}"
                echo -e "   Provider: ${GREEN}$provider${NC}"
                echo -e "   Architecture: ${PURPLE}$architecture${NC}"
                echo -e "   Response: ${response_text}..."
                
            else
                echo -e "${RED}❌ Falha no processamento!${NC}"
                echo -e "   Resposta: $response"
            fi
            ;;
            
        6)
            echo -e "\n${YELLOW}💾 Memory Stats...${NC}"
            
            if ! check_container; then
                echo -e "${RED}❌ Container não está rodando!${NC}"
                continue
            fi
            
            response=$(curl -s http://localhost:$PORT/v1/memory/stats 2>/dev/null || echo "{}")
            
            if echo "$response" | python3 -c "import sys, json; json.load(sys.stdin)" 2>/dev/null; then
                echo -e "${GREEN}✅ Memory stats disponíveis!${NC}"
                echo ""
                echo "$response" | python3 -m json.tool
            else
                echo -e "${RED}❌ Memory stats não disponíveis!${NC}"
                echo -e "   Resposta: $response"
            fi
            ;;
            
        7)
            echo -e "\n${YELLOW}🐚 Abrindo shell no container...${NC}"
            
            if ! check_container; then
                echo -e "${RED}❌ Container não está rodando!${NC}"
                continue
            fi
            
            echo -e "Conectando ao container... (digite 'exit' para sair)"
            docker exec -it $CONTAINER_NAME bash
            ;;
            
        8)
            echo -e "\n${YELLOW}⏹ Parando container...${NC}"
            docker stop $CONTAINER_NAME 2>/dev/null && echo -e "${GREEN}✅ Container parado${NC}" || echo -e "${YELLOW}⚠️ Container já estava parado${NC}"
            ;;
            
        9)
            echo -e "\n${YELLOW}🧹 Limpando tudo...${NC}"
            docker stop $CONTAINER_NAME 2>/dev/null || true
            docker rm $CONTAINER_NAME 2>/dev/null || true
            docker rmi $IMAGE_NAME:local 2>/dev/null || true
            echo -e "${GREEN}✅ Limpeza completa!${NC}"
            ;;
            
        "🔄")
            echo -e "\n${YELLOW}🔄 Rebuild completo...${NC}"
            
            # Parar e limpar
            docker stop $CONTAINER_NAME 2>/dev/null || true
            docker rm $CONTAINER_NAME 2>/dev/null || true
            
            # Rebuild
            echo -e "Building nova imagem..."
            docker build -t $IMAGE_NAME:local . --no-cache
            
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}✅ Rebuild concluído!${NC}"
                
                # Perguntar se quer fazer tag
                read -p "Fazer tag para ACR? (y/N) " tag_choice
                if [[ $tag_choice =~ ^[Yy]$ ]]; then
                    docker tag $IMAGE_NAME:local $FULL_IMAGE:$VERSION
                    docker tag $IMAGE_NAME:local $FULL_IMAGE:latest
                    echo -e "${GREEN}✅ Tags ACR criadas${NC}"
                fi
                
                # Perguntar se quer iniciar
                read -p "Iniciar container? (y/n) " start_choice
                if [[ $start_choice =~ ^[Yy]$ ]]; then
                    docker run -d \
                        --name $CONTAINER_NAME \
                        -p $PORT:8000 \
                        --env-file .env \
                        $IMAGE_NAME:local
                    
                    if [ $? -eq 0 ]; then
                        echo -e "${GREEN}✅ Container iniciado!${NC}"
                    fi
                fi
            else
                echo -e "${RED}❌ Rebuild falhou!${NC}"
            fi
            ;;
            
        0)
            echo -e "\n${GREEN}👋 Até mais!${NC}"
            exit 0
            ;;
            
        *)
            echo -e "${RED}❌ Opção inválida!${NC}"
            ;;
    esac
    
    if [ "$choice" != "3" ]; then
        echo -e "\n${YELLOW}Pressione Enter para continuar...${NC}"
        read
    fi
done