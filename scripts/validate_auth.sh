#!/bin/bash
# Script de Validação de Autenticação - Bot Framework Mesh
# Execute: chmod +x scripts/validate_auth.sh && ./scripts/validate_auth.sh

set -e

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

echo -e "${BLUE}🔐 VALIDAÇÃO DE AUTENTICAÇÃO - MESH BOT${NC}"
echo "============================================"
echo ""

# Função de logging
log() { echo -e "${YELLOW}[$(date +'%H:%M:%S')] $1${NC}"; }
success() { echo -e "${GREEN}✅ $1${NC}"; }
error() { echo -e "${RED}❌ $1${NC}"; }
warning() { echo -e "${YELLOW}⚠️ $1${NC}"; }

# 1. VERIFICAR .ENV
echo -e "${BLUE}1️⃣ VERIFICANDO ARQUIVO .ENV${NC}"
echo "================================"

if [ ! -f ".env" ]; then
    error ".env não encontrado!"
    echo "Execute: cp .env.example .env"
    exit 1
fi

success ".env encontrado"

# 2. VALIDAR VARIÁVEIS AZURE OPENAI
echo -e "\n${BLUE}2️⃣ VALIDANDO AZURE OPENAI${NC}"
echo "================================"

# Carregar variáveis
source .env

# Verificar endpoint
if [ -z "$AZURE_OPENAI_ENDPOINT" ]; then
    error "AZURE_OPENAI_ENDPOINT não configurado"
