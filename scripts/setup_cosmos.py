#!/usr/bin/env python3
"""
Setup Script para Cosmos DB
Cria database e containers necessários
"""
import os
import sys
from azure.cosmos import CosmosClient, PartitionKey
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

def setup_cosmos():
    """Configura Cosmos DB com estrutura necessária"""
    
    # Pegar credenciais
    endpoint = os.getenv("AZURE_COSMOS_ENDPOINT")
    key = os.getenv("AZURE_COSMOS_KEY")
    
    if not endpoint or not key:
        print("❌ AZURE_COSMOS_ENDPOINT e AZURE_COSMOS_KEY são necessários!")
        print("   Configure no .env ou exporte as variáveis")
        sys.exit(1)
    
    print(f"🔗 Conectando ao Cosmos DB...")
    print(f"   Endpoint: {endpoint}")
    
    try:
        # Conectar
        client = CosmosClient(endpoint, credential=key)
        
        # 1. Criar Database
        database_name = "meshbrain-memory"
        print(f"\n📁 Criando database '{database_name}'...")
        database = client.create_database_if_not_exists(database_name)
        print(f"   ✅ Database criado/verificado")
        
        # 2. Container: conversations (principal)
        print(f"\n📦 Criando container 'conversations'...")
        conversations = database.create_container_if_not_exists(
            id="conversations",
            partition_key=PartitionKey(path="/userId"),
            default_ttl=7776000,  # 90 dias
            offer_throughput=400   # RU/s mínimo
        )
        print(f"   ✅ Container 'conversations' criado")
        print(f"   ⚙️ TTL: 90 dias")
        print(f"   ⚙️ Throughput: 400 RU/s")
        
        # 3. Container: user_profiles (contexto)
        print(f"\n📦 Criando container 'user_profiles'...")
        profiles = database.create_container_if_not_exists(
            id="user_profiles",
            partition_key=PartitionKey(path="/userId"),
            offer_throughput=400
        )
        print(f"   ✅ Container 'user_profiles' criado")
        
        # 4. Container: memories (futuro - learning)
        print(f"\n📦 Criando container 'memories'...")
        memories = database.create_container_if_not_exists(
            id="memories",
            partition_key=PartitionKey(path="/userId"),
            default_ttl=2592000,  # 30 dias
            offer_throughput=400
        )
        print(f"   ✅ Container 'memories' criado")
        print(f"   ⚙️ TTL: 30 dias")
        
        # 5. Verificar estrutura
        print(f"\n✅ COSMOS DB CONFIGURADO COM SUCESSO!")
        print(f"\n📊 Estrutura criada:")
        print(f"   Database: {database_name}")
        print(f"   └── conversations (TTL: 90d, 400 RU/s)")
        print(f"   └── user_profiles (No TTL, 400 RU/s)")
        print(f"   └── memories (TTL: 30d, 400 RU/s)")
        
        # 6. Estimar custos
        total_rus = 400 * 3  # 3 containers
        estimated_cost = total_rus * 0.00008 * 730  # Custo aproximado por mês
        print(f"\n💰 Custo estimado: ~${estimated_cost:.2f}/mês")
        print(f"   Base: {total_rus} RU/s total")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERRO: {str(e)}")
        return False

def test_connection():
    """Testa a conexão criando um documento de teste"""
    endpoint = os.getenv("AZURE_COSMOS_ENDPOINT")
    key = os.getenv("AZURE_COSMOS_KEY")
    
    try:
        client = CosmosClient(endpoint, credential=key)
        database = client.get_database_client("meshbrain-memory")
        container = database.get_container_client("conversations")
        
        # Criar documento de teste
        test_doc = {
            "id": "test_doc",
            "userId": "test_user",
            "type": "test",
            "message": "Setup test",
            "timestamp": "2024-01-01T00:00:00Z"
        }
        
        # Tentar criar
        container.create_item(test_doc)
        print("\n🧪 Teste de escrita: ✅")
        
        # Tentar ler
        item = container.read_item("test_doc", "test_user")
        print("🧪 Teste de leitura: ✅")
        
        # Deletar teste
        container.delete_item("test_doc", "test_user")
        print("🧪 Teste de deleção: ✅")
        
        print("\n✅ TODOS OS TESTES PASSARAM!")
        return True
        
    except Exception as e:
        print(f"\n❌ Teste falhou: {str(e)}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("🚀 COSMOS DB SETUP SCRIPT")
    print("=" * 50)
    
    # Setup
    if setup_cosmos():
        print("\n" + "=" * 50)
        print("🧪 Executando testes...")
        print("=" * 50)
        test_connection()
    
    print("\n" + "=" * 50)
    print("✅ Setup completo!")
    print("=" * 50)