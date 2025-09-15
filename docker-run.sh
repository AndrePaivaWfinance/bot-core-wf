#!/bin/bash

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🐳 Bot Framework - Docker Setup${NC}"
echo "================================="

# Verificar se Docker está instalado
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker não está instalado!${NC}"
    echo "Instale Docker Desktop: https://www.docker.com/products/docker-desktop"
    exit 1
fi

# Verificar se Docker está rodando
if ! docker info &> /dev/null; then
    echo -e "${RED}❌ Docker não está rodando!${NC}"
    echo "Inicie o Docker Desktop e tente novamente."
    exit 1
fi

# Verificar arquivo .env
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  Arquivo .env não encontrado!${NC}"
    echo "Criando .env a partir do exemplo..."
    cp .env.example .env
    echo -e "${YELLOW}📝 Por favor, edite o arquivo .env com suas chaves do Azure!${NC}"
    echo "Depois execute este script novamente."
    exit 1
fi

# Menu de opções
echo ""
echo "Escolha uma opção:"
echo "1) Build e Run (primeira vez)"
echo "2) Apenas Run (imagem já existe)"
echo "3) Rebuild forçado"
echo "4) Parar containers"
echo "5) Ver logs"
echo "6) Limpar tudo"
echo ""
read -p "Opção: " option

case $option in
    1)
        echo -e "${GREEN}🔨 Building e iniciando...${NC}"
        docker-compose up --build -d
        ;;
    2)
        echo -e "${GREEN}🚀 Iniciando containers...${NC}"
        docker-compose up -d
        ;;
    3)
        echo -e "${YELLOW}🔄 Rebuild forçado...${NC}"
        docker-compose build --no-cache
        docker-compose up -d
        ;;
    4)
        echo -e "${YELLOW}⏹  Parando containers...${NC}"
        docker-compose down
        ;;
    5)
        echo -e "${GREEN}📋 Mostrando logs...${NC}"
        docker-compose logs -f
        ;;
    6)
        echo -e "${RED}🧹 Limpando tudo...${NC}"
        docker-compose down -v
        docker system prune -a
        ;;
    *)
        echo -e "${RED}Opção inválida!${NC}"
        exit 1
        ;;
esac

# Se iniciou o container, mostrar status
if [[ $option == 1 ]] || [[ $option == 2 ]] || [[ $option == 3 ]]; then
    echo ""
    echo -e "${GREEN}✅ Container iniciado!${NC}"
    echo ""
    echo "🔗 URLs disponíveis:"
    echo "   - API: http://localhost:8000"
    echo "   - Health: http://localhost:8000/healthz"
    echo "   - Docs: http://localhost:8000/docs"
    echo ""
    echo "📝 Comandos úteis:"
    echo "   - Ver logs: docker-compose logs -f"
    echo "   - Parar: docker-compose down"
    echo "   - Entrar no container: docker exec -it mesh-bot bash"
    echo ""
    echo -e "${GREEN}🧪 Testando health check...${NC}"
    sleep 5
    curl -s http://localhost:8000/healthz | python3 -m json.tool
fi