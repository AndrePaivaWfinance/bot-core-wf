from typing import Optional
from pydantic import BaseModel

class AzureConfig(BaseModel):
    """Azure-specific configuration"""
    openai_endpoint: Optional[str] = None
    openai_key: Optional[str] = None
    cosmos_endpoint: Optional[str] = None
    cosmos_key: Optional[str] = None
    storage_connection_string: Optional[str] = None
    app_insights_connection_string: Optional[str] = None
    
    def is_configured(self) -> bool:
        """Check if Azure services are configured"""
        return all([
            self.openai_endpoint,
            self.openai_key,
            self.cosmos_endpoint,
            self.cosmos_key,
            self.storage_connection_string
        ])