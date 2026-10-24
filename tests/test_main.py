import pytest
from fastapi.testclient import TestClient

def test_static_dashboard_html():
    from backend.main import app
    client = TestClient(app)
    response = client.get("/static/dashboard.html")
    assert response.status_code == 200

def test_websocket_endpoint():
    from backend.main import app
    client = TestClient(app)
    with client.websocket_connect("/ws/dashboard") as websocket:
        assert websocket is not None
