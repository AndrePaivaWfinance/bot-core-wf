import pytest
from memory.short_term import ShortTermMemory
from config.settings import Settings

@pytest.fixture
def settings():
    return Settings.from_yaml("bot_config.yaml")

@pytest.fixture
def short_term_memory(settings):
    return ShortTermMemory(settings)

@pytest.mark.asyncio
async def test_short_term_memory_store(short_term_memory):
    """Test storing and retrieving from short-term memory"""
    user_id = "testuser"
    message = {"text": "Hello", "intent": "greeting"}
    
    await short_term_memory.store(user_id, message)
    context = await short_term_memory.get_context(user_id)
    
    assert "short_term_memory" in context
    assert len(context["short_term_memory"]) == 1
    assert context["short_term_memory"][0]["data"]["text"] == "Hello"

@pytest.mark.asyncio
async def test_short_term_memory_limit(short_term_memory):
    """Test that short-term memory respects the limit"""
    user_id = "testuser2"
    
    # Store more messages than the limit
    for i in range(25):  # Limit is 20
        await short_term_memory.store(user_id, {"text": f"Message {i}"})
    
    context = await short_term_memory.get_context(user_id)
    assert len(context["short_term_memory"]) <= 20