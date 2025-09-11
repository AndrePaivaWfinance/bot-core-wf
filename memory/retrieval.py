from typing import Dict, List, Any
import os
import json
from pathlib import Path
from azure.storage.blob import BlobServiceClient
from config.settings import Settings
from utils.logger import get_logger

logger = get_logger(__name__)

class RetrievalSystem:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.blob_service_client = None
        self.local_index_path = Path("./.cache/index")
        
        if settings.blob_storage.connection_string:
            self._initialize_blob_client()
        
        # Create local index directory
        self.local_index_path.mkdir(parents=True, exist_ok=True)
    
    def _initialize_blob_client(self):
        try:
            self.blob_service_client = BlobServiceClient.from_connection_string(
                self.settings.blob_storage.connection_string
            )
            logger.info("Blob storage client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize blob storage client: {str(e)}")
    
    async def retrieve_relevant_documents(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Retrieve relevant documents for the query (simplified RAG)"""
        # For now, return some mock documents
        # In a real implementation, you would:
        # 1. Generate embeddings for the query
        # 2. Search for similar documents in the index
        # 3. Return the most relevant snippets
        
        mock_documents = [
            {
                "content": "This is a sample document about API integration. It explains how to make HTTP requests to external services.",
                "source": "sample_api_guide.txt",
                "relevance": 0.85
            },
            {
                "content": "The reporting system allows you to generate PDF and HTML reports from data. Use the report generator skill.",
                "source": "reporting_system.md",
                "relevance": 0.72
            },
            {
                "content": "User preferences are stored in long-term memory and can be accessed through the learning system.",
                "source": "user_guide.txt",
                "relevance": 0.68
            }
        ]
        
        # Filter documents based on simple keyword matching
        query_lower = query.lower()
        relevant_docs = []
        
        for doc in mock_documents:
            if any(keyword in query_lower for keyword in ["api", "http", "request"]):
                if "api" in doc["content"].lower():
                    relevant_docs.append(doc)
            elif any(keyword in query_lower for keyword in ["report", "summary", "document"]):
                if "report" in doc["content"].lower():
                    relevant_docs.append(doc)
            elif any(keyword in query_lower for keyword in ["preference", "like", "dislike"]):
                if "preference" in doc["content"].lower():
                    relevant_docs.append(doc)
        
        return relevant_docs[:limit]
    
    async def index_documents(self):
        """Index documents from blob storage (simplified)"""
        if not self.blob_service_client:
            logger.warning("Blob storage not configured, skipping document indexing")
            return
        
        try:
            container_client = self.blob_service_client.get_container_client(
                self.settings.blob_storage.container_documents
            )
            
            # List blobs in the container
            blobs = container_client.list_blobs()
            
            for blob in blobs:
                # Download blob content
                blob_client = container_client.get_blob_client(blob.name)
                blob_content = blob_client.download_blob().readall()
                
                # Simple indexing - just store the content locally
                index_entry = {
                    "name": blob.name,
                    "content": blob_content.decode('utf-8'),
                    "last_modified": blob.last_modified.isoformat() if blob.last_modified else None
                }
                
                # Save to local index
                index_file = self.local_index_path / f"{blob.name}.json"
                with open(index_file, 'w') as f:
                    json.dump(index_entry, f)
                
                logger.debug(f"Indexed document: {blob.name}")
            
            logger.info("Document indexing completed")
        except Exception as e:
            logger.error(f"Failed to index documents: {str(e)}")