else
    success "Endpoint: ${AZURE_OPENAI_ENDPOINT:0:30}..."
    
    # Verificar formato
    if [[ ! "$AZURE_OPENAI_ENDPOINT" =~ ^https://.*\.openai\.azure\.com/? ]]; then
        warning "Formato do endpoint parece incorreto"
        echo "   Esperado: https://seu-recurso.openai.azure.com/"
    fi
fi

# Verificar API Key
if [ -z "$AZURE_OPENAI_KEY" ]; then
    error "AZURE_OPENAI_KEY não configurado"
else
    key_length=${#AZURE_OPENAI_KEY}
    if [ $key_length -lt 20 ]; then
        warning "API Key muito curta ($key_length chars) - esperado 32+"
    else
        success "API Key configurada ($key_length chars)"
    fi
fi

# Verificar deployment
if [ -z "$AZURE_OPENAI_DEPLOYMENT" ]; then
    error "AZURE_OPENAI_DEPLOYMENT não configurado"
else
    success "Deployment: $AZURE_OPENAI_DEPLOYMENT"
fi

# Verificar model
if [ -z "$AZURE_OPENAI_MODEL" ]; then
    warning "AZURE_OPENAI_MODEL não configurado (usando deployment como fallback)"
else
    success "Model: $AZURE_OPENAI_MODEL"
    
    # Verificar consistência
    if [ "$AZURE_OPENAI_MODEL" != "$AZURE_OPENAI_DEPLOYMENT" ]; then
        warning "Model ($AZURE_OPENAI_MODEL) diferente de Deployment ($AZURE_OPENAI_DEPLOYMENT)"
        echo "   Isso pode causar problemas. Geralmente devem ser iguais."
    fi
fi

# Verificar API Version
if [ -z "$AZURE_OPENAI_API_VERSION" ]; then
    warning "AZURE_OPENAI_API_VERSION não configurado (usando padrão)"
else
    success "API Version: $AZURE_OPENAI_API_VERSION"
    
    # Verificar versões conhecidas
    known_versions="2024-02-01 2024-12-01-preview 2024-06-01 2024-08-01-preview"
    if [[ ! " $known_versions " =~ " $AZURE_OPENAI_API_VERSION " ]]; then
        warning "Versão não reconhecida. Versões conhecidas: $known_versions"
    fi
fi

# 3. VALIDAR CLAUDE/ANTHROPIC
echo -e "\n${BLUE}3️⃣ VALIDANDO CLAUDE (FALLBACK)${NC}"
echo "================================"

# Verificar ANTHROPIC_API_KEY (principal)
if [ -z "$ANTHROPIC_API_KEY" ]; then
    # Tentar CLAUDE_API_KEY como fallback
    if [ -z "$CLAUDE_API_KEY" ]; then
        warning "Nenhuma API Key do Claude configurada (fallback não disponível)"
    else
        success "CLAUDE_API_KEY configurada (compatibilidade)"
    fi
else
    success "ANTHROPIC_API_KEY configurada"
    
    # Verificar formato
    if [[ ! "$ANTHROPIC_API_KEY" =~ ^sk-ant- ]]; then
        warning "API Key não começa com 'sk-ant-' - pode estar incorreta"
    fi
fi

# 4. TESTE DE CONEXÃO AZURE
echo -e "\n${BLUE}4️⃣ TESTE DE CONEXÃO AZURE OPENAI${NC}"
echo "================================"

log "Testando conexão com Azure OpenAI..."

# Criar script Python para teste
cat > /tmp/test_azure.py << 'EOF'
import os
import sys
from openai import AzureOpenAI

try:
    client = AzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
    )
    
    response = client.chat.completions.create(
        model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        messages=[{"role": "user", "content": "Say 'Connection OK'"}],
        max_tokens=10
    )
    
    print(f"✅ Azure OpenAI: {response.choices[0].message.content}")
    sys.exit(0)
    
except Exception as e:
    print(f"❌ Azure OpenAI Error: {str(e)[:200]}")
    
    # Diagnóstico específico
    error_str = str(e).lower()
    if "401" in error_str or "unauthorized" in error_str:
        print("   → Chave API inválida ou expirada")
    elif "404" in error_str:
        print("   → Deployment não encontrado ou endpoint incorreto")
    elif "429" in error_str:
        print("   → Rate limit excedido")
    elif "connection" in error_str:
        print("   → Problema de conexão de rede")
    
    sys.exit(1)
EOF

# Executar teste
python3 /tmp/test_azure.py

# 5. TESTE DE CONEXÃO CLAUDE
echo -e "\n${BLUE}5️⃣ TESTE DE CONEXÃO CLAUDE${NC}"
echo "================================"

if [ -n "$ANTHROPIC_API_KEY" ] || [ -n "$CLAUDE_API_KEY" ]; then
    log "Testando conexão com Claude..."
    
    cat > /tmp/test_claude.py << 'EOF'
import os
import sys
import anthropic

api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")

if not api_key:
    print("⚠️ Claude: Nenhuma API key configurada")
    sys.exit(1)

try:
    client = anthropic.Anthropic(api_key=api_key)
    
    message = client.messages.create(
        model="claude-3-opus-20240229",
        max_tokens=10,
        messages=[{"role": "user", "content": "Say 'OK'"}]
    )
    
    text = message.content[0].text if message.content else "OK"
    print(f"✅ Claude: {text}")
    sys.exit(0)
    
except Exception as e:
    print(f"❌ Claude Error: {str(e)[:200]}")
    
    error_str = str(e).lower()
    if "api" in error_str and "key" in error_str:
        print("   → API Key inválida")
    elif "model_not_found" in error_str:
        print("   → Modelo não encontrado (tentando claude-3-opus)")
    
    sys.exit(1)
EOF

    python3 /tmp/test_claude.py
else
    warning "Claude não configurado - fallback não disponível"
fi

# 6. VALIDAR COSMOS DB (OPCIONAL)
echo -e "\n${BLUE}6️⃣ VALIDANDO COSMOS DB (OPCIONAL)${NC}"
echo "================================"

if [ -z "$AZURE_COSMOS_ENDPOINT" ] || [ -z "$AZURE_COSMOS_KEY" ]; then
    warning "Cosmos DB não configurado (memória persistente desabilitada)"
else
    success "Cosmos DB configurado"
    echo "   Endpoint: ${AZURE_COSMOS_ENDPOINT:0:40}..."
fi

# 7. RESUMO FINAL
echo -e "\n${BLUE}7️⃣ RESUMO DA VALIDAÇÃO${NC}"
echo "================================"

echo -e "\n${PURPLE}📊 Status Final:${NC}"

# Contar sucessos e falhas
if [ -n "$AZURE_OPENAI_KEY" ] && [ -n "$AZURE_OPENAI_ENDPOINT" ]; then
    echo "  ✅ Azure OpenAI: Configurado"
else
    echo "  ❌ Azure OpenAI: Não configurado"
fi

if [ -n "$ANTHROPIC_API_KEY" ] || [ -n "$CLAUDE_API_KEY" ]; then
    echo "  ✅ Claude Fallback: Configurado"
else
    echo "  ⚠️ Claude Fallback: Não configurado"
fi

if [ -n "$AZURE_COSMOS_ENDPOINT" ]; then
    echo "  ✅ Cosmos DB: Configurado"
else
    echo "  ⚠️ Cosmos DB: Não configurado"
fi

echo -e "\n${GREEN}✨ Validação concluída!${NC}"

# 8. SUGESTÕES
echo -e "\n${BLUE}💡 SUGESTÕES${NC}"
echo "================================"

echo "1. Se Azure falhar com 401: Regenere a chave no Portal Azure"
echo "2. Se Azure falhar com 404: Verifique o nome do deployment"
echo "3. Se Claude falhar: Verifique em console.anthropic.com"
echo "4. Para testar localmente: ./scripts/test_docker.sh"
echo "5. Para deploy: ./scripts/deploy.sh"

# Limpar arquivos temporários
rm -f /tmp/test_azure.py /tmp/test_claude.py

echo -e "\n${GREEN}🎯 Script concluído!${NC}"