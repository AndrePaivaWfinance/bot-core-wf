from typing import Dict, List, Any, Optional
import importlib
from skills.base_skill import BaseSkill
from skills.api_caller import APICallerSkill
from skills.report_generator import ReportGeneratorSkill
from skills.image_generator import ImageGeneratorSkill
from config.settings import Settings
from utils.logger import get_logger

logger = get_logger(__name__)

class SkillRegistry:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.skills: Dict[str, BaseSkill] = {}
    
    async def load_skills(self):
        """Load all enabled skills from configuration"""
        skill_configs = self.settings.skills.get("registry", [])
        
        for skill_config in skill_configs:
            if skill_config.get("enabled", False):
                await self._load_skill(skill_config)
        
        logger.info(f"Loaded {len(self.skills)} skills", skill_names=list(self.skills.keys()))
    
    async def _load_skill(self, skill_config: Dict[str, Any]):
        """Load a single skill"""
        skill_name = skill_config["name"]
        config = skill_config.get("config", {})
        
        try:
            if skill_name == "api_caller":
                skill_instance = APICallerSkill(config)
            elif skill_name == "report_generator":
                skill_instance = ReportGeneratorSkill(config)
            elif skill_name == "image_generator":
                skill_instance = ImageGeneratorSkill(config)
            else:
                # Try to load custom skill
                skill_instance = await self._load_custom_skill(skill_name, config)
            
            if skill_instance:
                self.skills[skill_name] = skill_instance
                logger.debug(f"Loaded skill: {skill_name}")
            else:
                logger.warning(f"Failed to load skill: {skill_name}")
        except Exception as e:
            logger.error(f"Error loading skill {skill_name}: {str(e)}")
    
    async def _load_custom_skill(self, skill_name: str, config: Dict[str, Any]) -> Optional[BaseSkill]:
        """Load a custom skill from external module"""
        try:
            # Try to import the skill module
            module_name = f"skills.{skill_name}"
            module = importlib.import_module(module_name)
            
            # Get the skill class (assuming class name is SkillNameSkill)
            class_name = f"{skill_name.title().replace('_', '')}Skill"
            skill_class = getattr(module, class_name)
            
            # Instantiate the skill
            return skill_class(config)
        except (ImportError, AttributeError) as e:
            logger.warning(f"Custom skill {skill_name} not found: {str(e)}")
            return None
    
    def get_skill(self, skill_name: str) -> Optional[BaseSkill]:
        """Get a skill by name"""
        return self.skills.get(skill_name)
    
    async def find_appropriate_skill(self, intent: str, context: Dict[str, Any]) -> Optional[BaseSkill]:
        """Find the most appropriate skill for the given intent"""
        for skill_name, skill in self.skills.items():
            if await skill.can_handle(intent, context):
                return skill
        
        return None
    
    def list_skills(self) -> List[str]:
        """List all loaded skills"""
        return list(self.skills.keys())