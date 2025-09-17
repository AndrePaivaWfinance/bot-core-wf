import os
import yaml
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

class LLMConfig(BaseModel):
    type: str
    endpoint: Optional[str] = Field(default=None, env="AZURE_OPENAI_ENDPOINT")
    api_key: Optional[str] = Field(default=None, env="AZURE_OPENAI_KEY")
    deployment_name: Optional[str] = Field(default=None, env="AZURE_OPENAI_DEPLOYMENT")
    temperature: float = 0.7
    max_tokens: int = 2000
    model: Optional[str] = Field(default=None, env="AZURE_OPENAI_MODEL")
    api_version: Optional[str] = Field(default="2024-12-01-preview", env="AZURE_OPENAI_API_VERSION")

class ClaudeConfig(BaseModel):
    # MUDANÇA PRINCIPAL: Usar ANTHROPIC_API_KEY como primário, CLAUDE_API_KEY como fallback
    api_key: Optional[str] = Field(default=None)
    api_version: str = Field(default="2023-06-01", env="CLAUDE_API_VERSION")
    model: str = Field(default="claude-opus-4-1-20250805")  # Modelo atualizado
    
    def __init__(self, **data):
        # Tenta ANTHROPIC_API_KEY primeiro, depois CLAUDE_API_KEY
        if not data.get('api_key'):
            data['api_key'] = os.getenv('ANTHROPIC_API_KEY') or os.getenv('CLAUDE_API_KEY')
        super().__init__(**data)

class CosmosConfig(BaseModel):
    endpoint: Optional[str] = None
    key: Optional[str] = None
    database: str = "bot_memory"
    ttl_days: int = 90

class BlobStorageConfig(BaseModel):
    connection_string: Optional[str] = None
    container_documents: str = "bot-documents"
    container_media: str = "bot-media"
    container_logs: str = "bot-logs"

class MemoryConfig(BaseModel):
    short_term: Dict[str, Any] = Field(default_factory=dict)
    long_term: Dict[str, Any] = Field(default_factory=dict)
    learning: Dict[str, Any] = Field(default_factory=dict)

class SkillConfig(BaseModel):
    name: str
    enabled: bool = True
    config: Dict[str, Any] = Field(default_factory=dict)

class BotConfig(BaseModel):
    id: str
    name: str
    type: str
    personality_template: str = "base_template.yaml"

class MonitoringConfig(BaseModel):
    app_insights_connection_string: Optional[str] = Field(default=None, env=["APP_INSIGHTS_CONNECTION_STRING", "APPLICATIONINSIGHTS_CONNECTION_STRING"])

class TeamsConfig(BaseModel):
    app_id: Optional[str] = None
    app_password: Optional[str] = None
    tenant_id: Optional[str] = None

class Settings(BaseModel):
    bot: BotConfig
    llm: Dict[str, Optional[LLMConfig]] = Field(default_factory=dict)
    cosmos: CosmosConfig
    blob_storage: BlobStorageConfig
    memory: MemoryConfig
    skills: Dict[str, Any] = Field(default_factory=dict)
    interfaces: Dict[str, Any] = Field(default_factory=dict)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    claude: ClaudeConfig = Field(default_factory=ClaudeConfig)
    teams: TeamsConfig = Field(default_factory=lambda: TeamsConfig(
        app_id=os.getenv("TEAMS_APP_ID") or os.getenv("MICROSOFT_APP_ID") or os.getenv("MicrosoftAppId"),
        app_password=os.getenv("TEAMS_APP_PASSWORD") or os.getenv("MICROSOFT_APP_PASSWORD") or os.getenv("MicrosoftAppPassword"),
        tenant_id=os.getenv("TEAMS_TENANT_ID") or os.getenv("MICROSOFT_APP_TENANT_ID") or os.getenv("MicrosoftAppTenantId"),
    ))
    
    @classmethod
    def from_yaml(cls, file_path: str = "bot_config.yaml"):
        if not os.path.exists(file_path):
            logging.warning(f"{file_path} not found. Falling back to environment variables only.")
            # Criar configuração padrão com variáveis de ambiente
            return cls._create_from_env()
        
        try:
            with open(file_path, 'r') as f:
                config_data = yaml.safe_load(f)

            def replace_env_vars(data):
                if isinstance(data, dict):
                    return {k: replace_env_vars(v) for k, v in data.items()}
                elif isinstance(data, list):
                    return [replace_env_vars(item) for item in data]
                elif isinstance(data, str) and data.startswith("${") and data.endswith("}"):
                    env_var = data[2:-1]
                    value = os.getenv(env_var, None)
                    if value is None or value == "":
                        logging.warning(f"Environment variable {env_var} not set or empty.")
                    return value
                elif data is None or (isinstance(data, str) and data.strip() == ""):
                    return None
                return data

            config_data = replace_env_vars(config_data)
            
            # Garantir que ClaudeConfig use a API key correta
            if 'llm' in config_data and 'fallback_llm' in config_data['llm']:
                fallback = config_data['llm']['fallback_llm']
                if not fallback.get('api_key'):
                    fallback['api_key'] = os.getenv('ANTHROPIC_API_KEY') or os.getenv('CLAUDE_API_KEY')
                # Garantir modelo correto
                if not fallback.get('model'):
                    fallback['model'] = 'claude-opus-4-1-20250805'
            
            return cls(**config_data)
            
        except Exception as e:
            logging.error(f"Error loading {file_path}: {e}. Falling back to environment variables only.")
            return cls._create_from_env()
    
    @classmethod
    def _create_from_env(cls):
        """Cria configuração apenas com variáveis de ambiente"""
        return cls(
            bot=BotConfig(
                id=os.getenv("BOT_ID", "local-bot"),
                name=os.getenv("BOT_NAME", "LocalBot"),
                type=os.getenv("BOT_TYPE", "test"),
            ),
            llm={
                "primary": LLMConfig(
                    type="azure_openai",
                    endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                    api_key=os.getenv("AZURE_OPENAI_KEY"),
                    deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
                    model=os.getenv("AZURE_OPENAI_MODEL"),
                    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
                ),
                "fallback_llm": {
                    "type": "claude",
                    "api_key": os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY"),
                    "model": "claude-opus-4-1-20250805",
                    "max_tokens": 2000
                }
            },
            cosmos=CosmosConfig(
                endpoint=os.getenv("COSMOS_ENDPOINT") or os.getenv("AZURE_COSMOS_ENDPOINT"),
                key=os.getenv("COSMOS_KEY") or os.getenv("AZURE_COSMOS_KEY"),
            ),
            blob_storage=BlobStorageConfig(
                connection_string=os.getenv("BLOB_STORAGE_CONNECTION_STRING") or os.getenv("AZURE_STORAGE_CONNECTION_STRING"),
            ),
            memory=MemoryConfig(),
            claude=ClaudeConfig(),  # Vai pegar ANTHROPIC_API_KEY automaticamente
            monitoring=MonitoringConfig(),
            teams=TeamsConfig()
        )

def get_settings() -> Settings:
    return Settings.from_yaml()