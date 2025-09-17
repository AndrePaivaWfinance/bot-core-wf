#!/bin/bash
# Script de Limpeza e Organização do Projeto
# Execute com: bash scripts/cleanup.sh

set -e

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🧹 LIMPEZA E ORGANIZAÇÃO DO PROJETO${NC}"
echo "======================================"

# 1. Confirmar antes de deletar
echo -e "${YELLOW}⚠️  Este script irá:${NC}"
echo "- Deletar arquivos deprecated"
echo "- Remover scripts de debug temporários"
echo "- Organizar a estrutura do projeto"
echo ""
read -p "Continuar? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${RED}Cancelado${NC}"
    exit 1
fi

# 2. Deletar arquivos desnecessários
echo -e "\n${YELLOW}🗑️  Removendo arquivos desnecessários...${NC}"

# Arquivos deprecated
[ -d ".deprecated" ] && rm -rf .deprecated && echo "  ✅ Removido: .deprecated/"
[ -f "memory/long_term.py" ] && rm memory/long_term.py && echo "  ✅ Removido: memory/long_term.py"
[ -f "memory/short_term.py" ] && rm memory/short_term.py && echo "  ✅ Removido: memory/short_term.py"

# Scripts temporários
[ -f "scripts/debug_claude_complete.sh" ] && rm scripts/debug_claude_complete.sh && echo "  ✅ Removido: scripts/debug_claude_complete.sh"
[ -f "debug_claude_complete.sh" ] && rm debug_claude_complete.sh && echo "  ✅ Removido: debug_claude_complete.sh"
[ -f "scripts/test_complete.sh" ] && rm scripts/test_complete.sh && echo "  ✅ Removido: scripts/test_complete.sh"

# Arquivos antigos
[ -f "core/brain-oldgpt.py" ] && rm core/brain-oldgpt.py && echo "  ✅ Removido: core/brain-oldgpt.py"
[ -f "scripts/test_cosmos_integration.py" ] && rm scripts/test_cosmos_integration.py && echo "  ✅ Removido: scripts/test_cosmos_integration.py"

# 3. Criar estrutura modular
echo -e "\n${YELLOW}📁 Criando estrutura modular...${NC}"

# Memory providers
mkdir -p memory/providers
echo "  ✅ Criado: memory/providers/"

# Interfaces
mkdir -p interfaces/channels
echo "  ✅ Criado: interfaces/channels/"

# Config sources
mkdir -p config/sources
echo "  ✅ Criado: config/sources/"

# Skills categories
mkdir -p skills/categories
echo "  ✅ Criado: skills/categories/"

# 4. Criar arquivos __init__.py onde faltam
echo -e "\n${YELLOW}📄 Criando arquivos __init__.py...${NC}"

touch memory/providers/__init__.py && echo "  ✅ Criado: memory/providers/__init__.py"
touch interfaces/channels/__init__.py && echo "  ✅ Criado: interfaces/channels/__init__.py"
touch config/sources/__init__.py && echo "  ✅ Criado: config/sources/__init__.py"
touch skills/categories/__init__.py && echo "  ✅ Criado: skills/categories/__init__.py"

# 5. Criar .gitignore correto
echo -e "\n${YELLOW}📝 Criando .gitignore correto...${NC}"
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual Environment
.venv/
venv/
ENV/
env/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# Environment
.env
.env.local
.env.*.local

# Logs
*.log
logs/

# Cache
.cache/
.pytest_cache/
.coverage
htmlcov/

# OS
.DS_Store
Thumbs.db

# Project specific
*.backup
.backup/
templates/reports/*.html

# Docker
.dockerignore

# Azure
*.PublishSettings
*.pubxml
*.pubxml.user

# Temporary
tmp/
temp/
EOF
echo "  ✅ .gitignore atualizado"

# 6. Organizar scripts
echo -e "\n${YELLOW}🔧 Organizando scripts...${NC}"

# Tornar scripts executáveis
chmod +x scripts/*.sh 2>/dev/null || true
echo "  ✅ Scripts tornados executáveis"

# 7. Limpar cache Python
echo -e "\n${YELLOW}🧹 Limpando cache Python...${NC}"
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
echo "  ✅ Cache Python limpo"

# 8. Estatísticas finais
echo -e "\n${GREEN}📊 ESTATÍSTICAS DO PROJETO${NC}"
echo "======================================"
echo -e "📁 Arquivos Python: $(find . -name "*.py" | wc -l)"
echo -e "📁 Arquivos de config: $(find . -name "*.yaml" -o -name "*.yml" | wc -l)"
echo -e "📁 Scripts: $(find scripts -name "*.sh" | wc -l)"
echo -e "📁 Testes: $(find tests -name "test_*.py" | wc -l)"

# 9. Verificar tamanho do projeto
PROJECT_SIZE=$(du -sh . | cut -f1)
echo -e "\n💾 Tamanho total do projeto: ${PROJECT_SIZE}"

echo -e "\n${GREEN}✅ LIMPEZA CONCLUÍDA!${NC}"
echo ""
echo -e "${BLUE}📋 Próximos passos:${NC}"
echo "1. Implementar os novos providers em memory/providers/"
echo "2. Atualizar brain.py para usar memory_manager"
echo "3. Testar localmente"
echo "4. Fazer commit das mudanças"
echo "5. Deploy para Azure"