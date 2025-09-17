"""
Config Manager - Gerenciador central de configurações
Suporta múltiplas fontes e hot-reload
"""
import os
import yaml
import json
from typing import Dict, Any, Optional, List
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading

from config.settings import Settings
from utils.logger import get_logger

logger = get_logger(__name__)

class ConfigSource:
    """Fonte de configuração (arquivo, env, remote, etc)"""
    pass

class FileConfigSource(ConfigSource):
    """Configuração de arquivo local"""
    
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
    
    def load(self) -> Dict[str, Any]:
        """Carrega configuração do arquivo"""
        if not self.file_path.exists():
            logger.warning(f"Config file not found: {self.file_path}")
            return {}
        
        try:
            with open(self.file_path, 'r') as f:
                if self.file_path.suffix == '.yaml':
                    return yaml.safe_load(f)
                elif self.file_path.suffix == '.json':
                    return json.load(f)
                else:
                    logger.error(f"Unsupported config format: {self.file_path.suffix}")
                    return {}
        except Exception as e:
            logger.error(f"Error loading config from {self.file_path}: {str(e)}")
            return {}

class EnvConfigSource(ConfigSource):
    """Configuração de variáveis de ambiente"""
    
    def __init__(self, prefix: str = "BOT_"):
        self.prefix = prefix
    
    def load(self) -> Dict[str, Any]:
        """Carrega configuração do ambiente"""
        config = {}
        for key, value in os.environ.items():
            if key.startswith(self.prefix):
                # Remove prefix e converte para lowercase
                config_key = key[len(self.prefix):].lower()
                config[config_key] = value
        return config

class ConfigManager:
    """
    Gerenciador central de configurações
    Suporta múltiplas fontes, validação e hot-reload
    """
    
    def __init__(self):
        self.sources: List[ConfigSource] = []
        self.config: Dict[str, Any] = {}
        self.settings: Optional[Settings] = None
        self.observers: List[Observer] = []
        self.callbacks: List[callable] = []
        self._lock = threading.Lock()
    
    def add_source(self, source: ConfigSource):
        """Adiciona fonte de configuração"""
        self.sources.append(source)
    
    def load_all(self) -> Settings:
        """Carrega todas as fontes e mescla"""
        with self._lock:
            merged_config = {}
            
            # Carregar cada fonte (ordem importa - última sobrescreve)
            for source in self.sources:
                try:
                    source_config = source.load()
                    merged_config = self._merge_configs(merged_config, source_config)
                except Exception as e:
                    logger.error(f"Error loading source {source.__class__.__name__}: {str(e)}")
            
            # Substituir variáveis de ambiente
            merged_config = self._replace_env_vars(merged_config)
            
            # Criar Settings
            try:
                self.settings = Settings(**merged_config)
                self.config = merged_config
                logger.info("✅ Configuration loaded successfully")
            except Exception as e:
                logger.error(f"Error creating Settings: {str(e)}")
                # Usar configuração padrão em caso de erro
                self.settings = Settings._create_from_env()
            
            return self.settings
    
    def _merge_configs(self, base: Dict, override: Dict) -> Dict:
        """Mescla duas configurações (deep merge)"""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _replace_env_vars(self, config: Any) -> Any:
        """Substitui ${VAR} por valores do ambiente"""
        if isinstance(config, dict):
            return {k: self._replace_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._replace_env_vars(item) for item in config]
        elif isinstance(config, str) and config.startswith("${") and config.endswith("}"):
            env_var = config[2:-1]
            return os.getenv(env_var)
        return config
    
    def watch_for_changes(self, file_path: str):
        """Monitora arquivo para mudanças (hot-reload)"""
        class ConfigFileHandler(FileSystemEventHandler):
            def __init__(self, manager: ConfigManager):
                self.manager = manager
            
            def on_modified(self, event):
                if not event.is_directory:
                    logger.info(f"Config file changed: {event.src_path}")
                    self.manager.reload()
        
        handler = ConfigFileHandler(self)
        observer = Observer()
        observer.schedule(handler, str(Path(file_path).parent), recursive=False)
        observer.start()
        self.observers.append(observer)
        
        logger.info(f"👁️ Watching config file: {file_path}")
    
    def reload(self):
        """Recarrega configuração"""
        logger.info("🔄 Reloading configuration...")
        old_settings = self.settings
        new_settings = self.load_all()
        
        # Notificar callbacks se mudou
        if old_settings != new_settings:
            for callback in self.callbacks:
                try:
                    callback(old_settings, new_settings)
                except Exception as e:
                    logger.error(f"Error in config change callback: {str(e)}")
    
    def on_config_change(self, callback: callable):
        """Registra callback para mudanças de config"""
        self.callbacks.append(callback)
    
    def get_settings(self) -> Settings:
        """Retorna settings atual"""
        if not self.settings:
            self.load_all()
        return self.settings
    
    def get(self, key: str, default: Any = None) -> Any:
        """Pega valor específico da config"""
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def validate(self) -> List[str]:
        """Valida configuração e retorna lista de problemas"""
        issues = []
        
        # Validar providers LLM
        if not self.get("llm.primary.api_key"):
            issues.append("Primary LLM API key not configured")
        
        # Validar memória
        if self.get("memory.long_term.enabled") and not self.get("cosmos.endpoint"):
            issues.append("Long-term memory enabled but Cosmos not configured")
        
        # Validar interfaces
        if self.get("interfaces.teams.enabled") and not self.get("teams.app_id"):
            issues.append("Teams interface enabled but app_id not configured")
        
        return issues
    
    def export(self, format: str = "yaml") -> str:
        """Exporta configuração atual"""
        if format == "yaml":
            return yaml.dump(self.config, default_flow_style=False)
        elif format == "json":
            return json.dumps(self.config, indent=2)
        else:
            raise ValueError(f"Unsupported export format: {format}")

# Singleton global
_config_manager = None

def get_config_manager() -> ConfigManager:
    """Retorna instância singleton do ConfigManager"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
        
        # Configurar fontes padrão
        _config_manager.add_source(FileConfigSource("bot_config.yaml"))
        _config_manager.add_source(EnvConfigSource("BOT_"))
        _config_manager.add_source(EnvConfigSource("AZURE_"))
        
        # Carregar
        _config_manager.load_all()
    
    return _config_manager