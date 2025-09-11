import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health_endpoint():
    """Test that health endpoint returns 200"""
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "bot" in response.json()
    assert "version" in response.json()

def test_metrics_endpoint():
    """Test that metrics endpoint returns 200"""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "llm_calls_total" in response.text

def test_message_endpoint():
    """Test that message endpoint accepts valid requests"""
    response = client.post(
        "/v1/messages",
        json={"user_id": "testuser", "message": "Hello"}
    )
    assert response.status_code == 200
    assert "response" in response.json()
    assert "metadata" in response.json()