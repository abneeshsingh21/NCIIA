"""
Test API Endpoints
"""

import pytest
from fastapi.testclient import TestClient

from nciia.api.server import create_app


@pytest.fixture
def client():
    """Create test client."""
    app = create_app()
    return TestClient(app)


class TestHealthEndpoints:
    """Test health check endpoints."""
    
    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data


class TestSignalEndpoints:
    """Test signal API endpoints."""
    
    def test_create_signal(self, client):
        response = client.post("/api/signals/", json={
            "type": "paste_site",
            "source_name": "Test Source",
            "raw_content": "Test signal content for API test",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["status"] in ["created", "duplicate"]
    
    def test_list_signals(self, client):
        response = client.get("/api/signals/")
        assert response.status_code == 200
        data = response.json()
        assert "signals" in data
        assert "total" in data


class TestPersonaEndpoints:
    """Test persona API endpoints."""
    
    def test_create_persona(self, client):
        response = client.post("/api/personas/", json={
            "seed_type": "username",
            "seed_value": "testuser123",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "created"
        assert "persona_id" in data
    
    def test_list_personas(self, client):
        response = client.get("/api/personas/")
        assert response.status_code == 200


class TestCaseEndpoints:
    """Test case API endpoints."""
    
    def test_create_case(self, client):
        response = client.post("/api/cases/", json={
            "name": "Test Investigation",
            "description": "Test case for API testing",
        })
        assert response.status_code == 201
        data = response.json()
        assert "case_id" in data
