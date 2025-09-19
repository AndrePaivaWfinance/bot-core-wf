#!/usr/bin/env python3
"""
Diagnóstico Completo do Bot Framework
Testa todos os fatores que podem impedir o WebChat de funcionar
"""

import json
import requests
import sys
import os
from datetime import datetime
from typing import Dict, Any, List

# Configurações
WEBAPP_URL = "https://meshbrain.azurewebsites.net"
BOT_NAME = "MeshBot"  # Substitua pelo nome real do seu bot
RESOURCE_GROUP = "BotResourceGroup"  # Substitua pelo seu resource group

class BotDiagnostics:
    def __init__(self):
        self.results = []
        self.errors = []
        self.warnings = []
        
    def log_result(self, test_name: str, status: str, details: str = ""):
        """Log resultado de um teste"""
        result = {
            "test": test_name,
            "status": status,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        self.results.append(result)
        
        icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{icon} {test_name}: {status}")
        if details:
            print(f"   {details}")
    
    def run_test(self, test_name: str, test_func):
        """Executa um teste com tratamento de erro"""
        try:
            result = test_func()
            if result:
                self.log_result(test_name, "PASS", str(result))
            else:
                self.log_result(test_name, "FAIL", "Test returned False")
                self.errors.append(test_name)
        except Exception as e:
            self.log_result(test_name, "ERROR", str(e))
            self.errors.append(test_name)
    
    # ========== TESTES DE ENDPOINT ==========
    
    def test_health_endpoint(self):
        """Testa se o endpoint de health está funcionando"""
        response = requests.get(f"{WEBAPP_URL}/healthz", timeout=10)
        if response.status_code != 200:
            raise Exception(f"Health endpoint returned {response.status_code}")
        return response.json()
    
    def test_api_messages_options(self):
        """Testa se o endpoint aceita OPTIONS (CORS)"""
        response = requests.options(f"{WEBAPP_URL}/api/messages", timeout=10)
        if response.status_code == 400:
            self.warnings.append("OPTIONS returns 400 - pode ser problema de CORS")
        return f"Status: {response.status_code}"
    
    def test_api_messages_post(self):
        """Testa POST no endpoint /api/messages"""
        test_activity = {
            "type": "message",
            "id": f"test_{datetime.now().timestamp()}",
            "timestamp": datetime.now().isoformat(),
            "channelId": "test",
            "from": {"id": "test_user", "name": "Test User"},
            "conversation": {"id": "test_conv"},
            "recipient": {"id": "bot", "name": "Bot"},
            "text": "Teste diagnóstico",
            "serviceUrl": "https://test.botframework.com",
            "locale": "pt-BR"
        }
        
        response = requests.post(
            f"{WEBAPP_URL}/api/messages",
            json=test_activity,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code != 200:
            raise Exception(f"POST returned {response.status_code}: {response.text}")
        
        data = response.json()
        
        # Validar resposta
        issues = []
        if not data.get("type"):
            issues.append("Missing 'type' field")
        if not data.get("from"):
            issues.append("Missing 'from' field")
        elif not data["from"].get("id"):
            issues.append("Missing 'from.id'")
        if not data.get("text"):
            issues.append("Missing 'text' field")
        
        if issues:
            self.warnings.extend(issues)
            return f"Response has issues: {', '.join(issues)}"
        
        return f"Valid response with from.id={data['from'].get('id')}"
    
    # ========== TESTES DE FORMATO ==========
    
    def test_response_format(self):
        """Testa se a resposta está no formato correto do Bot Framework"""
        test_activity = {
            "type": "message",
            "channelId": "webchat",
            "from": {"id": "user123"},
            "conversation": {"id": "conv123"},
            "text": "formato teste"
        }
        
        response = requests.post(
            f"{WEBAPP_URL}/api/messages",
            json=test_activity,
            timeout=10
        )
        
        if response.status_code != 200:
            return False
        
        data = response.json()
        required_fields = ["type", "from", "text"]
        missing = [f for f in required_fields if f not in data or data[f] is None]
        
        if missing:
            raise Exception(f"Missing required fields: {missing}")
        
        return True
    
    def test_conversation_update(self):
        """Testa conversationUpdate (novo membro)"""
        activity = {
            "type": "conversationUpdate",
            "channelId": "webchat",
            "membersAdded": [{"id": "user", "name": "User"}],
            "recipient": {"id": "bot"},
            "conversation": {"id": "conv"}
        }
        
        response = requests.post(
            f"{WEBAPP_URL}/api/messages",
            json=activity,
            timeout=10
        )
        
        return f"Status: {response.status_code}"
    
    # ========== TESTES DO BOT SERVICE ==========
    
    def test_bot_service_config(self):
        """Verifica configuração do Bot Service via Azure CLI"""
        print("\n📋 CONFIGURAÇÃO DO BOT SERVICE:")
        print("Execute estes comandos no Azure CLI para verificar:")
        print(f"""
az bot show --name {BOT_NAME} --resource-group {RESOURCE_GROUP} --query "properties.endpoint"
az bot show --name {BOT_NAME} --resource-group {RESOURCE_GROUP} --query "properties.msaAppId"
az bot webchat show --name {BOT_NAME} --resource-group {RESOURCE_GROUP}
        """)
        
        return "Comandos Azure CLI fornecidos"
    
    def test_app_settings(self):
        """Verifica variáveis de ambiente"""
        print("\n🔧 VARIÁVEIS DE AMBIENTE:")
        print("Execute este comando para verificar:")
        print(f"""
az webapp config appsettings list --name meshbrain --resource-group {RESOURCE_GROUP} | grep -E "(MICROSOFT_APP|TEAMS)"
        """)
        
        return "Comando fornecido"
    
    # ========== TESTES DE AUTENTICAÇÃO ==========
    
    def test_bot_framework_auth(self):
        """Testa autenticação com Bot Framework"""
        # Este teste simula uma mensagem vinda do Bot Framework real
        activity = {
            "type": "message",
            "id": "bf-test",
            "timestamp": datetime.now().isoformat(),
            "channelId": "emulator",  # Simula Bot Framework Emulator
            "from": {"id": "user", "name": "User"},
            "conversation": {"id": "conv", "isGroup": False, "conversationType": "personal"},
            "recipient": {"id": "bot"},
            "text": "auth test",
            "serviceUrl": "https://directline.botframework.com",
            "channelData": {},
            "locale": "pt-BR"
        }
        
        response = requests.post(
            f"{WEBAPP_URL}/api/messages",
            json=activity,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 401:
            self.errors.append("Authentication failed - check MICROSOFT_APP_ID and PASSWORD")
            return False
        
        return f"Auth test passed: {response.status_code}"
    
    # ========== ANÁLISE DE LOGS ==========
    
    def analyze_logs(self):
        """Fornece comandos para análise de logs"""
        print("\n📊 ANÁLISE DE LOGS:")
        print("Execute este comando para ver logs em tempo real:")
        print(f"""
az webapp log tail --name meshbrain --resource-group {RESOURCE_GROUP} | grep -E "(ERROR|WARNING|api/messages)"
        """)
        
        return "Comando de logs fornecido"
    
    # ========== TESTE DE WEBCHAT DIRETO ==========
    
    def test_direct_line(self):
        """Instruções para teste com Direct Line"""
        print("\n🌐 TESTE DIRECT LINE:")
        print("""
1. No Azure Portal, vá para o Bot Service
2. Em Channels, clique em "Configure Direct Line channel"
3. Copie uma das Secret Keys
4. Use esta chave para testar com curl:

curl -X POST https://directline.botframework.com/v3/directline/conversations \\
  -H "Authorization: Bearer YOUR_DIRECT_LINE_SECRET" \\
  -H "Content-Type: application/json"
        """)
        
        return "Instruções fornecidas"
    
    # ========== RELATÓRIO FINAL ==========
    
    def generate_report(self):
        """Gera relatório final com recomendações"""
        print("\n" + "=" * 60)
        print("📊 RELATÓRIO DE DIAGNÓSTICO")
        print("=" * 60)
        
        total_tests = len(self.results)
        passed = len([r for r in self.results if r["status"] == "PASS"])
        failed = len(self.errors)
        
        print(f"\n✅ Testes aprovados: {passed}/{total_tests}")
        print(f"❌ Testes falhados: {failed}/{total_tests}")
        
        if self.warnings:
            print(f"\n⚠️  AVISOS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"   - {warning}")
        
        if self.errors:
            print(f"\n❌ ERROS ({len(self.errors)}):")
            for error in self.errors:
                print(f"   - {error}")
        
        print("\n" + "=" * 60)
        print("💡 RECOMENDAÇÕES")
        print("=" * 60)
        
        if "Authentication failed" in str(self.errors):
            print("""
❌ PROBLEMA DE AUTENTICAÇÃO:
1. Verifique MICROSOFT_APP_ID e MICROSOFT_APP_PASSWORD
2. No Bot Service, vá em Configuration
3. Verifique se o App ID corresponde ao que está no Web App
4. Se necessário, gere um novo password no Azure AD
            """)
        
        if any("from" in str(w) for w in self.warnings):
            print("""
⚠️  PROBLEMA NO CAMPO 'FROM':
1. O campo 'from' deve conter o ID e nome do bot
2. Verifique se o bot_framework_handler.py foi atualizado
3. Certifique-se de que o deploy foi feito com a versão corrigida
            """)
        
        if "OPTIONS returns 400" in str(self.warnings):
            print("""
⚠️  POSSÍVEL PROBLEMA DE CORS:
1. O Bot Framework precisa de CORS configurado
2. Adicione 'https://botservice.hosting.portal.azure.net' às origens permitidas
3. Adicione 'https://webchat.botframework.com' também
            """)
        
        print("""
📋 CHECKLIST MANUAL ADICIONAL:

1. [ ] Bot Service Endpoint está correto?
   - Deve ser: https://meshbrain.azurewebsites.net/api/messages
   
2. [ ] O Bot está "Enabled" no Bot Service?
   - Status deve estar "Running"
   
3. [ ] WebChat Channel está configurado?
   - Deve aparecer em Channels com status "Running"
   
4. [ ] Teste no Bot Framework Emulator:
   - Baixe: https://github.com/Microsoft/BotFramework-Emulator
   - Configure com endpoint e credenciais
   - Teste localmente primeiro
   
5. [ ] Verifique o Application Insights (se configurado):
   - Procure por exceções ou erros 400/401/500

6. [ ] Limpe o cache do navegador:
   - Ou teste em aba anônima
   - Ou teste em outro navegador

7. [ ] Aguarde propagação:
   - Mudanças no Bot Service podem levar 2-5 minutos
        """)

def main():
    print("🔍 INICIANDO DIAGNÓSTICO COMPLETO DO BOT FRAMEWORK")
    print("=" * 60)
    
    diag = BotDiagnostics()
    
    # Executar todos os testes
    print("\n📡 TESTANDO ENDPOINTS...")
    diag.run_test("Health Endpoint", diag.test_health_endpoint)
    diag.run_test("API Messages OPTIONS", diag.test_api_messages_options)
    diag.run_test("API Messages POST", diag.test_api_messages_post)
    
    print("\n📝 TESTANDO FORMATO...")
    diag.run_test("Response Format", diag.test_response_format)
    diag.run_test("Conversation Update", diag.test_conversation_update)
    
    print("\n🔐 TESTANDO AUTENTICAÇÃO...")
    diag.run_test("Bot Framework Auth", diag.test_bot_framework_auth)
    
    print("\n⚙️ CONFIGURAÇÕES...")
    diag.run_test("Bot Service Config", diag.test_bot_service_config)
    diag.run_test("App Settings", diag.test_app_settings)
    diag.run_test("Log Analysis", diag.analyze_logs)
    diag.run_test("Direct Line Test", diag.test_direct_line)
    
    # Gerar relatório
    diag.generate_report()
    
    # Salvar resultados em arquivo
    with open("bot_diagnostics_report.json", "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "results": diag.results,
            "errors": diag.errors,
            "warnings": diag.warnings
        }, f, indent=2)
    
    print("\n📄 Relatório salvo em: bot_diagnostics_report.json")
    
    return 0 if not diag.errors else 1

if __name__ == "__main__":
    sys.exit(main())