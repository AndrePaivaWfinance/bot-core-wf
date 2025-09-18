import pytest
from skills.api_caller import APICallerSkill
from skills.skill_registry import SkillRegistry
from config.settings import Settings

@pytest.fixture
def settings():
    return Settings.from_yaml("bot_config.yaml")

@pytest.fixture
def api_caller_skill(settings):
    skill_config = next(
        (skill for skill in settings.skills.get("registry", []) if skill["name"] == "api_caller"),
        {}
    )
    return APICallerSkill(skill_config.get("config", {}))

@pytest.mark.asyncio
async def test_api_caller_can_handle(api_caller_skill):
    """Test that API caller can handle appropriate intents"""
    assert await api_caller_skill.can_handle("api_call", {}) == True
    assert await api_caller_skill.can_handle("make_request", {}) == True
    assert await api_caller_skill.can_handle("greeting", {}) == False

@pytest.mark.asyncio
async def test_api_caller_execute(api_caller_skill):
    """Test API caller execution (with mock URL)"""
    # This test uses httpbin.org which is a reliable test API
    result = await api_caller_skill.execute({
        "url": "https://httpbin.org/get",
        "method": "GET"
    }, {})
    
    assert "status_code" in result
    assert result["status_code"] == 200

@pytest.mark.asyncio
async def test_skill_registry(settings):
    """Test that skill registry loads skills correctly"""
    registry = SkillRegistry(settings)
    await registry.load_skills()
    
    assert len(registry.skills) > 0
    assert "api_caller" in registry.skills