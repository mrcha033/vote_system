import os
import importlib
import sys
import pytest

@pytest.fixture
def client(tmp_path):
    os.environ["SECRET_KEY"] = "test"
    os.environ["ADMIN_PASSWORD"] = "admin"
    os.environ["DB_PATH"] = str(tmp_path / "test.db")
    if "app.server" in sys.modules:
        importlib.reload(sys.modules["app.server"])
    module = importlib.reload(importlib.import_module("app"))
    app = module.app
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def login(client):
    return client.post("/login", data={"password": "admin"}, follow_redirects=True)


def test_login_required_redirect(client):
    rv = client.get("/admin")
    assert rv.status_code == 302
    assert "/login" in rv.headers["Location"]


def test_login_success_and_generate_tokens(client):
    response = login(client)
    assert "관리자 대시보드" in response.get_data(as_text=True)

    rv = client.post("/admin/generate_tokens", data={"count": "1"})
    assert rv.status_code == 200
    assert rv.mimetype == "application/zip"
