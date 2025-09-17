"""
Blob Provider - Storage COLD
Barato, lento, para arquivo de longo prazo
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from azure.storage.blob import BlobServiceClient
import json
import gzip

from config.settings import Settings
from utils.logger import get_logger

logger = get_logger(__name__)

class BlobProvider:
    """Provider de storage em Blob - COLD tier"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = None
        self.container_name = "conversation-archives"
        self.available = False
        
        self._initialize_blob()
    
    def _initialize_blob(self):
        """Inicializa conexão com Blob Storage"""
        try:
            connection_string = self.settings.blob_storage.connection_string
            
            if not connection_string:
                logger.warning("Blob storage not configured")
                return
            
            # Conectar
            self.client = BlobServiceClient.from_connection_string(connection_string)
            
            # Criar container se não existir
            container_client = self.client.get_container_client(self.container_name)
            if not container_client.exists():
                container_client.create_container()
                logger.info(f"Created blob container: {self.container_name}")
            
            self.available = True
            logger.info("✅ Blob storage provider initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize Blob: {str(e)}")
            self.available = False
    
    async def save(self, key: str, data: Dict[str, Any], **kwargs) -> bool:
        """Salva no Blob (comprimido)"""
        if not self.available:
            return False
        
        try:
            user_id = data.get("user_id", "unknown")
            timestamp = data.get("timestamp", datetime.now(timezone.utc).isoformat())
            date = timestamp[:10]  # YYYY-MM-DD
            
            # Path: userId/YYYY-MM-DD/key.json.gz
            blob_name = f"{user_id}/{date}/{key}.json.gz"
            
            # Comprimir dados
            json_data = json.dumps(data, ensure_ascii=False)
            compressed = gzip.compress(json_data.encode('utf-8'))
            
            # Upload
            blob_client = self.client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            blob_client.upload_blob(compressed, overwrite=True)
            
            # Log compression ratio
            compression_ratio = (1 - len(compressed)/len(json_data)) * 100
            logger.debug(f"Saved to Blob: {blob_name} (compression: {compression_ratio:.1f}%)")
            
            return True
            
        except Exception as e:
            logger.error(f"Blob save error: {str(e)}")
            return False
    
    async def load(self, key: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Carrega do Blob"""
        if not self.available:
            return None
        
        try:
            # Buscar por pattern
            container = self.client.get_container_client(self.container_name)
            blobs = container.list_blobs(name_starts_with=f"*/*/key.json.gz")
            
            for blob in blobs:
                if key in blob.name:
                    # Download e descomprimir
                    blob_client = container.get_blob_client(blob.name)
                    compressed = blob_client.download_blob().readall()
                    
                    # Descomprimir
                    json_data = gzip.decompress(compressed).decode('utf-8')
                    return json.loads(json_data)
            
            return None
            
        except Exception as e:
            logger.error(f"Blob load error: {str(e)}")
            return None
    
    async def search(self, query: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        """Busca no Blob (lento, usar com parcimônia)"""
        if not self.available:
            return []
        
        try:
            user_id = query.get("user_id")
            limit = query.get("limit", 10)
            time_range = query.get("time_range")  # (start_date, end_date)
            
            results = []
            container = self.client.get_container_client(self.container_name)
            
            # Listar blobs do usuário
            prefix = f"{user_id}/"
            if time_range:
                # Se tiver time_range, ser mais específico
                start_date, end_date = time_range
                # TODO: Implementar busca por range de data
                pass
            
            blobs = container.list_blobs(name_starts_with=prefix)
            
            for blob in blobs:
                if len(results) >= limit:
                    break
                
                try:
                    # Download e descomprimir
                    blob_client = container.get_blob_client(blob.name)
                    compressed = blob_client.download_blob().readall()
                    json_data = gzip.decompress(compressed).decode('utf-8')
                    data = json.loads(json_data)
                    results.append(data)
                except:
                    continue
            
            logger.debug(f"Found {len(results)} items in Blob for {user_id}")
            return results
            
        except Exception as e:
            logger.error(f"Blob search error: {str(e)}")
            return []
    
    async def delete(self, key: str, **kwargs) -> bool:
        """Deleta do Blob"""
        if not self.available:
            return False
        
        try:
            # Buscar blob
            container = self.client.get_container_client(self.container_name)
            blobs = container.list_blobs()
            
            for blob in blobs:
                if key in blob.name:
                    blob_client = container.get_blob_client(blob.name)
                    blob_client.delete_blob()
                    logger.debug(f"Deleted from Blob: {blob.name}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Blob delete error: {str(e)}")
            return False
    
    def is_available(self) -> bool:
        """Verifica se Blob está disponível"""
        return self.available