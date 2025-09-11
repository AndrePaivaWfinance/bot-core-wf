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
    endpoint: Optional[str] = None
    api_key: Optional[str] = None
    deployment_name: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2000
    model: Optional[str] = None

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

class Settings(BaseModel):
    bot: BotConfig
    llm: Dict[str, Optional[LLMConfig]] = Field(default_factory=dict)
    cosmos: CosmosConfig
    blob_storage: BlobStorageConfig
    memory: MemoryConfig
    skills: Dict[str, Any] = Field(default_factory=dict)
    interfaces: Dict[str, Any] = Field(default_factory=dict)
    monitoring: Dict[str, Any] = Field(default_factory=dict)
    
    @classmethod
    def from_yaml(cls, file_path: str = "bot_config.yaml"):
        if not os.path.exists(file_path):
            logging.warning(f"{file_path} not found. Falling back to environment variables only.")
            return cls(
                bot=BotConfig(
                    id=os.getenv("BOT_ID", "local-bot"),
                    name=os.getenv("BOT_NAME", "LocalBot"),
                    type=os.getenv("BOT_TYPE", "test"),
                ),
                llm={},
                cosmos=CosmosConfig(
                    endpoint=os.getenv("COSMOS_ENDPOINT"),
                    key=os.getenv("COSMOS_KEY"),
                ),
                blob_storage=BlobStorageConfig(
                    connection_string=os.getenv("BLOB_STORAGE_CONNECTION_STRING"),
                ),
                memory=MemoryConfig(),
            )
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
                    return os.getenv(env_var, data)
                return data

            config_data = replace_env_vars(config_data)
            return cls(**config_data)
        except Exception as e:
            logging.error(f"Error loading {file_path}: {e}. Falling back to environment variables only.")
            return cls(
                bot=BotConfig(
                    id=os.getenv("BOT_ID", "local-bot"),
                    name=os.getenv("BOT_NAME", "LocalBot"),
                    type=os.getenv("BOT_TYPE", "test"),
                ),
                llm={},
                cosmos=CosmosConfig(
                    endpoint=os.getenv("COSMOS_ENDPOINT"),
                    key=os.getenv("COSMOS_KEY"),
                ),
                blob_storage=BlobStorageConfig(
                    connection_string=os.getenv("BLOB_STORAGE_CONNECTION_STRING"),
                ),
                memory=MemoryConfig(),
            )

def get_settings() -> Settings:
    return Settings.from_yaml()