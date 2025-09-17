from typing import Dict, Any
from jinja2 import Environment, FileSystemLoader
import os
from pathlib import Path
from skills.base_skill import BaseSkill
from utils.logger import get_logger

logger = get_logger(__name__)

class ReportGeneratorSkill(BaseSkill):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.templates_path = self._get_config_value("templates_path", "templates/reports")
        
        # Ensure templates directory exists
        Path(self.templates_path).mkdir(parents=True, exist_ok=True)
        
        # Set up Jinja2 environment
        self.jinja_env = Environment(
            loader=FileSystemLoader(self.templates_path),
            autoescape=True
        )
    
    async def can_handle(self, intent: str, context: Dict[str, Any]) -> bool:
        return intent.lower() in ["generate_report", "create_report", "report_generation"]
    
    async def execute(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        try:
            report_type = parameters.get("type", "default")
            data = parameters.get("data", {})
            template_name = parameters.get("template", f"{report_type}.html")
            
            # Check if template exists
            if not self._template_exists(template_name):
                return {"error": f"Template {template_name} not found"}
            
            # Render template with data
            template = self.jinja_env.get_template(template_name)
            html_content = template.render(**data)
            
            # Optionally save to blob storage (stub implementation)
            save_to_storage = parameters.get("save", False)
            if save_to_storage:
                await self._save_report(html_content, report_type, context)
            
            return {
                "success": True,
                "report_type": report_type,
                "content": html_content,
                "saved": save_to_storage
            }
            
        except Exception as e:
            logger.error(f"Report generation error: {str(e)}")
            return {"error": str(e)}
    
    def _template_exists(self, template_name: str) -> bool:
        """Check if a template exists"""
        template_path = os.path.join(self.templates_path, template_name)
        return os.path.exists(template_path)
    
    async def _save_report(self, content: str, report_type: str, context: Dict[str, Any]) -> bool:
        """Save report to storage (stub implementation)"""
        # In a real implementation, this would save to Azure Blob Storage
        logger.debug(f"Would save {report_type} report to storage", content_length=len(content))
        return True