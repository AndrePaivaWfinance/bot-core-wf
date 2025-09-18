import pytest
from config.settings import Settings

def test_settings_loading():
    """Test that settings can be loaded from YAML"""
    settings = Settings.from_yaml("bot_config.yaml")
    assert settings is not None
    assert hasattr(settings, 'bot')
    assert hasattr(settings, 'llm')

def test_environment_variable_replacement(monkeypatch):
    """Test that environment variables are properly replaced"""
    monkeypatch.setenv("TEST_VAR", "test_value")
    
    # Create a temporary config file for testing
    test_config = {
        "bot": {
            "id": "${TEST_VAR}",
            "name": "TestBot",
            "type": "test",
            "personality_template": "base_template.yaml"
        },
        # ... other required fields
    }
    
    # This test would need a temporary YAML file
    # For now, we'll just verify the logic works in settings.py