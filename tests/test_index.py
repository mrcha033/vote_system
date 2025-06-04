import os
import importlib
import pytest

os.environ.setdefault("SECRET_KEY", "test")
os.environ.setdefault("ADMIN_PASSWORD", "test")
app = importlib.import_module("app").app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_index(client):
    rv = client.get('/')
    assert rv.status_code == 200
    assert '서버가 실행중입니다' in rv.get_data(as_text=True)
