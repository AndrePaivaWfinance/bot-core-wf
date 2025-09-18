#!/bin/bash
# Script para aplicar ajustes de timeout para Claude

set -e

# Cores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}🔧 APLICANDO AJUSTES DE TIMEOUT PARA CLAUDE${NC}"
echo "============================================"

# 1. Backup dos arquivos
echo -e "\n${YELLOW}1. Fazendo backup dos arquivos...${NC}"
cp test_memory_complete.py test_memory_complete.py.backup_$(date +%Y%m%d) 2>/dev/null || true
cp core/llm/claude_provider.py core/llm/claude_provider.py.backup_$(date +%Y%m%d) 2>/dev/null || true
echo -e "✅ Backups criados"

# 2. Ajustar timeout no teste
echo -e "\n${YELLOW}2. Ajustando timeout no teste para 40s...${NC}"
if [ -f "test_memory_complete.py" ]; then
    sed -i.tmp 's/TIMEOUT = 20/TIMEOUT = 40/g' test_memory_complete.py
    sed -i.tmp 's/TIMEOUT = 30/TIMEOUT = 40/g' test_memory_complete.py
    rm test_memory_complete.py.tmp 2>/dev/null || true
    echo -e "✅ test_memory_complete.py atualizado"
else
    echo -e "${RED}❌ test_memory_complete.py não encontrado${NC}"
fi

# 3. Ajustar timeout no Claude provider
echo -e "\n${YELLOW}3. Ajustando timeout no Claude provider...${NC}"
if [ -f "core/llm/claude_provider.py" ]; then
    # Timeout do cliente
    sed -i.tmp 's/timeout=30\.0/timeout=40.0/g' core/llm/claude_provider.py
    # Timeout interno
    sed -i.tmp 's/timeout=35\.0/timeout=45.0/g' core/llm/claude_provider.py
    rm core/llm/claude_provider.py.tmp 2>/dev/null || true
    echo -e "✅ claude_provider.py atualizado"
else
    echo -e "${RED}❌ claude_provider.py não encontrado${NC}"
fi

# 4. Verificar alterações
echo -e "\n${YELLOW}4. Verificando alterações...${NC}"
echo -e "\n📋 Timeout no teste:"
grep "^TIMEOUT = " test_memory_complete.py | head -1 || echo "Não encontrado"

echo -e "\n📋 Timeout no Claude provider:"
grep "timeout=40" core/llm/claude_provider.py | head -1 || echo "Não encontrado"

# 5. Criar arquivo de configuração de timeouts
echo -e "\n${YELLOW}5. Criando arquivo de configuração centralizada...${NC}"
cat > config/timeouts.py << 'EOF'
"""
Configuração centralizada de timeouts
"""
import os

class TimeoutConfig:
    """Configuração de timeouts para providers"""
    
    # Timeouts base
    AZURE_TIMEOUT = 10  # Azure é rápido
    CLAUDE_TIMEOUT = 40  # Claude precisa de mais tempo
    
    # Timeouts para testes
    TEST_TIMEOUT = 40  # Deve cobrir o pior caso (Claude)
    
    # Timeouts internos (margem de segurança +5s)
    AZURE_INTERNAL_TIMEOUT = 15
    CLAUDE_INTERNAL_TIMEOUT = 45
    
    # Timeout HTTP geral
    HTTP_TIMEOUT = 45
    
    @classmethod
    def get_provider_timeout(cls, provider_name: str) -> int:
        """Retorna timeout apropriado para o provider"""
        if "azure" in provider_name.lower():
            return cls.AZURE_TIMEOUT
        elif "claude" in provider_name.lower():
            return cls.CLAUDE_TIMEOUT
        else:
            return cls.HTTP_TIMEOUT
    
    @classmethod
    def from_env(cls):
        """Permite override via variáveis de ambiente"""
        cls.CLAUDE_TIMEOUT = int(os.getenv("CLAUDE_TIMEOUT", "40"))
        cls.AZURE_TIMEOUT = int(os.getenv("AZURE_TIMEOUT", "10"))
        cls.TEST_TIMEOUT = int(os.getenv("TEST_TIMEOUT", "40"))
        return cls
EOF

echo -e "✅ config/timeouts.py criado"

# 6. Resumo
echo -e "\n${GREEN}✅ AJUSTES APLICADOS COM SUCESSO!${NC}"
echo -e "\n📊 Configuração Final de Timeouts:"
echo -e "   • Testes: ${GREEN}40 segundos${NC}"
echo -e "   • Claude client: ${GREEN}40 segundos${NC}"
echo -e "   • Claude interno: ${GREEN}45 segundos${NC} (margem de segurança)"
echo -e "   • Azure: ${GREEN}10 segundos${NC} (não alterado)"

echo -e "\n${YELLOW}⚠️  IMPORTANTE:${NC}"
echo -e "   1. Reinicie o servidor: ${GREEN}python main.py${NC}"
echo -e "   2. Execute o teste: ${GREEN}python test_memory_complete.py${NC}"
echo -e "   3. Agora Claude deve funcionar sem timeouts!"

echo -e "\n${GREEN}🎯 Pronto para testar!${NC}"