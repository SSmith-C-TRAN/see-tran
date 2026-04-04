
import pytest
from app import create_app, db

@pytest.fixture
def app():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    })
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

def test_health_check(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json["ok"] is True
    assert response.json["data"]["status"] == "ok"

def test_index(client):
    response = client.get("/")
    assert response.status_code == 200

