import uuid
import re
from typing import Dict, Any, List
from datetime import datetime

def generate_id() -> str:
    """Generate a unique ID"""
    return str(uuid.uuid4())

def normalize_text(text: str) -> str:
    """Normalize text for processing"""
    if not text:
        return ""
    
    # Convert to lowercase and remove extra whitespace
    text = text.lower().strip()
    
    # Remove special characters (keep letters, numbers, and basic punctuation)
    text = re.sub(r'[^a-zA-Z0-9\s.,!?]', '', text)
    
    return text

def extract_entities(text: str) -> Dict[str, List[str]]:
    """Extract basic entities from text (simplified)"""
    entities = {
        "urls": re.findall(r'https?://[^\s]+', text),
        "emails": re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text),
        "numbers": re.findall(r'\b\d+\b', text),
    }
    
    return entities

def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def get_current_timestamp() -> str:
    """Get current timestamp in ISO format"""
    return datetime.now().isoformat()

def safe_get(dictionary: Dict[str, Any], keys: List[str], default: Any = None) -> Any:
    """Safely get a value from a nested dictionary"""
    current = dictionary
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current